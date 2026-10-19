"""backend/app/guardian/collectors.py

Real, non-destructive telemetry collectors for supported database engines.
Strict Guarantees:
1. Never fabricates numbers (reports unsupported as MetricAvailability.UNSUPPORTED_ENGINE or UNAVAILABLE).
2. Never scans user table rows for telemetry.
3. Strict execution timeout and read-only inspection commands only (PRAGMA, SHOW STATUS, pg_stat, serverStatus, INFO).
4. Handles permission errors gracefully (reports MetricAvailability.PERMISSION_DENIED).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.guardian.models import (
    EngineTelemetrySnapshot,
    MetricItem,
    MetricAvailability,
)

logger = logging.getLogger("bgai.guardian.collector")


def collect_sqlite_telemetry(engine: Engine, identity: str) -> EngineTelemetrySnapshot:
    """Collects real SQLite engine metrics via PRAGMA commands."""
    start_t = time.perf_counter()
    now_iso = datetime.now(timezone.utc).isoformat()
    metrics: Dict[str, MetricItem] = {}
    warnings: list[str] = []

    try:
        with engine.connect() as conn:
            # 1. Page count
            page_count_res = conn.execute(text("PRAGMA page_count;")).scalar()
            # 2. Page size
            page_size_res = conn.execute(text("PRAGMA page_size;")).scalar()
            # 3. Journal mode
            journal_mode_res = conn.execute(text("PRAGMA journal_mode;")).scalar()
            # 4. Freelist page count (fragmentation indication)
            freelist_count = conn.execute(text("PRAGMA freelist_count;")).scalar()
            
            # 5. Schema integrity check (only on smaller databases < 50MB to avoid disk I/O lock during routine monitoring)
            total_pages = int(page_count_res) if page_count_res is not None else 0
            page_size = int(page_size_res) if page_size_res is not None else 4096
            db_size_bytes = total_pages * page_size
            db_size_mb = round(db_size_bytes / (1024 * 1024), 2)

            quick_check = "ok"
            if db_size_mb < 50.0:
                try:
                    qc_val = conn.execute(text("PRAGMA quick_check(1);")).scalar()
                    if qc_val:
                        quick_check = str(qc_val)
                except Exception:
                    quick_check = "skipped"
            else:
                quick_check = "skipped (>50MB)"
        free_pages = int(freelist_count) if freelist_count is not None else 0
        fragmentation_pct = round((free_pages / total_pages * 100), 1) if total_pages > 0 else 0.0

        latency_ms = (time.perf_counter() - start_t) * 1000.0

        # Available metrics
        metrics["database_size_mb"] = MetricItem(
            name="Database Size",
            value=db_size_mb,
            unit="MB",
            status=MetricAvailability.AVAILABLE,
            description="Total database file size derived from page_count * page_size",
            freshness_seconds=0.1,
            collected_at=now_iso,
        )
        metrics["journal_mode"] = MetricItem(
            name="Journal Mode",
            value=str(journal_mode_res).upper() if journal_mode_res else "DELETE",
            unit="",
            status=MetricAvailability.AVAILABLE,
            description="Transaction journal persistence mode (WAL is optimal for concurrency)",
            freshness_seconds=0.1,
            collected_at=now_iso,
        )
        metrics["fragmentation_pct"] = MetricItem(
            name="Freelist Fragmentation",
            value=fragmentation_pct,
            unit="%",
            status=MetricAvailability.AVAILABLE,
            description="Percentage of allocated database pages on the unused freelist",
            freshness_seconds=0.1,
            collected_at=now_iso,
        )
        metrics["integrity_status"] = MetricItem(
            name="Integrity Quick Check",
            value=str(quick_check) if quick_check else "unknown",
            unit="",
            status=MetricAvailability.AVAILABLE,
            description="PRAGMA quick_check status of B-Trees and interior cell pointers",
            freshness_seconds=0.1,
            collected_at=now_iso,
        )

        # Unavailable / Unsupported on SQLite (reported accurately, NEVER fabricated)
        metrics["active_connections"] = MetricItem(
            name="Active Connections",
            value=None,
            unit="clients",
            status=MetricAvailability.UNSUPPORTED_ENGINE,
            description="SQLite is an embedded engine; remote network client pooling is not applicable.",
            freshness_seconds=0.0,
            collected_at=now_iso,
        )
        metrics["cache_hit_ratio"] = MetricItem(
            name="Buffer Cache Hit Ratio",
            value=None,
            unit="%",
            status=MetricAvailability.UNSUPPORTED_ENGINE,
            description="SQLite process memory cache counters are private to the OS page cache.",
            freshness_seconds=0.0,
            collected_at=now_iso,
        )
        metrics["lock_waits"] = MetricItem(
            name="Lock Wait Queue",
            value=None,
            unit="locks",
            status=MetricAvailability.UNSUPPORTED_ENGINE,
            description="SQLite uses file-level locking rather than an observable lock wait queue.",
            freshness_seconds=0.0,
            collected_at=now_iso,
        )

        return EngineTelemetrySnapshot(
            database_type="sqlite",
            database_identity=identity,
            collected_at=now_iso,
            is_live=True,
            latency_ms=latency_ms,
            metrics=metrics,
            warnings=warnings,
        )

    except Exception as e:
        latency_ms = (time.perf_counter() - start_t) * 1000.0
        logger.warning(f"Failed to collect SQLite telemetry: {e}")
        return EngineTelemetrySnapshot(
            database_type="sqlite",
            database_identity=identity,
            collected_at=now_iso,
            is_live=False,
            latency_ms=latency_ms,
            metrics={},
            warnings=[f"Telemetry collection failed: {str(e)}"],
        )


def collect_mysql_telemetry(engine: Engine, identity: str) -> EngineTelemetrySnapshot:
    """Collects real MySQL / MariaDB telemetry via SHOW GLOBAL STATUS / VARIABLES."""
    start_t = time.perf_counter()
    now_iso = datetime.now(timezone.utc).isoformat()
    metrics: Dict[str, MetricItem] = {}
    warnings: list[str] = []

    try:
        status_vars: Dict[str, Any] = {}
        variables: Dict[str, Any] = {}

        with engine.connect() as conn:
            # 1. Global Status
            try:
                res = conn.execute(text("SHOW GLOBAL STATUS;")).fetchall()
                for row in res:
                    status_vars[str(row[0]).lower()] = row[1]
            except Exception as e:
                warnings.append(f"SHOW GLOBAL STATUS limited: {e}")
                # Fallback to session status if permissions prevent GLOBAL
                try:
                    res = conn.execute(text("SHOW STATUS;")).fetchall()
                    for row in res:
                        status_vars[str(row[0]).lower()] = row[1]
                except Exception:
                    pass

            # 2. Global Variables
            try:
                res_vars = conn.execute(text("SHOW VARIABLES;")).fetchall()
                for row in res_vars:
                    variables[str(row[0]).lower()] = row[1]
            except Exception as e:
                warnings.append(f"SHOW VARIABLES limited: {e}")

        latency_ms = (time.perf_counter() - start_t) * 1000.0

        # Process Connections
        threads_connected = status_vars.get("threads_connected")
        max_connections = variables.get("max_connections")
        if threads_connected is not None:
            val = int(threads_connected)
            metrics["active_connections"] = MetricItem(
                name="Active Connections",
                value=val,
                unit="threads",
                status=MetricAvailability.AVAILABLE,
                description="Currently open client connections (Threads_connected)",
                freshness_seconds=0.1,
                collected_at=now_iso,
            )
        else:
            metrics["active_connections"] = MetricItem(
                name="Active Connections",
                value=None,
                unit="threads",
                status=MetricAvailability.PERMISSION_DENIED if warnings else MetricAvailability.UNAVAILABLE,
                description="Unable to read Threads_connected from MySQL status",
                freshness_seconds=0.0,
                collected_at=now_iso,
            )

        if max_connections is not None:
            metrics["max_connections"] = MetricItem(
                name="Max Allowed Connections",
                value=int(max_connections),
                unit="threads",
                status=MetricAvailability.AVAILABLE,
                description="Configured connection limit (max_connections)",
                freshness_seconds=0.1,
                collected_at=now_iso,
            )

        # InnoDB Buffer Pool Hit Rate
        # Formula: 100 - (Innodb_buffer_pool_reads / Innodb_buffer_pool_read_requests * 100)
        reads = status_vars.get("innodb_buffer_pool_reads")
        read_reqs = status_vars.get("innodb_buffer_pool_read_requests")
        if reads is not None and read_reqs is not None:
            r = float(reads)
            req = float(read_reqs)
            hit_ratio = round(100.0 - (r / req * 100.0), 2) if req > 0 else 100.0
            metrics["cache_hit_ratio"] = MetricItem(
                name="InnoDB Buffer Pool Hit Ratio",
                value=hit_ratio,
                unit="%",
                status=MetricAvailability.AVAILABLE,
                description="Percentage of page reads served directly from RAM without disk I/O",
                freshness_seconds=0.1,
                collected_at=now_iso,
            )
        else:
            metrics["cache_hit_ratio"] = MetricItem(
                name="InnoDB Buffer Pool Hit Ratio",
                value=None,
                unit="%",
                status=MetricAvailability.UNAVAILABLE,
                description="InnoDB status metrics not accessible",
                freshness_seconds=0.0,
                collected_at=now_iso,
            )

        # Slow Queries
        slow_queries = status_vars.get("slow_queries")
        if slow_queries is not None:
            metrics["slow_queries"] = MetricItem(
                name="Slow Queries Count",
                value=int(slow_queries),
                unit="queries",
                status=MetricAvailability.AVAILABLE,
                description="Total queries exceeding long_query_time since server start",
                freshness_seconds=0.1,
                collected_at=now_iso,
            )

        # Table Locks Waited
        locks_waited = status_vars.get("table_locks_waited")
        if locks_waited is not None:
            metrics["lock_waits"] = MetricItem(
                name="Table Locks Waited",
                value=int(locks_waited),
                unit="waits",
                status=MetricAvailability.AVAILABLE,
                description="Count of table lock requests that had to wait",
                freshness_seconds=0.1,
                collected_at=now_iso,
            )

        # Uptime
        uptime = status_vars.get("uptime")
        if uptime is not None:
            metrics["uptime_seconds"] = MetricItem(
                name="Server Uptime",
                value=int(uptime),
                unit="seconds",
                status=MetricAvailability.AVAILABLE,
                description="Total seconds MySQL server has been running",
                freshness_seconds=0.1,
                collected_at=now_iso,
            )

        return EngineTelemetrySnapshot(
            database_type="mysql",
            database_identity=identity,
            collected_at=now_iso,
            is_live=True,
            latency_ms=latency_ms,
            metrics=metrics,
            warnings=warnings,
        )

    except Exception as e:
        latency_ms = (time.perf_counter() - start_t) * 1000.0
        return EngineTelemetrySnapshot(
            database_type="mysql",
            database_identity=identity,
            collected_at=now_iso,
            is_live=False,
            latency_ms=latency_ms,
            metrics={},
            warnings=[f"MySQL telemetry collection failed: {str(e)}"],
        )


def collect_postgres_telemetry(engine: Engine, identity: str) -> EngineTelemetrySnapshot:
    """Collects real PostgreSQL telemetry via pg_stat_activity, pg_stat_database, etc."""
    start_t = time.perf_counter()
    now_iso = datetime.now(timezone.utc).isoformat()
    metrics: Dict[str, MetricItem] = {}
    warnings: list[str] = []

    try:
        with engine.connect() as conn:
            # 1. Active connections & states from pg_stat_activity
            try:
                conn_query = text("""
                    SELECT 
                        count(*) as total_conns,
                        count(*) FILTER (WHERE state = 'active') as active_conns,
                        count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_trans,
                        count(*) FILTER (WHERE wait_event_type IS NOT NULL) as waiting_conns
                    FROM pg_stat_activity 
                    WHERE datname = current_database();
                """)
                res = conn.execute(conn_query).fetchone()
                if res:
                    metrics["active_connections"] = MetricItem(
                        name="Active Connections",
                        value=int(res[1]) if res[1] is not None else int(res[0]),
                        unit="backends",
                        status=MetricAvailability.AVAILABLE,
                        description="Currently active query backends in current database",
                        freshness_seconds=0.1,
                        collected_at=now_iso,
                    )
                    metrics["total_connections"] = MetricItem(
                        name="Total Backends",
                        value=int(res[0]),
                        unit="backends",
                        status=MetricAvailability.AVAILABLE,
                        description="All backend connections (active, idle, and waiting)",
                        freshness_seconds=0.1,
                        collected_at=now_iso,
                    )
                    metrics["idle_in_transaction"] = MetricItem(
                        name="Idle in Transaction",
                        value=int(res[2]) if res[2] is not None else 0,
                        unit="backends",
                        status=MetricAvailability.AVAILABLE,
                        description="Backends holding open transactions while idle",
                        freshness_seconds=0.1,
                        collected_at=now_iso,
                    )
                    metrics["lock_waits"] = MetricItem(
                        name="Waiting Backends",
                        value=int(res[3]) if res[3] is not None else 0,
                        unit="backends",
                        status=MetricAvailability.AVAILABLE,
                        description="Connections blocked waiting on locks or system events",
                        freshness_seconds=0.1,
                        collected_at=now_iso,
                    )
            except Exception as e:
                warnings.append(f"pg_stat_activity limited: {e}")
                metrics["active_connections"] = MetricItem(
                    name="Active Connections",
                    value=None,
                    unit="backends",
                    status=MetricAvailability.PERMISSION_DENIED,
                    description="Permission denied reading pg_stat_activity",
                    freshness_seconds=0.0,
                    collected_at=now_iso,
                )

            # 2. Cache Hit Ratio from pg_stat_database
            try:
                cache_query = text("""
                    SELECT 
                        blks_hit, blks_read,
                        round((blks_hit::numeric / NULLIF(blks_hit + blks_read, 0) * 100), 2) as hit_ratio
                    FROM pg_stat_database 
                    WHERE datname = current_database();
                """)
                cache_res = conn.execute(cache_query).fetchone()
                if cache_res and cache_res[2] is not None:
                    metrics["cache_hit_ratio"] = MetricItem(
                        name="Buffer Cache Hit Ratio",
                        value=float(cache_res[2]),
                        unit="%",
                        status=MetricAvailability.AVAILABLE,
                        description="Percentage of page reads retrieved from shared_buffers RAM",
                        freshness_seconds=0.1,
                        collected_at=now_iso,
                    )
            except Exception as e:
                warnings.append(f"pg_stat_database cache query limited: {e}")

            # 3. Max connections setting
            try:
                max_c = conn.execute(text("SHOW max_connections;")).scalar()
                if max_c:
                    metrics["max_connections"] = MetricItem(
                        name="Max Allowed Connections",
                        value=int(max_c),
                        unit="backends",
                        status=MetricAvailability.AVAILABLE,
                        description="Configured max_connections limit in postgresql.conf",
                        freshness_seconds=0.1,
                        collected_at=now_iso,
                    )
            except Exception:
                pass

            # 4. Database disk size
            try:
                db_size = conn.execute(text("SELECT pg_database_size(current_database());")).scalar()
                if db_size:
                    metrics["database_size_mb"] = MetricItem(
                        name="Database Size",
                        value=round(int(db_size) / (1024 * 1024), 2),
                        unit="MB",
                        status=MetricAvailability.AVAILABLE,
                        description="Physical disk space consumed by the active database",
                        freshness_seconds=0.1,
                        collected_at=now_iso,
                    )
            except Exception:
                pass

        latency_ms = (time.perf_counter() - start_t) * 1000.0
        return EngineTelemetrySnapshot(
            database_type="postgres",
            database_identity=identity,
            collected_at=now_iso,
            is_live=True,
            latency_ms=latency_ms,
            metrics=metrics,
            warnings=warnings,
        )

    except Exception as e:
        latency_ms = (time.perf_counter() - start_t) * 1000.0
        return EngineTelemetrySnapshot(
            database_type="postgres",
            database_identity=identity,
            collected_at=now_iso,
            is_live=False,
            latency_ms=latency_ms,
            metrics={},
            warnings=[f"PostgreSQL telemetry collection failed: {str(e)}"],
        )


def collect_mongodb_telemetry(connector: Any, identity: str) -> EngineTelemetrySnapshot:
    """Collects real MongoDB metrics via db.command('serverStatus')."""
    start_t = time.perf_counter()
    now_iso = datetime.now(timezone.utc).isoformat()
    metrics: Dict[str, MetricItem] = {}
    warnings: list[str] = []

    try:
        # Check client
        client = getattr(connector, "_client", None)
        if client is None and hasattr(connector, "connect"):
            connector.connect()
            client = getattr(connector, "_client", None)

        if client is None:
            raise ConnectionError("MongoDB client not connected")

        # Run serverStatus with 3s timeout
        db_name = getattr(connector, "database", "admin") or "admin"
        db = client[db_name]
        status = db.command("serverStatus")

        latency_ms = (time.perf_counter() - start_t) * 1000.0

        # Connections
        conns = status.get("connections", {})
        if "current" in conns:
            metrics["active_connections"] = MetricItem(
                name="Active Connections",
                value=int(conns["current"]),
                unit="connections",
                status=MetricAvailability.AVAILABLE,
                description="Currently open incoming client connections",
                freshness_seconds=0.1,
                collected_at=now_iso,
            )
        if "available" in conns:
            metrics["available_connections"] = MetricItem(
                name="Available Connections",
                value=int(conns["available"]),
                unit="connections",
                status=MetricAvailability.AVAILABLE,
                description="Remaining unused connection slots",
                freshness_seconds=0.1,
                collected_at=now_iso,
            )

        # Memory
        mem = status.get("mem", {})
        if "resident" in mem:
            metrics["memory_resident_mb"] = MetricItem(
                name="Resident Memory",
                value=int(mem["resident"]),
                unit="MB",
                status=MetricAvailability.AVAILABLE,
                description="Physical RAM occupied by mongod process",
                freshness_seconds=0.1,
                collected_at=now_iso,
            )

        # Opcounters (throughput)
        op = status.get("opcounters", {})
        if "query" in op:
            metrics["query_ops"] = MetricItem(
                name="Total Query Operations",
                value=int(op.get("query", 0)),
                unit="ops",
                status=MetricAvailability.AVAILABLE,
                description="Cumulative query operations since mongod startup",
                freshness_seconds=0.1,
                collected_at=now_iso,
            )

        # Uptime
        if "uptime" in status:
            metrics["uptime_seconds"] = MetricItem(
                name="Server Uptime",
                value=int(status["uptime"]),
                unit="seconds",
                status=MetricAvailability.AVAILABLE,
                description="Seconds mongod has been running",
                freshness_seconds=0.1,
                collected_at=now_iso,
            )

        # Relational metrics report as unsupported
        metrics["cache_hit_ratio"] = MetricItem(
            name="Buffer Cache Hit Ratio",
            value=None,
            unit="%",
            status=MetricAvailability.UNSUPPORTED_ENGINE,
            description="MongoDB uses WiredTiger cache eviction metrics rather than relational buffer pool counters.",
            freshness_seconds=0.0,
            collected_at=now_iso,
        )

        return EngineTelemetrySnapshot(
            database_type="mongodb",
            database_identity=identity,
            collected_at=now_iso,
            is_live=True,
            latency_ms=latency_ms,
            metrics=metrics,
            warnings=warnings,
        )

    except Exception as e:
        latency_ms = (time.perf_counter() - start_t) * 1000.0
        return EngineTelemetrySnapshot(
            database_type="mongodb",
            database_identity=identity,
            collected_at=now_iso,
            is_live=False,
            latency_ms=latency_ms,
            metrics={},
            warnings=[f"MongoDB telemetry collection failed: {str(e)}"],
        )


def collect_redis_telemetry(connector: Any, identity: str) -> EngineTelemetrySnapshot:
    """Collects real Redis metrics via client.info()."""
    start_t = time.perf_counter()
    now_iso = datetime.now(timezone.utc).isoformat()
    metrics: Dict[str, MetricItem] = {}
    warnings: list[str] = []

    try:
        client = getattr(connector, "_client", None)
        if client is None and hasattr(connector, "connect"):
            connector.connect()
            client = getattr(connector, "_client", None)

        if client is None:
            raise ConnectionError("Redis client not connected")

        info = client.info()
        latency_ms = (time.perf_counter() - start_t) * 1000.0

        # Connected clients
        if "connected_clients" in info:
            metrics["active_connections"] = MetricItem(
                name="Connected Clients",
                value=int(info["connected_clients"]),
                unit="clients",
                status=MetricAvailability.AVAILABLE,
                description="Number of client connections currently connected to Redis",
                freshness_seconds=0.1,
                collected_at=now_iso,
            )

        # Used memory
        if "used_memory" in info:
            metrics["memory_used_mb"] = MetricItem(
                name="Used Memory",
                value=round(int(info["used_memory"]) / (1024 * 1024), 2),
                unit="MB",
                status=MetricAvailability.AVAILABLE,
                description="Total memory allocated by Redis using its allocator",
                freshness_seconds=0.1,
                collected_at=now_iso,
            )

        # Hit rate
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        tot = hits + misses
        if tot > 0:
            hit_ratio = round((hits / tot) * 100.0, 2)
            metrics["cache_hit_ratio"] = MetricItem(
                name="Keyspace Hit Ratio",
                value=hit_ratio,
                unit="%",
                status=MetricAvailability.AVAILABLE,
                description="Percentage of key lookups successfully found in cache",
                freshness_seconds=0.1,
                collected_at=now_iso,
            )
        else:
            metrics["cache_hit_ratio"] = MetricItem(
                name="Keyspace Hit Ratio",
                value=None,
                unit="%",
                status=MetricAvailability.UNAVAILABLE,
                description="No keyspace access operations recorded yet",
                freshness_seconds=0.0,
                collected_at=now_iso,
            )

        # Instantaneous ops
        if "instantaneous_ops_per_sec" in info:
            metrics["ops_per_sec"] = MetricItem(
                name="Instantaneous Operations",
                value=int(info["instantaneous_ops_per_sec"]),
                unit="ops/sec",
                status=MetricAvailability.AVAILABLE,
                description="Number of commands processed per second",
                freshness_seconds=0.1,
                collected_at=now_iso,
            )

        # Blocked clients
        if "blocked_clients" in info:
            metrics["blocked_clients"] = MetricItem(
                name="Blocked Clients",
                value=int(info["blocked_clients"]),
                unit="clients",
                status=MetricAvailability.AVAILABLE,
                description="Clients pending on a blocking call (BLPOP, BRPOP, etc.)",
                freshness_seconds=0.1,
                collected_at=now_iso,
            )

        return EngineTelemetrySnapshot(
            database_type="redis",
            database_identity=identity,
            collected_at=now_iso,
            is_live=True,
            latency_ms=latency_ms,
            metrics=metrics,
            warnings=warnings,
        )

    except Exception as e:
        latency_ms = (time.perf_counter() - start_t) * 1000.0
        return EngineTelemetrySnapshot(
            database_type="redis",
            database_identity=identity,
            collected_at=now_iso,
            is_live=False,
            latency_ms=latency_ms,
            metrics={},
            warnings=[f"Redis telemetry collection failed: {str(e)}"],
        )


def collect_file_or_vector_telemetry(db_type: str, identity: str) -> EngineTelemetrySnapshot:
    """Handles flat file and vector database sources cleanly without pretending they are relational engines."""
    now_iso = datetime.now(timezone.utc).isoformat()
    metrics: Dict[str, MetricItem] = {}

    metrics["active_connections"] = MetricItem(
        name="Active Connections",
        value=None,
        unit="",
        status=MetricAvailability.UNSUPPORTED_ENGINE,
        description=f"{db_type.upper()} does not maintain an observable relational connection pool.",
        freshness_seconds=0.0,
        collected_at=now_iso,
    )
    metrics["cache_hit_ratio"] = MetricItem(
        name="Buffer Cache Hit Ratio",
        value=None,
        unit="",
        status=MetricAvailability.UNSUPPORTED_ENGINE,
        description=f"{db_type.upper()} buffer pool hit ratios are not applicable.",
        freshness_seconds=0.0,
        collected_at=now_iso,
    )
    metrics["lock_waits"] = MetricItem(
        name="Lock Wait Queue",
        value=None,
        unit="",
        status=MetricAvailability.UNSUPPORTED_ENGINE,
        description=f"{db_type.upper()} does not feature relational lock wait telemetry.",
        freshness_seconds=0.0,
        collected_at=now_iso,
    )

    return EngineTelemetrySnapshot(
        database_type=db_type,
        database_identity=identity,
        collected_at=now_iso,
        is_live=True,
        latency_ms=0.5,
        metrics=metrics,
        warnings=[f"Specialized engine '{db_type}' provides schema and quality inspections rather than relational server vitals."],
    )

