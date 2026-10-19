"""backend/app/guardian/store.py

Persistent, thread-safe SQLite storage for AI Database Guardian incidents.
Stores incident lifecycle (DETECTED, ACKNOWLEDGED, RESOLVED) across application restarts.
Enforces strict user and tenant isolation.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.guardian.models import GuardianIncident, IncidentSeverity, IncidentStatus

logger = logging.getLogger("bgai.guardian.store")
_STORE_LOCK = threading.RLock()
_DEFAULT_DB_PATH = Path(__file__).resolve().parent / "bgai_guardian.db"


def _get_db_path() -> Path:
    override = os.getenv("BGAI_GUARDIAN_DB_PATH")
    if override:
        return Path(override)
    return _DEFAULT_DB_PATH


def _get_connection() -> sqlite3.Connection:
    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_guardian_store() -> None:
    """Initializes the guardian incident schema and ensures schema migrations."""
    with _STORE_LOCK:
        conn = _get_connection()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS guardian_incidents (
                    incident_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    database_identity TEXT NOT NULL,
                    database_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    category TEXT NOT NULL,
                    detected_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    observed_facts TEXT NOT NULL,
                    trigger_rule TEXT NOT NULL,
                    likely_root_cause TEXT NOT NULL,
                    confidence_score REAL NOT NULL,
                    confidence_justification TEXT,
                    limitations TEXT,
                    verification_steps TEXT NOT NULL,
                    ai_advisory TEXT,
                    recovery_rule TEXT,
                    recovered_at TEXT,
                    acknowledged_by TEXT,
                    acknowledged_at TEXT,
                    resolved_by TEXT,
                    resolved_at TEXT,
                    resolution_notes TEXT
                )
                """
            )
            # Safe schema migration for existing sqlite database
            columns = [col[1] for col in conn.execute("PRAGMA table_info(guardian_incidents)").fetchall()]
            if "confidence_justification" not in columns:
                conn.execute("ALTER TABLE guardian_incidents ADD COLUMN confidence_justification TEXT DEFAULT ''")
            if "limitations" not in columns:
                conn.execute("ALTER TABLE guardian_incidents ADD COLUMN limitations TEXT DEFAULT '[]'")
            if "recovery_rule" not in columns:
                conn.execute("ALTER TABLE guardian_incidents ADD COLUMN recovery_rule TEXT")
            if "recovered_at" not in columns:
                conn.execute("ALTER TABLE guardian_incidents ADD COLUMN recovered_at TEXT")

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_guardian_user_db ON guardian_incidents(user_id, database_identity)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_guardian_status ON guardian_incidents(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_guardian_category ON guardian_incidents(category)"
            )
            conn.commit()
        finally:
            conn.close()


def save_incident(incident: GuardianIncident) -> None:
    """Persists or updates a guardian incident."""
    with _STORE_LOCK:
        conn = _get_connection()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO guardian_incidents (
                    incident_id, user_id, database_identity, database_type,
                    title, severity, status, category, detected_at, updated_at,
                    observed_facts, trigger_rule, likely_root_cause, confidence_score,
                    confidence_justification, limitations, verification_steps, ai_advisory,
                    recovery_rule, recovered_at, acknowledged_by, acknowledged_at,
                    resolved_by, resolved_at, resolution_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    incident.incident_id,
                    incident.user_id,
                    incident.database_identity,
                    incident.database_type,
                    incident.title,
                    incident.severity.value,
                    incident.status.value,
                    incident.category,
                    incident.detected_at,
                    incident.updated_at,
                    json.dumps(incident.observed_facts),
                    incident.trigger_rule,
                    incident.likely_root_cause,
                    incident.confidence_score,
                    incident.confidence_justification,
                    json.dumps(incident.limitations),
                    json.dumps(incident.verification_steps),
                    incident.ai_advisory,
                    incident.recovery_rule,
                    incident.recovered_at,
                    incident.acknowledged_by,
                    incident.acknowledged_at,
                    incident.resolved_by,
                    incident.resolved_at,
                    incident.resolution_notes,
                ),
            )
            conn.commit()
        finally:
            conn.close()


def find_active_incident(
    user_id: str,
    database_identity: str,
    category: str,
    trigger_rule: str,
) -> Optional[GuardianIncident]:
    """Finds an existing unresolved incident matching the criteria to prevent deduplication."""
    with _STORE_LOCK:
        conn = _get_connection()
        try:
            cur = conn.execute(
                """
                SELECT * FROM guardian_incidents
                WHERE user_id = ? 
                  AND database_identity = ? 
                  AND category = ? 
                  AND trigger_rule = ?
                  AND status NOT IN ('resolved')
                ORDER BY detected_at DESC LIMIT 1
                """,
                (user_id, database_identity, category, trigger_rule),
            )
            row = cur.fetchone()
            if row:
                return _row_to_incident(row)
            return None
        finally:
            conn.close()


def list_incidents(
    user_id: str,
    database_identity: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = 50,
) -> List[GuardianIncident]:
    """Lists incidents filtered by user and optionally database identity and status."""
    with _STORE_LOCK:
        conn = _get_connection()
        try:
            query = "SELECT * FROM guardian_incidents WHERE user_id = ?"
            params: List[Any] = [user_id]

            if database_identity:
                query += " AND database_identity = ?"
                params.append(database_identity)

            if status_filter:
                query += " AND status = ?"
                params.append(status_filter)

            query += " ORDER BY updated_at DESC LIMIT ?"
            params.append(limit)

            cur = conn.execute(query, params)
            return [_row_to_incident(r) for r in cur.fetchall()]
        finally:
            conn.close()


def get_incident_by_id(user_id: str, incident_id: str) -> Optional[GuardianIncident]:
    """Retrieves a specific incident enforcing user isolation."""
    with _STORE_LOCK:
        conn = _get_connection()
        try:
            cur = conn.execute(
                "SELECT * FROM guardian_incidents WHERE user_id = ? AND incident_id = ?",
                (user_id, incident_id),
            )
            row = cur.fetchone()
            if row:
                return _row_to_incident(row)
            return None
        finally:
            conn.close()


def _row_to_incident(row: sqlite3.Row) -> GuardianIncident:
    # Safe fallback getter helper for columns in case of old schema rows
    keys = row.keys()
    conf_just = row["confidence_justification"] if "confidence_justification" in keys and row["confidence_justification"] else ""
    raw_limits = row["limitations"] if "limitations" in keys and row["limitations"] else "[]"
    rec_rule = row["recovery_rule"] if "recovery_rule" in keys else None
    rec_at = row["recovered_at"] if "recovered_at" in keys else None

    return GuardianIncident(
        incident_id=row["incident_id"],
        user_id=row["user_id"],
        database_identity=row["database_identity"],
        database_type=row["database_type"],
        title=row["title"],
        severity=IncidentSeverity(row["severity"]),
        status=IncidentStatus(row["status"]),
        category=row["category"],
        detected_at=row["detected_at"],
        updated_at=row["updated_at"],
        observed_facts=json.loads(row["observed_facts"]) if row["observed_facts"] else {},
        trigger_rule=row["trigger_rule"],
        likely_root_cause=row["likely_root_cause"],
        confidence_score=float(row["confidence_score"]),
        confidence_justification=conf_just,
        limitations=json.loads(raw_limits) if isinstance(raw_limits, str) else [],
        verification_steps=json.loads(row["verification_steps"]) if row["verification_steps"] else [],
        ai_advisory=row["ai_advisory"],
        recovery_rule=rec_rule,
        recovered_at=rec_at,
        acknowledged_by=row["acknowledged_by"],
        acknowledged_at=row["acknowledged_at"],
        resolved_by=row["resolved_by"],
        resolved_at=row["resolved_at"],
        resolution_notes=row["resolution_notes"],
    )

