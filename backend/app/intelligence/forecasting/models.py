from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ForecastCandidate:
    table: str
    date_column: str
    metric_column: Optional[str]
    metric_label: str
    calculation: str
    frequency: str  # "daily" | "weekly" | "monthly"
    historical_points_count: int
    min_date: str
    max_date: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "date_column": self.date_column,
            "metric_column": self.metric_column,
            "metric_label": self.metric_label,
            "calculation": self.calculation,
            "frequency": self.frequency,
            "historical_points_count": self.historical_points_count,
            "min_date": self.min_date,
            "max_date": self.max_date,
        }


@dataclass
class ForecastObservation:
    period: str
    value: float
    is_forecast: bool = False
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "period": self.period,
            "value": round(self.value, 2),
            "is_forecast": self.is_forecast,
            "lower_bound": round(self.lower_bound, 2) if self.lower_bound is not None else None,
            "upper_bound": round(self.upper_bound, 2) if self.upper_bound is not None else None,
        }


@dataclass
class ForecastResult:
    metric_name: str
    source_table: str
    date_column: str
    metric_column: Optional[str]
    frequency: str
    historical_range: dict[str, str]
    forecast_horizon: int
    horizon_unit: str
    observations: list[ForecastObservation]
    method: str
    model_params: dict[str, Any]
    validation: dict[str, Any]
    limitations: list[str]
    ai_explanation: Optional[str] = None
    chart: Optional[dict[str, Any]] = None
    sql_query: Optional[str] = None
    status: str = "success"
    error_message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "source_table": self.source_table,
            "date_column": self.date_column,
            "metric_column": self.metric_column,
            "frequency": self.frequency,
            "historical_range": self.historical_range,
            "forecast_horizon": self.forecast_horizon,
            "horizon_unit": self.horizon_unit,
            "observations": [o.to_dict() for o in self.observations],
            "method": self.method,
            "model_params": self.model_params,
            "validation": self.validation,
            "limitations": self.limitations,
            "ai_explanation": self.ai_explanation,
            "chart": self.chart,
            "sql_query": self.sql_query,
            "status": self.status,
            "error_message": self.error_message,
        }
