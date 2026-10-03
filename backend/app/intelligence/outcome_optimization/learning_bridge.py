"""
backend/app/intelligence/outcome_optimization/learning_bridge.py

Phase 8.9: Learning Bridge to Phase 8.5
Converts Phase 8.9 outcome measurements into Phase 8.5 OutcomeRecords,
extending the existing learning architecture without duplicating it.

Principle: Phase 8.9 does NOT create a new learning system.
It feeds into Phase 8.5's existing storage and learning engine.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.intelligence.outcome_optimization.models import (
    OutcomeMeasurement,
    EffectivenessLabel,
)
from app.intelligence.learning.models import OutcomeRecord, OutcomeStatus
from app.intelligence.learning.outcome_store import save_outcome

logger = logging.getLogger("bgai.outcome_optimization.learning_bridge")


def _effectiveness_to_outcome_status(effectiveness: str) -> str:
    """
    Map Phase 8.9 EffectivenessLabel to Phase 8.5 OutcomeStatus.

    This is the bridge between measurement-based Phase 8.9 and
    pattern-learning Phase 8.5.
    """
    mapping = {
        EffectivenessLabel.POSITIVE: OutcomeStatus.SUCCESSFUL,
        EffectivenessLabel.NEGATIVE: OutcomeStatus.FAILED,
        EffectivenessLabel.NEUTRAL: OutcomeStatus.PARTIAL,
        EffectivenessLabel.INCONCLUSIVE: OutcomeStatus.UNKNOWN,
        EffectivenessLabel.INSUFFICIENT_DATA: OutcomeStatus.UNKNOWN,
    }
    return mapping.get(effectiveness, OutcomeStatus.UNKNOWN)


def bridge_measurement_to_learning(
    measurement: OutcomeMeasurement,
    action_type: str = "GENERAL",
    question: Optional[str] = None,
) -> Optional[OutcomeRecord]:
    """
    Convert a Phase 8.9 OutcomeMeasurement to a Phase 8.5 OutcomeRecord
    and persist it to the Phase 8.5 learning store.

    Returns the saved OutcomeRecord, or None if the measurement has
    insufficient data to feed into the learning system.

    Does NOT create a parallel learning system — uses Phase 8.5's
    save_outcome() directly.
    """
    if measurement.effectiveness == EffectivenessLabel.INSUFFICIENT_DATA:
        logger.debug(
            "Skipping bridge for measurement %s — insufficient data to learn from.",
            measurement.measurement_id,
        )
        return None

    status = _effectiveness_to_outcome_status(measurement.effectiveness)

    # Build evidence dict for Phase 8.5
    evidence = {
        "measurement_id": measurement.measurement_id,
        "metric_name": measurement.metric_name,
        "table": measurement.source_table,
        "column": measurement.source_column,
        "baseline_value": measurement.baseline_value,
        "observed_value": measurement.observed_value,
        "delta": measurement.delta,
        "delta_pct": measurement.delta_pct,
        "effectiveness": measurement.effectiveness,
        "confidence": measurement.confidence,
        "attribution": measurement.attribution,
        "window": measurement.window,
        "source": "phase_8_9_measurement",
    }

    outcome = OutcomeRecord(
        user_id=measurement.user_id,
        action_id=measurement.action_id,
        action_type=action_type.upper() if action_type else "GENERAL",
        expected_outcome=(
            f"Measure effect of action on {measurement.metric_name}"
        ),
        actual_outcome=(
            f"Observed {measurement.effectiveness} change in '{measurement.metric_name}': "
            f"baseline={measurement.baseline_value}, "
            f"observed={measurement.observed_value}, "
            f"delta={measurement.delta}"
        ),
        status=status,
        question=question,
        evidence=evidence,
        notes=measurement.epistemic_note,
    )

    try:
        saved = save_outcome(outcome)
        logger.debug(
            "Bridged measurement %s → Phase 8.5 outcome %s (status=%s)",
            measurement.measurement_id,
            saved.outcome_id,
            saved.status,
        )
        return saved
    except Exception as e:
        logger.warning("Failed to bridge measurement to Phase 8.5: %s", str(e))
        return None
