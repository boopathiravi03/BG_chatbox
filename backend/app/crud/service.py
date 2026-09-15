from __future__ import annotations

from typing import Any

from app.crud.confirmation import clear_pending, get_pending, store_pending
from app.crud.intent import parse_crud_intent
from app.crud.matcher import match_records
from app.crud.planner import preview_delete, preview_insert, preview_update
from app.crud.resolver import resolve_table
from app.tools.execute_query import execute_query, validate_sql
from app.database.database_context import refresh_database_profile


def execute_confirmed(session_id: str) -> dict[str, Any]:
    pending = get_pending(session_id)

    if not pending:
        return {
            "success": False,
            "confirmed": False,
            "error": "There is no pending database operation to confirm.",
        }

    sql = pending.get("pending_sql")
    operation = pending.get("operation")
    table = pending.get("table")

    if not sql:
        clear_pending(session_id)
        return {
            "success": False,
            "confirmed": False,
            "error": "The pending database operation has expired.",
        }

    validation = validate_sql(sql)

    if not validation.get("allowed"):
        clear_pending(session_id)
        return {
            "success": False,
            "confirmed": False,
            "error": validation.get("reason", "Operation rejected."),
        }

    if not validation.get("requires_confirmation"):
        clear_pending(session_id)
        return {
            "success": False,
            "confirmed": False,
            "error": "This operation is not a valid pending database change.",
        }

    result = execute_query(sql)

    if result.get("success"):
        try:
            refresh_database_profile()
        except Exception:
            pass
        clear_pending(session_id)
        return {
            **result,
            "confirmed": True,
            "operation": operation,
            "table": table,
            "message": f"{operation.capitalize()} completed successfully.",
        }

    clear_pending(session_id)
    return {
        **result,
        "confirmed": False,
        "operation": operation,
        "table": table,
    }
