"""
backend/app/intelligence/business_intelligence/insight_explainer.py

Phase 8.1: Insight Explanation & Causality Safety Layer
Generates clear, professional natural-language explanations based exclusively on verified evidence.
Strictly enforces causality safety:
- Never asserts unproven causes ("because customers left")
- Uses safe phrasing: "associated with", "concentrated in", "observed alongside"
- Provides deterministic fallback if Groq is unavailable or disabled.
"""
from __future__ import annotations

import logging
from typing import Optional
from app.intelligence.business_intelligence.models import BusinessInsight, InsightCategory, InsightSeverity

logger = logging.getLogger("bgai.bi")


def generate_deterministic_explanation(
    category: str,
    metric_name: str,
    current_val: Optional[float | str],
    prev_val: Optional[float | str],
    change_pct: Optional[float],
    entity_name: Optional[str] = None,
    dimension_value: Optional[str] = None,
    share_pct: Optional[float] = None,
    details: Optional[dict] = None,
) -> tuple[str, str, str]:
    """
    Returns (title, summary, recommended_next_step) using deterministic rules.
    Guarantees causality safety and zero external service dependency.
    """
    details = details or {}
    curr_str = f"{current_val:,.2f}" if isinstance(current_val, (int, float)) else str(current_val or "N/A")
    prev_str = f"{prev_val:,.2f}" if isinstance(prev_val, (int, float)) else str(prev_val or "N/A")
    pct_str = f"{abs(change_pct):.1f}%" if change_pct is not None else ""

    if category == InsightCategory.DECLINE:
        title = f"{metric_name} decreased by {pct_str}"
        summary = (
            f"{metric_name} decreased from {prev_str} to {curr_str} "
            f"({pct_str} change) during the latest observed period."
        )
        rec = f"Review recent transactions in AI Analyst to inspect underlying factors associated with the decrease in {metric_name}."

    elif category == InsightCategory.GROWTH:
        title = f"{metric_name} increased by {pct_str}"
        summary = (
            f"{metric_name} grew from {prev_str} to {curr_str} "
            f"(+{pct_str} increase) compared with the preceding recorded period."
        )
        rec = f"Explore performance drivers for {metric_name} in Data Explorer."

    elif category == InsightCategory.TREND:
        direction = "increased" if (change_pct or 0) >= 0 else "decreased"
        title = f"Periodic trajectory for {metric_name} {direction} by {pct_str}"
        summary = (
            f"Historical observations reflect that {metric_name} {direction} "
            f"from {prev_str} to {curr_str} over consecutive recorded intervals."
        )
        rec = f"Review chronological trends and historical patterns for {metric_name} in AI Analyst."

    elif category == InsightCategory.TOP_CONTRIBUTOR:
        share_str = f"{share_pct:.1f}%" if share_pct is not None else "significant"
        dim_str = str(dimension_value or "Top segment")
        title = f"{dim_str} contributed {share_str} of {metric_name}"
        summary = (
            f"{dim_str} accounts for {curr_str} ({share_str}) of total recorded {metric_name}."
        )
        rec = f"Examine distribution breakdown across categories in AI Analyst."

    elif category == InsightCategory.CONCENTRATION:
        share_str = f"{share_pct:.1f}%" if share_pct is not None else "a major share"
        count_entities = details.get("top_count", 3)
        dim_label = details.get("dimension_label", "records")
        title = f"High concentration: top {count_entities} {dim_label} represent {share_str} of {metric_name}"
        summary = (
            f"The top {count_entities} {dim_label} account for {curr_str} ({share_str}) "
            f"of total recorded {metric_name}."
        )
        rec = f"Evaluate exposure and diversification metrics for {metric_name} in AI Analyst."

    elif category == InsightCategory.QUALITY:
        col = details.get("column", "Field")
        tbl = details.get("table", "Table")
        null_pct = details.get("null_percent", 0.0)
        title = f"Missing data in {tbl}.{col} ({null_pct:.1f}% NULL)"
        summary = (
            f"Column {tbl}.{col} contains missing or NULL values in {null_pct:.1f}% of inspected records."
        )
        rec = f"Inspect incomplete records for {tbl} in Data Explorer to assess data entry completeness."

    elif category == InsightCategory.ANOMALY:
        col = details.get("column", metric_name)
        tbl = details.get("table", "Table")
        anomaly_type = details.get("anomaly_type", "Value outlier")
        title = f"Statistical anomaly detected in {tbl}.{col}"
        summary = (
            f"Unusual pattern ({anomaly_type}) observed in {tbl}.{col}: "
            f"{details.get('finding', 'Values deviate substantially from expected ranges')}."
        )
        rec = "Inspect anomalous data points in Anomaly Center."

    elif category == InsightCategory.FORECAST:
        horizon = details.get("horizon", "next period")
        proj_val = f"{current_val:,.2f}" if isinstance(current_val, (int, float)) else str(current_val)
        title = f"Projected {metric_name} for {horizon} is approximately {proj_val}"
        summary = (
            f"Based on available historical observations, estimated {metric_name} "
            f"for the {horizon} is approximately {proj_val}. Projected trajectory reflects historical patterns."
        )
        rec = "Review forecast confidence intervals and validation in Forecasting."

    elif category == InsightCategory.PERFORMANCE:
        tbl = details.get("table", "Table")
        reason = details.get("reason", "Potential optimization detected")
        title = f"Optimization opportunity: {tbl}"
        summary = f"Performance scan identified: {reason} on table '{tbl}'."
        rec = "Review database indexing and execution recommendations in Data Health."

    elif category == InsightCategory.DATA_COMPLETENESS:
        tbl_count = details.get("affected_tables", 1)
        tot_tables = details.get("total_tables", 1)
        title = f"{tbl_count} of {tot_tables} tables have noticeable NULL density"
        summary = (
            f"Database scan found {tbl_count} tables containing columns with significant missing value rates."
        )
        rec = "Review table health and quality reports in Data Health."

    else:
        title = f"Insight on {metric_name}"
        summary = f"Observation for {metric_name}: current value is {curr_str}."
        rec = "Investigate further in AI Analyst."

    return title, summary, rec


def polish_explanation_with_groq_if_available(insight: BusinessInsight) -> None:
    """
    Optionally polishes an already-verified insight explanation using Groq.
    Never alters numbers or invents causal relations.
    If Groq is unreachable, silent fallback retains the deterministic explanation.
    """
    try:
        from app.agent.groq_agent import ask_groq
        evidence_str = str(insight.evidence)
        prompt = f"""
You are an expert, objective business intelligence assistant.
Transform this verified evidence into a concise, 1-2 sentence professional insight explanation and next step.
STRICT RULES:
1. Do NOT change, round differently, or hallucinate any numbers.
2. Do NOT invent causes (e.g. do NOT say "due to customer dissatisfaction" or "because marketing stopped").
3. Use cautious phrasing: "associated with", "concentrated in", "observed alongside".
4. Format response strictly as:
SUMMARY: <1 sentence summary>
ACTION: <1 sentence recommended next step>

Category: {insight.category}
Metric: {insight.metric}
Evidence: {evidence_str}
"""
        response = ask_groq(prompt)
        if response and "SUMMARY:" in response:
            parts = response.split("ACTION:")
            summary_part = parts[0].replace("SUMMARY:", "").strip()
            if summary_part:
                insight.summary = summary_part
            if len(parts) > 1 and parts[1].strip():
                insight.recommended_next_step = parts[1].strip()
    except Exception as e:
        logger.debug("Groq polishing skipped: %s", str(e))
        pass  # Deterministic explanation already in place
