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

    return None


def store_pending(
    session_id: str,
    operation: str,
    table: str,
    sql: str,
    preview_rows: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    from app.agent.orchestrator import conversation_state

    conversation_state[session_id] = {
        "pending_sql": sql,
        "operation": operation,
        "table": table,
        "preview_rows": preview_rows or [],
        "database_identity": _database_identity(),
        **(extra or {}),
    }


def get_pending(
    session_id: str,
) -> dict[str, Any] | None:
    from app.agent.orchestrator import conversation_state

    return conversation_state.get(session_id)


def clear_pending(session_id: str) -> None:
    from app.agent.orchestrator import conversation_state

    conversation_state.pop(session_id, None)
