"""
backend/app/intelligence/learning/outcome_engine.py

Phase 8.5: Deterministic Outcome & Learning Signal Synthesis Engine
Analyzes real historical user outcomes and feedback to discover empirical patterns,
compute success rates, and generate actionable, evidence-backed learning summaries.

Strict Epistemic Principles:
- Requires sufficient real historical data before asserting any learned pattern (MIN_OUTCOMES_THRESHOLD = 3).
- Zero hallucinated learning percentages or arbitrary ML certainty scores.
- Clear distinction between observed historical correlations and guaranteed future outcomes.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Optional

from app.intelligence.learning.models import (
    OutcomeRecord,
    FeedbackRecord,
    OutcomeStatus,
    FeedbackTargetType,
    LearningSummary,
    LearningPattern,
)
from app.intelligence.learning.outcome_store import list_outcomes, list_feedbacks

logger = logging.getLogger("bgai.learning.engine")

MIN_OUTCOMES_FOR_GLOBAL_LEARNING = 3
MIN_PATTERN_OCCURRENCES = 2

STANDARD_ACTION_TYPES = ["INVESTIGATE", "AUDIT", "COMPARE", "REMEDIATE"]


def synthesize_learning_summary(user_id: str) -> LearningSummary:
    """
    Computes a comprehensive, deterministic learning summary from real historical
    outcomes and feedback strictly scoped to the given user.
    """
    outcomes = list_outcomes(user_id=user_id, limit=500)
    feedbacks = list_feedbacks(user_id=user_id, limit=500)

    total_outcomes = len(outcomes)
    successful_count = sum(1 for o in outcomes if o.status == OutcomeStatus.SUCCESSFUL)
    partial_count = sum(1 for o in outcomes if o.status == OutcomeStatus.PARTIAL)
    failed_count = sum(1 for o in outcomes if o.status == OutcomeStatus.FAILED)
    unknown_count = sum(1 for o in outcomes if o.status == OutcomeStatus.UNKNOWN)

    total_feedbacks = len(feedbacks)
    useful_count = sum(1 for f in feedbacks if f.useful is True)
    not_useful_count = sum(1 for f in feedbacks if f.useful is False)
    accepted_count = sum(1 for f in feedbacks if f.accepted is True)
    rejected_count = sum(1 for f in feedbacks if f.accepted is False)

    insufficient_data = total_outcomes < MIN_OUTCOMES_FOR_GLOBAL_LEARNING

    # ── Group outcomes by action type ──────────────────────────────────────────
    action_type_stats = defaultdict(lambda: {"total": 0, "successful": 0, "partial": 0, "failed": 0, "unknown": 0})
    for o in outcomes:
        act = (o.action_type or "GENERAL").upper()
        stats = action_type_stats[act]
        stats["total"] += 1
        if o.status == OutcomeStatus.SUCCESSFUL:
            stats["successful"] += 1
        elif o.status == OutcomeStatus.PARTIAL:
            stats["partial"] += 1
        elif o.status == OutcomeStatus.FAILED:
            stats["failed"] += 1
        else:
            stats["unknown"] += 1

    # ── Derive Successful & Unsuccessful Patterns ──────────────────────────────
    successful_patterns: list[dict[str, Any]] = []
    rejected_patterns: list[dict[str, Any]] = []
    frequently_accepted_actions: list[dict[str, Any]] = []
    frequently_rejected_actions: list[dict[str, Any]] = []

    # Only derive recurring patterns if we have at least MIN_OUTCOMES_FOR_GLOBAL_LEARNING total outcomes
    if not insufficient_data:
        for act, stats in action_type_stats.items():
            tot = stats["total"]
            if tot >= MIN_PATTERN_OCCURRENCES:
                succ_rate = round(stats["successful"] / tot, 2)
                fail_rate = round(stats["failed"] / tot, 2)

                if succ_rate >= 0.6:
                    successful_patterns.append({
                        "pattern_id": f"pat_succ_{act.lower()}",
                        "action_type": act,
                        "description": (
                            f"Action type '{act}' demonstrated a {int(succ_rate * 100)}% historical success rate "
                            f"across {tot} recorded execution(s)."
                        ),
                        "total_occurrences": tot,
                        "success_rate": succ_rate,
                        "evidence_support": f"{stats['successful']}/{tot} successful outcomes",
                        "caveat": "Historical correlation does not guarantee future results.",
                    })
                elif fail_rate >= 0.5:
                    rejected_patterns.append({
                        "pattern_id": f"pat_fail_{act.lower()}",
                        "action_type": act,
                        "description": (
                            f"Action type '{act}' experienced obstacles in {int(fail_rate * 100)}% of "
                            f"{tot} recorded historical execution(s)."
                        ),
                        "total_occurrences": tot,
                        "failure_rate": fail_rate,
                        "evidence_support": f"{stats['failed']}/{tot} unsuccessful outcomes",
                        "caveat": "Investigate root cause constraints before repeating this action type.",
                    })

    # ── Feedback Patterns ──────────────────────────────────────────────────────
    if total_feedbacks >= 2:
        feedback_target_stats = defaultdict(lambda: {"accepted": 0, "rejected": 0, "total": 0})
        for f in feedbacks:
            tt = (f.target_type or "DECISION").upper()
            tgt_stats = feedback_target_stats[tt]
            tgt_stats["total"] += 1
            if f.accepted is True:
                tgt_stats["accepted"] += 1
            elif f.accepted is False:
                tgt_stats["rejected"] += 1

        for tt, fstats in feedback_target_stats.items():
            if fstats["accepted"] >= 2:
                frequently_accepted_actions.append({
                    "target_type": tt,
                    "accepted_count": fstats["accepted"],
                    "total_reviewed": fstats["total"],
                    "acceptance_rate": round(fstats["accepted"] / fstats["total"], 2),
                    "summary": f"Users accepted {fstats['accepted']} recommendations/plans of type '{tt}'.",
                })
            if fstats["rejected"] >= 2:
                frequently_rejected_actions.append({
                    "target_type": tt,
                    "rejected_count": fstats["rejected"],
                    "total_reviewed": fstats["total"],
                    "rejection_rate": round(fstats["rejected"] / fstats["total"], 2),
                    "summary": f"Users rejected {fstats['rejected']} recommendations/plans of type '{tt}'.",
                })

    # ── Areas With Insufficient Data ───────────────────────────────────────────
    areas_with_insufficient_data: list[str] = []
    if insufficient_data:
        areas_with_insufficient_data.append(
            f"Overall system learning has insufficient data (currently {total_outcomes}/{MIN_OUTCOMES_FOR_GLOBAL_LEARNING} required outcomes)."
        )

    for act in STANDARD_ACTION_TYPES:
        if action_type_stats[act]["total"] == 0:
            areas_with_insufficient_data.append(f"No historical execution outcomes recorded for action type '{act}'.")
        elif action_type_stats[act]["total"] < MIN_PATTERN_OCCURRENCES:
            areas_with_insufficient_data.append(f"Limited historical samples for '{act}' ({action_type_stats[act]['total']} outcome).")

    # ── Evidence Coverage Assessment ───────────────────────────────────────────
    outcomes_with_evidence = sum(1 for o in outcomes if o.evidence is not None)
    coverage_ratio = round(outcomes_with_evidence / total_outcomes, 2) if total_outcomes > 0 else 0.0

    evidence_coverage = {
        "outcomes_with_evidence_count": outcomes_with_evidence,
        "total_outcomes": total_outcomes,
        "coverage_ratio": coverage_ratio,
        "documented_percentage": f"{int(coverage_ratio * 100)}%",
    }

    return LearningSummary(
        user_id=user_id,
        total_outcomes=total_outcomes,
        successful_count=successful_count,
        partial_count=partial_count,
        failed_count=failed_count,
        unknown_count=unknown_count,
        total_feedbacks=total_feedbacks,
        useful_count=useful_count,
        not_useful_count=not_useful_count,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        successful_patterns=successful_patterns,
        rejected_patterns=rejected_patterns,
        frequently_accepted_actions=frequently_accepted_actions,
        frequently_rejected_actions=frequently_rejected_actions,
        evidence_coverage=evidence_coverage,
        areas_with_insufficient_data=areas_with_insufficient_data,
        insufficient_data=insufficient_data,
    )
