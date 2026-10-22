"""backend/app/tools/execute_query.py

Database query execution tool for BG AI 2.0.
All database executions across relational and non-relational engines pass through this module.
Integrates centralized CommandPolicy validation, confirmation gating, multi-connector routing,
and audit logging.
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional
from sqlalchemy import text

from app.database.database_manager import get_engine, get_current_db_type
from app.tools.command_policy import CommandPolicy, CommandCategory

# Compatibility sets
MUTATION_COMMANDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "CREATE",
    "DROP",
    "ALTER",
    "TRUNCATE",
}

READ_ONLY = {
    "SELECT",
    "SHOW",
    "DESCRIBE",
    "EXPLAIN",
    "PRAGMA",
}

DANGEROUS_OPERATIONS = {
    "DROP",
    "TRUNCATE",
}


def validate_sql(
    sql: str,
    connection_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validates a SQL query or database command against the centralized command policy.
    """
    target_conn = None
    uid = user_id
    try:
        from app.database.connection_context import get_request_user_id
        from app.connectors.registry import get_connection_registry

        if not uid:
            uid = get_request_user_id()
        if uid:
            reg = get_connection_registry()
            target_conn = (
                reg.get_connector(uid, connection_id)
                if connection_id
                else reg.get_active_connector(uid)
            )
    except Exception:
        pass

    db_type = (
        target_conn.connector_type
        if target_conn
        else get_current_db_type()
    )

    res = CommandPolicy.validate(
        sql=sql,
        dialect=db_type,
        connector=target_conn,
        user_id=uid,
    )
    return res.to_dict()


def execute_query(
    sql: str,
    connection_id: Optional[str] = None,
    is_confirmed: bool = False,
    high_risk_confirmed: bool = False,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Executes a SQL query or database command across relational or non-relational connectors
    under policy supervision.
    """
    target_conn = None
    uid = user_id
    client_ip = "unknown"
    try:
        from app.database.connection_context import (
            get_request_user_id,
            get_request_client_ip,
        )
        from app.connectors.registry import get_connection_registry

        if not uid:
            uid = get_request_user_id()
        client_ip = get_request_client_ip() or "unknown"

        if uid:
            reg = get_connection_registry()
            if connection_id:
                target_conn = reg.get_connector(uid, connection_id)
                if not target_conn:
                    return {
                        "success": False,
                        "columns": [],
                        "rows": [],
                        "error": f"Connection '{connection_id}' not found or unauthorized.",
                        "rows_returned": 0,
                    }
            else:
                target_conn = reg.get_active_connector(uid)
    except Exception:
        pass

    # 1. Non-Relational Connectors (MongoDB, Redis, Vector, etc.)
    if target_conn and target_conn.category != "relational":
        validation = CommandPolicy.validate(
            sql=sql,
            dialect=target_conn.connector_type,
            connector=target_conn,
            user_id=uid,
        ).to_dict()

        if not validation["allowed"]:
            return {
                "success": False,
                "columns": [],
                "rows": [],
                "error": validation["reason"],
                "operation": validation["operation"],
                "database": target_conn.connector_type,
                "affected_rows": 0,
            }

        if validation.get("requires_confirmation") and not is_confirmed:
            fingerprint = None
            if session_id:
                from app.crud.confirmation import store_pending

                staged = store_pending(
                    session_id=session_id,
                    operation=validation.get("operation", "query"),
                    table=validation.get("primary_table") or "collection",
                    sql=sql,
                    user_id=uid,
                    extra={
                        "is_high_risk": validation.get("is_high_risk", False),
                        "impact_summary": validation.get("impact_summary"),
                        "target_objects": validation.get("target_objects", []),
                        "connection_id": target_conn.connection_id,
                        "rollback_supported": validation.get("rollback_supported", False),
                        "rollback_limitations": validation.get("rollback_limitations", ""),
                        "params": params,
                    },
                )
                fingerprint = staged.get("fingerprint")

            return {
                "success": False,
                "requires_confirmation": True,
                "is_high_risk": validation.get("is_high_risk", False),
                "columns": [],
                "rows": [],
                "error": "This database operation requires explicit user confirmation before execution.",
                "operation": validation["operation"],
                "database": target_conn.connector_type,
                "impact_summary": validation.get("impact_summary"),
                "target_objects": validation.get("target_objects"),
                "fingerprint": fingerprint,
                "session_id": session_id.split(":", 1)[-1] if (session_id and ":" in session_id) else session_id,
                "rollback_supported": validation.get("rollback_supported", False),
                "rollback_limitations": validation.get("rollback_limitations", ""),
                "affected_rows": 0,
            }

        # Confirmed execution on non-relational connector
        res = target_conn.execute_query(sql, params=params)
        return {
            "success": res.success,
            "columns": res.columns,
            "rows": res.rows,
            "rows_returned": res.rows_returned,
            "operation": validation.get("operation", "query"),
            "database": target_conn.connector_type,
            "affected_rows": res.affected_rows or 0,
            "error": res.error,
            "source_id": target_conn.connection_id,
            "source_name": target_conn.name,
            "execution_time_ms": res.execution_time_ms,
        }

    # 2. Relational Policy-Based Validation
    db_type = (
        target_conn.connector_type
        if target_conn
        else get_current_db_type()
    )

    validation = CommandPolicy.validate(
        sql=sql,
        dialect=db_type,
        connector=target_conn,
        user_id=uid,
    ).to_dict()

    if not validation["allowed"]:
        try:
            from app.intelligence.governance.security_events import SecurityEventManager
            from app.intelligence.governance.models import (
                SecurityEventType,
                SecurityEventSeverity,
            )

            current_uid = uid or "default_user"
            db_id = target_conn.connector_type if target_conn else db_type

            if "Multiple SQL statements" in validation.get("reason", ""):
                SecurityEventManager.log_ip_threat(
                    user_id=current_uid,
                    database_identity=db_id,
                    event_type=SecurityEventType.INJECTION_PATTERN_DETECTED,
                    severity=SecurityEventSeverity.HIGH,
                    source_ip=client_ip,
                    resource="SQL_STATEMENT",
                    description=f"Multiple stacked SQL statements blocked from IP {client_ip}.",
                    mitigation="Denied multi-statement query execution to prevent stacked SQL injection.",
                    metadata={
                        "blocked_operation": validation.get("operation"),
                        "source_ip": client_ip,
                    },
                )
            elif "READ-ONLY" in validation.get("reason", ""):
                conn_name = target_conn.name if target_conn else "connection"
                SecurityEventManager.log_security_event(
                    user_id=current_uid,
                    database_identity=db_id,
                    event_type=SecurityEventType.UNAUTHORIZED_ACCESS,
                    severity=SecurityEventSeverity.HIGH,
                    source="connector_permission_guard",
                    resource=conn_name,
                    description=f"Blocked write attempt ({validation['operation'].upper()}) on READ-ONLY connection '{conn_name}'.",
                    mitigation="Enforced read-only connector guardrail.",
                    metadata={"operation": validation["operation"]},
                )
            elif validation.get("dangerous") or validation.get("category") == "PROHIBITED_SYSTEM":
                SecurityEventManager.log_ip_threat(
                    user_id=current_uid,
                    database_identity=db_id,
                    event_type=SecurityEventType.DDL_BLOCKED,
                    severity=SecurityEventSeverity.CRITICAL,
                    source_ip=client_ip,
                    resource="DATABASE_SCHEMA",
                    description=f"Prohibited or unsafe system command attempt ({validation['operation'].upper()}) from IP {client_ip}.",
                    mitigation="Blocked execution via SQL command policy gate.",
                    metadata={
                        "attempted_sql": validation["operation"].upper(),
                        "source_ip": client_ip,
                    },
                )
        except Exception:
            pass

        return {
            "success": False,
            "columns": [],
            "rows": [],
            "error": validation["reason"],
            "operation": validation["operation"],
            "database": db_type,
            "affected_rows": 0,
        }

    # 3. Confirmation Safeguards
    if validation.get("requires_confirmation") and not is_confirmed:
        fingerprint = None
        if session_id:
            from app.crud.confirmation import store_pending

            staged = store_pending(
                session_id=session_id,
                operation=validation.get("operation", "query"),
                table=validation.get("primary_table") or "database",
                sql=sql,
                user_id=uid,
                extra={
                    "is_high_risk": validation.get("is_high_risk", False),
                    "impact_summary": validation.get("impact_summary"),
                    "target_objects": validation.get("target_objects", []),
                    "connection_id": target_conn.connection_id if target_conn else None,
                    "rollback_supported": validation.get("rollback_supported", True),
                    "rollback_limitations": validation.get("rollback_limitations", ""),
                    "params": params,
                },
            )
            fingerprint = staged.get("fingerprint")

        return {
            "success": False,
            "requires_confirmation": True,
            "is_high_risk": validation.get("is_high_risk", False),
            "columns": [],
            "rows": [],
            "error": "This database operation requires explicit user confirmation before execution.",
            "operation": validation["operation"],
            "database": db_type,
            "impact_summary": validation.get("impact_summary"),
            "target_objects": validation.get("target_objects"),
            "fingerprint": fingerprint,
            "session_id": session_id.split(":", 1)[-1] if (session_id and ":" in session_id) else session_id,
            "rollback_supported": validation.get("rollback_supported"),
            "rollback_limitations": validation.get("rollback_limitations"),
            "affected_rows": 0,
        }

    if validation.get("is_high_risk") and is_confirmed and not high_risk_confirmed:
        return {
            "success": False,
            "requires_confirmation": True,
            "requires_high_risk_confirmation": True,
            "columns": [],
            "rows": [],
            "error": "This high-risk operation requires explicit confirmation.",
            "operation": validation["operation"],
            "database": db_type,
            "impact_summary": validation.get("impact_summary"),
            "affected_rows": 0,
        }

    # 4. Engine Resolution
    engine = None
    if target_conn and hasattr(target_conn, "get_engine"):
        try:
            engine = target_conn.get_engine()
        except Exception:
            engine = None

    if engine is None:
        engine = get_engine()

    if engine is None:
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "error": "No database is currently connected.",
            "operation": validation["operation"],
            "database": "none",
            "affected_rows": 0,
        }

    # 5. Database Execution
    start_time = time.perf_counter()
    try:
        operation = validation["operation"]
        clean_stmt = validation.get("clean_sql") or sql.strip()

        with engine.begin() as conn:
            # Dialect adaptation: SQLite TRUNCATE simulation
            if db_type == "sqlite" and operation == "truncate":
                primary_table = validation.get("primary_table")
                if not primary_table:
                    m = re.search(r"\bTRUNCATE\s+(?:TABLE\s+)?([`\"\[\w\.]+)", clean_stmt, re.I)
                    primary_table = m.group(1).strip("`\"[]") if m else "unknown"

                del_res = conn.execute(text(f'DELETE FROM "{primary_table}";'))
                affected = del_res.rowcount if del_res.rowcount is not None and del_res.rowcount >= 0 else 0
                try:
                    conn.execute(text(f"DELETE FROM sqlite_sequence WHERE name = '{primary_table}';"))
                except Exception:
                    pass

                elapsed = round((time.perf_counter() - start_time) * 1000.0, 2)
                return {
                    "success": True,
                    "columns": [],
                    "rows": [],
                    "rows_returned": 0,
                    "operation": "truncate",
                    "database": db_type,
                    "affected_rows": affected,
                    "execution_time_ms": elapsed,
                    "message": f"Table '{primary_table}' truncated successfully (via SQLite delete).",
                }

            # Standard SQL execution with parameters if provided
            stmt = text(clean_stmt)
            result = conn.execute(stmt, params or {})

            elapsed = round((time.perf_counter() - start_time) * 1000.0, 2)

            # Query returns rowset (SELECT, PRAGMA, SHOW, DESCRIBE, EXPLAIN)
            if result.returns_rows:
                rows = [dict(row._mapping) for row in result]
                columns = list(result.keys())

                return {
                    "success": True,
                    "columns": columns,
                    "rows": rows,
                    "rows_returned": len(rows),
                    "operation": operation,
                    "database": db_type,
                    "affected_rows": 0,
                    "execution_time_ms": elapsed,
                }

            # Query modified data or schema (INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, etc.)
            affected_rows = (
                result.rowcount
                if result.rowcount is not None and result.rowcount >= 0
                else 0
            )

            return {
                "success": True,
                "columns": [],
                "rows": [],
                "rows_returned": 0,
                "operation": operation,
                "database": db_type,
                "affected_rows": affected_rows,
                "execution_time_ms": elapsed,
                "message": f"{operation.capitalize()} completed successfully.",
            }

    except Exception as e:
        elapsed = round((time.perf_counter() - start_time) * 1000.0, 2)
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "rows_returned": 0,
            "operation": validation["operation"],
            "database": db_type,
            "affected_rows": 0,
            "execution_time_ms": elapsed,
            "error": str(e),
        }
