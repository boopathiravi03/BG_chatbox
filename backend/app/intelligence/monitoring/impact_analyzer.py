"""Phase 8.6 — Business impact analyser.

Takes raw signals from Phase 8.1–8.3 subsystems and derives deterministic
business_impact and possible_explanation strings. Never invents data.
"""
from __future__ import annotations

from typing import Any


# ── Anomaly → business impact ─────────────────────────────────────────────────

def anomaly_to_impact(anomaly: dict[str, Any]) -> str:
    """Convert an anomaly dict to a plain-language business-impact string."""
    table = anomaly.get("table", "unknown table")
    col = anomaly.get("column", "")
    value = anomaly.get("value")
    severity = anomaly.get("severity", "")

    parts = []
    if severity == "critical":
        parts.append("Critical data quality issue")
    else:
        parts.append("Potential data quality concern")

    if col:
        parts.append(f"in column '{col}' of table '{table}'")
    else:
        parts.append(f"in table '{table}'")

    if value is not None:
        parts.append(f"(detected value: {value})")

    return " ".join(parts) + ". Downstream reports or calculations may be affected."


def anomaly_to_explanation(anomaly: dict[str, Any]) -> str:
    reason = anomaly.get("reason", "")
    if reason:
        return f"Statistical analysis indicates: {reason}. No causal claim is made; this is an observed deviation."
    return "The value deviates from expected statistical bounds. Root cause requires manual investigation."


# ── Proactive alert → business impact ─────────────────────────────────────────

def alert_to_impact(alert: dict[str, Any]) -> str:
    category = alert.get("category", "")
    title = alert.get("title", "Unspecified alert")
    severity = alert.get("severity", "")

    prefix = {
        "critical": "High-priority alert",
        "warning": "Attention required",
        "info": "Informational notice",
    }.get(severity, "Alert")

    return f"{prefix}: {title}. Category: {category}. Business continuity or reporting accuracy may be affected."


def alert_to_explanation(alert: dict[str, Any]) -> str:
    recommendation = alert.get("recommendation", "")
    if recommendation:
        return f"System recommendation: {recommendation}. Verify with business context before taking action."
    return "Review alert details and supporting evidence. No causal conclusion is drawn automatically."


# ── BI insight → business impact ──────────────────────────────────────────────

def bi_insight_to_impact(insight: dict[str, Any]) -> str:
    title = insight.get("title", "")
    metric_type = insight.get("metric_type", "")
    if metric_type:
        return f"BI signal ({metric_type}): {title}. This pattern may affect business decisions or forecasts."
    return f"BI signal: {title}."


def bi_insight_to_explanation(insight: dict[str, Any]) -> str:
    description = insight.get("description", "")
    if description:
        return f"Observed pattern: {description}. Correlation does not imply causation."
    return "Statistical pattern detected in the connected database. Manual review recommended."
