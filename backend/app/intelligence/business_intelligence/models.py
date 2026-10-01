"""
backend/app/intelligence/business_intelligence/models.py

Phase 8.1: Automated Business Intelligence Data Models
Defines structured classes for business insights, context, metrics, and reports.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


class InsightCategory:
    TREND = "TREND"
    GROWTH = "GROWTH"
    DECLINE = "DECLINE"
    TOP_CONTRIBUTOR = "TOP_CONTRIBUTOR"
    CONCENTRATION = "CONCENTRATION"
    QUALITY = "QUALITY"
    ANOMALY = "ANOMALY"
    FORECAST = "FORECAST"
    PERFORMANCE = "PERFORMANCE"
    DATA_COMPLETENESS = "DATA_COMPLETENESS"

    ALL = {
        TREND, GROWTH, DECLINE, TOP_CONTRIBUTOR, CONCENTRATION,
        QUALITY, ANOMALY, FORECAST, PERFORMANCE, DATA_COMPLETENESS
    }


class InsightSeverity:
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

    ALL = {INFO, WARNING, CRITICAL}


@dataclass
class BusinessInsight:
    """Represents a single deterministic, evidence-backed business insight."""
    title: str
    summary: str
    category: str
    severity: str
    priority: float = 0.0
    id: str = field(default_factory=lambda: f"bi_{uuid.uuid4().hex[:8]}")
    metric: Optional[str] = None
    current_value: Optional[Any] = None
    previous_value: Optional[Any] = None
    change_value: Optional[Any] = None
    change_percent: Optional[float] = None
    source_tables: list[str] = field(default_factory=list)
    source_columns: list[str] = field(default_factory=list)
    sql: Optional[str] = None
    evidence: dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    investigation_type: str = "ai_analyst"  # ai_analyst | anomaly_center | data_explorer | forecasting | data_health
    recommended_next_step: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "category": self.category,
            "severity": self.severity,
            "priority": round(self.priority, 2),
            "metric": self.metric,
            "current_value": self.current_value,
            "previous_value": self.previous_value,
            "change_value": self.change_value,
            "change_percent": self.change_percent,
            "source_tables": self.source_tables,
            "source_columns": self.source_columns,
            "sql": self.sql,
            "evidence": self.evidence,
            "generated_at": self.generated_at,
            "investigation_type": self.investigation_type,
            "recommended_next_step": self.recommended_next_step,
        }


@dataclass
class BusinessContext:
    """Discovered business context inferred from schema and table contents."""
    entity_tables: list[dict[str, Any]] = field(default_factory=list)
    time_columns: list[dict[str, Any]] = field(default_factory=list)
    measure_columns: list[dict[str, Any]] = field(default_factory=list)
    dimension_columns: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    join_paths: list[dict[str, Any]] = field(default_factory=list)
    total_records: int = 0
    has_sufficient_data: bool = False
    reason: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_tables": self.entity_tables,
            "time_columns": self.time_columns,
            "measure_columns": self.measure_columns,
            "dimension_columns": self.dimension_columns,
            "relationships": self.relationships,
            "join_paths": self.join_paths,
            "total_records": self.total_records,
            "has_sufficient_data": self.has_sufficient_data,
            "reason": self.reason,
        }


@dataclass
class DiscoveredMetric:
    """A discovered numerical or count metric calculated from verifiable data."""
    name: str
    source_table: str
    source_columns: list[str]
    sql: str
    current_value: float
    calculation_method: str
    timestamp_col: Optional[str] = None
    confidence: float = 1.0
    source_tables: list[str] = field(default_factory=list)
    join_path: Optional[dict[str, Any]] = None
    aggregation: Optional[str] = None
    grouping: Optional[list[str]] = None
    filters: Optional[list[str]] = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.source_tables and self.source_table:
            self.source_tables = [self.source_table]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source_table": self.source_table,
            "source_tables": self.source_tables,
            "source_columns": self.source_columns,
            "sql": self.sql,
            "current_value": self.current_value,
            "calculation_method": self.calculation_method,
            "timestamp_col": self.timestamp_col,
            "confidence": self.confidence,
            "join_path": self.join_path,
            "aggregation": self.aggregation,
            "grouping": self.grouping,
            "filters": self.filters,
            "evidence": self.evidence,
        }


@dataclass
class BusinessIntelligenceReport:
    """Comprehensive BI report holding insights, metrics, and contextual summary."""
    insights: list[BusinessInsight] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=lambda: {"total": 0, "critical": 0, "warning": 0, "info": 0})
    business_context: Optional[BusinessContext] = None
    metrics: list[DiscoveredMetric] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = "success"
    message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.status == "success",
            "status": self.status,
            "message": self.message,
            "generated_at": self.generated_at,
            "summary": self.summary,
            "business_context": self.business_context.to_dict() if self.business_context else None,
            "metrics": [m.to_dict() for m in self.metrics],
            "insights": [i.to_dict() for i in self.insights],
        }
