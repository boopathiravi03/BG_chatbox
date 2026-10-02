"""
backend/app/intelligence/proactive/explainer.py

Phase 8.3: Proactive Intelligence Explanation & Recommendation Layer
Converts deterministic alert evidence into clear, objective, executive-level
business explanations and operational recommendations.

Strict Causality Safety:
- Never asserts unproven causes (e.g. "because customers were unhappy")
- Grounded strictly in verified alert evidence (delta, baseline, observed, thresholds)
- Zero dependency on external LLMs: deterministic explanation is always primary
- Optional Groq polishing layer with strict privacy: never sends raw rows, full tables,
  passwords, JWTs, or database credentials.
"""
from __future__ import annotations

import logging
from typing import Any, Optional, Tuple

from app.intelligence.proactive.models import (
    BusinessAlert,
    AlertCategory,
    AlertSeverity,
)

logger = logging.getLogger("bgai.proactive.explainer")


def generate_alert_explanation(alert: BusinessAlert) -> Tuple[str, str, Optional[dict[str, Any]]]:
    """
    Deterministically builds:
    (explanation, recommendation, action_suggestion)
    exclusively from the alert's verified evidence and metadata.
    """
    category = alert.category
    metric = alert.metric
    curr = alert.current_value
    prev = alert.previous_value
    pct = alert.delta_percent
    th = alert.threshold_applied or "configured threshold"
    tables = alert.source_tables
    main_table = tables[0] if tables else "database"
    evidence = alert.evidence or {}

    curr_str = f"{curr:,.2f}" if isinstance(curr, (int, float)) else str(curr if curr is not None else "N/A")
    prev_str = f"{prev:,.2f}" if isinstance(prev, (int, float)) else str(prev if prev is not None else "N/A")
    pct_str = f"{abs(pct):.1f}%" if pct is not None else ""

    friendly_name = metric.replace("_", " ").title()

    if category == AlertCategory.METRIC_DROP:
        explanation = (
            f"{friendly_name} decreased by {pct_str} from {prev_str} to {curr_str}, "
            f"crossing the configured {alert.severity.lower()} threshold ({th})."
        )
        recommendation = (
            f"Investigate the affected metric and review the underlying records in table '{main_table}' "
            f"for the affected period."
        )
        suggestion = {
            "agent": "analyst_agent",
            "task": f"Investigate {pct_str} decrease in {friendly_name} for table '{main_table}'",
        }

    elif category == AlertCategory.METRIC_SPIKE:
        explanation = (
            f"{friendly_name} increased by {pct_str} from {prev_str} to {curr_str}, "
            f"crossing the configured {alert.severity.lower()} threshold ({th})."
        )
        recommendation = (
            f"Review the underlying records in table '{main_table}' for the affected period "
            f"to identify the source of the increase."
        )
        suggestion = {
            "agent": "analyst_agent",
            "task": f"Review drivers for {pct_str} increase in {friendly_name} in '{main_table}'",
        }

    elif category == AlertCategory.DATA_QUALITY_DEGRADATION:
        orphan_count = evidence.get("orphan_count")
        null_rate = evidence.get("null_percentage") or evidence.get("null_rate")
        
        if orphan_count is not None and int(orphan_count) > 0:
            from_t = evidence.get("from_table", main_table)
            to_t = evidence.get("to_table", "parent table")
            explanation = (
                f"Found {int(orphan_count)} orphan reference(s) in child table '{from_t}' "
                f"referencing non-existent records in parent table '{to_t}' based on the verified foreign-key relationship."
            )
            recommendation = (
                f"Review the orphan references and verify whether the referenced parent records "
                f"in '{to_t}' should exist or be linked."
            )
            suggestion = {
                "agent": "action_agent",
                "task": f"Remediate orphan foreign keys in {from_t}",
            }
        else:
            col_name = alert.source_columns[0] if alert.source_columns else "column"
            null_pct_val = f"{float(null_rate):.1f}%" if null_rate is not None else f"{curr_str}%"
            explanation = (
                f"Column '{col_name}' in table '{main_table}' has a null rate of {null_pct_val}, "
                f"exceeding the configured threshold of {th}."
            )
            recommendation = (
                f"Review records containing NULL values in the affected column '{col_name}' "
                f"and validate the upstream data process."
            )
            suggestion = {
                "agent": "data_quality_agent",
                "task": f"Audit missing values in {main_table}.{col_name}",
            }

    elif category == AlertCategory.ANOMALY_DETECTED:
        zscore = evidence.get("zscore") or evidence.get("z_score")
        z_str = f"{float(zscore):.2f}" if zscore is not None else "significant deviation"
        explanation = (
            f"{friendly_name} produced an anomalous value with a z-score of {z_str}, "
            f"exceeding the configured anomaly threshold ({th})."
        )
        recommendation = (
            f"Investigate the affected period and compare the underlying records in '{main_table}' "
            f"with recent normal periods."
        )
        suggestion = {
            "agent": "anomaly_agent",
            "task": f"Inspect anomaly in {main_table} {friendly_name}",
        }

    elif category == AlertCategory.INVENTORY_RISK:
        explanation = (
            f"Inventory levels for {friendly_name} crossed the risk threshold ({th}) "
            f"with an observed value of {curr_str}."
        )
        recommendation = (
            f"Review stock levels and pending purchase orders for affected items in table '{main_table}'."
        )
        suggestion = {
            "agent": "action_agent",
            "task": f"Review reorder threshold for {main_table}",
        }

    elif category == AlertCategory.FORECAST_DEVIATION:
        explanation = (
            f"Observed value ({curr_str}) deviated significantly from the projected forecast range "
            f"for {friendly_name}."
        )
        recommendation = (
            f"Compare actual records against forecast baseline projections in the Forecasting view."
        )
        suggestion = {
            "agent": "analyst_agent",
            "task": f"Analyze forecast variance in {friendly_name}",
        }

    else:
        explanation = (
            f"Proactive alert triggered for {friendly_name} with current value of {curr_str}."
        )
        recommendation = f"Review table '{main_table}' in AI Analyst."
        suggestion = {
            "agent": "analyst_agent",
            "task": f"Analyze {friendly_name}",
        }

    return explanation, recommendation, suggestion


def apply_explanation_to_alert(alert: BusinessAlert) -> BusinessAlert:
    """Computes and assigns deterministic explanation, recommendation, and suggestion."""
    expl, rec, sugg = generate_alert_explanation(alert)
    alert.explanation = expl
    alert.recommendation = rec
    if sugg and not alert.action_suggestion:
        alert.action_suggestion = sugg
    return alert


def polish_alert_with_groq_if_available(alert: BusinessAlert) -> None:
    """
    Optionally polishes an existing alert explanation using Groq.
    STRICT PRIVACY & GROUNDING CONSTRAINTS:
    - Never sends raw database rows or full tables.
    - Never sends database connection strings, passwords, or tokens.
    - Never allows Groq to alter factual numbers, deltas, or thresholds.
    - Silent fallback retains the deterministic explanation if Groq is unavailable.
    """
    try:
        from app.agent.groq_agent import ask_groq

        # Send ONLY sanitized metric summary metadata (never raw rows)
        sanitized_summary = {
            "category": alert.category,
            "severity": alert.severity,
            "metric": alert.metric,
            "delta_percent": alert.delta_percent,
            "current_value": alert.current_value,
            "previous_value": alert.previous_value,
            "threshold_applied": alert.threshold_applied,
        }

        prompt = f"""
You are a senior data analyst assistant.
Rephrase the following verified proactive alert into a concise, professional 1-sentence explanation and 1-sentence recommendation.
STRICT SAFETY RULES:
1. Do NOT alter, fabricate, or re-calculate any numbers or percentages.
2. Do NOT invent root causes (e.g. do NOT say "because customers left" or "due to competitor actions").
3. Only describe what is explicitly verified in the metric summary.
4. Output format MUST be strictly:
EXPLANATION: <1 sentence>
RECOMMENDATION: <1 sentence>

Alert Summary:
{sanitized_summary}
"""
        response = ask_groq(prompt)
        if response and "EXPLANATION:" in response:
            parts = response.split("RECOMMENDATION:")
            expl_part = parts[0].replace("EXPLANATION:", "").strip()
            if expl_part:
                alert.explanation = expl_part
            if len(parts) > 1 and parts[1].strip():
                alert.recommendation = parts[1].strip()
    except Exception as e:
        logger.debug(f"Groq alert polishing skipped: {e}")
        pass

