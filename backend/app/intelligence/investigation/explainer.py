"""
backend/app/intelligence/investigation/explainer.py

Phase 8.7: Root-Cause Investigation Explainer
Generates clean, professional human-readable briefings with deterministic truth guarantees.

Privacy & Safety:
- Deterministic calculation first; Groq only polishes wording.
- Never sends raw rows, credentials, connection strings, JWTs, or PII to Groq.
- Fallback to deterministic narrative if Groq is unavailable.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.intelligence.investigation.models import (
    ObservedChange,
    EvidenceItem,
    ContributingFactor,
    Hypothesis,
    ConfidenceAssessment,
    InvestigationRecommendation,
)

logger = logging.getLogger("bgai.investigation.explainer")


def build_deterministic_explanation(
    observed_change: Optional[ObservedChange],
    evidence_items: list[EvidenceItem],
    contributing_factors: list[ContributingFactor],
    hypotheses: list[Hypothesis],
    confidence: Optional[ConfidenceAssessment],
    recommendations: list[InvestigationRecommendation],
    status: str,
) -> tuple[str, str]:
    """
    Builds a structured deterministic summary and full explanation narrative.
    Returns:
        (summary, full_explanation)
    """
    if status == "insufficient_evidence" or not observed_change:
        summary = "Insufficient database evidence to identify root-cause contributors."
        full = (
            "### Investigation Summary\n"
            "BG AI evaluated the connected database, but detected insufficient chronological or dimensional "
            "records to establish a root-cause explanation.\n\n"
            "**Missing Evidence:**\n"
            "- Multi-period time series or categorical dimensions were not present.\n"
            "- Recommended Action: Connect a dataset containing transaction timestamps and categorical dimensions."
        )
        return summary, full

    # Build concise headline summary
    direction = "declined" if (observed_change.delta or 0) < 0 else "increased" if (observed_change.delta or 0) > 0 else "changed"
    pct_str = f"{abs(observed_change.delta_percent or 0):.1f}%"
    summary = f"{observed_change.metric} {direction} by {pct_str} across comparison periods."

    # Build comprehensive explanation markdown
    lines = [
        f"### Root-Cause Investigation: {observed_change.metric}",
        f"\n**Observed Change:**\n- {observed_change.formatted_change or summary}",
    ]

    if evidence_items:
        lines.append("\n**Observed Evidence:**")
        for e in evidence_items[:4]:
            delta_str = f" ({e.delta_percent:+.1f}%)" if e.delta_percent is not None else ""
            lines.append(f"- {e.metric}: {e.current_value} vs previous {e.previous_value}{delta_str} [Source: {e.source_table}]")

    if contributing_factors:
        lines.append("\n**Contributing Factors:**")
        for i, cf in enumerate(contributing_factors[:3], 1):
            lines.append(f"{i}. {cf.observed_change}")

    if hypotheses:
        lines.append("\n**Hypotheses (Unconfirmed):**")
        for h in hypotheses:
            lines.append(f"- *{h.statement}*")
            lines.append(f"  > [!NOTE] {h.causality_caveat}")

    if confidence:
        lines.append(f"\n**Confidence Assessment:** **{confidence.level.value}**")
        lines.append(f"- {confidence.score_rationale}")

    if recommendations:
        lines.append("\n**Recommended Investigations:**")
        for r in recommendations:
            lines.append(f"- **{r.action_title}**: {r.reason} (Target: `{r.target_data}`)")

    full_narrative = "\n".join(lines)
    return summary, full_narrative


def polish_explanation_with_groq(
    summary: str,
    full_narrative: str,
    observed_metric: str,
    confidence_level: str,
) -> tuple[str, str]:
    """
    Optionally polishes narrative using Groq with strictly sanitized parameters.
    Falls back gracefully if Groq fails or is unconfigured.
    """
    try:
        from app.agent.groq_agent import ask_groq

        sanitized_prompt = (
            "You are a senior business intelligence investigator. "
            "Review the following deterministic root-cause investigation briefing and polish the executive summary "
            "for maximum clarity and executive readability. "
            "CRITICAL RULES:\n"
            "1. DO NOT change any numbers, percentages, metric names, or confidence levels.\n"
            "2. DO NOT claim proven causation; preserve unconfirmed hypothesis wording.\n"
            "3. Output ONLY the polished 1-2 sentence executive summary.\n\n"
            f"Metric: {observed_metric}\n"
            f"Confidence: {confidence_level}\n"
            f"Draft Summary: {summary}\n"
        )

        polished_summary = ask_groq(sanitized_prompt)
        if polished_summary and len(polished_summary.strip()) >= 15:
            clean_sum = polished_summary.strip().strip('"').strip("'")
            return clean_sum, full_narrative
    except Exception as e:
        logger.debug(f"Groq narrative polishing fallback to deterministic: {e}")

    return summary, full_narrative

