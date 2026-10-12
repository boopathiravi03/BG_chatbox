"""backend/app/intelligence/cross_db/models.py

Data structures for BG AI 2.0 Intelligent Cross-Database Querying & Federation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class QueryIntentType(str, Enum):
    SINGLE_SOURCE = "single_source"
    CROSS_SOURCE = "cross_source"
    VECTOR_SEARCH = "vector_search"
    AMBIGUOUS = "ambiguous"
    GENERAL = "general"


@dataclass
class SourceQueryPlan:
    """A sub-query planned for a specific database connector."""
    source_id: str
    source_name: str
    connector_type: str
    query_text: str
    expected_entity: str
    query_type: str = "sql"  # "sql" | "mongodb" | "vector"
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "connector_type": self.connector_type,
            "query_text": self.query_text,
            "expected_entity": self.expected_entity,
            "query_type": self.query_type,
        }


@dataclass
class SourceQueryResult:
    """Execution result for a single source."""
    source_id: str
    source_name: str
    connector_type: str
    query_text: str
    success: bool
    columns: List[str] = field(default_factory=list)
    rows: List[Dict[str, Any]] = field(default_factory=list)
    rows_returned: int = 0
    execution_time_ms: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "connector_type": self.connector_type,
            "query_text": self.query_text,
            "success": self.success,
            "columns": self.columns,
            "rows": self.rows,
            "rows_returned": self.rows_returned,
            "execution_time_ms": self.execution_time_ms,
            "error": self.error,
        }


@dataclass
class CrossDatabaseResponse:
    """Unified response containing multi-source data and explanation."""
    intent: QueryIntentType
    sources_used: List[Dict[str, Any]] = field(default_factory=list)
    sub_results: List[SourceQueryResult] = field(default_factory=list)
    combined_result: Optional[Dict[str, Any]] = None
    explanation: str = ""
    combination_strategy: Optional[str] = None  # "key_join" | "multi_metric" | "direct" | "none"
    chart: Optional[Dict[str, Any]] = None
    requires_disambiguation: bool = False
    disambiguation_options: List[Dict[str, str]] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent.value,
            "sources_used": self.sources_used,
            "sub_results": [r.to_dict() for r in self.sub_results],
            "combined_result": self.combined_result,
            "explanation": self.explanation,
            "combination_strategy": self.combination_strategy,
            "chart": self.chart,
            "requires_disambiguation": self.requires_disambiguation,
            "disambiguation_options": self.disambiguation_options,
            "error": self.error,
        }

