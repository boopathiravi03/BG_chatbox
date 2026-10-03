"""
backend/app/intelligence/predictive/learning_context.py

Phase 9.0: Learning & Outcome Context Integration
Connects predictive forecasting to Phase 8.9 measured outcomes and Phase 8.5
historical learning records.

Epistemic Principles:
- Observed historical action outcomes provide empirical context, NOT guarantees.
- Integrates with existing outcome stores; does not create a duplicate database.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.intelligence.outcome_optimization.outcome_tracker import list_measurements
from app.intelligence.outcome_optimization.models import EffectivenessLabel
from app.intelligence.learning.outcome_store import list_outcomes
from app.intelligence.learning.models import OutcomeStatus

logger = logging.getLogger("bgai.predictive.learning_context")


def get_historical_outcome_context(
    user_id: str, table_name: str, metric_name: Optional[str] = None
) -> dict[str, Any]:
    """
    Retrieves empirical context from Phase 8.9 outcome measurements and Phase 8.5 outcomes.
    Returns:
        {
            "has_history": bool,
            "summary": str,
            "positive_count": int,
            "negative_count": int,
            "total_outcomes": int,
            "supporting_references": list[dict[str, Any]],
        }
    """
    supporting_refs: list[dict[str, Any]] = []
    pos_count = 0
    neg_count = 0
    total_count = 0

    # 1. Inspect Phase 8.9 measurements on this table
    try:
        measurements = list_measurements(user_id=user_id, source_table=table_name, limit=50)
        for m in measurements:
            total_count += 1
            if m.effectiveness == EffectivenessLabel.POSITIVE:
                pos_count += 1
                supporting_refs.append({
                    "source": "phase_8_9_measurement",
                    "id": m.measurement_id,
                    "metric": m.metric_name,
                    "result": "POSITIVE",
                    "delta_pct": m.delta_pct,
                    "note": f"Observed {m.effectiveness} change (+{m.delta_pct}%) in '{m.metric_name}'.",
                })
            elif m.effectiveness == EffectivenessLabel.NEGATIVE:
                neg_count += 1
                supporting_refs.append({
                    "source": "phase_8_9_measurement",
                    "id": m.measurement_id,
                    "metric": m.metric_name,
                    "result": "NEGATIVE",
                    "delta_pct": m.delta_pct,
                    "note": f"Observed {m.effectiveness} change ({m.delta_pct}%) in '{m.metric_name}'.",
                })
    except Exception as e:
        logger.debug("Phase 8.9 measurements query error (non-critical): %s", str(e))

    # 2. Inspect Phase 8.5 outcomes
    try:
        outcomes = list_outcomes(user_id=user_id, limit=50)
        for o in outcomes:
            # Check if outcome refers to target table in evidence
            table_match = False
            if isinstance(o.evidence, dict) and o.evidence.get("table") == table_name:
                table_match = True
            elif o.notes and table_name.lower() in o.notes.lower():
                table_match = True

            if table_match:
                total_count += 1
                if o.status == OutcomeStatus.SUCCESSFUL:
                    pos_count += 1
                elif o.status == OutcomeStatus.FAILED:
                    neg_count += 1
                supporting_refs.append({
                    "source": "phase_8_5_outcome",
                    "id": o.outcome_id,
                    "status": o.status,
                    "action_type": o.action_type,
                    "note": f"Recorded {o.status} outcome for '{o.action_type}' on '{table_name}'.",
                })
    except Exception as e:
        logger.debug("Phase 8.5 outcomes query error (non-critical): %s", str(e))

    if total_count == 0:
        return {
            "has_history": False,
            "summary": "No historical action outcomes recorded for this entity table.",
            "positive_count": 0,
            "negative_count": 0,
            "total_outcomes": 0,
            "supporting_references": [],
        }

    summary = (
        f"Historical context: {total_count} past action outcome(s) observed on '{table_name}' "
        f"({pos_count} positive, {neg_count} negative). "
        "Historical correlation provides contextual evidence but does not guarantee future results."
    )

    return {
        "has_history": True,
        "summary": summary,
        "positive_count": pos_count,
        "negative_count": neg_count,
        "total_outcomes": total_count,
        "supporting_references": supporting_refs[:5],
    }
