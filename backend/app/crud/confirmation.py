from __future__ import annotations

from typing import Any

from app.database.database_manager import get_engine


def _database_identity() -> str | None:
    engine = get_engine()

    if engine is not None:
        try:
            return engine.url.render_as_string(
                hide_password=True
            )
        except Exception:
            pass

    try:
        from app.database.connection_context import get_request_user_id
        from app.connectors.registry import get_connection_registry
        uid = get_request_user_id()
        if uid:
            conn = get_connection_registry().get_active_connector(uid)
            if conn:
                return f"{conn.connector_type}://{conn.connection_id}"
    except Exception:
        pass

import hashlib
import json
import time

PENDING_OPERATION_TTL_SECONDS = 300  # 5 minutes


def _generate_fingerprint(
    operation: str,
    table: str,
    sql: str,
    database_identity: str | None,
) -> str:
    payload = f"{operation}:{table}:{sql}:{database_identity or ''}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def store_pending(
    session_id: str,
    operation: str,
    table: str,
    sql: str,
    preview_rows: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from app.agent.orchestrator import conversation_state

    db_id = _database_identity()
    fingerprint = _generate_fingerprint(operation, table, sql, db_id)
    now = time.time()

    pending_data = {
        "pending_sql": sql,
        "operation": operation,
        "table": table,
        "preview_rows": preview_rows or [],
        "database_identity": db_id,
        "fingerprint": fingerprint,
        "created_at": now,
        "expires_at": now + PENDING_OPERATION_TTL_SECONDS,
        "is_executing": False,
        **(extra or {}),
    }

    conversation_state[session_id] = pending_data
    return pending_data


def get_pending(
    session_id: str,
) -> dict[str, Any] | None:
    from app.agent.orchestrator import conversation_state

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

    conversation_state.pop(session_id, None)
