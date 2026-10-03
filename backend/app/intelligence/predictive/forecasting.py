"""
backend/app/intelligence/predictive/forecasting.py

Phase 9.0: Deterministic Time-Series Forecasting Algorithms
Implements six statistical forecasting strategies with zero arbitrary weights:
1. Naive Baseline (Persistence)
2. Simple Moving Average (SMA)
3. Weighted Moving Average (WMA)
4. Linear Trend (Ordinary Least Squares)
5. Holt's Linear Exponential Smoothing (SES + Trend Damping)
6. Seasonal Decomposition (when >= 2 full cycles exist)

Also provides deterministic trend direction detection and seasonality analysis.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timedelta
from typing import Optional

from app.intelligence.predictive.models import ForecastingMethod, TrendDirection


def generate_future_period_labels(last_label: str, frequency: str, count: int) -> list[str]:
    """Generates future chronological period labels (e.g. 2024-04, 2024-05 or 2024-01-15)."""
    labels = []

    # Format 1: Monthly "YYYY-MM"
    if re.match(r"^\d{4}-\d{2}$", last_label):
        year, month = map(int, last_label.split("-"))
        for _ in range(count):
            month += 1
            if month > 12:
                month = 1
                year += 1
            labels.append(f"{year:04d}-{month:02d}")
        return labels

    # Format 2: Daily "YYYY-MM-DD"
    if re.match(r"^\d{4}-\d{2}-\d{2}$", last_label):
        try:
            curr_date = datetime.strptime(last_label, "%Y-%m-%d")
            step_days = 7 if frequency == "weekly" else 1
            for _ in range(count):
                curr_date += timedelta(days=step_days)
                labels.append(curr_date.strftime("%Y-%m-%d"))
            return labels
        except Exception:
            pass

    # Fallback sequential periods
    for i in range(1, count + 1):
        labels.append(f"Period +{i}")
    return labels


# ── Forecasting Algorithms ───────────────────────────────────────────────────

def naive_forecast(series: list[float], horizon: int) -> tuple[list[float], list[float]]:
    """
    Naive baseline: projects the last observed value forward.
    Returns: (fitted_in_sample, forecast_out_of_sample)
    """
    n = len(series)
    if n == 0:
        return [], [0.0] * horizon

    fitted = [series[0]] + [series[i - 1] for i in range(1, n)]
    last_val = series[-1]
    forecast = [round(last_val, 2)] * horizon
    return fitted, forecast


def simple_moving_average_forecast(
    series: list[float], horizon: int, window: int = 3
) -> tuple[list[float], list[float]]:
    """
    Simple Moving Average (SMA).
    Returns: (fitted_in_sample, forecast_out_of_sample)
    """
    n = len(series)
    if n == 0:
        return [], [0.0] * horizon

    w = max(1, min(window, n))
    fitted = []
    for i in range(n):
        start_idx = max(0, i - w + 1)
        sub = series[start_idx : i + 1]
        fitted.append(sum(sub) / len(sub))

    last_sub = series[-w:]
    avg = sum(last_sub) / len(last_sub)
    forecast = [round(avg, 2)] * horizon
    return fitted, forecast


def weighted_moving_average_forecast(
    series: list[float], horizon: int, window: int = 3
) -> tuple[list[float], list[float]]:
    """
    Linearly Weighted Moving Average (WMA) giving higher weight to recent points.
    Returns: (fitted_in_sample, forecast_out_of_sample)
    """
    n = len(series)
    if n == 0:
        return [], [0.0] * horizon

    w = max(1, min(window, n))
    weights = list(range(1, w + 1))
    weight_sum = sum(weights)

    fitted = []
    for i in range(n):
        if i + 1 < w:
            sub = series[: i + 1]
            fitted.append(sum(sub) / len(sub))
        else:
            sub = series[i - w + 1 : i + 1]
            val = sum(s * wt for s, wt in zip(sub, weights)) / weight_sum
            fitted.append(val)

    last_sub = series[-w:]
    wma_val = sum(s * wt for s, wt in zip(last_sub, weights)) / weight_sum
    forecast = [round(wma_val, 2)] * horizon
    return fitted, forecast


def linear_trend_forecast(series: list[float], horizon: int) -> tuple[list[float], list[float]]:
    """
    Ordinary Least Squares (OLS) Linear Regression: y = slope * x + intercept.
    Returns: (fitted_in_sample, forecast_out_of_sample)
    """
    n = len(series)
    if n == 0:
        return [], [0.0] * horizon
    if n == 1:
        return [series[0]], [series[0]] * horizon

    x_vals = list(range(n))
    x_mean = sum(x_vals) / n
    y_mean = sum(series) / n

    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, series))
    denominator = sum((x - x_mean) ** 2 for x in x_vals)

    slope = numerator / denominator if denominator != 0 else 0.0
    intercept = y_mean - slope * x_mean

    fitted = [slope * x + intercept for x in x_vals]
    forecast = [round(slope * (n + h) + intercept, 2) for h in range(horizon)]
    return fitted, forecast


def exponential_smoothing_forecast(
    series: list[float],
    horizon: int,
    alpha: float = 0.4,
    beta: float = 0.2,
) -> tuple[list[float], list[float]]:
    """
    Holt's Linear Exponential Smoothing with trend damping.
    Returns: (fitted_in_sample, forecast_out_of_sample)
    """
    n = len(series)
    if n == 0:
        return [], [0.0] * horizon
    if n == 1:
        return [series[0]], [series[0]] * horizon

    level = series[0]
    trend = series[1] - series[0] if n > 1 else 0.0

    fitted = [level]
    for t in range(1, n):
        y = series[t]
        prev_level = level
        level = alpha * y + (1 - alpha) * (prev_level + trend)
        trend = beta * (level - prev_level) + (1 - beta) * (trend * 0.9)
        fitted.append(level + trend)

    forecast = []
    curr_level = level
    damped_trend = trend
    for _ in range(horizon):
        curr_level = curr_level + damped_trend
        damped_trend *= 0.9  # Damping prevents explosive projections
        forecast.append(round(curr_level, 2))

    return fitted, forecast


def seasonal_forecast(
    series: list[float], horizon: int, cycle_length: int = 7
) -> tuple[list[float], list[float]]:
    """
    Classical additive seasonal decomposition when series has at least 2 full cycles.
    Returns: (fitted_in_sample, forecast_out_of_sample)
    """
    n = len(series)
    if n < 2 * cycle_length:
        # Fallback to Holt's if insufficient cycles
        return exponential_smoothing_forecast(series, horizon)

    # 1. Trend component via centered moving average
    trend = []
    half = cycle_length // 2
    for i in range(n):
        start = max(0, i - half)
        end = min(n, i + half + 1)
        trend.append(sum(series[start:end]) / (end - start))

    # 2. Detrend and compute seasonal indices
    detrended = [s - t for s, t in zip(series, trend)]
    seasonal_indices = [0.0] * cycle_length
    counts = [0] * cycle_length

    for i, d in enumerate(detrended):
        idx = i % cycle_length
        seasonal_indices[idx] += d
        counts[idx] += 1

    for idx in range(cycle_length):
        if counts[idx] > 0:
            seasonal_indices[idx] /= counts[idx]

    # Normalize seasonal indices to sum to zero
    mean_idx = sum(seasonal_indices) / cycle_length
    seasonal_indices = [s - mean_idx for s in seasonal_indices]

    # 3. Fit in-sample
    fitted = [round(t + seasonal_indices[i % cycle_length], 2) for i, t in enumerate(trend)]

    # 4. Extrapolate trend linearly and add seasonal pattern
    slope = (trend[-1] - trend[0]) / max(1, n - 1)
    forecast = []
    for h in range(horizon):
        proj_trend = trend[-1] + slope * (h + 1)
        seas_component = seasonal_indices[(n + h) % cycle_length]
        forecast.append(round(proj_trend + seas_component, 2))

    return fitted, forecast


# ── Trend & Seasonality Detection ────────────────────────────────────────────

def detect_trend(series: list[float]) -> tuple[TrendDirection, float, str]:
    """
    Determines overall trend direction and relative slope.
    Returns: (TrendDirection, slope_pct_per_period, explanation)
    """
    n = len(series)
    if n < 2:
        return TrendDirection.STABLE, 0.0, "Insufficient historical points to establish trend."

    x_vals = list(range(n))
    x_mean = sum(x_vals) / n
    y_mean = sum(series) / n

    denom = sum((x - x_mean) ** 2 for x in x_vals)
    if denom == 0:
        return TrendDirection.STABLE, 0.0, "Zero variance in time sequence."

    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, series)) / denom
    mean_abs_y = abs(y_mean) if abs(y_mean) > 1e-6 else 1.0
    relative_slope_pct = (slope / mean_abs_y) * 100

    # Calculate coefficient of variation to detect volatility
    variance = sum((y - y_mean) ** 2 for y in series) / n
    std_dev = math.sqrt(variance)
    cv = std_dev / mean_abs_y

    if cv > 0.5 and abs(relative_slope_pct) < 15.0:
        return (
            TrendDirection.VOLATILE,
            round(relative_slope_pct, 2),
            f"Series demonstrates high volatility (variation coefficient {round(cv, 2)}).",
        )

    if relative_slope_pct > 2.0:
        return (
            TrendDirection.INCREASING,
            round(relative_slope_pct, 2),
            f"Observed upward trajectory averaging +{round(relative_slope_pct, 1)}% per period.",
        )
    elif relative_slope_pct < -2.0:
        return (
            TrendDirection.DECREASING,
            round(relative_slope_pct, 2),
            f"Observed downward trajectory averaging {round(relative_slope_pct, 1)}% per period.",
        )
    else:
        return (
            TrendDirection.STABLE,
            round(relative_slope_pct, 2),
            "Series demonstrates historical stability within +/-2% per period.",
        )


def detect_seasonality(series: list[float], frequency: str) -> tuple[bool, str]:
    """
    Detects whether seasonality can be mathematically confirmed from available history.
    Strictly avoids claiming seasonality when history is insufficient.
    """
    n = len(series)
    cycle = 7 if frequency == "daily" else 12

    if n < 2 * cycle:
        return (
            False,
            f"Seasonality could not be established: series contains {n} periods, but at least "
            f"{2 * cycle} periods (2 full cycles) are required.",
        )

    # Autocorrelation at lag = cycle
    y_mean = sum(series) / n
    denom = sum((y - y_mean) ** 2 for y in series)
    if denom == 0:
        return False, "Constant series; no seasonality present."

    numerator = sum((series[t] - y_mean) * (series[t - cycle] - y_mean) for t in range(cycle, n))
    autocorr = numerator / denom

    if autocorr > 0.4:
        return (
            True,
            f"Statistically significant recurring pattern detected at lag {cycle} (autocorrelation = {round(autocorr, 2)}).",
        )
    else:
        return (
            False,
            f"No prominent recurring seasonal cycle detected (lag {cycle} autocorrelation = {round(autocorr, 2)}).",
        )
