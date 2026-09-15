from __future__ import annotations

from typing import Any

from app.crud.confirmation import clear_pending, get_pending
from app.database.database_context import refresh_database_profile
from app.database.database_manager import get_engine
from app.tools.execute_query import execute_query, validate_sql


def _current_database_identity() -> str | None:
    engine = get_engine()

    if engine is None:
        return None

    try:
        return engine.url.render_as_string(
            hide_password=True
        )
    except Exception:
        return None


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

    current_engine = get_engine()

    if current_engine is None:
        clear_pending(session_id)
        return {
            "success": False,
            "confirmed": False,
            "error": "No database is currently connected.",
        }

    try:
        current_identity = current_engine.url.render_as_string(
            hide_password=True
        )
    except Exception:
        current_identity = None

    if pending.get("database_identity") != current_identity:
        clear_pending(session_id)
        return {
            "success": False,
            "confirmed": False,
            "error": (
                "The database connection changed after this "
                "operation was prepared. Please create the operation again."
            ),
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
