"""backend/app/connectors/mongodb.py

MongoDB Document Database Connector for BG AI 2.0:
- Native collection discovery and document sampling schema inference
- JSON-based and MQL-based query execution
- Read-only protection and bounded result sets
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional

from app.connectors.base import (
    BaseConnector,
    ConnectorCategory,
    ConnectorStatus,
    QueryResult,
)


class MongoDBConnector(BaseConnector):
    """Connector for MongoDB Document Databases."""

    def __init__(
        self,
        connection_id: str,
        name: str,
        host: str = "localhost",
        port: int = 27017,
        database: str = "admin",
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth_source: str = "admin",
        connection_string: Optional[str] = None,
        is_read_only: bool = False,
        user_id: str = "default_user",
    ):
        super().__init__(
            connection_id=connection_id,
            name=name,
            connector_type="mongodb",
            category=ConnectorCategory.DOCUMENT,
            is_read_only=is_read_only,
            user_id=user_id,
        )
        self.host = host
        self.port = int(port or 27017)
        self.database = database
        self.username = username
        self._password = password
        self.auth_source = auth_source
        self._connection_string = connection_string
        self._client: Any = None

    def _get_uri(self) -> str:
        if self._connection_string:
            return self._connection_string
        if self.username and self._password:
            return f"mongodb://{self.username}:{self._password}@{self.host}:{self.port}/{self.database}?authSource={self.auth_source}"
        return f"mongodb://{self.host}:{self.port}/{self.database}"

    def connect(self) -> bool:
        try:
            try:
                import pymongo
            except ImportError:
                raise RuntimeError(
                    "Python driver 'pymongo' is not installed in the environment for MongoDB. "
                    "Install with: pip install pymongo"
                )

            uri = self._get_uri()
            self._client = pymongo.MongoClient(
                uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
            )
            # Test connectivity
            self._client.admin.command("ping")
            self.touch_connected()
            return True
        except Exception as e:
            self.mark_error(str(e))
            self._client = None
            return False

    def disconnect(self) -> bool:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
        self.status = ConnectorStatus.DISCONNECTED
        self.clear_schema_cache()
        return True

    def test_connection(self) -> Dict[str, Any]:
        if self._client is None:
            ok = self.connect()
            if not ok:
                return {
                    "success": False,
                    "connected": False,
                    "error": self.last_error or "Failed to connect to MongoDB",
                }

        try:
            start = time.perf_counter()
            self._client.admin.command("ping")
            elapsed_ms = (time.perf_counter() - start) * 1000
            return {
                "success": True,
                "connected": True,
                "latency_ms": round(elapsed_ms, 2),
                "message": f"Connected to MongoDB database '{self.database}'",
            }
        except Exception as e:
            self.mark_error(str(e))
            return {
                "success": False,
                "connected": False,
                "error": str(e),
            }

    def get_schema(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Inspect MongoDB schema:
        Discovers collections and samples documents to infer fields and types.
        """
        now = time.time()
        if (
            not force_refresh
            and self._schema_cache is not None
            and (now - self._schema_cached_at) < self._cache_ttl_seconds
        ):
            return self._schema_cache

        if self._client is None and not self.connect():
            return {}

        try:
            db = self._client[self.database]
            collection_names = db.list_collection_names()
            schema: Dict[str, Any] = {}

            for col_name in collection_names:
                if col_name.startswith("system."):
                    continue

                col = db[col_name]
                sample_docs = list(col.find().limit(25))

                fields: Dict[str, Any] = {}
                for doc in sample_docs:
                    for k, v in doc.items():
                        t_name = type(v).__name__
                        if k not in fields:
                            fields[k] = {
                                "type": t_name,
                                "nullable": True,
                                "primary_key": k == "_id",
                            }

                schema[col_name] = fields

            self._schema_cache = schema
            self._schema_cached_at = now
            return schema
        except Exception as e:
            self.mark_error(f"MongoDB schema discovery failed: {str(e)}")
            return {}

    def get_stats(self) -> Dict[str, Any]:
        if self._client is None and not self.connect():
            return {"collections": 0, "documents": 0}

        try:
            db = self._client[self.database]
            cols = [c for c in db.list_collection_names() if not c.startswith("system.")]
            total_docs = 0
            for c in cols:
                try:
                    total_docs += db[c].estimated_document_count()
                except Exception:
                    pass

            return {
                "collections": len(cols),
                "documents": total_docs,
            }
        except Exception:
            return {"collections": 0, "documents": 0}

    def execute_query(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> QueryResult:
        """
        Execute MongoDB query.
        Accepts:
          1. JSON query: {"collection": "users", "filter": {"active": true}, "limit": 20}
          2. Simple MQL: db.users.find({"active": true}).limit(20)
        """
        if self._client is None and not self.connect():
            return QueryResult(
                success=False,
                error="MongoDB is not connected.",
                query_dialect="mongodb",
                source_id=self.connection_id,
                source_name=self.name,
            )

        start = time.perf_counter()
        clean = query.strip()

        try:
            db = self._client[self.database]
            collection_name: Optional[str] = None
            query_filter: Dict[str, Any] = {}
            limit: int = 100
            projection: Optional[Dict[str, Any]] = None

            # Attempt JSON parse
            if clean.startswith("{") and clean.endswith("}"):
                data = json.loads(clean)
                collection_name = data.get("collection") or data.get("from")
                query_filter = data.get("filter") or data.get("query") or {}
                projection = data.get("projection")
                limit = min(int(data.get("limit", 100)), 500)
            elif clean.startswith("db."):
                # Basic MQL regex: db.<collection>.find(<filter>)
                match = re.match(r"db\.([a-zA-Z0-9_-]+)\.find\((.*?)\)", clean)
                if match:
                    collection_name = match.group(1)
                    filter_str = match.group(2).strip()
                    if filter_str:
                        query_filter = json.loads(filter_str)
                else:
                    return QueryResult(
                        success=False,
                        error="Unsupported MQL syntax. Use JSON format: {'collection': 'name', 'filter': {...}}",
                        query_dialect="mongodb",
                        source_id=self.connection_id,
                        source_name=self.name,
                    )

            if not collection_name:
                return QueryResult(
                    success=False,
                    error="Missing collection name in query specification.",
                    query_dialect="mongodb",
                    source_id=self.connection_id,
                    source_name=self.name,
                )

            col = db[collection_name]
            cursor = col.find(query_filter, projection).limit(limit)

            raw_docs = list(cursor)
            elapsed_ms = (time.perf_counter() - start) * 1000

            # Normalize ObjectIds and datetime to strings
            rows: List[Dict[str, Any]] = []
            columns_set: set[str] = set()

            for doc in raw_docs:
                clean_row: Dict[str, Any] = {}
                for k, v in doc.items():
                    columns_set.add(k)
                    clean_row[k] = str(v) if not isinstance(v, (int, float, bool, str, list, dict, type(None))) else v
                rows.append(clean_row)

            cols = sorted(list(columns_set))

            return QueryResult(
                success=True,
                columns=cols,
                rows=rows,
                rows_returned=len(rows),
                execution_time_ms=round(elapsed_ms, 2),
                query_dialect="mongodb",
                executed_query=clean,
                source_id=self.connection_id,
                source_name=self.name,
            )

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return QueryResult(
                success=False,
                error=str(e),
                execution_time_ms=round(elapsed_ms, 2),
                query_dialect="mongodb",
                executed_query=clean,
                source_id=self.connection_id,
                source_name=self.name,
            )

    def to_sanitized_config(self) -> Dict[str, Any]:
        return {
            "type": "mongodb",
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
            "auth_source": self.auth_source,
            "password": "***" if self._password else None,
        }

