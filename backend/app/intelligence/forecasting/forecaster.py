from __future__ import annotations

import math
import re
from datetime import datetime, timedelta
from typing import Any, Optional
from sqlalchemy import text
from app.database.database_manager import get_engine, get_current_db_type
from app.intelligence.schema_analyzer import quote_identifier
from app.intelligence.ai_analyst.trend_analyzer import get_dialect_date_trunc
from app.agent.groq_agent import ask_groq
from app.intelligence.forecasting.models import (
    ForecastResult,
    ForecastObservation,
)
from app.intelligence.forecasting.validators import validate_holdout


def generate_next_period_labels(last_label: str, frequency: str, count: int) -> list[str]:
    """Generates future chronological period labels (e.g. 2024-04, 2024-05...)."""
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
            delta = timedelta(days=7 if frequency == "weekly" else 1)
            for _ in range(count):
                curr_date += delta
                labels.append(curr_date.strftime("%Y-%m-%d"))
            return labels
        except Exception:
            pass

    # Fallback: +1, +2, +3...
    for i in range(1, count + 1):
        labels.append(f"Period +{i}")
    return labels


def fit_and_predict_exponential_smoothing(
    series: list[float],
    horizon: int,
    alpha: float = 0.4,
    beta: float = 0.2,
) -> tuple[list[float], list[float], float]:
    """
    Fits Holt's Linear Exponential Smoothing with trend damping.
    Returns: (fitted_in_sample, forecast_out_of_sample, residual_std_err)
    """
    n = len(series)
    if n == 0:
        return [], [0.0] * horizon, 0.0

    if n == 1:
        return [series[0]], [series[0]] * horizon, 0.0

    # Initial level and trend
    level = series[0]
    trend = series[1] - series[0] if n > 1 else 0.0

    fitted = [level]

    for t in range(1, n):
        y = series[t]
        prev_level = level
        # Update level
        level = alpha * y + (1 - alpha) * (prev_level + trend)
        # Update trend (with 0.9 damping factor)
        trend = beta * (level - prev_level) + (1 - beta) * (trend * 0.9)
        fitted.append(level + trend)

    # Forecast
    forecast = []
    damped_trend = trend
    curr_level = level
    for h in range(1, horizon + 1):
        curr_level = curr_level + damped_trend
        damped_trend *= 0.9  # Damping to avoid explosive long-range trend
        forecast.append(round(curr_level, 2))

    # Calculate residual standard error
    residuals = [series[i] - fitted[i] for i in range(n)]
    dof = max(1, n - 2)
    res_variance = sum(r * r for r in residuals) / dof
    residual_std = math.sqrt(res_variance)

    return fitted, forecast, residual_std


def run_forecast(
    table: str,
    date_column: str,
    metric_column: Optional[str] = None,
    frequency: str = "monthly",
    horizon: int = 3,
    aggregation: str = "SUM",
) -> ForecastResult:
    """
    Executes end-to-end time-series forecasting:
    1. Extracts chronological historical aggregation from database
    2. Validates observation density and data distribution
    3. Fits deterministic statistical model (Holt's Linear / SES)
    4. Computes prediction intervals and holdout validation
    5. Formulates executive AI narrative via Groq
    """
    engine = get_engine()
    db_type = get_current_db_type()

    if engine is None or db_type == "none":
        return ForecastResult(
            metric_name=metric_column or "Count",
            source_table=table,
            date_column=date_column,
            metric_column=metric_column,
            frequency=frequency,
            historical_range={},
            forecast_horizon=horizon,
            horizon_unit="periods",
            observations=[],
            method="None",
            model_params={},
            validation={},
            limitations=["No database connected."],
            status="error",
            error_message="No database is currently connected.",
        )

    t_quoted = quote_identifier(table, db_type)
    d_quoted = quote_identifier(date_column, db_type)

    interval_arg = "month" if frequency == "monthly" else "day"
    date_expr = get_dialect_date_trunc(d_quoted, db_type, interval=interval_arg)

    if metric_column:
        m_quoted = quote_identifier(metric_column, db_type)
        val_expr = f"{aggregation.upper()}({m_quoted})"
    else:
        val_expr = "COUNT(*)"

    sql = f"""
        SELECT 
            {date_expr} as period,
            {val_expr} as metric_val
        FROM {t_quoted}
        WHERE {d_quoted} IS NOT NULL
        GROUP BY {date_expr}
        ORDER BY {date_expr} ASC
    """

    try:
        with engine.connect() as conn:
            rows = conn.execute(text(sql)).fetchall()
    except Exception as e:
        return ForecastResult(
            metric_name=metric_column or "Count",
            source_table=table,
            date_column=date_column,
            metric_column=metric_column,
            frequency=frequency,
            historical_range={},
            forecast_horizon=horizon,
            horizon_unit="periods",
            observations=[],
            method="None",
            model_params={},
            validation={},
            limitations=[f"Query execution error: {str(e)}"],
            sql_query=sql,
            status="error",
            error_message=f"Failed to query time-series history: {str(e)}",
        )

    clean_rows = [(str(r[0]), float(r[1]) if r[1] is not None else 0.0) for r in rows if r[0] is not None]

    if len(clean_rows) < 3:
        return ForecastResult(
            metric_name=metric_column or "Count",
            source_table=table,
            date_column=date_column,
            metric_column=metric_column,
            frequency=frequency,
            historical_range={},
            forecast_horizon=horizon,
            horizon_unit="periods",
            observations=[],
            method="None",
            model_params={},
            validation={},
            limitations=[
                "Insufficient historical observations. Forecasting requires at least 3 distinct time periods.",
            ],
            sql_query=sql,
            status="insufficient_data",
            error_message="Forecasting unavailable: less than 3 historical chronological periods were detected.",
        )

    hist_labels = [r[0] for r in clean_rows]
    hist_values = [r[1] for r in clean_rows]

    # Bound horizon appropriately
    safe_horizon = max(1, min(horizon, 12 if frequency == "monthly" else 30))

    # Holdout validation (if >= 5 points)
    if len(hist_values) >= 5:
        holdout_len = 1 if len(hist_values) < 8 else 2
        train_hist = hist_values[:-holdout_len]
        test_actual = hist_values[-holdout_len:]

        def holdout_pred_fn(train_data: list[float], h: int) -> list[float]:
            _, preds, _ = fit_and_predict_exponential_smoothing(train_data, h)
            return preds

        val_metrics = validate_holdout(train_hist, test_actual, holdout_pred_fn)
    else:
        val_metrics = {
            "validation_performed": False,
            "reason": "Historical series contains fewer than 5 periods; entire dataset used for model fit.",
            "mae": None,
            "mape": None,
            "limitation": "Holdout validation skipped to prevent under-fitting on small sample.",
        }

    # Model Fitting on full series
    fitted, future_preds, residual_std = fit_and_predict_exponential_smoothing(
        hist_values,
        safe_horizon,
        alpha=0.4,
        beta=0.2,
    )

    future_labels = generate_next_period_labels(hist_labels[-1], frequency, safe_horizon)

    # Observations array
    observations: list[ForecastObservation] = []

    # 1. Historical observations
    for lbl, val in zip(hist_labels, hist_values):
        observations.append(
            ForecastObservation(
                period=lbl,
                value=val,
                is_forecast=False,
            )
        )

    # 2. Forecast observations with 95% uncertainty intervals (1.96 * SE)
    for step, (f_lbl, f_val) in enumerate(zip(future_labels, future_preds), start=1):
        if residual_std > 0:
            # Variance expands with horizon
            step_se = residual_std * math.sqrt(1 + (step - 1) * 0.16)
            lower = max(0.0, f_val - 1.96 * step_se)  # Bound at 0 for positive measures
            upper = f_val + 1.96 * step_se
        else:
            lower = None
            upper = None

        observations.append(
            ForecastObservation(
                period=f_lbl,
                value=f_val,
                is_forecast=True,
                lower_bound=lower,
                upper_bound=upper,
            )
        )

    # Chart payload for ChartRenderer
    chart_labels = hist_labels + future_labels
    chart_values = hist_values + future_preds
    chart_payload = {
        "chart_type": "line",
        "title": f"Forecast for {metric_column or 'Volume'} ({safe_horizon} {frequency} periods)",
        "labels": chart_labels,
        "values": chart_values,
    }

    # Limitations
    limitations = [
        "Statistical projections assume continuation of observed patterns and exclude external unforeseen events.",
        "Uncertainty intervals widen progressively across longer forecast horizons.",
    ]
    if len(hist_values) < 6:
        limitations.append("Short historical baseline (< 6 periods); projections carry wider variance.")

    # Executive explanation (deterministic with optional Groq polish)
    metric_title = metric_column.replace("_", " ").title() if metric_column else f"{table.title()} Activity"
    historical_first = hist_values[0]
    historical_last = hist_values[-1]
    final_pred = future_preds[-1]

    trend_dir = "growth" if final_pred > historical_last else ("decline" if final_pred < historical_last else "stability")

    deterministic_summary = (
        f"Based on {len(hist_values)} historical {frequency} periods ({hist_labels[0]} to {hist_labels[-1]}), "
        f"the model projects {trend_dir} for {metric_title} toward {final_pred:,.2f} over the next {safe_horizon} periods. "
        f"This is an empirical statistical projection governed by past variance, not a guaranteed business outcome."
    )

    prompt = f"""You are BG AI's Senior Quantitative Data Analyst.
A deterministic time-series forecast was computed directly from verified database records:
- Metric: {metric_title} from '{table}'
- Frequency: {frequency}
- Historical Periods ({len(hist_values)}): {hist_labels[0]} to {hist_labels[-1]}
- Recent Observed Value: {historical_last:,.2f}
- Projected Values: {', '.join([f'{lbl}: {val:,.2f}' for lbl, val in zip(future_labels, future_preds)])}
- Validation MAE: {val_metrics.get('mae')}

Rules:
1. Summarize the trajectory in 2-3 concise sentences.
2. Clearly state this is a statistical projection, not a guarantee.
3. NEVER invent or alter the numbers.
4. Do NOT use markdown code blocks or greetings.
"""
    try:
        ai_exp = ask_groq(prompt)
        final_explanation = ai_exp.strip() if ai_exp and len(ai_exp.strip()) > 15 else deterministic_summary
    except Exception:
        final_explanation = deterministic_summary

    return ForecastResult(
        metric_name=metric_title,
        source_table=table,
        date_column=date_column,
        metric_column=metric_column,
        frequency=frequency,
        historical_range={"start": hist_labels[0], "end": hist_labels[-1]},
        forecast_horizon=safe_horizon,
        horizon_unit=f"{frequency} periods",
        observations=observations,
        method="Damped Holt's Linear Exponential Smoothing",
        model_params={"alpha": 0.4, "beta": 0.2, "damping_factor": 0.9},
        validation=val_metrics,
        limitations=limitations,
        ai_explanation=final_explanation,
        chart=chart_payload,
        sql_query=sql,
        status="success",
    )
