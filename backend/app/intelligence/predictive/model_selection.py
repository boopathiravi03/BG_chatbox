"""
backend/app/intelligence/predictive/model_selection.py

Phase 9.0: Evidence-Based Model Selection & Backtesting
Compares candidate forecasting strategies using empirical holdout backtesting.
Selects the model with minimum measured error (RMSE/MAE).

Epistemic Guard:
- When history is small (< 6 observations), transparently notes that model comparison
  was skipped, rather than inventing false model accuracy scores.
- Never divides by zero when calculating MAPE.
"""
from __future__ import annotations

import math
from typing import Callable, Optional

from app.intelligence.predictive.models import ForecastingMethod, ModelEvaluationMetric
from app.intelligence.predictive.forecasting import (
    naive_forecast,
    simple_moving_average_forecast,
    weighted_moving_average_forecast,
    linear_trend_forecast,
    exponential_smoothing_forecast,
    seasonal_forecast,
)

MIN_POINTS_FOR_HOLDOUT = 6


def calculate_mae(actuals: list[float], predictions: list[float]) -> Optional[float]:
    """Computes Mean Absolute Error (MAE)."""
    if not actuals or not predictions or len(actuals) != len(predictions):
        return None
    return round(sum(abs(a - p) for a, p in zip(actuals, predictions)) / len(actuals), 2)


def calculate_rmse(actuals: list[float], predictions: list[float]) -> Optional[float]:
    """Computes Root Mean Squared Error (RMSE)."""
    if not actuals or not predictions or len(actuals) != len(predictions):
        return None
    mse = sum((a - p) ** 2 for a, p in zip(actuals, predictions)) / len(actuals)
    return round(math.sqrt(mse), 2)


def calculate_mape(actuals: list[float], predictions: list[float]) -> tuple[Optional[float], Optional[str]]:
    """
    Computes Mean Absolute Percentage Error (MAPE).
    Guards strictly against division-by-zero.
    """
    if not actuals or not predictions or len(actuals) != len(predictions):
        return None, "Insufficient data for percentage error."

    if any(abs(a) < 1e-9 for a in actuals):
        return None, "MAPE omitted: actual series contains zero values (division by zero)."

    pct_errors = [abs((a - p) / a) * 100 for a, p in zip(actuals, predictions)]
    return round(sum(pct_errors) / len(pct_errors), 2), None


def evaluate_and_select_model(
    series: list[float], frequency: str = "monthly"
) -> tuple[str, list[ModelEvaluationMetric]]:
    """
    Evaluates candidate models against historical holdout data if sample size permits.
    Returns: (selected_method_name, list_of_evaluations)
    """
    n = len(series)

    # Candidate models definition
    candidates: list[tuple[str, Callable[[list[float], int], tuple[list[float], list[float]]]]] = [
        (ForecastingMethod.EXPONENTIAL_SMOOTHING.value, exponential_smoothing_forecast),
        (ForecastingMethod.LINEAR_TREND.value, linear_trend_forecast),
        (ForecastingMethod.WMA.value, lambda s, h: weighted_moving_average_forecast(s, h, window=3)),
        (ForecastingMethod.SMA.value, lambda s, h: simple_moving_average_forecast(s, h, window=3)),
        (ForecastingMethod.NAIVE.value, naive_forecast),
    ]

    cycle = 7 if frequency == "daily" else 12
    if n >= 2 * cycle:
        candidates.insert(
            0,
            (ForecastingMethod.SEASONAL.value, lambda s, h: seasonal_forecast(s, h, cycle_length=cycle)),
        )

    # If dataset is too small for split validation, fall back to Exponential Smoothing with caveat
    if n < MIN_POINTS_FOR_HOLDOUT:
        evals = [
            ModelEvaluationMetric(
                method=ForecastingMethod.EXPONENTIAL_SMOOTHING.value,
                mae=None,
                rmse=None,
                mape=None,
                mape_note="Holdout validation skipped: series contains fewer than 6 observations.",
                selected=True,
                reason="Defaulted to Exponential Smoothing because limited history prevented reliable backtesting.",
            )
        ]
        return ForecastingMethod.EXPONENTIAL_SMOOTHING.value, evals

    # Conduct holdout backtest (holdout size: 1 if n < 8 else 2)
    holdout_size = 1 if n < 8 else 2
    train = series[:-holdout_size]
    test = series[-holdout_size:]

    evals: list[ModelEvaluationMetric] = []
    best_method = ForecastingMethod.EXPONENTIAL_SMOOTHING.value
    best_error = float("inf")

    for method_name, forecast_fn in candidates:
        try:
            _, preds = forecast_fn(train, holdout_size)
            mae = calculate_mae(test, preds)
            rmse = calculate_rmse(test, preds)
            mape, mape_note = calculate_mape(test, preds)

            evals.append(
                ModelEvaluationMetric(
                    method=method_name,
                    mae=mae,
                    rmse=rmse,
                    mape=mape,
                    mape_note=mape_note,
                    selected=False,
                    reason="",
                )
            )

            # Rank by RMSE then MAE
            err = rmse if rmse is not None else (mae if mae is not None else float("inf"))
            if err < best_error:
                best_error = err
                best_method = method_name
        except Exception:
            continue

    # Mark the selected candidate
    for ev in evals:
        if ev.method == best_method:
            ev.selected = True
            ev.reason = f"Selected based on lowest holdout error (RMSE: {ev.rmse}, MAE: {ev.mae})."

    return best_method, evals
