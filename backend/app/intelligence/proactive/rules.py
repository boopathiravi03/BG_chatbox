"""
backend/app/intelligence/proactive/rules.py

Phase 8.3: Deterministic Threshold Rules & Change Classification
Provides mathematical change calculations, threshold evaluation, and severity
classification for proactive data intelligence.

Zero LLM calls for arithmetic or threshold evaluation.
100% deterministic calculations in Python.
"""
from __future__ import annotations

from typing import Optional, Tuple
from app.intelligence.proactive.models import (
    AlertRule,
    AlertSeverity,
    AlertCategory,
    AlertStatus,
)

# Standard default threshold configuration
DEFAULT_THRESHOLDS = {
    "metric_drop_critical": -30.0,    # Drop <= -30.0% -> CRITICAL
    "metric_drop_warning": -15.0,     # Drop <= -15.0% -> WARNING
    "metric_spike_warning": 40.0,     # Spike >= +40.0% -> WARNING
    "metric_spike_critical": 80.0,    # Spike >= +80.0% -> CRITICAL
    "anomaly_zscore": 2.5,            # Z-Score >= 2.5 -> WARNING / CRITICAL
    "null_rate_warning": 0.05,        # Null rate >= 5.0% -> WARNING
    "null_rate_critical": 0.20,       # Null rate >= 20.0% -> CRITICAL
    "min_sample_size": 3,             # Minimum historical periods required
}


def get_default_rules() -> list[AlertRule]:
    """Returns the default collection of threshold rules."""
    return [
        AlertRule(
            rule_id="default_metric_drop",
            name="Significant Metric Drop",
            category=AlertCategory.METRIC_DROP,
            severity=AlertSeverity.WARNING,
            drop_threshold_percent=DEFAULT_THRESHOLDS["metric_drop_warning"],
            min_sample_size=DEFAULT_THRESHOLDS["min_sample_size"],
            metadata={"critical_threshold": DEFAULT_THRESHOLDS["metric_drop_critical"]},
        ),
        AlertRule(
            rule_id="default_metric_spike",
            name="Significant Metric Spike",
            category=AlertCategory.METRIC_SPIKE,
            severity=AlertSeverity.WARNING,
            spike_threshold_percent=DEFAULT_THRESHOLDS["metric_spike_warning"],
            min_sample_size=DEFAULT_THRESHOLDS["min_sample_size"],
            metadata={"critical_threshold": DEFAULT_THRESHOLDS["metric_spike_critical"]},
        ),
        AlertRule(
            rule_id="default_anomaly",
            name="Statistical Outlier Anomaly",
            category=AlertCategory.ANOMALY_DETECTED,
            severity=AlertSeverity.WARNING,
            zscore_threshold=DEFAULT_THRESHOLDS["anomaly_zscore"],
            min_sample_size=DEFAULT_THRESHOLDS["min_sample_size"],
        ),
        AlertRule(
            rule_id="default_data_quality",
            name="Critical Column Null Rate Degradation",
            category=AlertCategory.DATA_QUALITY_DEGRADATION,
            severity=AlertSeverity.WARNING,
            metadata={"null_threshold": DEFAULT_THRESHOLDS["null_rate_warning"]},
        ),
    ]


def calculate_delta(
    current_value: Optional[float],
    previous_value: Optional[float]
) -> Optional[float]:
    """
    Computes absolute difference: current_value - previous_value.
    Returns None if either value is None.
    """
    if current_value is None or previous_value is None:
        return None
    try:
        return round(float(current_value) - float(previous_value), 4)
    except (TypeError, ValueError):
        return None


def calculate_delta_percent(
    current_value: Optional[float],
    previous_value: Optional[float]
) -> Optional[float]:
    """
    Computes percentage change: ((current - previous) / |previous|) * 100.
    Handles zero baselines gracefully without division by zero.
    """
    if current_value is None or previous_value is None:
        return None
    try:
        curr = float(current_value)
        prev = float(previous_value)

        if prev == 0.0:
            if curr == 0.0:
                return 0.0
            # From 0 to positive value is +100%, from 0 to negative is -100%
            return 100.0 if curr > 0 else -100.0

        return round(((curr - prev) / abs(prev)) * 100.0, 2)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def classify_severity(
    delta_percent: float,
    rule: Optional[AlertRule] = None
) -> Optional[str]:
    """
    Determines severity level based on percentage movement.
    Returns AlertSeverity.CRITICAL, AlertSeverity.WARNING, or None if below threshold.
    """
    drop_crit = (
        (rule.metadata.get("critical_threshold") if rule and rule.metadata else None)
        or DEFAULT_THRESHOLDS["metric_drop_critical"]
    )
    drop_warn = (
        (rule.drop_threshold_percent if rule and rule.drop_threshold_percent is not None else None)
        or DEFAULT_THRESHOLDS["metric_drop_warning"]
    )
    spike_warn = (
        (rule.spike_threshold_percent if rule and rule.spike_threshold_percent is not None else None)
        or DEFAULT_THRESHOLDS["metric_spike_warning"]
    )
    spike_crit = (
        (rule.metadata.get("critical_threshold") if rule and rule.metadata else None)
        or DEFAULT_THRESHOLDS["metric_spike_critical"]
    )

    if delta_percent <= drop_crit:
        return AlertSeverity.CRITICAL
    if delta_percent <= drop_warn:
        return AlertSeverity.WARNING
    if delta_percent >= spike_crit:
        return AlertSeverity.CRITICAL
    if delta_percent >= spike_warn:
        return AlertSeverity.WARNING

    return None


def classify_change(
    delta_percent: float,
    rule: Optional[AlertRule] = None
) -> Optional[Tuple[str, str, str]]:
    """
    Deterministically evaluates delta_percent and returns:
    (AlertCategory, AlertSeverity, threshold_applied_description) or None.
    """
    severity = classify_severity(delta_percent, rule)
    if not severity:
        return None

    if delta_percent < 0:
        category = AlertCategory.METRIC_DROP
        crit_th = (
            (rule.metadata.get("critical_threshold") if rule and rule.metadata else None)
            or DEFAULT_THRESHOLDS["metric_drop_critical"]
        )
        warn_th = (
            (rule.drop_threshold_percent if rule and rule.drop_threshold_percent is not None else None)
            or DEFAULT_THRESHOLDS["metric_drop_warning"]
        )
        applied = f"Drop <= {crit_th}%" if severity == AlertSeverity.CRITICAL else f"Drop <= {warn_th}%"
        return category, severity, applied
    else:
        category = AlertCategory.METRIC_SPIKE
        warn_th = (
            (rule.spike_threshold_percent if rule and rule.spike_threshold_percent is not None else None)
            or DEFAULT_THRESHOLDS["metric_spike_warning"]
        )
        crit_th = (
            (rule.metadata.get("critical_threshold") if rule and rule.metadata else None)
            or DEFAULT_THRESHOLDS["metric_spike_critical"]
        )
        applied = f"Spike >= +{crit_th}%" if severity == AlertSeverity.CRITICAL else f"Spike >= +{warn_th}%"
        return category, severity, applied


def evaluate_null_rate(
    null_rate: float,
    rule: Optional[AlertRule] = None
) -> Optional[Tuple[str, str, str]]:
    """
    Evaluates column null percentage (0.0 to 1.0) against data quality thresholds.
    """
    crit_th = DEFAULT_THRESHOLDS["null_rate_critical"]
    warn_th = (
        (rule.metadata.get("null_threshold") if rule and rule.metadata else None)
        or DEFAULT_THRESHOLDS["null_rate_warning"]
    )

    if null_rate >= crit_th:
        return (
            AlertCategory.DATA_QUALITY_DEGRADATION,
            AlertSeverity.CRITICAL,
            f"Null rate >= {crit_th * 100:.1f}%",
        )
    elif null_rate >= warn_th:
        return (
            AlertCategory.DATA_QUALITY_DEGRADATION,
            AlertSeverity.WARNING,
            f"Null rate >= {warn_th * 100:.1f}%",
        )
    return None


def evaluate_anomaly(
    zscore: float,
    rule: Optional[AlertRule] = None
) -> Optional[Tuple[str, str, str]]:
    """
    Evaluates standard deviation z-score against statistical anomaly thresholds.
    """
    th = (
        (rule.zscore_threshold if rule and rule.zscore_threshold is not None else None)
        or DEFAULT_THRESHOLDS["anomaly_zscore"]
    )

    abs_z = abs(zscore)
    if abs_z >= 3.5:
        return (
            AlertCategory.ANOMALY_DETECTED,
            AlertSeverity.CRITICAL,
            f"Z-Score >= 3.5 (Observed: {abs_z:.2f})",
        )
    elif abs_z >= th:
        return (
            AlertCategory.ANOMALY_DETECTED,
            AlertSeverity.WARNING,
            f"Z-Score >= {th:.1f} (Observed: {abs_z:.2f})",
        )
    return None
