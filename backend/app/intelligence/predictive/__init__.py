"""
backend/app/intelligence/predictive/__init__.py

Phase 9.0: Advanced Predictive & Simulation Intelligence
Exposes statistical time-series forecasting, what-if scenario simulations,
model selection, uncertainty analysis, and evidence explanations.
"""
from app.intelligence.predictive.models import (
    ConfidenceTier,
    DataQualityStatus,
    ForecastPoint,
    ForecastingMethod,
    ModelEvaluationMetric,
    PredictionEvidence,
    PredictionExplanation,
    PredictionResult,
    ScenarioComparison,
    ScenarioResult,
    ScenarioType,
    TrendDirection,
)
from app.intelligence.predictive.data_quality import (
    DataQualityReport,
    TimeSeriesCandidate,
    discover_predictive_candidates,
    extract_and_evaluate_time_series,
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
from app.intelligence.predictive.model_selection import (
    calculate_mae,
    calculate_mape,
    calculate_rmse,
    evaluate_and_select_model,
)
from app.intelligence.predictive.uncertainty import (
    compute_prediction_intervals,
    determine_confidence_tier,
)
from app.intelligence.predictive.scenario_engine import (
    compare_scenarios,
    simulate_what_if_scenario,
)
from app.intelligence.predictive.learning_context import (
    get_historical_outcome_context,
)
from app.intelligence.predictive.explainer import (
    explain_prediction_narrative,
    generate_structured_explanation,
)
from app.intelligence.predictive.predictor import run_prediction
from app.intelligence.predictive.store import (
    clear_predictive_store,
    get_prediction,
    list_predictions,
    save_prediction,
)

__all__ = [
    # Models
    "ConfidenceTier",
    "DataQualityStatus",
    "ForecastPoint",
    "ForecastingMethod",
    "ModelEvaluationMetric",
    "PredictionEvidence",
    "PredictionExplanation",
    "PredictionResult",
    "ScenarioComparison",
    "ScenarioResult",
    "ScenarioType",
    "TrendDirection",
    # Data Quality
    "DataQualityReport",
    "TimeSeriesCandidate",
    "discover_predictive_candidates",
    "extract_and_evaluate_time_series",
    # Forecasting Algorithms
    "naive_forecast",
    "simple_moving_average_forecast",
    "weighted_moving_average_forecast",
    "linear_trend_forecast",
    "exponential_smoothing_forecast",
    "seasonal_forecast",
    "detect_trend",
    "detect_seasonality",
    "generate_future_period_labels",
    # Model Selection & Metrics
    "calculate_mae",
    "calculate_rmse",
    "calculate_mape",
    "evaluate_and_select_model",
    # Uncertainty
    "compute_prediction_intervals",
    "determine_confidence_tier",
    # Scenarios
    "simulate_what_if_scenario",
    "compare_scenarios",
    # Learning
    "get_historical_outcome_context",
    # Explanations
    "generate_structured_explanation",
    "explain_prediction_narrative",
    # Orchestrator
    "run_prediction",
    # Storage
    "save_prediction",
    "get_prediction",
    "list_predictions",
    "clear_predictive_store",
]
