"""backend/app/connectors/base.py

Base connector abstractions and data models for BG AI 2.0 Multi-Database Architecture.
"""

from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class ConnectorCategory(str, Enum):
    RELATIONAL = "relational"
    DOCUMENT = "document"
    VECTOR = "vector"
    FILE = "file"


class ConnectorStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass
class ConnectorCapabilities:
    """Explicit capability matrix for a database connector and connection instance."""
    can_read_data: bool = True
    can_insert_records: bool = True
    can_update_records: bool = True
    can_delete_records: bool = True
    can_create_entities: bool = True
    can_alter_schema: bool = True
    can_manage_indexes: bool = True
    can_execute_raw_queries: bool = True
    supports_transactions: bool = True
    read_only_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "can_read_data": self.can_read_data,
            "can_insert_records": self.can_insert_records,
            "can_update_records": self.can_update_records,
            "can_delete_records": self.can_delete_records,
            "can_create_entities": self.can_create_entities,
            "can_alter_schema": self.can_alter_schema,
            "can_manage_indexes": self.can_manage_indexes,
            "can_execute_raw_queries": self.can_execute_raw_queries,
            "supports_transactions": self.supports_transactions,
            "read_only_reason": self.read_only_reason,
        }


@dataclass
class QueryResult:
    """Standardized result returned by connector execution."""
    success: bool
    columns: List[str] = field(default_factory=list)
    rows: List[Dict[str, Any]] = field(default_factory=list)
    rows_returned: int = 0
    execution_time_ms: float = 0.0
    error: Optional[str] = None
    affected_rows: Optional[int] = None
    query_dialect: str = "sql"
    executed_query: Optional[str] = None
    source_id: Optional[str] = None
    source_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "columns": self.columns,
            "rows": self.rows,
            "rows_returned": self.rows_returned,
            "execution_time_ms": self.execution_time_ms,
            "error": self.error,
            "affected_rows": self.affected_rows,
            "query_dialect": self.query_dialect,
            "executed_query": self.executed_query,
            "source_id": self.source_id,
            "source_name": self.source_name,
        }


@dataclass
class VectorDocument:
    """Document payload retrieved from a vector database."""
    id: str
    score: float
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    vector: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "score": round(self.score, 4),
            "text": self.text,
            "metadata": self.metadata,
        }


@dataclass
class VectorSearchResult:
    """Results from a similarity search on a vector collection."""
    success: bool
    collection: str
    query_text: Optional[str] = None
    documents: List[VectorDocument] = field(default_factory=list)
    total_found: int = 0
    execution_time_ms: float = 0.0
    error: Optional[str] = None
    source_id: Optional[str] = None
    source_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "collection": self.collection,
            "query_text": self.query_text,
            "documents": [d.to_dict() for d in self.documents],
            "total_found": self.total_found,
            "execution_time_ms": self.execution_time_ms,
            "error": self.error,
            "source_id": self.source_id,
            "source_name": self.source_name,
        }


class BaseConnector(abc.ABC):
    """
    Abstract Base Class for all BG AI database connectors.
    Each instance manages an isolated connection pool, schema cache, and lifecycle.
    """

    def __init__(
        self,
        connection_id: str,
        name: str,
        connector_type: str,
        category: ConnectorCategory,
        is_read_only: bool = False,
        user_id: str = "default_user",
    ):
        self.connection_id = connection_id
        self.name = name
        self.connector_type = connector_type
        self.category = category
        self.is_read_only = is_read_only
        self.user_id = user_id

        self.status: ConnectorStatus = ConnectorStatus.DISCONNECTED
        self.created_at: str = datetime.now(timezone.utc).isoformat()
        self.last_connected_at: Optional[str] = None
        self.last_error: Optional[str] = None

        # Schema & metadata cache
        self._schema_cache: Optional[Dict[str, Any]] = None
        self._schema_cached_at: float = 0.0
        self._cache_ttl_seconds: float = 300.0  # 5 minutes

    @abc.abstractmethod
    def connect(self) -> bool:
        """Establish connection pool/client and verify connectivity."""
        pass

    @abc.abstractmethod
    def disconnect(self) -> bool:
        """Safely dispose connection pool or client."""
        pass

    @abc.abstractmethod
    def test_connection(self) -> Dict[str, Any]:
        """Test live connectivity and return diagnostic dictionary."""
        pass

    @abc.abstractmethod
    def get_schema(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Return schema dictionary. For SQL: {table: {col: info}}. For Vector: {collection: info}."""
        pass

    @abc.abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Return stats: tables/collections count, row/vector count, size, etc."""
        pass

    @abc.abstractmethod
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> QueryResult:
        """Execute query appropriate for this connector."""
        pass

    def clear_schema_cache(self) -> None:
        """Invalidate the schema cache."""
        self._schema_cache = None
        self._schema_cached_at = 0.0

    def get_records(
        self,
        entity: str,
        limit: int = 25,
        offset: int = 0,
        sort_by: Optional[str] = None,
        sort_dir: str = "asc",
        search: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fetch paginated, sortable, searchable records from table or collection."""
        raise NotImplementedError(f"{self.connector_type} does not support browsing records.")

    def create_record(self, entity: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new record or document."""
        raise NotImplementedError(f"{self.connector_type} does not support creating records.")

    def update_record(self, entity: str, primary_key: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing record or document."""
        raise NotImplementedError(f"{self.connector_type} does not support updating records.")

    def delete_record(self, entity: str, primary_key: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a record or document."""
        raise NotImplementedError(f"{self.connector_type} does not support deleting records.")

    def create_entity(self, name: str, definition: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new table or collection."""
        raise NotImplementedError(f"{self.connector_type} does not support creating entities.")

    def rename_entity(self, old_name: str, new_name: str) -> Dict[str, Any]:
        """Rename an existing table or collection."""
        raise NotImplementedError(f"{self.connector_type} does not support renaming entities.")

    def drop_entity(self, name: str) -> Dict[str, Any]:
        """Drop a table or collection."""
        raise NotImplementedError(f"{self.connector_type} does not support dropping entities.")

    def create_index(self, entity: str, fields: List[str], index_name: Optional[str] = None, unique: bool = False) -> Dict[str, Any]:
        """Create an index on specified fields of table or collection."""
        raise NotImplementedError(f"{self.connector_type} does not support creating indexes.")

    def drop_index(self, entity: str, index_name: str) -> Dict[str, Any]:
        """Drop an index from table or collection."""
        raise NotImplementedError(f"{self.connector_type} does not support dropping indexes.")

    def get_capabilities(self) -> ConnectorCapabilities:
        """Return dynamic capabilities supported by this connection."""
        if self.is_read_only:
            return ConnectorCapabilities(
                can_read_data=True,
                can_insert_records=False,
                can_update_records=False,
                can_delete_records=False,
                can_create_entities=False,
                can_alter_schema=False,
                can_manage_indexes=False,
                can_execute_raw_queries=True,
                supports_transactions=True,
                read_only_reason=f"Connection '{self.name}' is configured in Read-Only mode.",
            )
        return ConnectorCapabilities()

    def touch_connected(self) -> None:
        """Update last connected timestamp and status."""
        self.status = ConnectorStatus.CONNECTED
        self.last_connected_at = datetime.now(timezone.utc).isoformat()
        self.last_error = None

    def mark_error(self, err: str) -> None:
        """Record connection error."""
        self.status = ConnectorStatus.ERROR
        self.last_error = str(err)

    @abc.abstractmethod
    def to_sanitized_config(self) -> Dict[str, Any]:
        """Return connector configuration with secrets/passwords redacted."""
        pass

    def to_dict(self, include_schema: bool = False) -> Dict[str, Any]:
        """Public serializable summary of the connection."""
        stats = {}
        try:
            if self.status == ConnectorStatus.CONNECTED:
                stats = self.get_stats()
        except Exception:
            pass

        data: Dict[str, Any] = {
            "connection_id": self.connection_id,
            "name": self.name,
            "connector_type": self.connector_type,
            "category": self.category.value,
            "is_read_only": self.is_read_only,
            "capabilities": self.get_capabilities().to_dict(),
            "status": self.status.value,
            "created_at": self.created_at,
            "last_connected_at": self.last_connected_at,
            "last_error": self.last_error,
            "config": self.to_sanitized_config(),
            "stats": stats,
        }

        if include_schema and self.status == ConnectorStatus.CONNECTED:
            try:
                data["schema"] = self.get_schema()
            except Exception:
                data["schema"] = {}

        return data

