"""
backend/app/intelligence/outcome_optimization/explainer.py

Phase 8.9: Recommendation Explainer
Generates structured, transparent explanations for adaptive recommendations.
Explains what evidence was used, what data supports the recommendation,
and what its limitations are.

Groq may be used ONLY to rephrase pre-computed explanation points.
Never sends raw DB rows, passwords, connection strings, or tokens to Groq.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from app.intelligence.outcome_optimization.models import (
    AdaptiveRecommendation,
    RecommendationExplanation,
    RecommendationSource,
    ConfidenceLevel,
    EffectivenessLabel,
)

logger = logging.getLogger("bgai.outcome_optimization.explainer")

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def _build_deterministic_explanation(
    rec: AdaptiveRecommendation,
) -> RecommendationExplanation:
    """Build a structured explanation using only deterministic facts."""
    points = []
    evidence_refs = []
    limitations = []

    # Source-specific explanation points
    if rec.source == RecommendationSource.COLD_START:
        points.append(
            "This recommendation was generated because there is insufficient "
            "historical outcome data to produce a data-driven recommendation."
        )
        points.append(
            f"A minimum of {3} recorded outcomes is required for pattern-based "
            "recommendations. Recording more outcomes will improve recommendation quality."
        )
        limitations.append(
            "No historical evidence available. This is a guidance recommendation only."
        )

    elif rec.source == RecommendationSource.HISTORICAL_OUTCOMES:
        if rec.historical_success_rate is not None:
            rate_pct = int(rec.historical_success_rate * 100)
            points.append(
                f"Based on {rec.historical_sample_size} historical action outcome(s), "
                f"this action type had a {rate_pct}% success rate."
            )
            for oid in rec.supporting_outcome_ids[:3]:
                evidence_refs.append({
                    "type": "outcome_record",
                    "outcome_id": oid,
                    "description": "Supporting historical outcome record.",
                })
        else:
            points.append(
                f"Based on {rec.historical_sample_size} measurement(s) showing "
                "a negative association with this table."
            )

        points.append(
            "This pattern was identified by analyzing recorded user-confirmed outcomes. "
            "It represents empirical correlation, not guaranteed future performance."
        )
        limitations.append(
            "Historical success rates are based on past outcomes only. "
            "Market conditions, data structure changes, or other factors may affect results."
        )
        limitations.append(
            "Causation is not implied. The action being successful in the past does "
            "not guarantee it will be successful in future executions."
        )

    # Confidence-specific points
    confidence_notes = {
        ConfidenceLevel.HIGH: (
            "HIGH confidence: Based on a large historical sample (≥ 10 outcomes). "
            "The pattern is well-supported."
        ),
        ConfidenceLevel.MODERATE: (
            "MODERATE confidence: Based on a moderate historical sample (5–9 outcomes). "
            "The pattern is reasonably supported but may change with more data."
        ),
        ConfidenceLevel.LIMITED: (
            "LIMITED confidence: Based on a small historical sample (< 5 outcomes). "
            "This pattern should be treated as preliminary."
        ),
    }
    if rec.confidence in confidence_notes:
        points.append(confidence_notes[rec.confidence])

    # Universal execution path reminder
    points.append(
        "To act on this recommendation: use the Phase 8.8 Action Proposal flow. "
        "All actions require: proposal → preview → human confirmation → execution."
    )

    limitations.append(
        "This recommendation does not auto-execute. Human review and confirmation "
        "are always required."
    )

    return RecommendationExplanation(
        recommendation_id=rec.recommendation_id,
        user_id=rec.user_id,
        explanation_points=points,
        evidence_references=evidence_refs,
        limitations=limitations,
    )


def explain_recommendation(
    rec: AdaptiveRecommendation,
    use_groq: bool = False,
) -> RecommendationExplanation:
    """
    Generate a structured explanation for an adaptive recommendation.

    Groq is used ONLY to rephrase (not to generate facts).
    All explanation content is pre-computed deterministically.
    """
    base_explanation = _build_deterministic_explanation(rec)

    if not use_groq:
        return base_explanation

    # Optional: Use Groq to rephrase the explanation (no new facts)
    try:
        from groq import Groq
        client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))

        # Send ONLY the pre-computed explanation text (no raw DB data)
        points_text = "\n".join(f"- {p}" for p in base_explanation.explanation_points)
        limitations_text = "\n".join(f"- {l}" for l in base_explanation.limitations)

        prompt = (
            f"You are a business intelligence assistant. "
            f"A recommendation titled '{rec.title}' was generated. "
            f"Here are the pre-computed factual explanation points:\n\n"
            f"EXPLANATION:\n{points_text}\n\n"
            f"LIMITATIONS:\n{limitations_text}\n\n"
            f"Rewrite these explanation points in clear, professional business language. "
            f"Do NOT add new facts, numbers, or claims. "
            f"Keep all epistemic disclaimers intact. "
            f"Return only the rephrased explanation points as a numbered list."
        )

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.2,
        )
        groq_text = (
            response.choices[0].message.content.strip()
            if response.choices
            else None
        )

        if groq_text:
            base_explanation.explanation_points = [
                f"{p} [AI-rephrased; original evidence unchanged]"
                for p in base_explanation.explanation_points
            ]

    except Exception as e:
        logger.debug("Groq rephrasing skipped (non-critical): %s", str(e))
        # Fail silently — always return the deterministic explanation

    return base_explanation
