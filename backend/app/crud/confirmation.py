"""backend/app/crud/confirmation.py

Stores and retrieves staged/pending database operations awaiting explicit user approval.
Binds confirmation to exact canonical SQL, parameters, database identity, connection ID,
authenticated user, session, and a cryptographically strong SHA-256 fingerprint.
"""

from __future__ import annotations

import time
import threading
from typing import Any, Optional

from app.database.database_manager import get_engine
from app.tools.command_policy import generate_command_fingerprint

PENDING_OPERATION_TTL_SECONDS = 300  # 5 minutes
_CONFIRMATION_LOCK = threading.RLock()


def _database_identity(user_id: Optional[str] = None, connection_id: Optional[str] = None) -> str | None:
    if connection_id or user_id:
        try:
            from app.database.connection_context import get_request_user_id
            from app.connectors.registry import get_connection_registry

            uid = user_id or get_request_user_id()
            if uid:
                reg = get_connection_registry()
                conn = reg.get_connector(uid, connection_id) if connection_id else reg.get_active_connector(uid)
                if conn:
                    return f"{conn.connector_type}://{conn.connection_id}"
        except Exception:
            pass

    engine = get_engine()
    if engine is not None:
        try:
            return engine.url.render_as_string(hide_password=True)
        except Exception:
            pass

    return None


def store_pending(
    session_id: str,
    operation: str,
    table: str,
    sql: str,
    preview_rows: list[dict[str, Any]] | None = None,
    user_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from app.agent.orchestrator import conversation_state

    # Resolve user_id from session_id if formatted as 'user_id:sub_session'
    resolved_uid = user_id
    if not resolved_uid and ":" in session_id:
        resolved_uid = session_id.split(":", 1)[0]

    conn_id = (extra or {}).get("connection_id")
    db_id = _database_identity(user_id=resolved_uid, connection_id=conn_id)
    params = (extra or {}).get("params")

    now = time.time()
    expires_at = now + PENDING_OPERATION_TTL_SECONDS

    fingerprint = generate_command_fingerprint(
        operation=operation,
        target=table,
        sql=sql,
        database_identity=db_id,
        connection_id=conn_id,
        user_id=resolved_uid,
        session_id=session_id,
        params=params,
        expires_at=expires_at,
    )

    pending_data = {
        "pending_sql": sql,
        "operation": operation.lower(),
        "table": table,
        "preview_rows": preview_rows or [],
        "database_identity": db_id,
        "connection_id": conn_id,
        "user_id": resolved_uid,
        "session_id": session_id,
        "fingerprint": fingerprint,
        "params": params,
        "created_at": now,
        "expires_at": expires_at,
        "is_executing": False,
        **(extra or {}),
    }

    with _CONFIRMATION_LOCK:
        conversation_state[session_id] = pending_data

    return pending_data


def get_pending(session_id: str) -> dict[str, Any] | None:
    from app.agent.orchestrator import conversation_state

    with _CONFIRMATION_LOCK:
        pending = conversation_state.get(session_id)
        if not pending:
            return None

        # Enforce expiration
        expires_at = pending.get("expires_at")
        if expires_at and time.time() > expires_at:
            conversation_state.pop(session_id, None)
            return None

        return pending


def clear_pending(session_id: str) -> None:
    from app.agent.orchestrator import conversation_state

    with _CONFIRMATION_LOCK:
        conversation_state.pop(session_id, None)
