"""backend/app/connectors/__init__.py

BG AI 2.0 Multi-Database Connectors Package.
"""

from app.connectors.base import (
    BaseConnector,
    ConnectorCategory,
    ConnectorStatus,
    QueryResult,
    VectorDocument,
    VectorSearchResult,
)
from app.connectors.relational import (
    RelationalConnector,
    SQLiteConnector,
    MySQLConnector,
    PostgreSQLConnector,
    MSSQLConnector,
    MariaDBConnector,
)
from app.connectors.mongodb import MongoDBConnector
from app.connectors.vector import (
    VectorConnector,
    QdrantConnector,
    ChromaConnector,
)
from app.connectors.file_connectors import (
    CSVConnector,
    ExcelConnector,
    JSONConnector,
)
from app.connectors.registry import (
    ConnectionRegistry,
    get_connection_registry,
    get_supported_connectors_catalog,
)

__all__ = [
    "BaseConnector",
    "ConnectorCategory",
    "ConnectorStatus",
    "QueryResult",
    "VectorDocument",
    "VectorSearchResult",
    "RelationalConnector",
    "SQLiteConnector",
    "MySQLConnector",
    "PostgreSQLConnector",
    "MSSQLConnector",
    "MariaDBConnector",
    "MongoDBConnector",
    "VectorConnector",
    "QdrantConnector",
    "ChromaConnector",
    "CSVConnector",
    "ExcelConnector",
    "JSONConnector",
    "ConnectionRegistry",
    "get_connection_registry",
    "get_supported_connectors_catalog",
]

