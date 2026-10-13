"""backend/app/intelligence/governance/audit_store.py

Thread-safe SQLite storage for Phase 9.3: Enterprise Governance & Observability.
Provides:
1. Append-oriented governance audit log with tamper-evident cryptographic hash-chaining.
2. Security events tracking and persistence.
3. Agent trace telemetry storage.
4. Data access monitoring events.
5. Strict tenant (user_id) and database (database_identity) isolation.
6. Bounded pagination and safe filtering.
"""

from __future__ import annotations

import os
import json
import uuid
import hashlib
import sqlite3
import threading
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime, timezone

from app.intelligence.governance.models import (
    GovernanceAuditEvent,
    SecurityEventRecord,
    AgentTraceRecord,
    DataAccessEvent,
    GovernanceEventType,
    ActorType,
    RiskLevel,
    SecurityEventType,
    SecurityEventSeverity,
    PolicyDecision,
)

_DB_LOCK = threading.RLock()
_DEFAULT_DB_PATH = Path(__file__).resolve().parent / "bgai_governance.db"
GENESIS_HASH = "0" * 64


def _get_db_path() -> Path:
    override = os.getenv("BGAI_GOVERNANCE_DB_PATH")
    if override:
        return Path(override)
    return _DEFAULT_DB_PATH


def _init_db(conn: sqlite3.Connection) -> None:
    # 1. Audit events with hash chain
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS governance_audit_events (
            event_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            user_id TEXT NOT NULL,
            database_identity TEXT NOT NULL,
            event_type TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            actor_type TEXT NOT NULL,
            agent_id TEXT,
            orchestration_id TEXT,
            action TEXT NOT NULL,
            result TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            policy_result TEXT,
            request_id TEXT,
            metadata TEXT NOT NULL,
            previous_event_hash TEXT NOT NULL,
            event_hash TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_user_db ON governance_audit_events(user_id, database_identity)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON governance_audit_events(timestamp)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_event_type ON governance_audit_events(event_type)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_risk ON governance_audit_events(risk_level)"
    )

    # 2. Security events
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS security_events (
            event_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            user_id TEXT NOT NULL,
            database_identity TEXT NOT NULL,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            source TEXT NOT NULL,
            resource TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL,
            mitigation TEXT,
            metadata TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sec_user_db ON security_events(user_id, database_identity)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sec_severity ON security_events(severity)"
    )

    # 3. Agent traces
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_traces (
            trace_id TEXT PRIMARY KEY,
            request_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            database_identity TEXT NOT NULL,
            tool_or_capability TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            duration_ms REAL NOT NULL,
            status TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            policy_decision TEXT NOT NULL,
            evidence_count INTEGER NOT NULL,
            orchestration_id TEXT,
            step_id TEXT,
            error_message TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_traces_user_db ON agent_traces(user_id, database_identity)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_traces_orch ON agent_traces(orchestration_id)"
    )

    # 4. Data access events
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS data_access_events (
            access_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            user_id TEXT NOT NULL,
            database_identity TEXT NOT NULL,
            agent_id TEXT,
            operation TEXT NOT NULL,
            query_fingerprint TEXT NOT NULL,
            tables_referenced TEXT NOT NULL,
            is_write INTEGER NOT NULL,
            duration_ms REAL NOT NULL,
            row_count INTEGER,
            status TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_access_user_db ON data_access_events(user_id, database_identity)"
    )
    conn.commit()


def _get_connection() -> sqlite3.Connection:
    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def _compute_event_hash(event: GovernanceAuditEvent, prev_hash: str) -> str:
    """
    Computes a canonical SHA-256 hash chaining this event to the previous event hash.
    """
    canonical_dict = {
        "event_id": event.event_id,
        "timestamp": event.timestamp,
        "user_id": event.user_id,
        "database_identity": event.database_identity,
        "event_type": event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type),
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "actor_type": event.actor_type.value if hasattr(event.actor_type, "value") else str(event.actor_type),
        "action": event.action,
        "result": event.result,
        "risk_level": event.risk_level.value if hasattr(event.risk_level, "value") else str(event.risk_level),
        "prev_hash": prev_hash,
    }
    canonical_json = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


# ── Audit Event Persistence ──────────────────────────────────────────────────

def save_audit_event(event: GovernanceAuditEvent) -> GovernanceAuditEvent:
    """
    Appends an audit event to the tamper-evident hash chain for the given user.
    """
    with _DB_LOCK:
        conn = _get_connection()
        try:
            _init_db(conn)
            cur = conn.cursor()

            # Find the most recent event hash for this user's chain
            cur.execute(
                """
                SELECT event_hash FROM governance_audit_events
                WHERE user_id = ?
                ORDER BY timestamp DESC, rowid DESC
                LIMIT 1
                """,
                (event.user_id,),
            )
            row = cur.fetchone()
            prev_hash = row["event_hash"] if row else GENESIS_HASH

            if not event.event_id:
                event.event_id = f"ev_{uuid.uuid4().hex[:12]}"
            if not event.timestamp:
                event.timestamp = datetime.now(timezone.utc).isoformat()

            event.previous_event_hash = prev_hash
            event.event_hash = _compute_event_hash(event, prev_hash)

            cur.execute(
                """
                INSERT INTO governance_audit_events (
                    event_id, timestamp, user_id, database_identity, event_type,
                    resource_type, resource_id, actor_type, agent_id, orchestration_id,
                    action, result, risk_level, policy_result, request_id, metadata,
                    previous_event_hash, event_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.timestamp,
                    event.user_id,
                    event.database_identity,
                    event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type),
                    event.resource_type,
                    event.resource_id,
                    event.actor_type.value if hasattr(event.actor_type, "value") else str(event.actor_type),
                    event.agent_id,
                    event.orchestration_id,
                    event.action,
                    event.result,
                    event.risk_level.value if hasattr(event.risk_level, "value") else str(event.risk_level),
                    event.policy_result.value if hasattr(event.policy_result, "value") and event.policy_result else (str(event.policy_result) if event.policy_result else None),
                    event.request_id,
                    json.dumps(event.metadata or {}),
                    event.previous_event_hash,
                    event.event_hash,
                ),
            )
            conn.commit()
            return event
        finally:
            conn.close()


def list_audit_events(
    user_id: str,
    database_identity: Optional[str] = None,
    event_type: Optional[GovernanceEventType] = None,
    actor_type: Optional[ActorType] = None,
    risk_level: Optional[RiskLevel] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[GovernanceAuditEvent]:
    """
    Retrieves paginated, filtered audit events for a given user.
    Enforces maximum bounded limit of 200 items.
    """
    safe_limit = max(1, min(limit, 200))
    safe_offset = max(0, offset)

    with _DB_LOCK:
        conn = _get_connection()
        try:
            _init_db(conn)
            cur = conn.cursor()

            query = "SELECT * FROM governance_audit_events WHERE user_id = ?"
            params: List[Any] = [user_id]

            if database_identity:
                query += " AND database_identity = ?"
                params.append(database_identity)

            if event_type:
                query += " AND event_type = ?"
                params.append(event_type.value if hasattr(event_type, "value") else str(event_type))

            if actor_type:
                query += " AND actor_type = ?"
                params.append(actor_type.value if hasattr(actor_type, "value") else str(actor_type))

            if risk_level:
                query += " AND risk_level = ?"
                params.append(risk_level.value if hasattr(risk_level, "value") else str(risk_level))

            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time)

            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time)

            query += " ORDER BY timestamp DESC, rowid DESC LIMIT ? OFFSET ?"
            params.extend([safe_limit, safe_offset])

            cur.execute(query, params)
            rows = cur.fetchall()

            events = [_row_to_audit_event(r) for r in rows]
            return events
        finally:
            conn.close()


def verify_audit_chain(user_id: str) -> Tuple[bool, int, List[str]]:
    """
    Verifies cryptographic hash-chaining integrity across all audit events for a user.
    Returns (is_valid, verified_count, list_of_discrepancies).
    """
    with _DB_LOCK:
        conn = _get_connection()
        try:
            _init_db(conn)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT * FROM governance_audit_events
                WHERE user_id = ?
                ORDER BY timestamp ASC, rowid ASC
                """,
                (user_id,),
            )
            rows = cur.fetchall()
            if not rows:
                return True, 0, []

            expected_prev_hash = GENESIS_HASH
            discrepancies = []
            verified_count = 0

            for r in rows:
                ev = _row_to_audit_event(r)
                if ev.previous_event_hash != expected_prev_hash:
                    discrepancies.append(
                        f"Event {ev.event_id} broken link: prev_hash {ev.previous_event_hash} != expected {expected_prev_hash}"
                    )
                calculated_hash = _compute_event_hash(ev, ev.previous_event_hash or GENESIS_HASH)
                if ev.event_hash != calculated_hash:
                    discrepancies.append(
                        f"Event {ev.event_id} hash mismatch: stored {ev.event_hash} != computed {calculated_hash}"
                    )
                expected_prev_hash = ev.event_hash or calculated_hash
                verified_count += 1

            return len(discrepancies) == 0, verified_count, discrepancies
        finally:
            conn.close()


# ── Security Events Persistence ──────────────────────────────────────────────

def save_security_event(event: SecurityEventRecord) -> SecurityEventRecord:
    """Saves a security incident or blocked action event."""
    with _DB_LOCK:
        conn = _get_connection()
        try:
            _init_db(conn)
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO security_events (
                    event_id, timestamp, user_id, database_identity, event_type,
                    severity, source, resource, description, status, mitigation, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    status=excluded.status,
                    mitigation=excluded.mitigation,
                    metadata=excluded.metadata
                """,
                (
                    event.event_id,
                    event.timestamp,
                    event.user_id,
                    event.database_identity,
                    event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type),
                    event.severity.value if hasattr(event.severity, "value") else str(event.severity),
                    event.source,
                    event.resource,
                    event.description,
                    event.status,
                    event.mitigation,
                    json.dumps(event.metadata or {}),
                ),
            )
            conn.commit()
            return event
        finally:
            conn.close()


def list_security_events(
    user_id: str,
    database_identity: Optional[str] = None,
    severity: Optional[SecurityEventSeverity] = None,
    event_type: Optional[SecurityEventType] = None,
    ip_address: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[SecurityEventRecord]:
    """Retrieves paginated security events for a user."""
    safe_limit = max(1, min(limit, 200))
    safe_offset = max(0, offset)

    with _DB_LOCK:
        conn = _get_connection()
        try:
            _init_db(conn)
            cur = conn.cursor()

            query = "SELECT * FROM security_events WHERE user_id = ?"
            params: List[Any] = [user_id]

            if database_identity:
                query += " AND database_identity = ?"
                params.append(database_identity)

            if severity:
                query += " AND severity = ?"
                params.append(severity.value if hasattr(severity, "value") else str(severity))

            if event_type:
                query += " AND event_type = ?"
                params.append(event_type.value if hasattr(event_type, "value") else str(event_type))

            if ip_address:
                # Filter by source_ip stored in metadata JSON
                query += " AND json_extract(metadata, '$.source_ip') = ?"
                params.append(ip_address)

            query += " ORDER BY timestamp DESC, rowid DESC LIMIT ? OFFSET ?"
            params.extend([safe_limit, safe_offset])

            cur.execute(query, params)
            rows = cur.fetchall()
            return [_row_to_security_event(r) for r in rows]
        finally:
            conn.close()


# ── Agent Trace Telemetry ────────────────────────────────────────────────────

def save_agent_trace(trace: AgentTraceRecord) -> AgentTraceRecord:
    """Saves telemetry for an agent execution step."""
    with _DB_LOCK:
        conn = _get_connection()
        try:
            _init_db(conn)
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO agent_traces (
                    trace_id, request_id, agent_id, user_id, database_identity,
                    tool_or_capability, started_at, completed_at, duration_ms,
                    status, risk_level, policy_decision, evidence_count,
                    orchestration_id, step_id, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trace_id) DO UPDATE SET
                    completed_at=excluded.completed_at,
                    duration_ms=excluded.duration_ms,
                    status=excluded.status,
                    evidence_count=excluded.evidence_count,
                    error_message=excluded.error_message
                """,
                (
                    trace.trace_id,
                    trace.request_id,
                    trace.agent_id,
                    trace.user_id,
                    trace.database_identity,
                    trace.tool_or_capability,
                    trace.started_at,
                    trace.completed_at,
                    trace.duration_ms,
                    trace.status,
                    trace.risk_level.value if hasattr(trace.risk_level, "value") else str(trace.risk_level),
                    trace.policy_decision.value if hasattr(trace.policy_decision, "value") else str(trace.policy_decision),
                    trace.evidence_count,
                    trace.orchestration_id,
                    trace.step_id,
                    trace.error_message,
                ),
            )
            conn.commit()
            return trace
        finally:
            conn.close()


def get_agent_trace(trace_id: str, user_id: str) -> Optional[AgentTraceRecord]:
    """Retrieves a single agent execution trace by ID with user isolation."""
    with _DB_LOCK:
        conn = _get_connection()
        try:
            _init_db(conn)
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM agent_traces WHERE trace_id = ? AND user_id = ?",
                (trace_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            return _row_to_agent_trace(row)
        finally:
            conn.close()


def list_agent_traces_for_orchestration(
    orchestration_id: str, user_id: str
) -> List[AgentTraceRecord]:
    """Retrieves all agent execution traces for an orchestration run."""
    with _DB_LOCK:
        conn = _get_connection()
        try:
            _init_db(conn)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT * FROM agent_traces
                WHERE orchestration_id = ? AND user_id = ?
                ORDER BY started_at ASC
                """,
                (orchestration_id, user_id),
            )
            rows = cur.fetchall()
            return [_row_to_agent_trace(r) for r in rows]
        finally:
            conn.close()


# ── Data Access Events ───────────────────────────────────────────────────────

def save_data_access_event(event: DataAccessEvent) -> DataAccessEvent:
    """Persists a data access monitoring event."""
    with _DB_LOCK:
        conn = _get_connection()
        try:
            _init_db(conn)
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO data_access_events (
                    access_id, timestamp, user_id, database_identity, agent_id,
                    operation, query_fingerprint, tables_referenced, is_write,
                    duration_ms, row_count, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.access_id,
                    event.timestamp,
                    event.user_id,
                    event.database_identity,
                    event.agent_id,
                    event.operation,
                    event.query_fingerprint,
                    json.dumps(event.tables_referenced),
                    1 if event.is_write else 0,
                    event.duration_ms,
                    event.row_count,
                    event.status,
                ),
            )
            conn.commit()
            return event
        finally:
            conn.close()


def list_data_access_events(
    user_id: str,
    database_identity: Optional[str] = None,
    limit: int = 50,
) -> List[DataAccessEvent]:
    """Retrieves recent data access events for a user."""
    safe_limit = max(1, min(limit, 200))
    with _DB_LOCK:
        conn = _get_connection()
        try:
            _init_db(conn)
            cur = conn.cursor()
            query = "SELECT * FROM data_access_events WHERE user_id = ?"
            params: List[Any] = [user_id]
            if database_identity:
                query += " AND database_identity = ?"
                params.append(database_identity)
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(safe_limit)
            cur.execute(query, params)
            rows = cur.fetchall()
            return [_row_to_data_access_event(r) for r in rows]
        finally:
            conn.close()


def clear_governance_data_for_user(user_id: str) -> None:
    """Clears governance audit data for a specific tenant (user isolation)."""
    with _DB_LOCK:
        conn = _get_connection()
        try:
            _init_db(conn)
            cur = conn.cursor()
            cur.execute("DELETE FROM governance_audit_events WHERE user_id = ?", (user_id,))
            cur.execute("DELETE FROM security_events WHERE user_id = ?", (user_id,))
            cur.execute("DELETE FROM agent_traces WHERE user_id = ?", (user_id,))
            cur.execute("DELETE FROM data_access_events WHERE user_id = ?", (user_id,))
            conn.commit()
        finally:
            conn.close()


# ── Row conversion helpers ───────────────────────────────────────────────────

def _row_to_audit_event(row: sqlite3.Row) -> GovernanceAuditEvent:
    return GovernanceAuditEvent.from_dict({
        "event_id": row["event_id"],
        "timestamp": row["timestamp"],
        "user_id": row["user_id"],
        "database_identity": row["database_identity"],
        "event_type": row["event_type"],
        "resource_type": row["resource_type"],
        "resource_id": row["resource_id"],
        "actor_type": row["actor_type"],
        "agent_id": row["agent_id"],
        "orchestration_id": row["orchestration_id"],
        "action": row["action"],
        "result": row["result"],
        "risk_level": row["risk_level"],
        "policy_result": row["policy_result"],
        "request_id": row["request_id"],
        "metadata": json.loads(row["metadata"] or "{}"),
        "previous_event_hash": row["previous_event_hash"],
        "event_hash": row["event_hash"],
    })


def _row_to_security_event(row: sqlite3.Row) -> SecurityEventRecord:
    return SecurityEventRecord.from_dict({
        "event_id": row["event_id"],
        "timestamp": row["timestamp"],
        "user_id": row["user_id"],
        "database_identity": row["database_identity"],
        "event_type": row["event_type"],
        "severity": row["severity"],
        "source": row["source"],
        "resource": row["resource"],
        "description": row["description"],
        "status": row["status"],
        "mitigation": row["mitigation"] or "",
        "metadata": json.loads(row["metadata"] or "{}"),
    })


def _row_to_agent_trace(row: sqlite3.Row) -> AgentTraceRecord:
    return AgentTraceRecord.from_dict({
        "trace_id": row["trace_id"],
        "request_id": row["request_id"],
        "agent_id": row["agent_id"],
        "user_id": row["user_id"],
        "database_identity": row["database_identity"],
        "tool_or_capability": row["tool_or_capability"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "duration_ms": row["duration_ms"] or 0.0,
        "status": row["status"],
        "risk_level": row["risk_level"],
        "policy_decision": row["policy_decision"],
        "evidence_count": row["evidence_count"] or 0,
        "orchestration_id": row["orchestration_id"],
        "step_id": row["step_id"],
        "error_message": row["error_message"],
    })


def _row_to_data_access_event(row: sqlite3.Row) -> DataAccessEvent:
    return DataAccessEvent.from_dict({
        "access_id": row["access_id"],
        "timestamp": row["timestamp"],
        "user_id": row["user_id"],
        "database_identity": row["database_identity"],
        "agent_id": row["agent_id"],
        "operation": row["operation"],
        "query_fingerprint": row["query_fingerprint"],
        "tables_referenced": json.loads(row["tables_referenced"] or "[]"),
        "is_write": bool(row["is_write"]),
        "duration_ms": row["duration_ms"] or 0.0,
        "row_count": row["row_count"],
        "status": row["status"],
    })


class GovernanceAuditStore:
    """Convenience class wrapper around audit store functions."""

    save_audit_event = staticmethod(save_audit_event)
    list_audit_events = staticmethod(list_audit_events)
    verify_audit_chain = staticmethod(verify_audit_chain)
    save_security_event = staticmethod(save_security_event)
    list_security_events = staticmethod(list_security_events)
    save_agent_trace = staticmethod(save_agent_trace)
    get_agent_trace = staticmethod(get_agent_trace)
    list_agent_traces_for_orchestration = staticmethod(list_agent_traces_for_orchestration)
    save_data_access_event = staticmethod(save_data_access_event)
    list_data_access_events = staticmethod(list_data_access_events)
    clear_governance_data_for_user = staticmethod(clear_governance_data_for_user)


_audit_store_instance = GovernanceAuditStore()


def get_audit_store() -> GovernanceAuditStore:
    """Return singleton GovernanceAuditStore."""
    return _audit_store_instance
