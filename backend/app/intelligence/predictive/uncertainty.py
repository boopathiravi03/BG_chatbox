"""
backend/app/intelligence/predictive/uncertainty.py

Phase 9.0: Uncertainty Quantification & Confidence Tiers
Calculates statistical prediction intervals based on historical residual variance
and assigns defensible confidence tiers (HIGH, MODERATE, LIMITED).

Epistemic Rules:
- No arbitrary precision; intervals expand with forecast horizon step (sqrt(h)).
- Confidence tiers are grounded in observation count, backtest error, and volatility.
- Disclaims future certainty explicitly.
"""
from __future__ import annotations

import math
from typing import Optional

from app.intelligence.predictive.models import (
    ConfidenceTier,
    ForecastPoint,
    ModelEvaluationMetric,
    TrendDirection,
)


def compute_prediction_intervals(
    actuals: list[float],
    fitted: list[float],
    forecast_values: list[float],
    future_labels: list[str],
    is_non_negative: bool = True,
) -> list[ForecastPoint]:
    """
    Computes expanding prediction intervals: +/- (1.96 * SE * sqrt(h)).
    Returns list of ForecastPoint objects for the forecast horizon.
    """
    n = len(actuals)
    horizon = len(forecast_values)

    if n < 2 or len(fitted) != n:
        # Default fallback uncertainty if residual variance cannot be calculated
        points = []
        for h, (lbl, val) in enumerate(zip(future_labels, forecast_values), start=1):
            width = abs(val) * 0.15 * math.sqrt(h)  # Baseline +/-15% widening interval
            low = max(0.0, val - width) if is_non_negative else val - width
            high = val + width
            points.append(
                ForecastPoint(
                    period=lbl,
                    value=val,
                    is_forecast=True,
                    lower_bound=low,
                    upper_bound=high,
                    uncertainty_width=width * 2,
                )
            )
        return points

    # Calculate residual standard error
    residuals = [a - f for a, f in zip(actuals, fitted)]
    dof = max(1, n - 2)
    residual_variance = sum(r * r for r in residuals) / dof
    residual_std = math.sqrt(residual_variance)

    points = []
    for h, (lbl, val) in enumerate(zip(future_labels, forecast_values), start=1):
        if residual_std > 0:
            width = 1.96 * residual_std * math.sqrt(h)
            low = max(0.0, val - width) if is_non_negative else val - width
            high = val + width
        else:
            width = 0.0
            low = val
            high = val

        points.append(
            ForecastPoint(
                period=lbl,
                value=val,
                is_forecast=True,
                lower_bound=low,
                upper_bound=high,
                uncertainty_width=width * 2,
            )
        )

    return points


def determine_confidence_tier(
    observation_count: int,
    trend: TrendDirection,
    selected_eval: Optional[ModelEvaluationMetric] = None,
    mean_value: float = 1.0,
) -> tuple[ConfidenceTier, str]:
    """
    Evaluates evidence to assign HIGH, MODERATE, or LIMITED confidence.
    Returns: (ConfidenceTier, rationale_text)
    """
    # 1. Check data points threshold
    if observation_count < 6:
        return (
            ConfidenceTier.LIMITED,
            f"Limited confidence: Series contains only {observation_count} observations. "
            "Statistical sample size is insufficient for high confidence.",
        )

    if trend == TrendDirection.VOLATILE:
        return (
            ConfidenceTier.LIMITED,
            "Limited confidence: Series demonstrates historical volatility, widening future variance.",
        )

    # 2. Check holdout performance if available
    if selected_eval and selected_eval.rmse is not None and abs(mean_value) > 1e-6:
        rel_error = selected_eval.rmse / abs(mean_value)
        if observation_count >= 12 and rel_error <= 0.15:
            return (
                ConfidenceTier.HIGH,
                f"High confidence: Series contains {observation_count} observations with low holdout error "
                f"(RMSE/Mean ratio: {round(rel_error * 100, 1)}%).",
            )
        elif rel_error <= 0.35:
            return (
                ConfidenceTier.MODERATE,
                f"Moderate confidence: Backtest demonstrated acceptable accuracy "
                f"(RMSE/Mean ratio: {round(rel_error * 100, 1)}%) over {observation_count} observations.",
            )

    if observation_count >= 10:
        return (
            ConfidenceTier.MODERATE,
            f"Moderate confidence: Based on {observation_count} consistent observations and stable trajectory.",
        )

    return (
        ConfidenceTier.LIMITED,
        f"Limited confidence: Small historical sample ({observation_count} periods) limits forecast precision.",
    )
