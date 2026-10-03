"""
backend/app/intelligence/outcome_optimization/__init__.py

Phase 8.9: Closed-Loop Outcome Optimization & Adaptive Recommendations
Public interface for the outcome_optimization package.
"""
from app.intelligence.outcome_optimization.models import (
    OutcomeMeasurement,
    OutcomeAnalysis,
    AdaptiveRecommendation,
    RecommendationExplanation,
    EffectivenessLabel,
    ConfidenceLevel,
    AttributionStatus,
    MeasurementWindow,
    RecommendationSource,
)
from app.intelligence.outcome_optimization.outcome_tracker import (
    save_measurement,
    get_measurement,
    list_measurements,
    save_recommendation,
    get_recommendation,
    list_recommendations,
    clear_outcome_opt_store,
    reset_engine as reset_outcome_opt_engine,
)
from app.intelligence.outcome_optimization.baseline_engine import (
    compute_baseline_for_metric,
    discover_measurable_metrics,
)
from app.intelligence.outcome_optimization.effectiveness import (
    classify_effectiveness,
    describe_effectiveness,
)
from app.intelligence.outcome_optimization.attribution import assess_attribution
from app.intelligence.outcome_optimization.measurement_engine import measure_metric_outcome
from app.intelligence.outcome_optimization.analysis_engine import run_outcome_analysis
from app.intelligence.outcome_optimization.recommendation_engine import (
    generate_adaptive_recommendations,
)
from app.intelligence.outcome_optimization.learning_bridge import (
    bridge_measurement_to_learning,
)
from app.intelligence.outcome_optimization.explainer import explain_recommendation

__all__ = [
    # Models
    "OutcomeMeasurement",
    "OutcomeAnalysis",
    "AdaptiveRecommendation",
    "RecommendationExplanation",
    "EffectivenessLabel",
    "ConfidenceLevel",
    "AttributionStatus",
    "MeasurementWindow",
    "RecommendationSource",
    # Persistence
    "save_measurement",
    "get_measurement",
    "list_measurements",
    "save_recommendation",
    "get_recommendation",
    "list_recommendations",
    "clear_outcome_opt_store",
    "reset_outcome_opt_engine",
    # Engines
    "compute_baseline_for_metric",
    "discover_measurable_metrics",
    "classify_effectiveness",
    "describe_effectiveness",
    "assess_attribution",
    "measure_metric_outcome",
    "run_outcome_analysis",
    "generate_adaptive_recommendations",
    "bridge_measurement_to_learning",
    "explain_recommendation",
]
