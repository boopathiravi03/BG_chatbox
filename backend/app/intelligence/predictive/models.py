"""
backend/app/intelligence/predictive/models.py

Phase 9.0: Advanced Predictive & Simulation Intelligence Models
Defines strongly typed data contracts for evidence-based forecasting,
what-if scenario simulation, uncertainty analysis, and model backtesting.

Strict Epistemic & Safety Principles:
- All forecasts are statistical projections based on real historical data.
- Never fabricates future certainty or claims predictive guarantees.
- Distinguishes observed facts, statistical forecasts, and scenario assumptions.
- Causal claims are strictly prohibited unless supported by verified empirical elasticity.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Optional


# ── Enumerations ─────────────────────────────────────────────────────────────

class ConfidenceTier(str, Enum):
    HIGH = "HIGH"         # Rich historical data, low backtest error, stable trend
    MODERATE = "MODERATE" # Adequate observations, moderate variance, reasonable fit
    LIMITED = "LIMITED"   # Small sample (<10 points), volatile series, or baseline fallback


class TrendDirection(str, Enum):
    INCREASING = "INCREASING"
    DECREASING = "DECREASING"
    STABLE = "STABLE"
    VOLATILE = "VOLATILE"


class ScenarioType(str, Enum):
    BASELINE = "BASELINE"
    UPLIFT = "UPLIFT"
    REDUCTION = "REDUCTION"
    GROWTH = "GROWTH"
    DECLINE = "DECLINE"
    CUSTOM = "CUSTOM"


class ForecastingMethod(str, Enum):
    NAIVE = "NAIVE"
    SMA = "SIMPLE_MOVING_AVERAGE"
    WMA = "WEIGHTED_MOVING_AVERAGE"
    LINEAR_TREND = "LINEAR_TREND"
    EXPONENTIAL_SMOOTHING = "EXPONENTIAL_SMOOTHING"
    SEASONAL = "SEASONAL_DECOMPOSITION"


class DataQualityStatus(str, Enum):
    VALID = "VALID"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NO_TEMPORAL_DIMENSION = "NO_TEMPORAL_DIMENSION"
    HIGH_MISSING_RATE = "HIGH_MISSING_RATE"
    IRREGULAR_INTERVALS = "IRREGULAR_INTERVALS"


# ── Data Point Models ─────────────────────────────────────────────────────────

@dataclass
class ForecastPoint:
    """A single time period observation or forecast value with uncertainty bounds."""
    period: str
    value: float
    is_forecast: bool = False
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    uncertainty_width: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "period": self.period,
            "value": round(self.value, 2),
            "is_forecast": self.is_forecast,
            "lower_bound": round(self.lower_bound, 2) if self.lower_bound is not None else None,
            "upper_bound": round(self.upper_bound, 2) if self.upper_bound is not None else None,
            "uncertainty_width": round(self.uncertainty_width, 2) if self.uncertainty_width is not None else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ForecastPoint":
        return cls(
            period=str(data.get("period", "")),
            value=float(data.get("value", 0.0)),
            is_forecast=bool(data.get("is_forecast", False)),
            lower_bound=float(data["lower_bound"]) if data.get("lower_bound") is not None else None,
            upper_bound=float(data["upper_bound"]) if data.get("upper_bound") is not None else None,
            uncertainty_width=float(data["uncertainty_width"]) if data.get("uncertainty_width") is not None else None,
        )


@dataclass
class ModelEvaluationMetric:
    """Historical backtest evaluation metrics across candidate models."""
    method: str
    mae: Optional[float] = None
    rmse: Optional[float] = None
    mape: Optional[float] = None
    mape_note: Optional[str] = None
    selected: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelEvaluationMetric":
        return cls(
            method=data.get("method", ""),
            mae=data.get("mae"),
            rmse=data.get("rmse"),
            mape=data.get("mape"),
            mape_note=data.get("mape_note"),
            selected=bool(data.get("selected", False)),
            reason=data.get("reason", ""),
        )


@dataclass
class PredictionEvidence:
    """Auditable evidence lineage demonstrating where forecast inputs originated."""
    source_table: str
    date_column: str
    metric_column: Optional[str]
    aggregation: str
    historical_count: int
    min_date: str
    max_date: str
    sql_lineage: str
    historical_outcome_support: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PredictionEvidence":
        return cls(
            source_table=data.get("source_table", ""),
            date_column=data.get("date_column", ""),
            metric_column=data.get("metric_column"),
            aggregation=data.get("aggregation", "SUM"),
            historical_count=int(data.get("historical_count", 0)),
            min_date=data.get("min_date", ""),
            max_date=data.get("max_date", ""),
            sql_lineage=data.get("sql_lineage", ""),
            historical_outcome_support=list(data.get("historical_outcome_support") or []),
        )


# ── Prediction Results ────────────────────────────────────────────────────────

@dataclass
class PredictionResult:
    """Full predictive result including historical data, forecast, evaluation, and caveats."""
    prediction_id: str = field(default_factory=lambda: f"pred_{uuid.uuid4().hex[:10]}")
    user_id: str = ""
    database_identity: str = ""
    metric_name: str = ""
    source_table: str = ""
    date_column: str = ""
    metric_column: Optional[str] = None
    frequency: str = "monthly"  # "daily" | "weekly" | "monthly"
    forecast_horizon_days: int = 30
    horizon_periods: int = 1
    points: list[ForecastPoint] = field(default_factory=list)
    selected_method: str = ForecastingMethod.EXPONENTIAL_SMOOTHING.value
    trend_direction: str = TrendDirection.STABLE.value
    seasonality_detected: bool = False
    seasonality_summary: str = "Seasonality could not be established from the available history."
    confidence_tier: str = ConfidenceTier.LIMITED.value
    confidence_rationale: str = ""
    data_quality_status: str = DataQualityStatus.VALID.value
    model_evaluations: list[ModelEvaluationMetric] = field(default_factory=list)
    evidence: Optional[PredictionEvidence] = None
    assumptions: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    ai_summary: Optional[str] = None
    status: str = "success"  # "success" | "insufficient_data" | "error"
    error_message: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "user_id": self.user_id,
            "database_identity": self.database_identity,
            "metric_name": self.metric_name,
            "source_table": self.source_table,
            "date_column": self.date_column,
            "metric_column": self.metric_column,
            "frequency": self.frequency,
            "forecast_horizon_days": self.forecast_horizon_days,
            "horizon_periods": self.horizon_periods,
            "points": [p.to_dict() for p in self.points],
            "selected_method": self.selected_method,
            "trend_direction": self.trend_direction,
            "seasonality_detected": self.seasonality_detected,
            "seasonality_summary": self.seasonality_summary,
            "confidence_tier": self.confidence_tier,
            "confidence_rationale": self.confidence_rationale,
            "data_quality_status": self.data_quality_status,
            "model_evaluations": [m.to_dict() for m in self.model_evaluations],
            "evidence": self.evidence.to_dict() if self.evidence else None,
            "assumptions": self.assumptions,
            "limitations": self.limitations,
            "ai_summary": self.ai_summary,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PredictionResult":
        ev = PredictionEvidence.from_dict(data["evidence"]) if data.get("evidence") else None
        points = [ForecastPoint.from_dict(p) for p in data.get("points", [])]
        evals = [ModelEvaluationMetric.from_dict(m) for m in data.get("model_evaluations", [])]
        return cls(
            prediction_id=data.get("prediction_id", f"pred_{uuid.uuid4().hex[:10]}"),
            user_id=data.get("user_id", ""),
            database_identity=data.get("database_identity", ""),
            metric_name=data.get("metric_name", ""),
            source_table=data.get("source_table", ""),
            date_column=data.get("date_column", ""),
            metric_column=data.get("metric_column"),
            frequency=data.get("frequency", "monthly"),
            forecast_horizon_days=int(data.get("forecast_horizon_days", 30)),
            horizon_periods=int(data.get("horizon_periods", 1)),
            points=points,
            selected_method=data.get("selected_method", ForecastingMethod.EXPONENTIAL_SMOOTHING.value),
            trend_direction=data.get("trend_direction", TrendDirection.STABLE.value),
            seasonality_detected=bool(data.get("seasonality_detected", False)),
            seasonality_summary=data.get("seasonality_summary", ""),
            confidence_tier=data.get("confidence_tier", ConfidenceTier.LIMITED.value),
            confidence_rationale=data.get("confidence_rationale", ""),
            data_quality_status=data.get("data_quality_status", DataQualityStatus.VALID.value),
            model_evaluations=evals,
            evidence=ev,
            assumptions=list(data.get("assumptions") or []),
            limitations=list(data.get("limitations") or []),
            ai_summary=data.get("ai_summary"),
            status=data.get("status", "success"),
            error_message=data.get("error_message"),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
        )


# ── Scenario & What-If Models ────────────────────────────────────────────────

@dataclass
class ScenarioResult:
    """Simulation of a baseline forecast under an explicit what-if condition."""
    scenario_id: str = field(default_factory=lambda: f"scen_{uuid.uuid4().hex[:10]}")
    prediction_id: str = ""
    scenario_name: str = ""
    scenario_type: str = ScenarioType.CUSTOM.value
    change_percent: Optional[float] = None
    absolute_change: Optional[float] = None
    baseline_projected_total: float = 0.0
    scenario_projected_total: float = 0.0
    delta_total: float = 0.0
    delta_percent: float = 0.0
    scenario_points: list[ForecastPoint] = field(default_factory=list)
    assumption_statement: str = ""
    causal_disclaimer: str = (
        "Scenario arithmetic describes mathematical projection under the stated assumption. "
        "It does not establish that action taken in reality will cause this change."
    )
    limitations: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "prediction_id": self.prediction_id,
            "scenario_name": self.scenario_name,
            "scenario_type": self.scenario_type,
            "change_percent": self.change_percent,
            "absolute_change": self.absolute_change,
            "baseline_projected_total": round(self.baseline_projected_total, 2),
            "scenario_projected_total": round(self.scenario_projected_total, 2),
            "delta_total": round(self.delta_total, 2),
            "delta_percent": round(self.delta_percent, 2),
            "scenario_points": [p.to_dict() for p in self.scenario_points],
            "assumption_statement": self.assumption_statement,
            "causal_disclaimer": self.causal_disclaimer,
            "limitations": self.limitations,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScenarioResult":
        points = [ForecastPoint.from_dict(p) for p in data.get("scenario_points", [])]
        return cls(
            scenario_id=data.get("scenario_id", f"scen_{uuid.uuid4().hex[:10]}"),
            prediction_id=data.get("prediction_id", ""),
            scenario_name=data.get("scenario_name", ""),
            scenario_type=data.get("scenario_type", ScenarioType.CUSTOM.value),
            change_percent=data.get("change_percent"),
            absolute_change=data.get("absolute_change"),
            baseline_projected_total=float(data.get("baseline_projected_total", 0.0)),
            scenario_projected_total=float(data.get("scenario_projected_total", 0.0)),
            delta_total=float(data.get("delta_total", 0.0)),
            delta_percent=float(data.get("delta_percent", 0.0)),
            scenario_points=points,
            assumption_statement=data.get("assumption_statement", ""),
            causal_disclaimer=data.get(
                "causal_disclaimer",
                "Scenario arithmetic describes mathematical projection. Causal effect is not established.",
            ),
            limitations=list(data.get("limitations") or []),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
        )


@dataclass
class ScenarioComparison:
    """Side-by-side comparison of baseline forecast against multiple simulation scenarios."""
    comparison_id: str = field(default_factory=lambda: f"comp_{uuid.uuid4().hex[:10]}")
    metric_name: str = ""
    forecast_horizon_days: int = 30
    baseline_total: float = 0.0
    scenarios: list[ScenarioResult] = field(default_factory=list)
    summary_table: list[dict[str, Any]] = field(default_factory=list)
    guidance: str = (
        "Scenarios reflect hypothetical parameter adjustments. "
        "Evaluate real-world feasibility before taking business actions."
    )
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "comparison_id": self.comparison_id,
            "metric_name": self.metric_name,
            "forecast_horizon_days": self.forecast_horizon_days,
            "baseline_total": round(self.baseline_total, 2),
            "scenarios": [s.to_dict() for s in self.scenarios],
            "summary_table": self.summary_table,
            "guidance": self.guidance,
            "created_at": self.created_at,
        }


# ── Explanation Models ───────────────────────────────────────────────────────

@dataclass
class PredictionExplanation:
    """Structured, evidence-grounded explanation of predictive calculations."""
    prediction_id: str
    metric_name: str
    historical_summary: str
    method_rationale: str
    backtest_evaluation: str
    trend_and_seasonality: str
    uncertainty_explanation: str
    limitations: list[str]
    phase89_historical_signals: list[str] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
