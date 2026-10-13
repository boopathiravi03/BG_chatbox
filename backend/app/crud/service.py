from __future__ import annotations

from typing import Any

from app.crud.confirmation import clear_pending, get_pending
from app.database.database_context import refresh_database_profile
from app.database.database_manager import get_engine
from app.tools.execute_query import execute_query, validate_sql


def _current_database_identity() -> str | None:
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
    active_connector = None
    if current_engine is None:
        try:
            from app.database.connection_context import get_request_user_id
            from app.connectors.registry import get_connection_registry
            uid = get_request_user_id()
            if uid:
                active_connector = get_connection_registry().get_active_connector(uid)
        except Exception:
            pass

        if active_connector is None:
            clear_pending(session_id)
            return {
                "success": False,
                "confirmed": False,
                "error": "No database is currently connected.",
            }

    current_identity = _current_database_identity()

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

    if current_engine is not None:
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
            from app.database.database_context import get_database_profile
            prof = get_database_profile()
            if prof and hasattr(prof, "tables") and table:
                affected = result.get("affected_rows") or 1
                if operation == "insert":
                    if hasattr(prof, "total_rows") and prof.total_rows is not None:
                        prof.total_rows += affected
                    if table in prof.tables and hasattr(prof.tables[table], "row_count") and prof.tables[table].row_count is not None:
                        prof.tables[table].row_count += affected
                elif operation == "delete":
                    if hasattr(prof, "total_rows") and prof.total_rows is not None:
                        prof.total_rows = max(0, prof.total_rows - affected)
                    if table in prof.tables and hasattr(prof.tables[table], "row_count") and prof.tables[table].row_count is not None:
                        prof.tables[table].row_count = max(0, prof.tables[table].row_count - affected)
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
