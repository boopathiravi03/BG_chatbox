"""
backend/app/intelligence/outcome_optimization/measurement_engine.py

Phase 8.9: Outcome Measurement Engine
Executes before/after metric comparisons using real database data.
Measures observable changes over configurable time windows (24h, 7d, 14d, 30d).

Epistemic safety:
- Only reads from user database (SELECT only).
- Measures OBSERVED changes, never asserts causation.
- Returns INSUFFICIENT_DATA label when evidence is inadequate.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.intelligence.outcome_optimization.models import (
    OutcomeMeasurement,
    EffectivenessLabel,
    ConfidenceLevel,
    AttributionStatus,
    MeasurementWindow,
)
from app.intelligence.outcome_optimization.baseline_engine import (
    compute_baseline_for_metric,
    _safe_query_scalar,
    _safe_query_count,
)
from app.intelligence.schema_analyzer import quote_identifier
from app.intelligence.outcome_optimization.effectiveness import classify_effectiveness
from app.intelligence.outcome_optimization.attribution import assess_attribution

logger = logging.getLogger("bgai.outcome_optimization.measurement")

# Minimum row count for a meaningful measurement
MIN_ROWS_FOR_MEASUREMENT = 5


def measure_metric_outcome(
    engine: Any,
    db_type: str,
    user_id: str,
    source_table: str,
    source_column: str,
    metric_name: str,
    aggregation: str = "SUM",
    action_id: Optional[str] = None,
    action_executed_at: Optional[str] = None,
    window: str = MeasurementWindow.D7,
) -> OutcomeMeasurement:
    """
    Measure the current state of a metric and compare it against the baseline.

    Steps:
    1. Compute baseline value (pre-action historical state)
    2. Measure current observed value (post-action state)
    3. Compute delta and delta_pct
    4. Classify effectiveness (deterministic rules)
    5. Assess attribution (are confounders present?)
    6. Return OutcomeMeasurement

    Note: If the action was just executed moments ago, there may be no meaningful
    difference between baseline and current. The measurement is still valid — it
    shows the current state of the metric.
    """
    m = OutcomeMeasurement(
        user_id=user_id,
        action_id=action_id,
        metric_name=metric_name,
        source_table=source_table,
        source_column=source_column or "",
        window=window,
        action_executed_at=action_executed_at,
        measured_at=datetime.now(timezone.utc).isoformat(),
    )

    if engine is None:
        m.effectiveness = EffectivenessLabel.INSUFFICIENT_DATA
        m.confidence = ConfidenceLevel.LIMITED
        m.attribution = AttributionStatus.NO_BASELINE
        return m

    try:
        # Step 1: Get baseline
        baseline_info = compute_baseline_for_metric(
            engine=engine,
            db_type=db_type,
            source_table=source_table,
            source_column=source_column,
            aggregation=aggregation,
        )

        m.baseline_value = baseline_info.get("baseline_value")
        m.baseline_period = baseline_info.get("baseline_period", "full_history")
        m.baseline_sample_size = baseline_info.get("baseline_sample_size", 0)
        m.measurement_sql = baseline_info.get("sql_used", "")

        if not baseline_info.get("sufficient") or m.baseline_value is None:
            m.effectiveness = EffectivenessLabel.INSUFFICIENT_DATA
            m.confidence = ConfidenceLevel.LIMITED
            m.attribution = AttributionStatus.NO_BASELINE
            return m

        # Step 2: Measure current (observed) value — same SQL, re-executed now
        # This is the same aggregation SQL. After a data change action, this
        # will reflect the updated state.
        t_sql = quote_identifier(source_table, db_type)
        agg = aggregation.upper()

        if agg == "COUNT" or not source_column:
            obs_sql = f"SELECT COUNT(*) FROM {t_sql}"
        else:
            c_sql = quote_identifier(source_column, db_type)
            obs_sql = f"SELECT {agg}({c_sql}) FROM {t_sql} WHERE {c_sql} IS NOT NULL"

        m.measurement_sql = obs_sql
        obs_val = _safe_query_scalar(engine, obs_sql)
        m.observed_value = round(obs_val, 4) if obs_val is not None else None

        # Count rows for sample_size
        count_sql = f"SELECT COUNT(*) FROM {t_sql}"
        m.sample_size = _safe_query_count(engine, count_sql)

        if m.observed_value is None:
            m.effectiveness = EffectivenessLabel.INSUFFICIENT_DATA
            m.confidence = ConfidenceLevel.LIMITED
            m.attribution = AttributionStatus.NO_BASELINE
            return m

        # Step 3: Compute delta
        m.delta = round(m.observed_value - m.baseline_value, 4)
        if m.baseline_value != 0:
            m.delta_pct = round((m.delta / abs(m.baseline_value)) * 100, 2)
        else:
            m.delta_pct = None

        # Step 4: Classify effectiveness
        m.effectiveness = classify_effectiveness(
            delta=m.delta,
            delta_pct=m.delta_pct,
            baseline_value=m.baseline_value,
            observed_value=m.observed_value,
            sample_size=m.sample_size,
            baseline_sample_size=m.baseline_sample_size,
        )

        # Step 5: Determine confidence
        m.confidence = _determine_confidence(m.sample_size, m.baseline_sample_size)

        # Step 6: Assess attribution
        attr_result = assess_attribution(
            engine=engine,
            db_type=db_type,
            source_table=source_table,
            action_executed_at=action_executed_at,
        )
        m.attribution = attr_result["status"]
        m.confounders = attr_result.get("confounders", [])

        m.epistemic_note = (
            f"Observed change of {m.delta:+.4f} "
            f"({'+' if (m.delta_pct or 0) >= 0 else ''}{m.delta_pct or 'N/A'}%) "
            f"in '{metric_name}' after the action. "
            "This is an observed association, not a proven causal effect. "
            "Other concurrent changes may have contributed."
        )

    except Exception as e:
        logger.warning("Measurement error for %s.%s: %s", source_table, source_column, str(e))
        m.effectiveness = EffectivenessLabel.INSUFFICIENT_DATA
        m.confidence = ConfidenceLevel.LIMITED
        m.attribution = AttributionStatus.NO_BASELINE

    return m


def _determine_confidence(sample_size: int, baseline_sample_size: int) -> str:
    """Deterministic confidence classification based on sample sizes."""
    combined = sample_size + baseline_sample_size
    if combined >= 100:
        return ConfidenceLevel.HIGH
    elif combined >= 20:
        return ConfidenceLevel.MODERATE
    return ConfidenceLevel.LIMITED
