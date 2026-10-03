"""
backend/app/intelligence/predictive/predictor.py

Phase 9.0: Advanced Predictive Intelligence Orchestrator
Coordinates schema discovery, data quality validation, candidate backtesting,
deterministic forecasting, uncertainty quantification, and learning context integration.

Guaranteed Epistemic Safety:
- Returns structured INSUFFICIENT_DATA if requirements are unmet.
- Never fabricates future certainty or claims predictive guarantees.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.database.database_manager import get_engine, get_current_db_type
from app.intelligence.table_explorer import classify_semantic_type
from app.intelligence.schema_analyzer import analyze_schema
from app.intelligence.predictive.models import (
    DataQualityStatus,
    ForecastPoint,
    ForecastingMethod,
    PredictionEvidence,
    PredictionResult,
    TrendDirection,
)
from app.intelligence.predictive.data_quality import (
    extract_and_evaluate_time_series,
    discover_predictive_candidates,
)
from app.intelligence.predictive.forecasting import (
    detect_seasonality,
    detect_trend,
    exponential_smoothing_forecast,
    generate_future_period_labels,
    linear_trend_forecast,
    naive_forecast,
    seasonal_forecast,
    simple_moving_average_forecast,
    weighted_moving_average_forecast,
)
from app.intelligence.predictive.model_selection import evaluate_and_select_model
from app.intelligence.predictive.uncertainty import (
    compute_prediction_intervals,
    determine_confidence_tier,
)
from app.intelligence.predictive.learning_context import get_historical_outcome_context
from app.intelligence.predictive.store import save_prediction

logger = logging.getLogger("bgai.predictive.predictor")


def run_prediction(
    user_id: str,
    table: str,
    date_column: Optional[str] = None,
    metric_column: Optional[str] = None,
    metric_name: Optional[str] = None,
    aggregation: str = "SUM",
    frequency: str = "monthly",
    horizon_days: int = 30,
    force_method: Optional[str] = None,
    engine: Optional[Any] = None,
    db_type: Optional[str] = None,
) -> PredictionResult:
    """
    Executes end-to-end evidence-based predictive forecasting on real database data.
    """
    if engine is None:
        engine = get_engine()
    if db_type is None:
        db_type = get_current_db_type()

    db_identity = ""
    try:
        if engine and hasattr(engine, "url"):
            db_identity = engine.url.render_as_string(hide_password=True)
    except Exception:
        db_identity = "connected_db"

    clean_metric_name = metric_name or (
        f"{aggregation.title()} of {metric_column.replace('_', ' ').title()}"
        if metric_column
        else f"Total {table.replace('_', ' ').title()} Count"
    )

    if engine is None or db_type == "none":
        res = PredictionResult(
            user_id=user_id,
            database_identity=db_identity,
            metric_name=clean_metric_name,
            source_table=table,
            date_column=date_column or "",
            metric_column=metric_column,
            forecast_horizon_days=horizon_days,
            status="error",
            data_quality_status=DataQualityStatus.INSUFFICIENT_DATA.value,
            error_message="No database is currently connected.",
            limitations=["Forecasting requires an active database connection."],
        )
        return save_prediction(res)

    # 1. Auto-discover date column if not provided
    if not date_column:
        schema_info = analyze_schema(engine, db_type)
        table_meta = schema_info.get("tables", {}).get(table, {})
        cols = table_meta.get("columns", [])
        for col in cols:
            c_name = col.get("name", "")
            c_type = str(col.get("type", "TEXT"))
            sem = classify_semantic_type(c_name, c_type)
            if sem in ("Date", "Timestamp") or any(
                term in c_name.lower() for term in ("date", "time", "created_at", "updated_at", "timestamp")
            ):
                date_column = c_name
                break

    if not date_column:
        res = PredictionResult(
            user_id=user_id,
            database_identity=db_identity,
            metric_name=clean_metric_name,
            source_table=table,
            date_column="",
            metric_column=metric_column,
            forecast_horizon_days=horizon_days,
            status="insufficient_data",
            data_quality_status=DataQualityStatus.NO_TEMPORAL_DIMENSION.value,
            error_message=f"No suitable date/timestamp column was found on table '{table}'.",
            limitations=[
                "Time-series prediction requires at least one date or timestamp dimension.",
            ],
        )
        return save_prediction(res)

    # Map horizon_days to period count based on frequency
    if frequency == "daily":
        horizon_periods = max(1, min(horizon_days, 90))
    elif frequency == "weekly":
        horizon_periods = max(1, min(horizon_days // 7, 24))
    else:  # monthly
        horizon_periods = max(1, min(horizon_days // 30 or 1, 12))

    # 2. Extract and evaluate data quality
    quality_report = extract_and_evaluate_time_series(
        engine=engine,
        db_type=db_type,
        table=table,
        date_column=date_column,
        metric_column=metric_column,
        aggregation=aggregation,
        frequency=frequency,
    )

    if not quality_report.is_sufficient:
        res = PredictionResult(
            user_id=user_id,
            database_identity=db_identity,
            metric_name=clean_metric_name,
            source_table=table,
            date_column=date_column,
            metric_column=metric_column,
            frequency=frequency,
            forecast_horizon_days=horizon_days,
            horizon_periods=horizon_periods,
            status="insufficient_data",
            data_quality_status=quality_report.status.value,
            error_message="; ".join(quality_report.issues),
            limitations=quality_report.issues,
        )
        return save_prediction(res)

    clean_series = quality_report.clean_series
    hist_labels = [p[0] for p in clean_series]
    hist_values = [p[1] for p in clean_series]

    # 3. Model selection & backtesting
    if force_method:
        selected_method = force_method
        evaluations = []
    else:
        selected_method, evaluations = evaluate_and_select_model(
            series=hist_values, frequency=frequency
        )

    # 4. Generate forecast
    cycle = 7 if frequency == "daily" else 12
    if selected_method == ForecastingMethod.NAIVE.value:
        fitted, future_preds = naive_forecast(hist_values, horizon_periods)
    elif selected_method == ForecastingMethod.SMA.value:
        fitted, future_preds = simple_moving_average_forecast(hist_values, horizon_periods, window=3)
    elif selected_method == ForecastingMethod.WMA.value:
        fitted, future_preds = weighted_moving_average_forecast(hist_values, horizon_periods, window=3)
    elif selected_method == ForecastingMethod.LINEAR_TREND.value:
        fitted, future_preds = linear_trend_forecast(hist_values, horizon_periods)
    elif selected_method == ForecastingMethod.SEASONAL.value:
        fitted, future_preds = seasonal_forecast(hist_values, horizon_periods, cycle_length=cycle)
    else:
        # Default: Exponential smoothing
        selected_method = ForecastingMethod.EXPONENTIAL_SMOOTHING.value
        fitted, future_preds = exponential_smoothing_forecast(hist_values, horizon_periods)

    # 5. Trend & Seasonality Analysis
    trend_dir, trend_slope, trend_note = detect_trend(hist_values)
    seasonality_present, seasonality_note = detect_seasonality(hist_values, frequency)

    # 6. Future period labels and uncertainty intervals
    future_labels = generate_future_period_labels(hist_labels[-1], frequency, horizon_periods)
    forecast_points = compute_prediction_intervals(
        actuals=hist_values,
        fitted=fitted,
        forecast_values=future_preds,
        future_labels=future_labels,
        is_non_negative=True,
    )

    # Historical observations points
    all_points: list[ForecastPoint] = []
    for lbl, val in zip(hist_labels, hist_values):
        all_points.append(
            ForecastPoint(
                period=lbl,
                value=round(val, 2),
                is_forecast=False,
            )
        )
    all_points.extend(forecast_points)

    # 7. Confidence tier evaluation
    selected_eval = next((m for m in evaluations if m.selected), None)
    avg_hist_val = sum(hist_values) / len(hist_values) if hist_values else 1.0
    conf_tier, conf_rationale = determine_confidence_tier(
        observation_count=len(hist_values),
        trend=trend_dir,
        selected_eval=selected_eval,
        mean_value=avg_hist_val,
    )

    # 8. Learning context integration (Phase 8.9 / Phase 8.5)
    learning_info = get_historical_outcome_context(user_id=user_id, table_name=table)

    # 9. Formulate evidence lineage
    evidence = PredictionEvidence(
        source_table=table,
        date_column=date_column,
        metric_column=metric_column,
        aggregation=aggregation,
        historical_count=len(hist_values),
        min_date=quality_report.min_date,
        max_date=quality_report.max_date,
        sql_lineage=quality_report.sql_executed,
        historical_outcome_support=learning_info.get("supporting_references", []),
    )

    # 10. Formulate assumptions & limitations
    assumptions = [
        f"Assumes historical data generating process continues over the next {horizon_days} days.",
        f"Model selected: {selected_method.replace('_', ' ').title()}.",
    ]
    if learning_info.get("has_history"):
        assumptions.append(learning_info["summary"])

    limitations = list(quality_report.issues)
    limitations.extend([
        "Forecast is an empirical projection; unforeseen external shocks or market changes are not captured.",
        "Uncertainty intervals widen with time distance from the last observation.",
    ])

    result = PredictionResult(
        user_id=user_id,
        database_identity=db_identity,
        metric_name=clean_metric_name,
        source_table=table,
        date_column=date_column,
        metric_column=metric_column,
        frequency=frequency,
        forecast_horizon_days=horizon_days,
        horizon_periods=horizon_periods,
        points=all_points,
        selected_method=selected_method,
        trend_direction=trend_dir.value,
        seasonality_detected=seasonality_present,
        seasonality_summary=seasonality_note,
        confidence_tier=conf_tier.value,
        confidence_rationale=conf_rationale,
        data_quality_status=DataQualityStatus.VALID.value,
        model_evaluations=evaluations,
        evidence=evidence,
        assumptions=assumptions,
        limitations=limitations,
        status="success",
    )

    return save_prediction(result)
