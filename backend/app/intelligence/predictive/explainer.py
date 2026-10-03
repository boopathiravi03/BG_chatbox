"""
backend/app/intelligence/predictive/explainer.py

Phase 9.0: Predictive Explanation & Evidence Lineage
Synthesizes transparent, evidence-grounded explanations detailing data lineage,
statistical method selection, backtesting metrics, and uncertainty constraints.

Groq Privacy & Safety:
- Deterministic calculation runs locally.
- Groq may be used optionally ONLY for linguistic rephrasing of pre-computed facts.
- Never sends database credentials, raw rows, or PII to external APIs.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from app.intelligence.predictive.models import (
    PredictionExplanation,
    PredictionResult,
)

logger = logging.getLogger("bgai.predictive.explainer")

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def generate_structured_explanation(pred: PredictionResult) -> PredictionExplanation:
    """
    Builds a deterministic, comprehensive explanation covering all aspects of the prediction.
    """
    hist_points = [p for p in pred.points if not p.is_forecast]
    forecast_points = [p for p in pred.points if p.is_forecast]

    # 1. Historical Summary
    if hist_points:
        vals = [p.value for p in hist_points]
        avg_val = round(sum(vals) / len(vals), 2)
        min_p = hist_points[0].period
        max_p = hist_points[-1].period
        hist_summary = (
            f"Analyzed {len(hist_points)} historical periods from {min_p} to {max_p}. "
            f"Historical values averaged {avg_val} (min: {min(vals)}, max: {max(vals)})."
        )
    else:
        hist_summary = "No historical observations available."

    # 2. Method Rationale & Backtesting
    selected_eval = next((m for m in pred.model_evaluations if m.selected), None)
    if selected_eval and selected_eval.rmse is not None:
        method_rationale = (
            f"Selected {pred.selected_method.replace('_', ' ').title()} based on empirical backtest performance. "
            f"Achieved holdout Root Mean Squared Error (RMSE) of {selected_eval.rmse} "
            f"and Mean Absolute Error (MAE) of {selected_eval.mae}."
        )
        if selected_eval.mape is not None:
            method_rationale += f" Mean Absolute Percentage Error (MAPE) was {selected_eval.mape}%."
    else:
        method_rationale = (
            f"Fitted {pred.selected_method.replace('_', ' ').title()}. "
            "Full series was utilized for model parameter stability due to limited historical sample."
        )

    # 3. Trend & Seasonality
    trend_seasonality = (
        f"Trend trajectory: {pred.trend_direction}. {pred.seasonality_summary}"
    )

    # 4. Uncertainty
    uncertainty_exp = (
        f"Confidence tier: {pred.confidence_tier}. {pred.confidence_rationale} "
        "Prediction intervals widen as the forecast horizon extends (scaled with sqrt(h))."
    )

    # 5. Phase 8.9 historical action outcomes
    outcome_signals = []
    if pred.evidence and pred.evidence.historical_outcome_support:
        for ref in pred.evidence.historical_outcome_support:
            outcome_signals.append(ref.get("note", "Historical action outcome recorded."))

    # 6. Limitations
    limitations = list(pred.limitations)
    if "Statistical projection assumes continuation of underlying generative process." not in limitations:
        limitations.append("Statistical projection assumes continuation of underlying generative process.")
    if "External macroeconomic shifts, policy adjustments, and competitive responses are not modeled." not in limitations:
        limitations.append("External macroeconomic shifts, policy adjustments, and competitive responses are not modeled.")

    return PredictionExplanation(
        prediction_id=pred.prediction_id,
        metric_name=pred.metric_name,
        historical_summary=hist_summary,
        method_rationale=method_rationale,
        backtest_evaluation=selected_eval.reason if selected_eval else "Holdout backtest not performed.",
        trend_and_seasonality=trend_seasonality,
        uncertainty_explanation=uncertainty_exp,
        limitations=limitations,
        phase89_historical_signals=outcome_signals,
    )


def explain_prediction_narrative(
    pred: PredictionResult, use_groq: bool = False
) -> PredictionExplanation:
    """
    Generates explanation. If use_groq is requested, rephrases pre-computed summary
    without introducing new claims or accessing raw database records.
    """
    explanation = generate_structured_explanation(pred)

    if not use_groq:
        return explanation

    try:
        from groq import Groq
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            return explanation

        client = Groq(api_key=api_key)

        prompt = (
            f"You are a business intelligence assistant explaining a predictive forecast.\n"
            f"Metric: {pred.metric_name}\n"
            f"Method: {pred.selected_method}\n"
            f"Confidence: {pred.confidence_tier}\n"
            f"Summary: {explanation.historical_summary}\n"
            f"Method Rationale: {explanation.method_rationale}\n"
            f"Trend: {explanation.trend_and_seasonality}\n"
            f"Uncertainty: {explanation.uncertainty_explanation}\n\n"
            f"Formulate a concise 2-sentence executive summary explaining how this forecast was derived. "
            f"Do NOT invent numbers or claim future certainty. Keep caveats intact."
        )

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.2,
        )
        if response.choices and response.choices[0].message.content:
            pred.ai_summary = response.choices[0].message.content.strip()

    except Exception as e:
        logger.debug("Groq explanation rephrasing skipped (non-critical): %s", str(e))

    return explanation
