"""backend/app/crud/service.py

Execution service for user-confirmed database operations.
Validates cryptographic fingerprints, user session ownership, connection stability,
schema constraints, high-risk approvals, and executes confirmed SQL or native commands
through the CommandPolicy-protected execution engine.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from app.crud.confirmation import clear_pending, get_pending
from app.database.database_context import refresh_database_profile, get_database_profile
from app.database.database_manager import get_engine
from app.tools.execute_query import execute_query, validate_sql


def _current_database_identity(user_id: Optional[str] = None, connection_id: Optional[str] = None) -> str | None:
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


def execute_confirmed(
    session_id: str,
    fingerprint: str | None = None,
    high_risk_confirmed: bool = False,
    user_id: str | None = None,
) -> dict[str, Any]:
    pending = get_pending(session_id)

    if not pending:
        return {
            "success": False,
            "confirmed": False,
            "error": "There is no pending database operation to confirm, or the operation has expired.",
        }

    # 1. Atomic concurrency lock: prevent duplicate or concurrent execution
    if pending.get("is_executing"):
        return {
            "success": False,
            "confirmed": False,
            "error": "Operation is already executing. Please wait.",
        }
    pending["is_executing"] = True

    try:
        # 2. Cross-user isolation verification
        expected_uid = pending.get("user_id")
        if not expected_uid and ":" in session_id:
            expected_uid = session_id.split(":", 1)[0]
        if expected_uid and user_id and expected_uid != user_id:
            clear_pending(session_id)
            return {
                "success": False,
                "confirmed": False,
                "error": "Unauthorized: this confirmation belongs to a different user session.",
            }

        # 3. Preview Fingerprint Verification
        stored_fp = pending.get("fingerprint")
        if not fingerprint or not stored_fp or fingerprint != stored_fp:
            clear_pending(session_id)
            return {
                "success": False,
                "confirmed": False,
                "error": "Confirmation fingerprint missing, invalid, or preview expired. Please preview the operation again.",
            }

        sql = pending.get("pending_sql")
        operation = pending.get("operation") or "query"
        table = pending.get("table")
        where_clause = pending.get("where_clause")
        is_high_risk = pending.get("is_high_risk", False)
        conn_id = pending.get("connection_id")
        params = pending.get("params")

        if not sql:
            clear_pending(session_id)
            return {
                "success": False,
                "confirmed": False,
                "error": "The pending database operation has expired.",
            }

        # 4. High-Risk Confirmation Enforcement
        if is_high_risk and not high_risk_confirmed:
            pending["is_executing"] = False
            return {
                "success": False,
                "confirmed": False,
                "requires_high_risk_confirmation": True,
                "estimated_affected_rows": pending.get("estimated_affected_rows"),
                "impact_summary": pending.get("impact_summary"),
                "error": "This is a destructive or high-impact operation requiring explicit high-risk confirmation.",
            }

        # 5. Connection Availability & Identity Binding
        if conn_id:
            try:
                from app.connectors.registry import get_connection_registry
                reg = get_connection_registry()
                cur_conn = reg.get_connector(expected_uid, conn_id) if expected_uid else None
                if not cur_conn:
                    clear_pending(session_id)
                    return {
                        "success": False,
                        "confirmed": False,
                        "error": f"The database connection '{conn_id}' changed or was disconnected after this operation was prepared.",
                    }
            except Exception:
                pass

        current_identity = _current_database_identity(user_id=expected_uid, connection_id=conn_id)
        if pending.get("database_identity") and current_identity and pending.get("database_identity") != current_identity:
            clear_pending(session_id)
            return {
                "success": False,
                "confirmed": False,
                "error": (
                    "The database connection changed after this operation was prepared. "
                    "Please preview and stage the operation again on the current connection."
                ),
            }

        # 6. Schema & Target Revalidation
        current_engine = get_engine()
        existing_tables = set()
        has_inspected_tables = False
        if current_engine is not None:
            try:
                from sqlalchemy import inspect
                existing_tables = set(inspect(current_engine).get_table_names())
                has_inspected_tables = True
            except Exception:
                pass
        if not has_inspected_tables:
            prof = get_database_profile()
            if prof and hasattr(prof, "tables") and prof.tables:
                existing_tables = set(prof.tables.keys())
                has_inspected_tables = True

        # For DROP, TRUNCATE, ALTER, UPDATE, DELETE: verify target table exists
        if operation in ("drop", "truncate", "alter", "update", "delete") and table and has_inspected_tables:
            clean_tbl = table.strip("`\"[]")
            if clean_tbl not in existing_tables and "IF EXISTS" not in sql.upper():
                clear_pending(session_id)
                return {
                    "success": False,
                    "confirmed": False,
                    "error": f"Target table '{clean_tbl}' is no longer present in the database.",
                }

        # Re-check count immediately before execution for bounded UPDATE and DELETE
        current_engine = get_engine()
        if operation in ("update", "delete") and where_clause and current_engine is not None:
            try:
                from app.crud.matcher import count_matching_records

                count_res = count_matching_records(table, where_clause, schema)
                if count_res.get("success"):
                    live_cnt = count_res.get("count")
                    old_cnt = pending.get("estimated_affected_rows")
                    if old_cnt is not None and live_cnt != old_cnt:
                        if abs(live_cnt - old_cnt) > max(5, int(old_cnt * 0.2)) or (
                            live_cnt > 100 and not is_high_risk
                        ):
                            clear_pending(session_id)
                            return {
                                "success": False,
                                "confirmed": False,
                                "error": (
                                    f"The number of matching records changed from {old_cnt} to {live_cnt} since preview. "
                                    "Please re-run the request to preview updated records."
                                ),
                            }
            except Exception:
                pass

        # 7. Policy Re-validation
        validation = validate_sql(sql, connection_id=conn_id)
        if not validation.get("allowed"):
            clear_pending(session_id)
            return {
                "success": False,
                "confirmed": False,
                "error": validation.get("reason", "Operation rejected by policy."),
            }

        if not validation.get("requires_confirmation"):
            clear_pending(session_id)
            return {
                "success": False,
                "confirmed": False,
                "error": "This operation is not a valid pending database change.",
            }

        # 8. Single-Use Replay Prevention: Clear pending record immediately
        clear_pending(session_id)

        # 9. Execute Confirmed Operation
        result = execute_query(
            sql=sql,
            connection_id=conn_id,
            is_confirmed=True,
            high_risk_confirmed=high_risk_confirmed,
            user_id=expected_uid,
            params=params,
        )

        if result.get("success"):
            # Invalidate schema cache so UI and agent immediately see updated entities
            try:
                refresh_database_profile()
            except Exception:
                pass

            affected = result.get("affected_rows", 0)
            msg = result.get("message") or f"{operation.capitalize()} completed successfully."
            if affected > 0:
                msg = f"{operation.capitalize()} completed successfully. Affected rows: {affected}."

            return {
                **result,
                "confirmed": True,
                "operation": operation,
                "table": table,
                "affected_rows": affected,
                "message": msg,
            }

        return {
            **result,
            "confirmed": False,
            "operation": operation,
            "table": table,
        }

    finally:
        p = get_pending(session_id)
        if p:
            p["is_executing"] = False
