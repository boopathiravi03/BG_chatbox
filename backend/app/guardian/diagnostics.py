"""backend/app/guardian/diagnostics.py

Rule-based operational diagnostic and root-cause engine for AI Database Guardian.
Strictly separates:
1. Observed Facts (telemetry & metrics)
2. Rule Detections (threshold triggers)
3. Probabilistic Root Causes (with confidence scores and clear explanation of uncertainty)
4. Safe, non-destructive verification queries (read-only PRAGMA / EXPLAIN / SELECT)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.guardian.models import (
    EngineTelemetrySnapshot,
    GuardianIncident,
    IncidentSeverity,
    IncidentStatus,
    MetricAvailability,
)


def evaluate_telemetry_incidents(
    user_id: str,
    telemetry: EngineTelemetrySnapshot,
) -> List[GuardianIncident]:
    """
    Evaluates engine telemetry against deterministic, documented operational thresholds.
    Generates structured incidents with verifiable facts, calibrated confidence justifications,
    explicit diagnostic limitations, and defined recovery conditions.
    """
    incidents: List[GuardianIncident] = []
    now_iso = datetime.now(timezone.utc).isoformat()
    db_type = telemetry.database_type
    metrics = telemetry.metrics

    # ─────────────────────────────────────────────────────────────────────────────
    # RULE 1: Connection Pool Saturation (Relational / Document)
    # Threshold: Active connections >= 85% of max_connections, or >= 50 clients
    # ─────────────────────────────────────────────────────────────────────────────
    active_conn = metrics.get("active_connections")
    max_conn = metrics.get("max_connections")

    if (
        active_conn
        and active_conn.status == MetricAvailability.AVAILABLE
        and active_conn.value is not None
    ):
        conn_val = int(active_conn.value)
        max_val = int(max_conn.value) if max_conn and max_conn.value else None

        utilization_pct = round((conn_val / max_val * 100), 1) if max_val else None

        if (max_val and utilization_pct and utilization_pct >= 85.0) or (not max_val and conn_val >= 80):
            incidents.append(
                GuardianIncident(
                    incident_id=f"inc_{uuid.uuid4().hex[:8]}",
                    user_id=user_id,
                    database_identity=telemetry.database_identity,
                    database_type=db_type,
                    title="Elevated Database Connection Pool Saturation",
                    severity=IncidentSeverity.CRITICAL if (utilization_pct and utilization_pct >= 95) else IncidentSeverity.WARNING,
                    status=IncidentStatus.DETECTED,
                    category="connection_pool",
                    detected_at=now_iso,
                    updated_at=now_iso,
                    observed_facts={
                        "active_connections": conn_val,
                        "max_connections": max_val if max_val else "Unlimited / Default",
                        "utilization_percent": utilization_pct if utilization_pct else "N/A",
                    },
                    trigger_rule="active_connections >= 85% of max_connections or > 80 backends",
                    likely_root_cause="Probable unclosed connection leak in application worker processes, sudden traffic surge, or prolonged long-running queries locking sessions.",
                    confidence_score=0.88,
                    confidence_justification="High confidence derived directly from server process table metrics (Threads_connected / pg_stat_activity); limited only by whether proxy/pooler masks client origins.",
                    limitations=[
                        "External connection poolers (e.g., PgBouncer) may report their own pool sizing rather than backend host limits.",
                        "Does not distinguish between application threads and administrative background workers without processlist inspection.",
                    ],
                    verification_steps=[
                        "Inspect currently running client processes and query durations: "
                        + ("SELECT pid, now() - query_start AS duration, state, query FROM pg_stat_activity WHERE state != 'idle';" if db_type == "postgres" else "SHOW FULL PROCESSLIST;"),
                        "Check client application error logs for connection pool exhaustion (e.g. Timeout waiting for connection).",
                    ],
                    recovery_rule="active_connections < 70% of max_connections or < 50 backends",
                )
            )

    # ─────────────────────────────────────────────────────────────────────────────
    # RULE 2: Buffer Cache / Hit Ratio Degradation (MySQL, Postgres, Redis)
    # Threshold: Hit ratio < 80.0% (indicates severe disk I/O thrashing)
    # ─────────────────────────────────────────────────────────────────────────────
    cache_hit = metrics.get("cache_hit_ratio")
    if (
        cache_hit
        and cache_hit.status == MetricAvailability.AVAILABLE
        and cache_hit.value is not None
    ):
        hit_pct = float(cache_hit.value)
        if hit_pct < 80.0:
            incidents.append(
                GuardianIncident(
                    incident_id=f"inc_{uuid.uuid4().hex[:8]}",
                    user_id=user_id,
                    database_identity=telemetry.database_identity,
                    database_type=db_type,
                    title="Degraded Buffer Cache Hit Efficiency",
                    severity=IncidentSeverity.WARNING,
                    status=IncidentStatus.DETECTED,
                    category="cache_efficiency",
                    detected_at=now_iso,
                    updated_at=now_iso,
                    observed_facts={
                        "cache_hit_ratio": hit_pct,
                        "unit": "%",
                    },
                    trigger_rule="cache_hit_ratio < 80.0%",
                    likely_root_cause="Frequent full table scans evicting cached pages from RAM, or insufficient RAM allocation for shared_buffers / innodb_buffer_pool_size.",
                    confidence_score=0.82,
                    confidence_justification="Calibrated on cumulative page read requests vs disk reads. Recently restarted instances may show transiently low hit rates during cache warm-up.",
                    limitations=[
                        "Cache metrics are cumulative since server startup; recent query patterns may be obscured by historical totals unless server uptime is considered.",
                        "OS file system page cache hits are not reflected in database engine buffer statistics.",
                    ],
                    verification_steps=[
                        "Identify tables with high sequential scan counts vs index scans: "
                        + ("SELECT relname, seq_scan, idx_scan FROM pg_stat_user_tables WHERE seq_scan > 100 ORDER BY seq_scan DESC LIMIT 10;" if db_type == "postgres" else "SHOW GLOBAL STATUS LIKE 'Innodb_buffer_pool_%';"),
                        "Review recent queries in SQL Lab for missing WHERE clauses or unindexed filter predicates.",
                    ],
                    recovery_rule="cache_hit_ratio >= 85.0%",
                )
            )

    # ─────────────────────────────────────────────────────────────────────────────
    # RULE 3: Elevated Lock Contention / Blocked Sessions
    # Threshold: lock_waits > 3 or blocked_clients > 3
    # ─────────────────────────────────────────────────────────────────────────────
    lock_waits = metrics.get("lock_waits") or metrics.get("blocked_clients")
    if (
        lock_waits
        and lock_waits.status == MetricAvailability.AVAILABLE
        and lock_waits.value is not None
    ):
        waits = int(lock_waits.value)
        if waits > 3:
            incidents.append(
                GuardianIncident(
                    incident_id=f"inc_{uuid.uuid4().hex[:8]}",
                    user_id=user_id,
                    database_identity=telemetry.database_identity,
                    database_type=db_type,
                    title="Active Transaction Lock Contention Detected",
                    severity=IncidentSeverity.WARNING if waits < 10 else IncidentSeverity.CRITICAL,
                    status=IncidentStatus.DETECTED,
                    category="lock_contention",
                    detected_at=now_iso,
                    updated_at=now_iso,
                    observed_facts={
                        "waiting_lock_count": waits,
                    },
                    trigger_rule="lock_waits > 3",
                    likely_root_cause="Overlapping concurrent update transactions modifying the same table rows, or prolonged transactions held open inside application threads.",
                    confidence_score=0.79,
                    confidence_justification="Direct count of threads/backends in waiting status; specific lock graph requires superuser access to pg_locks / performance_schema.",
                    limitations=[
                        "Requires elevated database privileges to view transaction lock graphs across separate client sessions.",
                    ],
                    verification_steps=[
                        "Inspect transactions held idle in transaction: "
                        + ("SELECT pid, now() - xact_start AS duration, query FROM pg_stat_activity WHERE state = 'idle in transaction';" if db_type == "postgres" else "SELECT * FROM information_schema.innodb_locks;"),
                        "Verify application code does not perform slow network API calls while inside an open database transaction block.",
                    ],
                    recovery_rule="lock_waits <= 1",
                )
            )

    # ─────────────────────────────────────────────────────────────────────────────
    # RULE 4: SQLite Freelist Fragmentation & Journal Health
    # ─────────────────────────────────────────────────────────────────────────────
    if db_type == "sqlite":
        frag = metrics.get("fragmentation_pct")
        size = metrics.get("database_size_mb")
        journal = metrics.get("journal_mode")

        if frag and frag.value is not None and size and size.value is not None:
            frag_val = float(frag.value)
            size_val = float(size.value)
            if frag_val >= 35.0 and size_val >= 5.0:
                incidents.append(
                    GuardianIncident(
                        incident_id=f"inc_{uuid.uuid4().hex[:8]}",
                        user_id=user_id,
                        database_identity=telemetry.database_identity,
                        database_type=db_type,
                        title="High SQLite Freelist Page Fragmentation",
                        severity=IncidentSeverity.INFO,
                        status=IncidentStatus.DETECTED,
                        category="storage",
                        detected_at=now_iso,
                        updated_at=now_iso,
                        observed_facts={
                            "fragmentation_percent": frag_val,
                            "database_size_mb": size_val,
                        },
                        trigger_rule="fragmentation_pct >= 35% and database_size_mb >= 5.0",
                        likely_root_cause="Large volumes of deleted or overwritten rows leaving un-compacted pages on the SQLite freelist.",
                        confidence_score=0.92,
                        confidence_justification="Exact page arithmetic: freelist_count / page_count computed via PRAGMA introspection.",
                        limitations=[
                            "Compaction (VACUUM) requires exclusive write lock and free disk space equal to database size.",
                        ],
                        verification_steps=[
                            "Check freelist page count: PRAGMA freelist_count;",
                            "Consider scheduling off-peak compaction using VACUUM to reclaim filesystem disk blocks.",
                        ],
                        recovery_rule="fragmentation_pct < 20.0%",
                    )
                )

        if journal and journal.value == "DELETE":
            incidents.append(
                GuardianIncident(
                    incident_id=f"inc_{uuid.uuid4().hex[:8]}",
                    user_id=user_id,
                    database_identity=telemetry.database_identity,
                    database_type=db_type,
                    title="Sub-Optimal SQLite Journal Mode (DELETE)",
                    severity=IncidentSeverity.INFO,
                    status=IncidentStatus.DETECTED,
                    category="concurrency",
                    detected_at=now_iso,
                    updated_at=now_iso,
                    observed_facts={
                        "journal_mode": "DELETE",
                    },
                    trigger_rule="journal_mode == 'DELETE'",
                    likely_root_cause="Database uses classic rollback journaling which locks entire database file against concurrent readers during write transactions.",
                    confidence_score=0.95,
                    confidence_justification="Deterministic pragma value: journal_mode is explicitly DELETE.",
                    limitations=[
                        "WAL mode requires shared memory and POSIX advisory locks; not supported on network filesystems (NFS/SMB).",
                    ],
                    verification_steps=[
                        "Verify current journal mode: PRAGMA journal_mode;",
                        "Evaluating WAL mode (PRAGMA journal_mode=WAL;) permits concurrent readers without blocking writes.",
                    ],
                    recovery_rule="journal_mode == 'WAL'",
                )
            )

    return incidents

