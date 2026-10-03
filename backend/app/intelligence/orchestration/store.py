"""
backend/app/intelligence/orchestration/store.py

Thread-safe SQLite storage for Phase 9.2: Advanced Agent Orchestration runs.
Strictly isolates records by (user_id, database_identity).
"""

from __future__ import annotations

import os
import json
import sqlite3
import threading
from typing import List, Optional, Dict, Any
from pathlib import Path

from app.intelligence.orchestration.models import OrchestrationRun

_DB_LOCK = threading.RLock()
_DEFAULT_DB_PATH = Path(__file__).resolve().parent / "bgai_orchestration.db"


def _get_db_path() -> Path:
    override = os.getenv("BGAI_ORCHESTRATION_DB_PATH")
    if override:
        return Path(override)
    return _DEFAULT_DB_PATH


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS orchestration_runs (
            orchestration_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            database_identity TEXT NOT NULL,
            goal TEXT NOT NULL,
            status TEXT NOT NULL,
            task_graph TEXT,
            evidence_ledger TEXT,
            conflicts TEXT,
            proposed_action TEXT,
            executive_summary TEXT,
            explanation TEXT,
            confidence_tier TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT,
            duration_ms REAL,
            metadata TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_orchestration_user_db ON orchestration_runs(user_id, database_identity)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_orchestration_created ON orchestration_runs(created_at DESC)"
    )
    conn.commit()


def _get_connection() -> sqlite3.Connection:
    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def save_orchestration_run(run: OrchestrationRun) -> None:
    """Saves or updates an OrchestrationRun record in SQLite."""
    with _DB_LOCK:
        conn = _get_connection()
        try:
            _init_db(conn)
            run_dict = run.to_dict()
            conn.execute(
                """
                INSERT INTO orchestration_runs (
                    orchestration_id, user_id, database_identity, goal, status,
                    task_graph, evidence_ledger, conflicts, proposed_action,
                    executive_summary, explanation, confidence_tier, created_at,
                    updated_at, completed_at, duration_ms, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(orchestration_id) DO UPDATE SET
                    status=excluded.status,
                    task_graph=excluded.task_graph,
                    evidence_ledger=excluded.evidence_ledger,
                    conflicts=excluded.conflicts,
                    proposed_action=excluded.proposed_action,
                    executive_summary=excluded.executive_summary,
                    explanation=excluded.explanation,
                    confidence_tier=excluded.confidence_tier,
                    updated_at=excluded.updated_at,
                    completed_at=excluded.completed_at,
                    duration_ms=excluded.duration_ms,
                    metadata=excluded.metadata
                """,
                (
                    run.orchestration_id,
                    run.user_id,
                    run.database_identity,
                    run.goal,
                    run.status.value,
                    json.dumps(run_dict.get("task_graph")),
                    json.dumps(run_dict.get("evidence_ledger", [])),
                    json.dumps(run_dict.get("conflicts", [])),
                    json.dumps(run_dict.get("proposed_action")),
                    run.executive_summary,
                    json.dumps(run_dict.get("explanation", {})),
                    run.confidence_tier.value,
                    run.created_at,
                    run.updated_at,
                    run.completed_at,
                    run.duration_ms,
                    json.dumps(run_dict.get("metadata", {})),
                ),
            )
            conn.commit()
        finally:
            conn.close()


def get_orchestration_run(
    orchestration_id: str,
    user_id: str,
    database_identity: str,
) -> Optional[OrchestrationRun]:
    """Retrieves an OrchestrationRun by ID with tenant and DB isolation."""
    with _DB_LOCK:
        conn = _get_connection()
        try:
            _init_db(conn)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT * FROM orchestration_runs
                WHERE orchestration_id = ? AND user_id = ? AND database_identity = ?
                """,
                (orchestration_id, user_id, database_identity),
            )
            row = cur.fetchone()
            if not row:
                return None
            return _row_to_run(row)
        finally:
            conn.close()


def list_orchestration_runs(
    user_id: str,
    database_identity: str,
    limit: int = 20,
) -> List[OrchestrationRun]:
    """Lists orchestration runs for a given user and database."""
    with _DB_LOCK:
        conn = _get_connection()
        try:
            _init_db(conn)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT * FROM orchestration_runs
                WHERE user_id = ? AND database_identity = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, database_identity, limit),
            )
            rows = cur.fetchall()
            return [_row_to_run(r) for r in rows]
        finally:
            conn.close()


def delete_orchestration_run(
    orchestration_id: str,
    user_id: str,
    database_identity: str,
) -> bool:
    """Deletes a run matching the tenant and DB isolation boundaries."""
    with _DB_LOCK:
        conn = _get_connection()
        try:
            _init_db(conn)
            cur = conn.cursor()
            cur.execute(
                """
                DELETE FROM orchestration_runs
                WHERE orchestration_id = ? AND user_id = ? AND database_identity = ?
                """,
                (orchestration_id, user_id, database_identity),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def clear_user_orchestration_runs(user_id: str, database_identity: Optional[str] = None) -> None:
    """Clears orchestration runs for tests or user session reset."""
    with _DB_LOCK:
        conn = _get_connection()
        try:
            _init_db(conn)
            if database_identity:
                conn.execute(
                    "DELETE FROM orchestration_runs WHERE user_id = ? AND database_identity = ?",
                    (user_id, database_identity),
                )
            else:
                conn.execute(
                    "DELETE FROM orchestration_runs WHERE user_id = ?",
                    (user_id,),
                )
            conn.commit()
        finally:
            conn.close()


def _row_to_run(row: sqlite3.Row) -> OrchestrationRun:
    data = {
        "orchestration_id": row["orchestration_id"],
        "user_id": row["user_id"],
        "database_identity": row["database_identity"],
        "goal": row["goal"],
        "status": row["status"],
        "task_graph": json.loads(row["task_graph"]) if row["task_graph"] else None,
        "evidence_ledger": json.loads(row["evidence_ledger"]) if row["evidence_ledger"] else [],
        "conflicts": json.loads(row["conflicts"]) if row["conflicts"] else [],
        "proposed_action": json.loads(row["proposed_action"]) if row["proposed_action"] else None,
        "executive_summary": row["executive_summary"] or "",
        "explanation": json.loads(row["explanation"]) if row["explanation"] else {},
        "confidence_tier": row["confidence_tier"] or "HIGH",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "completed_at": row["completed_at"],
        "duration_ms": row["duration_ms"] or 0.0,
        "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
    }
    return OrchestrationRun.from_dict(data)
