from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Evidence:
    metric_name: str
    calculation: str
    source_table: str
    source_column: Optional[str] = None
    date_column: Optional[str] = None
    current_value: Optional[float | int | str] = None
    previous_value: Optional[float | int | str] = None
    absolute_change: Optional[float] = None
    percentage_change: Optional[float] = None
    growth_rate: Optional[float] = None
    direction: Optional[str] = None  # "up" | "down" | "flat"
    sample_count: int = 0
    time_period: Optional[str] = None
    breakdown: list[dict[str, Any]] = field(default_factory=list)
    confidence_note: str = "Calculated directly from verified database records."

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "calculation": self.calculation,
            "source_table": self.source_table,
            "source_column": self.source_column,
            "date_column": self.date_column,
            "current_value": self.current_value,
            "previous_value": self.previous_value,
            "absolute_change": self.absolute_change,
            "percentage_change": self.percentage_change,
            "growth_rate": self.growth_rate,
            "direction": self.direction,
            "sample_count": self.sample_count,
            "time_period": self.time_period,
            "breakdown": self.breakdown,
            "confidence_note": self.confidence_note,
        }


@dataclass
class RecommendedInvestigation:
    label: str
    action: str  # "explorer" | "sqllab" | "health" | "analytics"
    target: Optional[str] = None  # table name or query
    query: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "action": self.action,
            "target": self.target,
            "query": self.query,
        }


@dataclass
class AnalystResult:
    question: str
    analysis_type: str  # "trend" | "comparison" | "ranking" | "distribution" | "diagnostic" | "quality" | "correlation" | "overview"
    key_insight: str
    evidence: Evidence
    chart: Optional[dict[str, Any]] = None
    breakdown: list[dict[str, Any]] = field(default_factory=list)
    recommended_investigations: list[RecommendedInvestigation] = field(default_factory=list)
    ai_explanation: str = ""
    sql_query: Optional[str] = None
    status: str = "success"
    error_message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "analysis_type": self.analysis_type,
            "key_insight": self.key_insight,
            "evidence": self.evidence.to_dict() if self.evidence else None,
            "chart": self.chart,
            "breakdown": self.breakdown,
            "recommended_investigations": [i.to_dict() for i in self.recommended_investigations],
            "ai_explanation": self.ai_explanation,
            "sql_query": self.sql_query,
            "status": self.status,
            "error_message": self.error_message,
        }


@dataclass
class QuickAction:
    id: str
    title: str
    question: str
    category: str
    table: Optional[str] = None
    metric: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "question": self.question,
            "category": self.category,
            "table": self.table,
            "metric": self.metric,
        }
