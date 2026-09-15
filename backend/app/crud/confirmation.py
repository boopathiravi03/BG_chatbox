from __future__ import annotations

from typing import Any


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
        **(extra or {}),
    }


def get_pending(session_id: str) -> dict[str, Any] | None:
    from app.agent.orchestrator import conversation_state

    return conversation_state.get(session_id)


def clear_pending(session_id: str) -> None:
    from app.agent.orchestrator import conversation_state

    conversation_state.pop(session_id, None)
