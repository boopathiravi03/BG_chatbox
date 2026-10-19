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


def execute_confirmed(
    session_id: str,
    fingerprint: str | None = None,
    high_risk_confirmed: bool = False,
) -> dict[str, Any]:
    pending = get_pending(session_id)

    if not pending:
        return {
            "success": False,
            "confirmed": False,
            "error": "There is no pending database operation to confirm, or the operation has expired.",
        }

    # Atomic concurrency lock: prevent double-clicks or duplicate requests
    if pending.get("is_executing"):
        return {
            "success": False,
            "confirmed": False,
            "error": "Operation is already executing. Please wait.",
        }
    pending["is_executing"] = True

    try:
        # Fingerprint verification if supplied
        if fingerprint and pending.get("fingerprint") and fingerprint != pending.get("fingerprint"):
            clear_pending(session_id)
            return {
                "success": False,
                "confirmed": False,
                "error": "Confirmation fingerprint mismatch or outdated preview. Please preview the operation again.",
            }

        sql = pending.get("pending_sql")
        operation = pending.get("operation")
        table = pending.get("table")
        where_clause = pending.get("where_clause")
        is_high_risk = pending.get("is_high_risk", False)

        if not sql:
            clear_pending(session_id)
            return {
                "success": False,
                "confirmed": False,
                "error": "The pending database operation has expired.",
            }

        # Check high-risk confirmation
        if is_high_risk and not high_risk_confirmed:
            # We do NOT clear pending here so user can explicitly confirm with high_risk_confirmed=True
            pending["is_executing"] = False
            return {
                "success": False,
                "confirmed": False,
                "requires_high_risk_confirmation": True,
                "estimated_affected_rows": pending.get("estimated_affected_rows"),
                "error": "This operation affects more than 100 rows and requires explicit high-risk confirmation.",
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

        # Schema & Revalidation immediately prior to execution
        from app.database.database_context import get_database_profile
        from app.crud.matcher import count_matching_records
        prof = get_database_profile()
        schema = prof.schema if prof and hasattr(prof, "schema") else {}

        if table and schema and table not in schema:
            clear_pending(session_id)
            return {
                "success": False,
                "confirmed": False,
                "error": f"Target table '{table}' is no longer present in the database.",
            }

        # Re-check count immediately before execution for UPDATE and DELETE
        if operation in ("update", "delete") and where_clause and current_engine is not None:
            count_res = count_matching_records(table, where_clause, schema)
            if count_res.get("success"):
                live_cnt = count_res.get("count")
                old_cnt = pending.get("estimated_affected_rows")
                # If estimate changed materially (> 20% or crossed high risk threshold), invalidate
                if old_cnt is not None and live_cnt != old_cnt:
                    if abs(live_cnt - old_cnt) > max(5, int(old_cnt * 0.2)) or (live_cnt > 100 and not is_high_risk):
                        clear_pending(session_id)
                        return {
                            "success": False,
                            "confirmed": False,
                            "error": f"The number of matching records changed from {old_cnt} to {live_cnt} since preview. Please re-run the request to preview updated records.",
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
                "affected_rows": result.get("affected_rows", 1 if operation == "insert" else 0),
                "message": f"{operation.capitalize()} completed successfully. Affected rows: {result.get('affected_rows', 1 if operation == 'insert' else 0)}.",
            }

        clear_pending(session_id)
        return {
            **result,
            "confirmed": False,
            "operation": operation,
            "table": table,
        }
    finally:
        # If pending wasn't cleared, ensure is_executing is released
        p = get_pending(session_id)
        if p:
            p["is_executing"] = False
