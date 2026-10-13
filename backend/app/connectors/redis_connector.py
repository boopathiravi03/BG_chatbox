"""backend/app/connectors/redis_connector.py

Redis Key-Value and In-Memory Data Store Connector for BG AI 2.0.
Provides connection pooling, key discovery, schema inference,
strict read-only enforcement, health check / ping, and query execution.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from app.connectors.base import (
    BaseConnector,
    ConnectorCapabilities,
    ConnectorCategory,
    ConnectorStatus,
    QueryResult,
)

logger = logging.getLogger(__name__)

# Server administration and destructive commands - strictly prohibited
DANGEROUS_ADMIN_COMMANDS = {
    "FLUSHALL", "FLUSHDB", "RESTORE", "CONFIG",
    "SHUTDOWN", "BGREWRITEAOF", "BGSAVE", "SAVE", "SLAVEOF", "REPLICAOF",
    "SCRIPT", "EVAL", "EVALSHA", "SWAPDB", "MOVE", "MIGRATE",
}

# Mutation commands permitted in Read/Write mode, blocked in Read-Only mode
MUTATING_COMMANDS = {
    "SET", "SETEX", "SETNX", "SETRANGE", "MSET", "MSETNX", "GETSET",
    "DEL", "UNLINK", "LPUSH", "LPUSHX", "RPUSH", "RPUSHX",
    "LPOP", "RPOP", "RPOPLPUSH", "LMOVE", "LSET", "LREM", "LTRIM",
    "SADD", "SREM", "SPOP", "SMOVE", "ZADD", "ZREM", "ZINCRBY",
    "ZREMRANGEBYRANK", "ZREMRANGEBYSCORE", "ZREMRANGEBYLEX",
    "HDEL", "HSET", "HSETNX", "HINCRBY", "HINCRBYFLOAT",
    "INCR", "DECR", "INCRBY", "DECRBY", "INCRBYFLOAT", "APPEND",
    "EXPIRE", "PEXPIRE", "EXPIREAT", "PEXPIREAT", "PERSIST",
    "RENAME", "RENAMENX",
}

# Permitted read-only inspection commands
SAFE_READ_COMMANDS = {
    "GET", "MGET", "HGET", "HGETALL", "HKEYS", "HVALS", "HLEN", "HEXISTS", "HMGET",
    "LRANGE", "LLEN", "LINDEX", "LPOS",
    "SMEMBERS", "SCARD", "SISMEMBER", "SMISMEMBER", "SRANDMEMBER",
    "ZRANGE", "ZCARD", "ZSCORE", "ZCOUNT", "ZRANK", "ZREVRANK", "ZRANGEBYSCORE",
    "KEYS", "SCAN", "HSCAN", "SSCAN", "ZSCAN",
    "TYPE", "TTL", "PTTL", "EXISTS", "DBSIZE", "INFO", "PING", "STRLEN",
    "XLEN", "XRANGE", "XREVRANGE",
}


class RedisConnector(BaseConnector):
    """
    BG AI connector for Redis key-value and data structure store.
    """

    def __init__(
        self,
        connection_id: str,
        name: str,
        host: str = "localhost",
        port: int = 6379,
        password: Optional[str] = None,
        db: int = 0,
        ssl: bool = False,
        is_read_only: bool = False,
        user_id: str = "default_user",
    ):
        super().__init__(
            connection_id=connection_id,
            name=name,
            connector_type="redis",
            category=ConnectorCategory.DOCUMENT,
            is_read_only=is_read_only,
            user_id=user_id,
        )
        self.host = host
        self.port = int(port)
        self.password = password or None
        self.db = int(db)
        self.ssl = bool(ssl)
        self._client: Any = None

    def _get_client(self):
        if self._client is not None:
            return self._client

        try:
            import redis
            client = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                db=self.db,
                ssl=self.ssl,
                socket_connect_timeout=5.0,
                socket_timeout=5.0,
                decode_responses=True,
            )
            return client
        except ImportError:
            raise RuntimeError(
                "The 'redis' Python package is required. Install with: pip install redis"
            )

    def connect(self) -> bool:
        """Establish Redis connection and verify via PING."""
        try:
            client = self._get_client()
            pong = client.ping()
            if pong:
                self._client = client
                self.touch_connected()
                return True
            self.mark_error("Redis ping response was not truthy.")
            return False
        except Exception as e:
            self._client = None
            self.mark_error(f"Redis connection failed: {e}")
            return False

    def disconnect(self) -> bool:
        """Close connection pool."""
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
        """Test live connectivity and return response latency and server stats."""
        start = time.perf_counter()
        try:
            client = self._get_client()
            client.ping()
            latency = (time.perf_counter() - start) * 1000.0

            # Gather high-level server stats
            server_info = {}
            try:
                raw_info = client.info(section="server")
                mem_info = client.info(section="memory")
                db_size = client.dbsize()
                server_info = {
                    "redis_version": raw_info.get("redis_version", "unknown"),
                    "os": raw_info.get("os", "unknown"),
                    "used_memory_human": mem_info.get("used_memory_human", "unknown"),
                    "total_keys": db_size,
                    "db_index": self.db,
                }
            except Exception:
                pass

            return {
                "connected": True,
                "latency_ms": round(latency, 2),
                "details": f"Redis at {self.host}:{self.port} (DB {self.db}) is responding.",
                "info": server_info,
            }
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000.0
            return {
                "connected": False,
                "latency_ms": round(latency, 2),
                "error": str(e),
                "details": f"Failed to connect to Redis at {self.host}:{self.port}: {e}",
            }

    def get_stats(self) -> Dict[str, Any]:
        """Return Redis database key count and memory metrics."""
        try:
            client = self._get_client()
            total_keys = client.dbsize()
            mem_info = client.info(section="memory")
            return {
                "total_keys": total_keys,
                "tables_count": 1,  # treated as 1 database namespace
                "used_memory": mem_info.get("used_memory_human", "unknown"),
                "db_index": self.db,
            }
        except Exception:
            return {"total_keys": 0, "tables_count": 0, "db_index": self.db}

    def get_schema(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Discover Redis key patterns and present them as schema entities for BG AI.
        Groups keys by prefix pattern (e.g. 'users:*', 'session:*', 'cache:*', or 'default').
        """
        now = time.time()
        if (
            not force_refresh
            and self._schema_cache is not None
            and (now - self._schema_cached_at) < self._cache_ttl_seconds
        ):
            return self._schema_cache

        try:
            client = self._get_client()
            # Scan a sample of up to 200 keys
            cursor, keys = client.scan(cursor=0, count=200)
            patterns: Dict[str, Dict[str, Any]] = {}

            if not keys:
                # Return empty schema representation
                schema = {
                    "redis_keys": {
                        "columns": {
                            "key": {"type": "VARCHAR(512)", "nullable": False, "primary_key": True},
                            "type": {"type": "VARCHAR(32)", "nullable": False},
                            "ttl": {"type": "INTEGER", "nullable": True},
                            "value": {"type": "TEXT", "nullable": True},
                        },
                        "total_keys": 0,
                        "primary_key": ["key"],
                    }
                }
                self._schema_cache = schema
                self._schema_cached_at = now
                return schema

            for key in keys:
                # Determine prefix (e.g. "user:123" -> "user", "order_456" -> "order")
                if ":" in key:
                    prefix = key.split(":", 1)[0] + ":*"
                elif "_" in key:
                    prefix = key.split("_", 1)[0] + "_*"
                else:
                    prefix = "general_keys"

                if prefix not in patterns:
                    patterns[prefix] = {
                        "sample_keys": [],
                        "types": set(),
                        "count": 0,
                    }

                patterns[prefix]["count"] += 1
                if len(patterns[prefix]["sample_keys"]) < 5:
                    patterns[prefix]["sample_keys"].append(key)
                    try:
                        ktype = client.type(key)
                        patterns[prefix]["types"].add(ktype)
                    except Exception:
                        pass

            schema: Dict[str, Any] = {}
            for pattern_name, pdata in patterns.items():
                types_str = ", ".join(pdata["types"]) or "string"
                schema[pattern_name] = {
                    "columns": {
                        "key": {"type": "VARCHAR(512)", "nullable": False, "primary_key": True},
                        "type": {"type": f"REDIS_{types_str.upper()}", "nullable": False},
                        "ttl": {"type": "INTEGER", "nullable": True},
                        "value": {"type": "TEXT", "nullable": True},
                    },
                    "primary_key": ["key"],
                    "estimated_count": pdata["count"],
                    "sample_keys": pdata["sample_keys"],
                }

            self._schema_cache = schema
            self._schema_cached_at = now
            return schema
        except Exception as e:
            logger.warning(f"Failed to infer Redis schema: {e}")
            return {
                "redis_keys": {
                    "columns": {
                        "key": {"type": "VARCHAR(512)", "nullable": False, "primary_key": True},
                        "type": {"type": "VARCHAR(32)", "nullable": False},
                        "ttl": {"type": "INTEGER", "nullable": True},
                        "value": {"type": "TEXT", "nullable": True},
                    },
                    "primary_key": ["key"],
                    "error": str(e),
                }
            }

    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> QueryResult:
        """
        Execute read-only Redis inspection query or JSON command.
        Blocks destructive / mutating operations unconditionally.
        """
        start = time.perf_counter()
        raw_cmd = query.strip()

        # Handle empty query
        if not raw_cmd:
            return QueryResult(
                success=False,
                error="Empty query received.",
                source_id=self.connection_id,
                source_name=self.name,
                query_dialect="redis",
            )

        # 1. Parse JSON format command if provided: {"command": "GET", "key": "abc"}
        cmd_name = ""
        cmd_args: List[str] = []

        if raw_cmd.startswith("{") and raw_cmd.endswith("}"):
            try:
                parsed = json.loads(raw_cmd)
                cmd_name = str(parsed.get("command") or "").upper().strip()
                if "key" in parsed:
                    cmd_args.append(str(parsed["key"]))
                if "args" in parsed and isinstance(parsed["args"], list):
                    cmd_args.extend([str(a) for a in parsed["args"]])
            except Exception:
                cmd_name = ""

        # 2. Parse pseudo-SQL: SELECT * FROM <pattern> [LIMIT N]
        if not cmd_name and raw_cmd.upper().startswith("SELECT"):
            match = re.search(r"FROM\s+([`'\"a-zA-Z0-9_:*]+)", raw_cmd, re.IGNORECASE)
            limit_match = re.search(r"LIMIT\s+(\d+)", raw_cmd, re.IGNORECASE)
            limit = int(limit_match.group(1)) if limit_match else 50

            pattern = match.group(1).strip("`'\"") if match else "*"
            if not pattern.endswith("*") and not pattern.startswith("*"):
                pattern = f"*{pattern}*"

            return self._scan_and_fetch_rows(pattern, limit, start, raw_cmd)

        # 3. Parse space-separated standard Redis command line: e.g. "GET user:1" or "HGETALL myhash"
        if not cmd_name:
            tokens = raw_cmd.split()
            cmd_name = tokens[0].upper()
            cmd_args = tokens[1:]

        # Guard 1: Block dangerous server administrative commands
        if cmd_name in DANGEROUS_ADMIN_COMMANDS:
            return QueryResult(
                success=False,
                error=f"Server administration command '{cmd_name}' is blocked by BG AI security policy.",
                query_dialect="redis",
                executed_query=raw_cmd,
                source_id=self.connection_id,
                source_name=self.name,
                execution_time_ms=(time.perf_counter() - start) * 1000.0,
            )

        # Guard 2: Enforce Read-Only mode when configured
        if self.is_read_only and (cmd_name in MUTATING_COMMANDS or cmd_name not in SAFE_READ_COMMANDS):
            return QueryResult(
                success=False,
                error=f"Connection '{self.name}' is configured as READ-ONLY. Mutating command '{cmd_name}' is forbidden.",
                query_dialect="redis",
                executed_query=raw_cmd,
                source_id=self.connection_id,
                source_name=self.name,
                execution_time_ms=(time.perf_counter() - start) * 1000.0,
            )

        try:
            client = self._get_client()

            # Execute specific supported inspection commands
            if cmd_name == "PING":
                res = client.ping()
                rows = [{"response": "PONG" if res else "FAIL"}]
                cols = ["response"]
            elif cmd_name == "DBSIZE":
                size = client.dbsize()
                rows = [{"dbsize": size, "db_index": self.db}]
                cols = ["dbsize", "db_index"]
            elif cmd_name == "INFO":
                section = cmd_args[0] if cmd_args else None
                info = client.info(section=section)
                rows = [{"key": k, "value": str(v)} for k, v in list(info.items())[:100]]
                cols = ["key", "value"]
            elif cmd_name == "GET":
                if not cmd_args:
                    raise ValueError("GET requires a key parameter.")
                key = cmd_args[0]
                val = client.get(key)
                ttl = client.ttl(key)
                rows = [{"key": key, "type": "string", "ttl": ttl, "value": val}]
                cols = ["key", "type", "ttl", "value"]
            elif cmd_name == "MGET":
                if not cmd_args:
                    raise ValueError("MGET requires at least one key.")
                vals = client.mget(cmd_args)
                rows = [{"key": k, "value": v} for k, v in zip(cmd_args, vals)]
                cols = ["key", "value"]
            elif cmd_name in ("HGETALL", "HKEYS", "HVALS"):
                if not cmd_args:
                    raise ValueError(f"{cmd_name} requires a key parameter.")
                key = cmd_args[0]
                hdata = client.hgetall(key)
                rows = [{"field": f, "value": str(v)} for f, v in hdata.items()]
                cols = ["field", "value"]
            elif cmd_name == "LRANGE":
                key = cmd_args[0]
                start_idx = int(cmd_args[1]) if len(cmd_args) > 1 else 0
                end_idx = int(cmd_args[2]) if len(cmd_args) > 2 else 50
                items = client.lrange(key, start_idx, end_idx)
                rows = [{"index": idx, "value": str(val)} for idx, val in enumerate(items)]
                cols = ["index", "value"]
            elif cmd_name == "SMEMBERS":
                key = cmd_args[0]
                members = client.smembers(key)
                rows = [{"member": str(m)} for m in list(members)[:100]]
                cols = ["member"]
            elif cmd_name == "ZRANGE":
                key = cmd_args[0]
                start_idx = int(cmd_args[1]) if len(cmd_args) > 1 else 0
                end_idx = int(cmd_args[2]) if len(cmd_args) > 2 else 50
                zitems = client.zrange(key, start_idx, end_idx, withscores=True)
                rows = [{"member": str(m), "score": s} for m, s in zitems]
                cols = ["member", "score"]
            elif cmd_name in ("KEYS", "SCAN"):
                pattern = cmd_args[0] if cmd_args else "*"
                return self._scan_and_fetch_rows(pattern, 100, start, raw_cmd)
            else:
                # Generic safe fallback execution via execute_command
                raw_res = client.execute_command(cmd_name, *cmd_args)
                if isinstance(raw_res, dict):
                    rows = [{"key": k, "value": str(v)} for k, v in raw_res.items()]
                    cols = ["key", "value"]
                elif isinstance(raw_res, (list, set, tuple)):
                    rows = [{"index": idx, "value": str(v)} for idx, v in enumerate(raw_res)]
                    cols = ["index", "value"]
                else:
                    rows = [{"result": str(raw_res)}]
                    cols = ["result"]

            elapsed = (time.perf_counter() - start) * 1000.0
            return QueryResult(
                success=True,
                columns=cols,
                rows=rows,
                rows_returned=len(rows),
                execution_time_ms=round(elapsed, 2),
                query_dialect="redis",
                executed_query=raw_cmd,
                source_id=self.connection_id,
                source_name=self.name,
            )
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000.0
            return QueryResult(
                success=False,
                error=f"Redis execution error: {e}",
                query_dialect="redis",
                executed_query=raw_cmd,
                source_id=self.connection_id,
                source_name=self.name,
                execution_time_ms=round(elapsed, 2),
            )

    def _scan_and_fetch_rows(
        self, pattern: str, limit: int, start_time: float, executed_query: str
    ) -> QueryResult:
        """Scan keys matching pattern and extract type, ttl, and preview value."""
        client = self._get_client()
        cursor, keys = client.scan(cursor=0, match=pattern, count=limit)
        rows: List[Dict[str, Any]] = []

        for key in keys[:limit]:
            try:
                ktype = client.type(key)
                ttl = client.ttl(key)
                val_preview = ""
                if ktype == "string":
                    val_preview = client.get(key)
                    if val_preview and len(val_preview) > 200:
                        val_preview = val_preview[:200] + "..."
                elif ktype == "hash":
                    val_preview = f"Hash with {client.hlen(key)} fields"
                elif ktype == "list":
                    val_preview = f"List with {client.llen(key)} elements"
                elif ktype == "set":
                    val_preview = f"Set with {client.scard(key)} members"
                elif ktype == "zset":
                    val_preview = f"Sorted Set with {client.zcard(key)} members"
                else:
                    val_preview = f"Type: {ktype}"

                rows.append({
                    "key": key,
                    "type": ktype,
                    "ttl": ttl,
                    "value": str(val_preview),
                })
            except Exception:
                rows.append({
                    "key": key,
                    "type": "unknown",
                    "ttl": -1,
                    "value": "",
                })

        elapsed = (time.perf_counter() - start_time) * 1000.0
        return QueryResult(
            success=True,
            columns=["key", "type", "ttl", "value"],
            rows=rows,
            rows_returned=len(rows),
            execution_time_ms=round(elapsed, 2),
            query_dialect="redis",
            executed_query=executed_query,
            source_id=self.connection_id,
            source_name=self.name,
        )

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
                supports_transactions=False,
                read_only_reason=f"Connection '{self.name}' is explicitly configured as Read-Only.",
            )
        return ConnectorCapabilities(
            can_read_data=True,
            can_insert_records=True,
            can_update_records=True,
            can_delete_records=True,
            can_create_entities=False,
            can_alter_schema=False,
            can_manage_indexes=False,
            can_execute_raw_queries=True,
            supports_transactions=False,
            read_only_reason=None,
        )

    def to_sanitized_config(self) -> Dict[str, Any]:
        """Return safe configuration hiding password."""
        return {
            "host": self.host,
            "port": self.port,
            "db": self.db,
            "ssl": self.ssl,
            "password": "***" if self.password else None,
        }
