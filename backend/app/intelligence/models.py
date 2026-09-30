from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Literal


@dataclass
class AttentionItem:
    id: str
    category: Literal["critical", "warning", "performance", "insight", "healthy"]
    title: str
    description: str
    table: str | None = None
    column: str | None = None
    target_module: Literal["health", "explorer", "sqllab", "analytics"] = "health"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DataQualitySummary:
    null_percentage: float = 0.0
    empty_tables: list[str] = field(default_factory=list)
    null_heavy_columns: list[dict[str, Any]] = field(default_factory=list)
    duplicate_table_schemas: list[list[str]] = field(default_factory=list)
    orphan_foreign_keys: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PerformanceFinding:
    type: str
    table: str
    column: str | None
    description: str
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BusinessMetric:
    label: str
    value: str
    table: str
    column: str
    calculation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DatabaseIntelligenceReport:
    database_type: str
    database_name: str
    total_tables: int
    total_rows: int
    total_columns: int
    total_relationships: int
    health_score: int
    schema_summary: dict[str, list[dict[str, Any]]]
    data_quality: DataQualitySummary
    performance_findings: list[PerformanceFinding]
    business_metrics: list[BusinessMetric]
    attention_items: list[AttentionItem]
    scan_timestamp: str
    scan_duration_ms: int
    is_partial: bool = False
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "database_type": self.database_type,
            "database_name": self.database_name,
            "total_tables": self.total_tables,
            "total_rows": self.total_rows,
            "total_columns": self.total_columns,
            "total_relationships": self.total_relationships,
            "health_score": self.health_score,
            "schema_summary": self.schema_summary,
            "data_quality": self.data_quality.to_dict(),
            "performance_findings": [f.to_dict() for f in self.performance_findings],
            "business_metrics": [m.to_dict() for m in self.business_metrics],
            "attention_items": [item.to_dict() for item in self.attention_items],
            "scan_timestamp": self.scan_timestamp,
            "scan_duration_ms": self.scan_duration_ms,
            "is_partial": self.is_partial,
            "error_message": self.error_message,
        }
