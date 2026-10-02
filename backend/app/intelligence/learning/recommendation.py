"""
backend/app/intelligence/learning/recommendation.py

Phase 8.5: Recommendation Enrichment via Historical Outcome Intelligence
Uses verified historical user outcomes to augment Phase 8.4 recommendations with
empirical context.

Strict Epistemic Principles:
- Only references historical support if sufficient real successful outcomes exist (>= 2).
- Explicitly states that historical patterns do NOT guarantee future outcomes.
- Never fabricates or hallucinates outcome support when historical data is absent or insufficient.
"""
from __future__ import annotations

import logging
from typing import Sequence
from app.intelligence.decision.models import RecommendedInvestigation, PlanStep
from app.intelligence.learning.models import OutcomeStatus
from app.intelligence.learning.outcome_store import list_outcomes

logger = logging.getLogger("bgai.learning.recommendation")

MIN_SUCCESSES_FOR_SUPPORT = 2


def enrich_recommendations_with_history(
    investigations: list[RecommendedInvestigation],
    plan_steps: list[PlanStep],
    user_id: str,
) -> tuple[list[RecommendedInvestigation], list[PlanStep]]:
    """
    Enriches Phase 8.4 investigations and plan steps with real historical outcome context.
    """
    try:
        outcomes = list_outcomes(user_id=user_id, limit=200)
        if not outcomes:
            return investigations, plan_steps

        # Compute successes by action type and table
        success_by_action: dict[str, int] = {}
        success_by_table: dict[str, int] = {}

        for o in outcomes:
            if o.status == OutcomeStatus.SUCCESSFUL:
                act = (o.action_type or "").upper()
                success_by_action[act] = success_by_action.get(act, 0) + 1
                # If evidence references table
                if isinstance(o.evidence, dict) and o.evidence.get("table"):
                    tbl = str(o.evidence["table"]).lower()
                    success_by_table[tbl] = success_by_table.get(tbl, 0) + 1

        # Enrich Plan Steps where empirical support exists
        for step in plan_steps:
            act_type = (step.action_type or "").upper()
            succ_count = success_by_action.get(act_type, 0)
            if succ_count >= MIN_SUCCESSES_FOR_SUPPORT:
                support_note = (
                    f" (Historical outcome support: observed {succ_count} successful outcomes for similar '{act_type}' actions. "
                    "Past patterns do not guarantee future success.)"
                )
                if support_note not in step.description:
                    step.description = f"{step.description}{support_note}"

        # Enrich Investigations where empirical support exists
        for inv in investigations:
            tbl = (inv.target_table or "").lower()
            if tbl and success_by_table.get(tbl, 0) >= MIN_SUCCESSES_FOR_SUPPORT:
                succ_count = success_by_table[tbl]
                support_note = (
                    f" (Historical context: {succ_count} previous investigation(s) involving '{tbl}' "
                    "led to confirmed problem resolution.)"
                )
                if support_note not in inv.rationale:
                    inv.rationale = f"{inv.rationale}{support_note}"

    except Exception as e:
        logger.debug("Recommendation enrichment encountered error: %s", str(e))

    return investigations, plan_steps
