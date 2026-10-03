"""
backend/app/intelligence/outcome_optimization/recommendation_engine.py

Phase 8.9: Adaptive Recommendation Engine
Generates recommendations informed by real historical outcome data.

Rules:
- Recommendations are ONLY generated when real historical data supports them.
- NO auto-execution. User must go through Phase 8.8 Action Proposal flow.
- Cold start: returns COLD_START source when < MIN_OUTCOMES_FOR_RECS outcomes exist.
- Never fabricates historical success rates or sample sizes.
- Always provides requires_human_confirmation=True.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from app.intelligence.learning.outcome_store import list_outcomes
from app.intelligence.learning.models import OutcomeStatus
from app.intelligence.outcome_optimization.outcome_tracker import (
    list_measurements,
    save_recommendation,
)
from app.intelligence.outcome_optimization.models import (
    AdaptiveRecommendation,
    ConfidenceLevel,
    EffectivenessLabel,
    RecommendationSource,
)

logger = logging.getLogger("bgai.outcome_optimization.recommendations")

MIN_OUTCOMES_FOR_RECS = 3
MIN_SUCCESSES_FOR_RECOMMENDATION = 2
MIN_SUCCESS_RATE_FOR_RECOMMENDATION = 0.5  # At least 50% success rate


def generate_adaptive_recommendations(user_id: str) -> list[AdaptiveRecommendation]:
    """
    Generate adaptive recommendations from Phase 8.5 outcomes and Phase 8.9 measurements.

    Steps:
    1. Load Phase 8.5 historical outcomes (action_type → success rates)
    2. Load Phase 8.9 measurements (table-level effectiveness signals)
    3. Synthesize recommendations from patterns with sufficient evidence
    4. Return cold-start recommendation if insufficient data
    """
    # Step 1: Phase 8.5 historical outcomes
    try:
        outcomes = list_outcomes(user_id=user_id, limit=200)
    except Exception as e:
        logger.warning("Failed to load outcomes: %s", str(e))
        outcomes = []

    # Step 2: Phase 8.9 measurements
    try:
        measurements = list_measurements(user_id=user_id, limit=100)
    except Exception as e:
        logger.warning("Failed to load measurements: %s", str(e))
        measurements = []

    recommendations: list[AdaptiveRecommendation] = []

    if len(outcomes) < MIN_OUTCOMES_FOR_RECS:
        # Cold start
        cold_rec = AdaptiveRecommendation(
            user_id=user_id,
            title="Build Your Outcome History",
            description=(
                "Record outcomes for your executed actions to unlock personalized "
                "adaptive recommendations. Currently "
                f"{len(outcomes)}/{MIN_OUTCOMES_FOR_RECS} outcomes recorded."
            ),
            action_type="RECORD_OUTCOME",
            target_table="",
            rationale=(
                f"Adaptive recommendations require at least {MIN_OUTCOMES_FOR_RECS} "
                "recorded outcomes to identify meaningful patterns."
            ),
            source=RecommendationSource.COLD_START,
            confidence=ConfidenceLevel.LIMITED,
            caveat=(
                "This is a guidance recommendation, not a data action. "
                "Record more outcomes to enable evidence-based recommendations."
            ),
        )
        save_recommendation(cold_rec)
        return [cold_rec]

    # Step 3a: Action-type success patterns from Phase 8.5
    action_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"total": 0, "successful": 0, "outcome_ids": [], "tables": set()}
    )

    for o in outcomes:
        act = (o.action_type or "GENERAL").upper()
        action_stats[act]["total"] += 1
        if o.status == OutcomeStatus.SUCCESSFUL:
            action_stats[act]["successful"] += 1
            action_stats[act]["outcome_ids"].append(o.outcome_id)
        if o.evidence and isinstance(o.evidence, dict) and o.evidence.get("table"):
            action_stats[act]["tables"].add(str(o.evidence["table"]))

    for act, stats in action_stats.items():
        tot = stats["total"]
        succ = stats["successful"]
        if tot < MIN_SUCCESSES_FOR_RECOMMENDATION:
            continue

        rate = succ / tot
        if rate < MIN_SUCCESS_RATE_FOR_RECOMMENDATION:
            continue

        # Determine confidence
        if tot >= 10:
            conf = ConfidenceLevel.HIGH
        elif tot >= 5:
            conf = ConfidenceLevel.MODERATE
        else:
            conf = ConfidenceLevel.LIMITED

        tables = list(stats["tables"])
        target_table = tables[0] if tables else ""

        rec = AdaptiveRecommendation(
            user_id=user_id,
            title=f"Repeat Successful {act.title()} Action",
            description=(
                f"Historical data shows {act} actions have been successful in "
                f"{int(rate * 100)}% of {tot} recorded executions. "
                f"Consider applying this action type again where appropriate."
            ),
            action_type=act,
            target_table=target_table,
            rationale=(
                f"Evidence: {succ}/{tot} historical '{act}' actions resulted in "
                f"SUCCESSFUL outcomes. Success rate: {int(rate * 100)}%. "
                "Note: Past patterns do not guarantee future results."
            ),
            source=RecommendationSource.HISTORICAL_OUTCOMES,
            historical_success_rate=round(rate, 3),
            historical_sample_size=tot,
            confidence=conf,
            supporting_outcome_ids=stats["outcome_ids"][:5],
            caveat=(
                "Recommendation based on observed historical outcome patterns. "
                "Human review is required before any action is taken."
            ),
        )
        save_recommendation(rec)
        recommendations.append(rec)

    # Step 3b: Table-level effectiveness signals from Phase 8.9 measurements
    table_meas_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"positive": 0, "negative": 0, "total": 0, "measurement_ids": []}
    )

    for meas in measurements:
        tbl = meas.source_table
        if not tbl:
            continue
        table_meas_stats[tbl]["total"] += 1
        table_meas_stats[tbl]["measurement_ids"].append(meas.measurement_id)
        if meas.effectiveness == EffectivenessLabel.POSITIVE:
            table_meas_stats[tbl]["positive"] += 1
        elif meas.effectiveness == EffectivenessLabel.NEGATIVE:
            table_meas_stats[tbl]["negative"] += 1

    for tbl, stats in table_meas_stats.items():
        tot = stats["total"]
        if tot < 2:
            continue

        pos = stats["positive"]
        neg = stats["negative"]

        if neg > pos and neg >= 2:
            # Flag tables with negative outcomes
            rec = AdaptiveRecommendation(
                user_id=user_id,
                title=f"Review Actions on '{tbl}'",
                description=(
                    f"Measurements on table '{tbl}' have shown "
                    f"{neg} negative outcome(s) across {tot} measurement(s). "
                    "Consider reviewing recent changes to this table."
                ),
                action_type="INVESTIGATE",
                target_table=tbl,
                rationale=(
                    f"Evidence: {neg}/{tot} outcome measurements on '{tbl}' "
                    "showed negative effectiveness. "
                    "Negative association does not imply causation."
                ),
                source=RecommendationSource.HISTORICAL_OUTCOMES,
                historical_sample_size=tot,
                confidence=ConfidenceLevel.LIMITED if tot < 5 else ConfidenceLevel.MODERATE,
                caveat=(
                    "This observation is based on measured metric changes. "
                    "The relationship is associative, not causal."
                ),
            )
            save_recommendation(rec)
            recommendations.append(rec)

    if not recommendations:
        # Sufficient data but no strong patterns found
        neutral_rec = AdaptiveRecommendation(
            user_id=user_id,
            title="No Strong Patterns Detected Yet",
            description=(
                f"With {len(outcomes)} recorded outcomes, no clear repeatable "
                "success or failure patterns were identified. Continue recording "
                "outcomes for more actionable recommendations."
            ),
            action_type="OBSERVE",
            target_table="",
            rationale=(
                "Patterns are identified when at least 2 outcomes of the same "
                "action type have a success rate ≥ 50%."
            ),
            source=RecommendationSource.HISTORICAL_OUTCOMES,
            confidence=ConfidenceLevel.LIMITED,
            caveat="More outcome data will improve recommendation quality.",
        )
        save_recommendation(neutral_rec)
        recommendations.append(neutral_rec)

    return recommendations
