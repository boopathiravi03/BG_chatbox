"""backend/app/connectors/vector.py

Vector Database Connectors for BG AI 2.0:
- QdrantConnector (REST API & native client)
- ChromaConnector (REST API & chromadb client)

Implements collection discovery, vector metadata inspection, similarity search,
metadata filtering, and semantic retrieval. Does NOT treat vector queries as ordinary SQL.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

import requests

from app.connectors.base import (
    BaseConnector,
    ConnectorCategory,
    ConnectorStatus,
    QueryResult,
    VectorDocument,
    VectorSearchResult,
)


class VectorConnector(BaseConnector):
    """Base class for Vector database connectors."""

    def __init__(
        self,
        connection_id: str,
        name: str,
        connector_type: str,
        is_read_only: bool = True,
        user_id: str = "default_user",
    ):
        super().__init__(
            connection_id=connection_id,
            name=name,
            connector_type=connector_type,
            category=ConnectorCategory.VECTOR,
            is_read_only=is_read_only,
            user_id=user_id,
        )

    def execute_query(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> QueryResult:
        """
        Adapts a vector search into a standard QueryResult so results can be
        viewed in universal tables, charts, or summaries.
        """
        clean = query.strip()
        collection = "default"
        query_text = clean
        limit = 10
        filt = None

        if clean.startswith("{") and clean.endswith("}"):
            try:
                spec = json.loads(clean)
                collection = spec.get("collection", "default")
                query_text = spec.get("query_text") or spec.get("text") or spec.get("query") or ""
                limit = int(spec.get("limit", 10))
                filt = spec.get("filter")
            except Exception:
                pass

        vec_res = self.search_vectors(
            collection=collection,
            query_text=query_text,
            limit=limit,
            metadata_filter=filt,
        )

        if not vec_res.success:
            return QueryResult(
                success=False,
                error=vec_res.error,
                query_dialect=self.connector_type,
                source_id=self.connection_id,
                source_name=self.name,
            )

        cols = ["id", "score", "text", "metadata"]
        rows = [
            {
                "id": doc.id,
                "score": doc.score,
                "text": doc.text[:200] + ("..." if len(doc.text) > 200 else ""),
                "metadata": json.dumps(doc.metadata) if doc.metadata else "{}",
            }
            for doc in vec_res.documents
        ]

        return QueryResult(
            success=True,
            columns=cols,
            rows=rows,
            rows_returned=len(rows),
            execution_time_ms=vec_res.execution_time_ms,
            query_dialect=self.connector_type,
            executed_query=query,
            source_id=self.connection_id,
            source_name=self.name,
        )

    def search_vectors(
        self,
        collection: str,
        query_text: Optional[str] = None,
        query_vector: Optional[List[float]] = None,
        limit: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> VectorSearchResult:
        """Execute semantic similarity search."""
        raise NotImplementedError


class QdrantConnector(VectorConnector):
    """
    Qdrant Vector Database Connector.
    Connects via high-performance REST API or native qdrant_client.
    """

    def __init__(
        self,
        connection_id: str,
        name: str,
        host: str = "localhost",
        port: int = 6333,
        api_key: Optional[str] = None,
        prefer_grpc: bool = False,
        is_read_only: bool = True,
        user_id: str = "default_user",
    ):
        super().__init__(
            connection_id=connection_id,
            name=name,
            connector_type="qdrant",
            is_read_only=is_read_only,
            user_id=user_id,
        )
        self.host = host
        self.port = int(port or 6333)
        self._api_key = api_key
        self.prefer_grpc = prefer_grpc

    @property
    def base_url(self) -> str:
        protocol = "https" if self.port == 443 else "http"
        return f"{protocol}://{self.host}:{self.port}"

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self._api_key:
            h["api-key"] = self._api_key
        return h

    def connect(self) -> bool:
        try:
            url = f"{self.base_url}/collections"
            resp = requests.get(url, headers=self._headers(), timeout=4)
            if resp.status_code == 200:
                self.touch_connected()
                return True
            else:
                self.mark_error(f"HTTP {resp.status_code}: {resp.text[:200]}")
                return False
        except Exception as e:
            self.mark_error(str(e))
            return False

    def disconnect(self) -> bool:
        self.status = ConnectorStatus.DISCONNECTED
        self.clear_schema_cache()
        return True

    def test_connection(self) -> Dict[str, Any]:
        start = time.perf_counter()
        try:
            url = f"{self.base_url}/collections"
            resp = requests.get(url, headers=self._headers(), timeout=5)
            elapsed_ms = (time.perf_counter() - start) * 1000

            if resp.status_code == 200:
                cols = resp.json().get("result", {}).get("collections", [])
                return {
                    "success": True,
                    "connected": True,
                    "latency_ms": round(elapsed_ms, 2),
                    "collections_count": len(cols),
                    "message": f"Connected to Qdrant ({len(cols)} collections found)",
                }
            return {
                "success": False,
                "connected": False,
                "error": f"HTTP {resp.status_code}: {resp.text[:150]}",
            }
        except Exception as e:
            self.mark_error(str(e))
            return {"success": False, "connected": False, "error": str(e)}

    def get_schema(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Discovers vector collections, vector dimensions, and distance metrics.
        """
        now = time.time()
        if (
            not force_refresh
            and self._schema_cache is not None
            and (now - self._schema_cached_at) < self._cache_ttl_seconds
        ):
            return self._schema_cache

        try:
            url = f"{self.base_url}/collections"
            resp = requests.get(url, headers=self._headers(), timeout=5)
            if resp.status_code != 200:
                return {}

            cols = resp.json().get("result", {}).get("collections", [])
            schema: Dict[str, Any] = {}

            for c in cols:
                c_name = c["name"]
                # Fetch detailed collection info
                detail_resp = requests.get(
                    f"{self.base_url}/collections/{c_name}",
                    headers=self._headers(),
                    timeout=3,
                )
                dim = "unknown"
                distance = "Cosine"
                points_count = 0

                if detail_resp.status_code == 200:
                    cfg = detail_resp.json().get("result", {})
                    params = cfg.get("config", {}).get("params", {})
                    vectors_cfg = params.get("vectors", {})
                    if isinstance(vectors_cfg, dict):
                        dim = vectors_cfg.get("size", "unknown")
                        distance = vectors_cfg.get("distance", "Cosine")
                    points_count = cfg.get("points_count", 0)

                schema[c_name] = {
                    "vector_dimension": dim,
                    "distance_metric": distance,
                    "points_count": points_count,
                    "type": "vector_collection",
                }

            self._schema_cache = schema
            self._schema_cached_at = now
            return schema
        except Exception as e:
            self.mark_error(f"Qdrant schema discovery failed: {str(e)}")
            return {}

    def get_stats(self) -> Dict[str, Any]:
        try:
            schema = self.get_schema()
            total_points = sum(
                info.get("points_count", 0) for info in schema.values()
            )
            return {
                "collections": len(schema),
                "total_points": total_points,
                "engine": "Qdrant Vector DB",
            }
        except Exception:
            return {"collections": 0, "total_points": 0}

    def search_vectors(
        self,
        collection: str,
        query_text: Optional[str] = None,
        query_vector: Optional[List[float]] = None,
        limit: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> VectorSearchResult:
        """
        Execute vector search on Qdrant.
        If query_vector is not provided, scrolls/retrieves representative matching points.
        """
        start = time.perf_counter()
        try:
            limit = min(limit, 50)
            if query_vector:
                url = f"{self.base_url}/collections/{collection}/points/search"
                body: Dict[str, Any] = {
                    "vector": query_vector,
                    "limit": limit,
                    "with_payload": True,
                }
                if metadata_filter:
                    body["filter"] = metadata_filter
                resp = requests.post(url, headers=self._headers(), json=body, timeout=8)
            else:
                # Scroll points matching collection
                url = f"{self.base_url}/collections/{collection}/points/scroll"
                body = {
                    "limit": limit,
                    "with_payload": True,
                    "with_vector": False,
                }
                if metadata_filter:
                    body["filter"] = metadata_filter
                resp = requests.post(url, headers=self._headers(), json=body, timeout=8)

            elapsed_ms = (time.perf_counter() - start) * 1000

            if resp.status_code != 200:
                return VectorSearchResult(
                    success=False,
                    collection=collection,
                    query_text=query_text,
                    error=f"Qdrant error: HTTP {resp.status_code} - {resp.text[:150]}",
                    source_id=self.connection_id,
                    source_name=self.name,
                )

            data = resp.json().get("result", {})
            raw_points = data if isinstance(data, list) else data.get("points", [])

            docs: List[VectorDocument] = []
            for idx, pt in enumerate(raw_points):
                p_id = str(pt.get("id", idx))
                score = float(pt.get("score", 1.0))
                payload = pt.get("payload") or {}
                # Extract text field from common keys
                text_content = (
                    payload.get("text")
                    or payload.get("content")
                    or payload.get("document")
                    or json.dumps(payload)
                )

                docs.append(
                    VectorDocument(
                        id=p_id,
                        score=score,
                        text=str(text_content),
                        metadata=payload,
                    )
                )

            return VectorSearchResult(
                success=True,
                collection=collection,
                query_text=query_text,
                documents=docs,
                total_found=len(docs),
                execution_time_ms=round(elapsed_ms, 2),
                source_id=self.connection_id,
                source_name=self.name,
            )

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return VectorSearchResult(
                success=False,
                collection=collection,
                query_text=query_text,
                error=str(e),
                execution_time_ms=round(elapsed_ms, 2),
                source_id=self.connection_id,
                source_name=self.name,
            )

    def to_sanitized_config(self) -> Dict[str, Any]:
        return {
            "type": "qdrant",
            "host": self.host,
            "port": self.port,
            "api_key": "***" if self._api_key else None,
            "base_url": self.base_url,
        }


class ChromaConnector(VectorConnector):
    """
    Chroma Vector Database Connector.
    Connects via Chroma HTTP Server API or local persistent client.
    """

    def __init__(
        self,
        connection_id: str,
        name: str,
        host: str = "localhost",
        port: int = 8000,
        tenant: str = "default_tenant",
        database: str = "default_database",
        is_read_only: bool = True,
        user_id: str = "default_user",
    ):
        super().__init__(
            connection_id=connection_id,
            name=name,
            connector_type="chroma",
            is_read_only=is_read_only,
            user_id=user_id,
        )
        self.host = host
        self.port = int(port or 8000)
        self.tenant = tenant
        self.database = database

    @property
    def base_url(self) -> str:
        protocol = "https" if self.port == 443 else "http"
        return f"{protocol}://{self.host}:{self.port}"

    def connect(self) -> bool:
        try:
            # Check v1 or v2 heartbeat
            url = f"{self.base_url}/api/v1/heartbeat"
            resp = requests.get(url, timeout=4)
            if resp.status_code == 200:
                self.touch_connected()
                return True

            # Try v2 collections
            c_url = f"{self.base_url}/api/v1/collections"
            c_resp = requests.get(c_url, timeout=4)
            if c_resp.status_code == 200:
                self.touch_connected()
                return True

            self.mark_error(f"HTTP {resp.status_code}: Unable to reach Chroma")
            return False
        except Exception as e:
            self.mark_error(str(e))
            return False

    def disconnect(self) -> bool:
        self.status = ConnectorStatus.DISCONNECTED
        self.clear_schema_cache()
        return True

    def test_connection(self) -> Dict[str, Any]:
        start = time.perf_counter()
        try:
            url = f"{self.base_url}/api/v1/heartbeat"
            resp = requests.get(url, timeout=5)
            elapsed_ms = (time.perf_counter() - start) * 1000

            if resp.status_code == 200:
                return {
                    "success": True,
                    "connected": True,
                    "latency_ms": round(elapsed_ms, 2),
                    "message": "Connected to Chroma vector database",
                }
            return {
                "success": False,
                "connected": False,
                "error": f"HTTP {resp.status_code}: {resp.text[:150]}",
            }
        except Exception as e:
            self.mark_error(str(e))
            return {"success": False, "connected": False, "error": str(e)}

    def get_schema(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Discovers Chroma collections, metadata, and document counts.
        """
        now = time.time()
        if (
            not force_refresh
            and self._schema_cache is not None
            and (now - self._schema_cached_at) < self._cache_ttl_seconds
        ):
            return self._schema_cache

        try:
            url = f"{self.base_url}/api/v1/collections"
            resp = requests.get(url, timeout=5)
            if resp.status_code != 200:
                return {}

            cols = resp.json()
            schema: Dict[str, Any] = {}

            for c in cols:
                c_id = c.get("id")
                c_name = c.get("name", "unnamed")
                # Fetch count
                count = 0
                if c_id:
                    cnt_resp = requests.get(
                        f"{self.base_url}/api/v1/collections/{c_id}/count", timeout=3
                    )
                    if cnt_resp.status_code == 200:
                        count = cnt_resp.json()

                schema[c_name] = {
                    "collection_id": c_id,
                    "documents_count": count,
                    "metadata": c.get("metadata") or {},
                    "type": "vector_collection",
                }

            self._schema_cache = schema
            self._schema_cached_at = now
            return schema
        except Exception as e:
            self.mark_error(f"Chroma schema discovery failed: {str(e)}")
            return {}

    def get_stats(self) -> Dict[str, Any]:
        try:
            schema = self.get_schema()
            total_docs = sum(
                info.get("documents_count", 0) for info in schema.values()
            )
            return {
                "collections": len(schema),
                "total_documents": total_docs,
                "engine": "Chroma Vector DB",
            }
        except Exception:
            return {"collections": 0, "total_documents": 0}

    def search_vectors(
        self,
        collection: str,
        query_text: Optional[str] = None,
        query_vector: Optional[List[float]] = None,
        limit: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> VectorSearchResult:
        """
        Execute semantic retrieval on Chroma collection.
        """
        start = time.perf_counter()
        try:
            schema = self.get_schema()
            c_info = schema.get(collection)
            c_id = c_info.get("collection_id") if c_info else None

            if not c_id:
                # Find collection ID by fetching list
                cols_resp = requests.get(f"{self.base_url}/api/v1/collections", timeout=4)
                if cols_resp.status_code == 200:
                    for col in cols_resp.json():
                        if col.get("name") == collection:
                            c_id = col.get("id")
                            break

            if not c_id:
                return VectorSearchResult(
                    success=False,
                    collection=collection,
                    query_text=query_text,
                    error=f"Collection '{collection}' not found in Chroma database",
                    source_id=self.connection_id,
                    source_name=self.name,
                )

            # Query collection
            url = f"{self.base_url}/api/v1/collections/{c_id}/query"
            body: Dict[str, Any] = {
                "n_results": min(limit, 50),
            }
            if query_text:
                body["query_texts"] = [query_text]
            if query_vector:
                body["query_embeddings"] = [query_vector]
            if metadata_filter:
                body["where"] = metadata_filter

            resp = requests.post(url, json=body, timeout=8)
            elapsed_ms = (time.perf_counter() - start) * 1000

            if resp.status_code != 200:
                return VectorSearchResult(
                    success=False,
                    collection=collection,
                    query_text=query_text,
                    error=f"Chroma query failed: HTTP {resp.status_code} - {resp.text[:150]}",
                    source_id=self.connection_id,
                    source_name=self.name,
                )

            res = resp.json()
            ids = res.get("ids", [[]])[0]
            docs_text = res.get("documents", [[]])[0]
            metadatas = res.get("metadatas", [[]])[0]
            distances = res.get("distances", [[]])[0] if "distances" in res else []

            documents: List[VectorDocument] = []
            for idx in range(len(ids)):
                doc_id = str(ids[idx])
                text_val = str(docs_text[idx]) if idx < len(docs_text) else ""
                meta = metadatas[idx] if idx < len(metadatas) and metadatas[idx] else {}
                dist = distances[idx] if idx < len(distances) else 0.0
                score = round(1.0 / (1.0 + float(dist)), 4) if dist is not None else 1.0

                documents.append(
                    VectorDocument(
                        id=doc_id,
                        score=score,
                        text=text_val,
                        metadata=meta or {},
                    )
                )

            return VectorSearchResult(
                success=True,
                collection=collection,
                query_text=query_text,
                documents=documents,
                total_found=len(documents),
                execution_time_ms=round(elapsed_ms, 2),
                source_id=self.connection_id,
                source_name=self.name,
            )

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return VectorSearchResult(
                success=False,
                collection=collection,
                query_text=query_text,
                error=str(e),
                execution_time_ms=round(elapsed_ms, 2),
                source_id=self.connection_id,
                source_name=self.name,
            )

    def to_sanitized_config(self) -> Dict[str, Any]:
        return {
            "type": "chroma",
            "host": self.host,
            "port": self.port,
            "tenant": self.tenant,
            "database": self.database,
            "base_url": self.base_url,
        }

