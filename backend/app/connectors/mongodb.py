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
from urllib.parse import quote_plus

from app.connectors.base import (
    BaseConnector,
    ConnectorCapabilities,
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
        database: str = "bg_ai_db",
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth_source: Optional[str] = None,
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
        self.auth_source = auth_source or database or "bg_ai_db"
        self._connection_string = connection_string
        self._client: Any = None

    def _get_uri(self) -> str:
        """Build a MongoDB URI with credentials safely percent-encoded.

        MongoDB usernames/passwords may contain reserved URI characters such as
        @, :, /, ?, #, and %. Encoding them prevents URI parsing/authentication
        errors. A complete user-supplied URI is intentionally left unchanged.
        """
        if self._connection_string:
            return self._connection_string

        database = quote_plus(str(self.database or "bg_ai_db"))
        if self.username and self._password:
            username = quote_plus(str(self.username), safe="")
            password = quote_plus(str(self._password), safe="")
            effective_auth = self.auth_source or self.database or "bg_ai_db"
            auth_source = quote_plus(str(effective_auth), safe="")
            return (
                f"mongodb://{username}:{password}@{self.host}:{self.port}/"
                f"{database}?authSource={auth_source}"
            )
        return f"mongodb://{self.host}:{self.port}/{database}"

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

            server_read_only = False
            try:
                hello_res = self._client.admin.command("hello")
                if hello_res.get("readOnly") is True:
                    server_read_only = True
            except Exception:
                pass

            return {
                "success": True,
                "connected": True,
                "latency_ms": round(elapsed_ms, 2),
                "is_read_only": self.is_read_only or server_read_only,
                "server_read_only": server_read_only,
                "access_mode": "Read-Only" if (self.is_read_only or server_read_only) else "Read/Write",
                "message": f"Connected to MongoDB database '{self.database}'" + (" (Server Read-Only)" if server_read_only else ""),
                "capabilities": self.get_capabilities().to_dict(),
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

    def _clean_val(self, val: Any) -> Any:
        if val is None:
            return None
        if hasattr(val, "isoformat"):
            return val.isoformat()
        t_name = type(val).__name__
        if t_name == "ObjectId":
            return str(val)
        if isinstance(val, dict):
            return {k: self._clean_val(v) for k, v in val.items()}
        if isinstance(val, list):
            return [self._clean_val(item) for item in val]
        return val

    def _parse_pk(self, val: Any) -> Any:
        try:
            from bson import ObjectId
            if isinstance(val, str) and len(val) == 24:
                return ObjectId(val)
        except Exception:
            pass
        return val

    def execute_query(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> QueryResult:
        """
        Execute MongoDB query or command.
        Supports:
          1. JSON query/command:
             - Find: {"collection": "users", "filter": {"status": "active"}, "limit": 25}
             - Aggregate: {"collection": "orders", "pipeline": [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]}
             - Insert: {"action": "insert", "collection": "users", "doc": {"name": "Alice"}}
             - Update: {"action": "update", "collection": "users", "filter": {"name": "Alice"}, "update": {"$set": {"status": "active"}}}
             - Delete: {"action": "delete", "collection": "users", "filter": {"name": "Alice"}}
             - Count: {"action": "count", "collection": "users"}
          2. MQL operations:
             - db.users.find({...}).limit(20)
             - db.users.aggregate([...])
             - db.users.insertOne({...})
             - db.users.updateOne({...}, {...})
             - db.users.deleteOne({...})
             - db.users.countDocuments({...})
             - db.createCollection("name")
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
            action = "find"
            collection_name: Optional[str] = None
            query_filter: Dict[str, Any] = {}
            doc_payload: Optional[Dict[str, Any]] = None
            update_payload: Optional[Dict[str, Any]] = None
            pipeline: Optional[List[Dict[str, Any]]] = None
            limit: int = 100
            projection: Optional[Dict[str, Any]] = None

            # 1. Parse JSON
            if clean.startswith("{") and clean.endswith("}"):
                data = json.loads(clean)
                action = data.get("action", "find").lower()
                collection_name = data.get("collection") or data.get("from")
                query_filter = data.get("filter") or data.get("query") or {}
                doc_payload = data.get("doc") or data.get("document") or data.get("data")
                update_payload = data.get("update")
                pipeline = data.get("pipeline")
                projection = data.get("projection")
                limit = min(int(data.get("limit", 100)), 500)
                if pipeline is not None and action == "find":
                    action = "aggregate"

            # 2. Parse MQL
            elif clean.startswith("db."):
                # db.createCollection("reviews")
                m_create = re.match(r'db\.createCollection\(["\']([a-zA-Z0-9_-]+)["\']\)', clean)
                if m_create:
                    action = "create_collection"
                    collection_name = m_create.group(1)
                else:
                    # db.<col>.<op>(...)
                    m_op = re.match(r'db\.([a-zA-Z0-9_-]+)\.([a-zA-Z0-9_]+)\((.*)\)', clean, re.DOTALL)
                    if m_op:
                        collection_name = m_op.group(1)
                        op_name = m_op.group(2)
                        args_str = m_op.group(3).strip()

                        if op_name in ("find", "find_one"):
                            action = "find"
                            if args_str:
                                # parse find(filter) or find(filter).limit(n)
                                query_filter = json.loads(args_str.split(").limit(")[0]) if args_str.startswith("{") else {}
                                if ".limit(" in args_str:
                                    try:
                                        limit = int(args_str.split(".limit(")[1].rstrip(")"))
                                    except Exception:
                                        pass
                        elif op_name in ("aggregate",):
                            action = "aggregate"
                            pipeline = json.loads(args_str) if args_str.startswith("[") else []
                        elif op_name in ("insertOne", "insert"):
                            action = "insert"
                            doc_payload = json.loads(args_str) if args_str else {}
                        elif op_name in ("updateOne", "update"):
                            action = "update"
                            # split filter and update object
                            parts = re.split(r",\s*\{", args_str, maxsplit=1)
                            if len(parts) == 2:
                                query_filter = json.loads(parts[0])
                                update_payload = json.loads("{" + parts[1])
                        elif op_name in ("deleteOne", "delete", "remove"):
                            action = "delete"
                            query_filter = json.loads(args_str) if args_str else {}
                        elif op_name in ("countDocuments", "count"):
                            action = "count"
                            query_filter = json.loads(args_str) if args_str.startswith("{") else {}
                        elif op_name in ("drop",):
                            action = "drop_collection"

            if not collection_name:
                return QueryResult(
                    success=False,
                    error="Missing collection name in MongoDB query. Example: db.users.find({}) or {'collection': 'users'}",
                    query_dialect="mongodb",
                    source_id=self.connection_id,
                    source_name=self.name,
                )

            # Check Read-Only for mutations
            if self.is_read_only and action in ("insert", "update", "delete", "create_collection", "drop_collection"):
                return QueryResult(
                    success=False,
                    error=f"Connection '{self.name}' is READ-ONLY. Action '{action}' is blocked.",
                    query_dialect="mongodb",
                    source_id=self.connection_id,
                    source_name=self.name,
                )

            col = db[collection_name]

            # Execute action
            if action == "find":
                cursor = col.find(query_filter, projection).limit(limit)
                raw_docs = list(cursor)
                elapsed_ms = (time.perf_counter() - start) * 1000

                rows: List[Dict[str, Any]] = [self._clean_val(doc) for doc in raw_docs]
                cols = sorted(list({k for r in rows for k in r.keys()})) if rows else ["_id"]

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

            elif action == "aggregate":
                cursor = col.aggregate(pipeline or [], allowDiskUse=True)
                raw_docs = list(cursor)
                elapsed_ms = (time.perf_counter() - start) * 1000

                rows = [self._clean_val(doc) for doc in raw_docs]
                cols = sorted(list({k for r in rows for k in r.keys()})) if rows else []

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

            elif action == "insert":
                if not doc_payload:
                    raise ValueError("Document payload required for insert operation.")
                res = col.insert_one(doc_payload)
                elapsed_ms = (time.perf_counter() - start) * 1000

                return QueryResult(
                    success=True,
                    columns=["inserted_id"],
                    rows=[{"inserted_id": str(res.inserted_id)}],
                    rows_returned=1,
                    affected_rows=1,
                    execution_time_ms=round(elapsed_ms, 2),
                    query_dialect="mongodb",
                    executed_query=clean,
                    source_id=self.connection_id,
                    source_name=self.name,
                )

            elif action == "update":
                if not update_payload:
                    raise ValueError("Update modifications required for update operation.")
                # Ensure $set wrapper if not present
                if not any(k.startswith("$") for k in update_payload.keys()):
                    update_payload = {"$set": update_payload}
                res = col.update_one(query_filter, update_payload)
                elapsed_ms = (time.perf_counter() - start) * 1000

                return QueryResult(
                    success=True,
                    columns=["modified_count", "matched_count"],
                    rows=[{"modified_count": res.modified_count, "matched_count": res.matched_count}],
                    rows_returned=1,
                    affected_rows=res.modified_count,
                    execution_time_ms=round(elapsed_ms, 2),
                    query_dialect="mongodb",
                    executed_query=clean,
                    source_id=self.connection_id,
                    source_name=self.name,
                )

            elif action == "delete":
                res = col.delete_one(query_filter)
                elapsed_ms = (time.perf_counter() - start) * 1000

                return QueryResult(
                    success=True,
                    columns=["deleted_count"],
                    rows=[{"deleted_count": res.deleted_count}],
                    rows_returned=1,
                    affected_rows=res.deleted_count,
                    execution_time_ms=round(elapsed_ms, 2),
                    query_dialect="mongodb",
                    executed_query=clean,
                    source_id=self.connection_id,
                    source_name=self.name,
                )

            elif action == "count":
                cnt = col.count_documents(query_filter)
                elapsed_ms = (time.perf_counter() - start) * 1000

                return QueryResult(
                    success=True,
                    columns=["count"],
                    rows=[{"count": cnt}],
                    rows_returned=1,
                    execution_time_ms=round(elapsed_ms, 2),
                    query_dialect="mongodb",
                    executed_query=clean,
                    source_id=self.connection_id,
                    source_name=self.name,
                )

            elif action == "create_collection":
                db.create_collection(collection_name)
                elapsed_ms = (time.perf_counter() - start) * 1000
                self.clear_schema_cache()

                return QueryResult(
                    success=True,
                    columns=["collection"],
                    rows=[{"collection": collection_name, "status": "created"}],
                    rows_returned=1,
                    affected_rows=1,
                    execution_time_ms=round(elapsed_ms, 2),
                    query_dialect="mongodb",
                    executed_query=clean,
                    source_id=self.connection_id,
                    source_name=self.name,
                )

            else:
                return QueryResult(
                    success=False,
                    error=f"Unsupported MongoDB action: '{action}'",
                    query_dialect="mongodb",
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
        """Fetch paginated, searchable documents from a MongoDB collection."""
        if self._client is None and not self.connect():
            raise RuntimeError("MongoDB connection is not established.")

        db = self._client[self.database]
        col = db[entity]

        safe_limit = min(max(1, limit), 200)
        safe_offset = max(0, offset)
        sort_order = 1 if str(sort_dir).lower() == "asc" else -1

        query_filter: Dict[str, Any] = {}

        # 1. Text search across fields
        if search and search.strip():
            # Search by regex across common fields or sample fields
            query_filter["$or"] = [
                {"name": {"$regex": search.strip(), "$options": "i"}},
                {"title": {"$regex": search.strip(), "$options": "i"}},
                {"email": {"$regex": search.strip(), "$options": "i"}},
                {"status": {"$regex": search.strip(), "$options": "i"}},
                {"code": {"$regex": search.strip(), "$options": "i"}},
            ]

        # 2. Field filters
        if filters and isinstance(filters, dict):
            for f_k, f_v in filters.items():
                if f_v is not None and f_k != "$or":
                    query_filter[f_k] = self._parse_pk(f_v) if f_k == "_id" else f_v

        # Sorting
        sort_field = sort_by or "_id"
        sort_spec = [(sort_field, sort_order)]

        cursor = col.find(query_filter).sort(sort_spec).skip(safe_offset).limit(safe_limit)
        raw_docs = list(cursor)

        # Fast count optimization: if on first page and returned docs < safe_limit, exact total is known without scanning collection
        if safe_offset == 0 and len(raw_docs) < safe_limit and not query_filter:
            total_count = len(raw_docs)
        elif not query_filter:
            try:
                total_count = col.estimated_document_count()
            except Exception:
                total_count = col.count_documents(query_filter)
        else:
            try:
                total_count = col.count_documents(query_filter)
            except Exception:
                total_count = col.estimated_document_count()

        records = [self._clean_val(doc) for doc in raw_docs]
        col_names = sorted(list({k for r in records for k in r.keys()})) if records else ["_id"]

        return {
            "success": True,
            "entity": entity,
            "records": records,
            "columns": col_names,
            "total_count": total_count,
            "limit": safe_limit,
            "offset": safe_offset,
            "primary_keys": ["_id"],
            "is_read_only": self.is_read_only,
        }

    def create_record(self, entity: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a document into collection."""
        if self.is_read_only:
            raise PermissionError(f"Connection '{self.name}' is READ-ONLY.")
        if self._client is None and not self.connect():
            raise RuntimeError("MongoDB is not connected.")

        db = self._client[self.database]
        col = db[entity]

        clean_doc = dict(data)
        if "_id" in clean_doc and not clean_doc["_id"]:
            clean_doc.pop("_id")

        res = col.insert_one(clean_doc)

        return {
            "success": True,
            "inserted_id": str(res.inserted_id),
            "affected_rows": 1,
            "message": f"Document inserted into '{entity}' successfully.",
        }

    def update_record(self, entity: str, primary_key: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a document identified by _id or primary key."""
        if self.is_read_only:
            raise PermissionError(f"Connection '{self.name}' is READ-ONLY.")
        if self._client is None and not self.connect():
            raise RuntimeError("MongoDB is not connected.")

        db = self._client[self.database]
        col = db[entity]

        filter_spec: Dict[str, Any] = {}
        for pk_k, pk_v in primary_key.items():
            filter_spec[pk_k] = self._parse_pk(pk_v) if pk_k == "_id" else pk_v

        clean_data = {k: v for k, v in data.items() if k != "_id"}
        res = col.update_one(filter_spec, {"$set": clean_data})

        return {
            "success": True,
            "affected_rows": res.modified_count,
            "message": f"Document in '{entity}' updated successfully ({res.modified_count} updated).",
        }

    def delete_record(self, entity: str, primary_key: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a document identified by _id or primary key."""
        if self.is_read_only:
            raise PermissionError(f"Connection '{self.name}' is READ-ONLY.")
        if self._client is None and not self.connect():
            raise RuntimeError("MongoDB is not connected.")

        db = self._client[self.database]
        col = db[entity]

        filter_spec: Dict[str, Any] = {}
        for pk_k, pk_v in primary_key.items():
            filter_spec[pk_k] = self._parse_pk(pk_v) if pk_k == "_id" else pk_v

        res = col.delete_one(filter_spec)

        return {
            "success": True,
            "affected_rows": res.deleted_count,
            "message": f"Document deleted from '{entity}' successfully ({res.deleted_count} deleted).",
        }

    def create_entity(self, name: str, definition: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new collection."""
        if self.is_read_only:
            raise PermissionError(f"Connection '{self.name}' is READ-ONLY.")
        if self._client is None and not self.connect():
            raise RuntimeError("MongoDB is not connected.")

        db = self._client[self.database]
        db.create_collection(name.strip())
        self.clear_schema_cache()

        return {"success": True, "message": f"Collection '{name}' created successfully."}

    def rename_entity(self, old_name: str, new_name: str) -> Dict[str, Any]:
        """Rename an existing collection."""
        if self.is_read_only:
            raise PermissionError(f"Connection '{self.name}' is READ-ONLY.")
        if self._client is None and not self.connect():
            raise RuntimeError("MongoDB is not connected.")

        db = self._client[self.database]
        db[old_name].rename(new_name.strip())
        self.clear_schema_cache()

        return {"success": True, "message": f"Collection '{old_name}' renamed to '{new_name}'."}

    def drop_entity(self, name: str) -> Dict[str, Any]:
        """Drop a collection."""
        if self.is_read_only:
            raise PermissionError(f"Connection '{self.name}' is READ-ONLY.")
        if self._client is None and not self.connect():
            raise RuntimeError("MongoDB is not connected.")

        db = self._client[self.database]
        db.drop_collection(name.strip())
        self.clear_schema_cache()

        return {"success": True, "message": f"Collection '{name}' dropped successfully."}

    def create_index(self, entity: str, fields: List[str], index_name: Optional[str] = None, unique: bool = False) -> Dict[str, Any]:
        """Create an index on specified fields of collection."""
        if self.is_read_only:
            raise PermissionError(f"Connection '{self.name}' is configured as READ-ONLY.")
        if self._client is None and not self.connect():
            raise RuntimeError("MongoDB is not connected.")
        if not fields:
            raise ValueError("At least one field is required to create an index.")

        import pymongo
        db = self._client[self.database]
        col = db[entity]
        keys = [(f, pymongo.ASCENDING) for f in fields]
        kwargs = {}
        if index_name:
            kwargs["name"] = index_name
        if unique:
            kwargs["unique"] = True
        idx_res = col.create_index(keys, **kwargs)
        self.clear_schema_cache()
        return {"success": True, "index_name": idx_res, "message": f"{'Unique index' if unique else 'Index'} '{idx_res}' created on collection '{entity}'."}

    def drop_index(self, entity: str, index_name: str) -> Dict[str, Any]:
        """Drop an index from collection."""
        if self.is_read_only:
            raise PermissionError(f"Connection '{self.name}' is configured as READ-ONLY.")
        if self._client is None and not self.connect():
            raise RuntimeError("MongoDB is not connected.")

        db = self._client[self.database]
        col = db[entity]
        col.drop_index(index_name)
        self.clear_schema_cache()
        return {"success": True, "index_name": index_name, "message": f"Index '{index_name}' dropped from '{entity}'."}

    def get_capabilities(self) -> ConnectorCapabilities:
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
                read_only_reason=f"Connection '{self.name}' is explicitly configured as Read-Only.",
            )
        return ConnectorCapabilities(
            can_read_data=True,
            can_insert_records=True,
            can_update_records=True,
            can_delete_records=True,
            can_create_entities=True,
            can_alter_schema=True,
            can_manage_indexes=True,
            can_execute_raw_queries=True,
            supports_transactions=True,
            read_only_reason=None,
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

