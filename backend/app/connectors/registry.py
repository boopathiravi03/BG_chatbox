"""backend/app/connectors/registry.py

Centralized Multi-Database Connection Registry for BG AI 2.0.
Thread-safe per-user registry managing independent connections, lifecycle,
health status, active source switching, and factory creation.
"""

from __future__ import annotations

import threading
import uuid
from typing import Any, Dict, List, Optional

from app.connectors.base import (
    BaseConnector,
    ConnectorCategory,
    ConnectorStatus,
)
from app.connectors.relational import (
    SQLiteConnector,
    MySQLConnector,
    PostgreSQLConnector,
    MSSQLConnector,
    MariaDBConnector,
)
from app.connectors.mongodb import MongoDBConnector
from app.connectors.redis_connector import RedisConnector
from app.connectors.vector import QdrantConnector, ChromaConnector
from app.connectors.file_connectors import CSVConnector, ExcelConnector, JSONConnector


class ConnectionRegistry:
    """Thread-safe multi-connection registry with per-user isolation."""

    def __init__(self):
        self._lock = threading.RLock()
        # user_id -> dict[connection_id -> BaseConnector]
        self._connections: Dict[str, Dict[str, BaseConnector]] = {}
        # user_id -> active connection_id
        self._active_connections: Dict[str, str] = {}

    def list_connectors(self, user_id: str) -> List[BaseConnector]:
        """List all registered connectors for a user."""
        with self._lock:
            user_map = self._connections.get(user_id, {})
            return list(user_map.values())

    def get_connector(
        self, user_id: str, connection_id: str
    ) -> Optional[BaseConnector]:
        """Retrieve a specific connector by ID for a user."""
        with self._lock:
            user_map = self._connections.get(user_id, {})
            return user_map.get(connection_id)

    def get_active_connector(self, user_id: str) -> Optional[BaseConnector]:
        """Return user's currently selected active connector."""
        with self._lock:
            active_id = self._active_connections.get(user_id)
            user_map = self._connections.get(user_id, {})
            if active_id and active_id in user_map:
                return user_map[active_id]
            # Fallback to first available connector
            if user_map:
                first_id = next(iter(user_map.keys()))
                self._active_connections[user_id] = first_id
                return user_map[first_id]
            return None

    def set_active_connector(self, user_id: str, connection_id: str) -> bool:
        """Switch user's active connector focus."""
        with self._lock:
            user_map = self._connections.get(user_id, {})
            if connection_id in user_map:
                self._active_connections[user_id] = connection_id
                return True
            return False

    def register_connector(self, connector: BaseConnector) -> BaseConnector:
        """Register a connector instance for a user."""
        with self._lock:
            user_id = connector.user_id
            if user_id not in self._connections:
                self._connections[user_id] = {}

            self._connections[user_id][connector.connection_id] = connector

            # If no active connector set yet, set this one
            if user_id not in self._active_connections:
                self._active_connections[user_id] = connector.connection_id

            return connector

    def disconnect_connector(self, user_id: str, connection_id: str) -> bool:
        """Disconnect and stop a specific connection without affecting others."""
        with self._lock:
            user_map = self._connections.get(user_id, {})
            conn = user_map.get(connection_id)
            if conn:
                conn.disconnect()
                return True
            return False

    def remove_connector(self, user_id: str, connection_id: str) -> bool:
        """Disconnect and completely remove a connector from user's registry."""
        with self._lock:
            user_map = self._connections.get(user_id, {})
            conn = user_map.pop(connection_id, None)
            if conn:
                conn.disconnect()

            # If this was active, select another if available
            if self._active_connections.get(user_id) == connection_id:
                if user_map:
                    self._active_connections[user_id] = next(iter(user_map.keys()))
                else:
                    self._active_connections.pop(user_id, None)

            return conn is not None

    def disconnect_all(self, user_id: str) -> bool:
        """Disconnect and remove all connections for a user."""
        with self._lock:
            user_map = self._connections.pop(user_id, {})
            for conn in user_map.values():
                try:
                    conn.disconnect()
                except Exception:
                    pass
            self._active_connections.pop(user_id, None)
            return True

    def rename_connector(self, user_id: str, connection_id: str, new_name: str) -> bool:
        """Rename a connection display name."""
        with self._lock:
            conn = self.get_connector(user_id, connection_id)
            if conn:
                conn.name = new_name.strip()
                return True
            return False

    def update_permissions(
        self, user_id: str, connection_id: str, is_read_only: bool
    ) -> bool:
        """Update read-only permission flag."""
        with self._lock:
            conn = self.get_connector(user_id, connection_id)
            if conn:
                conn.is_read_only = is_read_only
                return True
            return False

    def create_connector_from_config(
        self, user_id: str, config: Dict[str, Any], auto_register: bool = True
    ) -> BaseConnector:
        """
        Factory to instantiate and optionally register a connector from connection parameters.
        """
        c_type = (config.get("connector_type") or config.get("db_type") or "sqlite").lower().strip()
        conn_id = config.get("connection_id") or f"conn_{uuid.uuid4().hex[:10]}"
        name = (config.get("name") or f"{c_type.upper()} Data Source").strip()
        is_read_only = bool(config.get("is_read_only", False))

        connector: BaseConnector

        # Clean string fields to prevent accidental leading/trailing whitespace
        host = str(config.get("host", "localhost") or "localhost").strip()
        database = str(config.get("database", "") or "").strip()
        username = str(config.get("username", "") or "").strip()
        password = str(config.get("password") or "")

        if c_type == "sqlite":
            path = config.get("database") or config.get("database_path") or ":memory:"
            connector = SQLiteConnector(
                connection_id=conn_id,
                name=name,
                database_path=str(path).strip(),
                is_read_only=is_read_only,
                user_id=user_id,
            )
        elif c_type == "mysql":
            connector = MySQLConnector(
                connection_id=conn_id,
                name=name,
                host=host,
                port=int(config.get("port", 3306)),
                database=database,
                username=username or "root",
                password=password,
                is_read_only=is_read_only,
                user_id=user_id,
            )
        elif c_type == "mariadb":
            connector = MariaDBConnector(
                connection_id=conn_id,
                name=name,
                host=host,
                port=int(config.get("port", 3306)),
                database=database,
                username=username or "root",
                password=password,
                is_read_only=is_read_only,
                user_id=user_id,
            )
        elif c_type == "postgres":
            connector = PostgreSQLConnector(
                connection_id=conn_id,
                name=name,
                host=host,
                port=int(config.get("port", 5432)),
                database=database,
                username=username or "postgres",
                password=password,
                is_read_only=is_read_only,
                user_id=user_id,
            )
        elif c_type in ("sqlserver", "mssql"):
            connector = MSSQLConnector(
                connection_id=conn_id,
                name=name,
                host=config.get("host", "localhost"),
                port=int(config.get("port", 1433)),
                database=config.get("database", ""),
                username=config.get("username", "sa"),
                password=config.get("password", ""),
                driver=config.get("driver", "ODBC Driver 18 for SQL Server"),
                is_read_only=is_read_only,
                user_id=user_id,
            )
        elif c_type == "mongodb":
            target_db = config.get("database") or "bg_ai_db"
            auth_src = config.get("auth_source") or config.get("authSource") or target_db
            connector = MongoDBConnector(
                connection_id=conn_id,
                name=name,
                host=config.get("host", "localhost"),
                port=int(config.get("port", 27017)),
                database=target_db,
                username=config.get("username"),
                password=config.get("password"),
                auth_source=auth_src,
                connection_string=config.get("connection_string"),
                is_read_only=is_read_only,
                user_id=user_id,
            )
        elif c_type == "redis":
            connector = RedisConnector(
                connection_id=conn_id,
                name=name,
                host=config.get("host", "localhost"),
                port=int(config.get("port", 6379)),
                password=config.get("password"),
                db=int(config.get("db", 0)),
                ssl=bool(config.get("ssl", False)),
                is_read_only=is_read_only,
                user_id=user_id,
            )
        elif c_type == "qdrant":
            connector = QdrantConnector(
                connection_id=conn_id,
                name=name,
                host=config.get("host", "localhost"),
                port=int(config.get("port", 6333)),
                api_key=config.get("api_key"),
                is_read_only=is_read_only,
                user_id=user_id,
            )
        elif c_type == "chroma":
            connector = ChromaConnector(
                connection_id=conn_id,
                name=name,
                host=config.get("host", "localhost"),
                port=int(config.get("port", 8000)),
                tenant=config.get("tenant", "default_tenant"),
                database=config.get("database", "default_database"),
                is_read_only=is_read_only,
                user_id=user_id,
            )
        elif c_type == "csv":
            connector = CSVConnector(
                connection_id=conn_id,
                name=name,
                file_path=config.get("file_path", ""),
                delimiter=config.get("delimiter", ","),
                is_read_only=is_read_only,
                user_id=user_id,
            )
        elif c_type == "excel":
            connector = ExcelConnector(
                connection_id=conn_id,
                name=name,
                file_path=config.get("file_path", ""),
                is_read_only=is_read_only,
                user_id=user_id,
            )
        elif c_type == "json":
            connector = JSONConnector(
                connection_id=conn_id,
                name=name,
                file_path=config.get("file_path", ""),
                is_read_only=is_read_only,
                user_id=user_id,
            )
        else:
            raise ValueError(f"Unsupported connector type: '{c_type}'")

        if auto_register:
            return self.register_connector(connector)
        return connector


# Global singleton registry instance
_global_registry = ConnectionRegistry()


def get_connection_registry() -> ConnectionRegistry:
    return _global_registry


def get_supported_connectors_catalog() -> List[Dict[str, Any]]:
    """
    Catalog of all connectors supported in BG AI 2.0.
    """
    return [
        # Priority 1: Core Relational
        {
            "id": "sqlite",
            "name": "SQLite",
            "category": "relational",
            "description": "Embedded fast ACID relational database and local file databases",
            "default_port": None,
            "badge": "Built-in",
            "status": "ready",
            "fields": ["database_path"],
        },
        {
            "id": "mysql",
            "name": "MySQL",
            "category": "relational",
            "description": "World's most popular open-source relational database server",
            "default_port": 3306,
            "badge": "Popular",
            "status": "ready",
            "fields": ["host", "port", "database", "username", "password"],
        },
        {
            "id": "postgres",
            "name": "PostgreSQL",
            "category": "relational",
            "description": "Advanced enterprise-grade object-relational database",
            "default_port": 5432,
            "badge": "Enterprise",
            "status": "ready",
            "fields": ["host", "port", "database", "username", "password"],
        },
        {
            "id": "mariadb",
            "name": "MariaDB",
            "category": "relational",
            "description": "High-performance drop-in replacement for MySQL",
            "default_port": 3306,
            "badge": "Fast",
            "status": "ready",
            "fields": ["host", "port", "database", "username", "password"],
        },
        {
            "id": "mssql",
            "name": "Microsoft SQL Server",
            "category": "relational",
            "description": "Microsoft enterprise relational database management system",
            "default_port": 1433,
            "badge": "Enterprise",
            "status": "ready",
            "fields": ["host", "port", "database", "username", "password", "driver"],
        },
        # Priority 2: NoSQL & Key-Value
        {
            "id": "mongodb",
            "name": "MongoDB",
            "category": "document",
            "description": "Document-based distributed NoSQL database with flexible JSON schemas",
            "default_port": 27017,
            "badge": "Document",
            "status": "ready",
            "fields": ["host", "port", "database", "username", "password", "auth_source"],
        },
        {
            "id": "redis",
            "name": "Redis",
            "category": "document",
            "description": "Blazing-fast in-memory key-value data store and cache",
            "default_port": 6379,
            "badge": "Key-Value",
            "status": "ready",
            "fields": ["host", "port", "password", "db", "ssl"],
        },
        # Priority 3: Vector Databases
        {
            "id": "qdrant",
            "name": "Qdrant",
            "category": "vector",
            "description": "Vector search engine and vector database with payload filtering",
            "default_port": 6333,
            "badge": "Vector AI",
            "status": "ready",
            "fields": ["host", "port", "api_key"],
        },
        {
            "id": "chroma",
            "name": "Chroma DB",
            "category": "vector",
            "description": "Open-source AI-native embedding database for LLM applications",
            "default_port": 8000,
            "badge": "Embeddings",
            "status": "ready",
            "fields": ["host", "port", "tenant", "database"],
        },
        # Priority 3: Files & Flat Sources
        {
            "id": "csv",
            "name": "CSV Data Source",
            "category": "file",
            "description": "Query tabular comma/tab-separated values with full SQL capabilities",
            "default_port": None,
            "badge": "Tabular",
            "status": "ready",
            "fields": ["file_path", "delimiter"],
        },
        {
            "id": "excel",
            "name": "Excel Workbook",
            "category": "file",
            "description": "Transform sheets in .xlsx/.xls workbooks into queryable SQL tables",
            "default_port": None,
            "badge": "Spreadsheet",
            "status": "ready",
            "fields": ["file_path"],
        },
        {
            "id": "json",
            "name": "JSON File Source",
            "category": "file",
            "description": "Analyze structured and nested JSON files using relational schemas",
            "default_port": None,
            "badge": "Semi-structured",
            "status": "ready",
            "fields": ["file_path"],
        },
    ]

