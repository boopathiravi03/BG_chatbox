"""
backend/app/intelligence/outcome_optimization/analysis_engine.py

Phase 8.9: Outcome Analysis Engine
Orchestrates full action → measurement → analysis → learning pipeline.

Given an action_id (from Phase 8.8), it:
1. Retrieves the action proposal from Phase 8.8 audit store
2. Discovers relevant metrics for the action's target table
3. Measures each metric's current state vs baseline
4. Computes effectiveness and attribution
5. Bridges results to Phase 8.5 learning store
6. Returns a complete OutcomeAnalysis

Safety:
- All database access is read-only.
- User isolation strictly enforced.
- No fabricated metrics or fabricated outcomes.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.intelligence.outcome_optimization.models import (
    OutcomeAnalysis,
    OutcomeMeasurement,
    EffectivenessLabel,
    ConfidenceLevel,
    AttributionStatus,
    MeasurementWindow,
)
from app.intelligence.outcome_optimization.baseline_engine import (
    discover_measurable_metrics,
)
from app.intelligence.outcome_optimization.measurement_engine import (
    measure_metric_outcome,
)
from app.intelligence.outcome_optimization.outcome_tracker import (
    save_measurement,
    list_measurements,
)
from app.intelligence.outcome_optimization.effectiveness import describe_effectiveness
from app.intelligence.outcome_optimization.learning_bridge import (
    bridge_measurement_to_learning,
)

logger = logging.getLogger("bgai.outcome_optimization.analysis")

# Maximum metrics to measure per analysis (to avoid excessive DB load)
MAX_METRICS_PER_ANALYSIS = 5


def run_outcome_analysis(
    user_id: str,
    action_id: str,
    engine: Any,
    db_type: str,
    window: str = MeasurementWindow.D7,
    force_remeasure: bool = False,
) -> OutcomeAnalysis:
    """
    Run a complete outcome analysis for a Phase 8.8 action.

    Returns OutcomeAnalysis with measurements across discovered metrics.
    If engine is None, returns INSUFFICIENT_DATA analysis.
    """
    analysis = OutcomeAnalysis(
        action_id=action_id,
        user_id=user_id,
    )

    if engine is None:
        analysis.overall_effectiveness = EffectivenessLabel.INSUFFICIENT_DATA
        analysis.overall_confidence = ConfidenceLevel.LIMITED
        analysis.attribution_summary = AttributionStatus.NO_BASELINE
        analysis.summary = "No database connection available for outcome analysis."
        analysis.data_gaps.append("No active database connection.")
        return analysis

    # Step 1: Try to retrieve action details from Phase 8.8
    action_executed_at = None
    action_type = "GENERAL"
    target_table = ""

    try:
        from app.intelligence.actions.action_audit import get_action
        action = get_action(action_id=action_id, user_id=user_id)
        if action is not None:
            action_type = action.action_type or "GENERAL"
            target_table = action.target.table if action.target else ""
            analysis.action_type = str(action_type)
            analysis.target_table = target_table
            # Try to get execution timestamp from audit
            from app.intelligence.actions.action_audit import list_audits
            audits = list_audits(user_id=user_id, limit=50)
            for audit in audits:
                if audit.action_id == action_id:
                    action_executed_at = audit.timestamp
                    break
    except Exception as e:
        logger.debug("Could not load action details for %s: %s", action_id, str(e))
        analysis.data_gaps.append(f"Could not retrieve action details: {str(e)}")

    # Step 2: Check for existing measurements (avoid recomputing unless forced)
    if not force_remeasure:
        existing = list_measurements(user_id=user_id, action_id=action_id, limit=20)
        if existing:
            analysis.measurements = existing
            analysis.overall_effectiveness = _aggregate_effectiveness(existing)
            analysis.overall_confidence = _aggregate_confidence(existing)
            analysis.attribution_summary = _aggregate_attribution(existing)
            analysis.summary = _build_summary(analysis, existing)
            return analysis

    # Step 3: Discover metrics for this database
    try:
        all_metrics = discover_measurable_metrics(engine=engine, db_type=db_type)
    except Exception as e:
        logger.warning("Metric discovery failed: %s", str(e))
        all_metrics = []

    if not all_metrics:
        analysis.overall_effectiveness = EffectivenessLabel.INSUFFICIENT_DATA
        analysis.data_gaps.append(
            "No measurable metrics found in the connected database."
        )
        analysis.summary = (
            "No measurable business metrics could be discovered for this database. "
            "Outcome analysis requires at least one numeric column for measurement."
        )
        return analysis

    # Step 4: Prioritize metrics for the target table
    # First try to measure metrics from the action's target table,
    # then fill remaining slots with other metrics.
    target_metrics = [m for m in all_metrics if m.get("source_table") == target_table]
    other_metrics = [m for m in all_metrics if m.get("source_table") != target_table]

    ordered_metrics = (target_metrics + other_metrics)[:MAX_METRICS_PER_ANALYSIS]

    if not ordered_metrics:
        ordered_metrics = all_metrics[:MAX_METRICS_PER_ANALYSIS]

    # Step 5: Measure each metric
    measurements: list[OutcomeMeasurement] = []
    for metric in ordered_metrics:
        try:
            m = measure_metric_outcome(
                engine=engine,
                db_type=db_type,
                user_id=user_id,
                source_table=metric["source_table"],
                source_column=metric.get("source_column", ""),
                metric_name=metric["metric_name"],
                aggregation=metric.get("aggregation", "SUM"),
                action_id=action_id,
                action_executed_at=action_executed_at,
                window=window,
            )
            # Save to Phase 8.9 store
            save_measurement(m)
            measurements.append(m)

            # Bridge to Phase 8.5 learning
            try:
                bridge_measurement_to_learning(
                    measurement=m,
                    action_type=action_type,
                    question=f"Outcome for action {action_id} on {metric['source_table']}",
                )
            except Exception as bridge_err:
                logger.debug("Bridge error (non-critical): %s", str(bridge_err))

        except Exception as e:
            logger.warning(
                "Measurement failed for %s.%s: %s",
                metric.get("source_table"),
                metric.get("source_column"),
                str(e),
            )
            analysis.data_gaps.append(
                f"Could not measure '{metric.get('metric_name')}': {str(e)}"
            )

    analysis.measurements = measurements

    # Step 6: Aggregate effectiveness/confidence/attribution
    if measurements:
        analysis.overall_effectiveness = _aggregate_effectiveness(measurements)
        analysis.overall_confidence = _aggregate_confidence(measurements)
        analysis.attribution_summary = _aggregate_attribution(measurements)
    else:
        analysis.overall_effectiveness = EffectivenessLabel.INSUFFICIENT_DATA
        analysis.overall_confidence = ConfidenceLevel.LIMITED
        analysis.attribution_summary = AttributionStatus.NO_BASELINE
        analysis.data_gaps.append("No measurements could be completed.")

    analysis.summary = _build_summary(analysis, measurements)
    return analysis


def _aggregate_effectiveness(measurements: list[OutcomeMeasurement]) -> str:
    """Aggregate individual metric effectiveness to overall label."""
    if not measurements:
        return EffectivenessLabel.INSUFFICIENT_DATA

    counts = {
        EffectivenessLabel.POSITIVE: 0,
        EffectivenessLabel.NEGATIVE: 0,
        EffectivenessLabel.NEUTRAL: 0,
        EffectivenessLabel.INCONCLUSIVE: 0,
        EffectivenessLabel.INSUFFICIENT_DATA: 0,
    }

    for m in measurements:
        label = m.effectiveness or EffectivenessLabel.INSUFFICIENT_DATA
        counts[label] = counts.get(label, 0) + 1

    total = len(measurements)
    data_available = total - counts[EffectivenessLabel.INSUFFICIENT_DATA]

    if data_available == 0:
        return EffectivenessLabel.INSUFFICIENT_DATA

    # Majority rules; POSITIVE/NEGATIVE take precedence over NEUTRAL/INCONCLUSIVE
    pos = counts[EffectivenessLabel.POSITIVE]
    neg = counts[EffectivenessLabel.NEGATIVE]
    neutral = counts[EffectivenessLabel.NEUTRAL]
    inconclusive = counts[EffectivenessLabel.INCONCLUSIVE]

    if pos > neg and pos > neutral:
        return EffectivenessLabel.POSITIVE
    if neg > pos and neg > neutral:
        return EffectivenessLabel.NEGATIVE
    if neutral >= inconclusive and neutral > 0:
        return EffectivenessLabel.NEUTRAL
    return EffectivenessLabel.INCONCLUSIVE


def _aggregate_confidence(measurements: list[OutcomeMeasurement]) -> str:
    """Aggregate confidence: use the minimum (most conservative) confidence."""
    if not measurements:
        return ConfidenceLevel.LIMITED

    order = {ConfidenceLevel.HIGH: 3, ConfidenceLevel.MODERATE: 2, ConfidenceLevel.LIMITED: 1}
    min_conf = min(
        (m.confidence or ConfidenceLevel.LIMITED for m in measurements),
        key=lambda c: order.get(c, 0),
    )
    return min_conf


def _aggregate_attribution(measurements: list[OutcomeMeasurement]) -> str:
    """Aggregate attribution: CONFOUNDERS_PRESENT if any measurement has it."""
    for m in measurements:
        if m.attribution == AttributionStatus.CONFOUNDERS_PRESENT:
            return AttributionStatus.CONFOUNDERS_PRESENT
        if m.attribution == AttributionStatus.INSUFFICIENT_WINDOW:
            return AttributionStatus.INSUFFICIENT_WINDOW
    return AttributionStatus.OBSERVED_OUTCOME


def _build_summary(analysis: OutcomeAnalysis, measurements: list[OutcomeMeasurement]) -> str:
    """Build a human-readable summary of the outcome analysis."""
    if not measurements:
        return (
            f"No outcome measurements could be completed for action '{analysis.action_id}'. "
            "Ensure the database is connected and contains measurable numeric data."
        )

    eff_desc = describe_effectiveness(analysis.overall_effectiveness)
    conf_note = {
        ConfidenceLevel.HIGH: "high confidence",
        ConfidenceLevel.MODERATE: "moderate confidence",
        ConfidenceLevel.LIMITED: "limited confidence (small sample)",
    }.get(analysis.overall_confidence, "unknown confidence")

    metric_names = ", ".join(
        m.metric_name for m in measurements
        if m.effectiveness != EffectivenessLabel.INSUFFICIENT_DATA
    )

    summary = (
        f"Outcome analysis for action '{analysis.action_id}' measured "
        f"{len(measurements)} metric(s). "
        f"Overall observed effectiveness: {analysis.overall_effectiveness} ({conf_note}). "
        f"{eff_desc}"
    )

    if metric_names:
        summary += f" Metrics analyzed: {metric_names}."

    if analysis.attribution_summary == AttributionStatus.CONFOUNDERS_PRESENT:
        summary += (
            " Note: Potential confounders were detected. "
            "The observed changes may not be attributable solely to this action."
        )

    summary += (
        " This analysis describes observed associations. "
        "Causation is not claimed."
    )

    return summary
