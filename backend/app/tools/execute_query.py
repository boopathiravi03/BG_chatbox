import re
from typing import Optional, Dict, Any, List
from sqlalchemy import text

from app.database.database_manager import get_engine, get_current_db_type


DANGEROUS_OPERATIONS = {
    "drop",
    "alter",
    "truncate",
    "attach",
    "detach",
}

READ_ONLY = {
    "select",
    "with",
    "pragma",
}

WRITE_OPERATIONS = {
    "insert",
    "update",
    "delete",
    "create",
}


def _extract_first_operation(sql: str) -> str:
    cleaned = sql.strip().lower()

    cleaned = re.sub(
        r"/\*.*?\*/",
        " ",
        cleaned,
        flags=re.DOTALL,
    )

    cleaned = re.sub(
        r"--[^\n]*",
        " ",
        cleaned,
    )

    cleaned = cleaned.strip().strip(";")

    parts = re.split(r"\s+", cleaned)

    return parts[0] if parts else ""


def has_multiple_statements(sql: str) -> bool:
    normalized = re.sub(r"\s+", " ", sql.strip())

    return ";" in normalized.rstrip(";")


def validate_sql(sql: str):
    operation = _extract_first_operation(sql)

    if not operation:
        return {
            "allowed": False,
            "operation": "",
            "reason": "Empty SQL query.",
            "requires_confirmation": False,
        }

    if has_multiple_statements(sql):
        return {
            "allowed": False,
            "operation": operation,
            "reason": "Multiple SQL statements are not allowed.",
            "requires_confirmation": False,
        }

    # ---------------------------------------------------------
    # READ OPERATIONS
    # ---------------------------------------------------------
    if operation == "pragma":
        if "=" in sql:
            return {
                "allowed": False,
                "operation": operation,
                "reason": "PRAGMA configuration statements modifying database parameters are not permitted.",
                "requires_confirmation": False,
            }
        return {
            "allowed": True,
            "operation": operation,
            "requires_confirmation": False,
        }

    if operation in READ_ONLY:
        return {
            "allowed": True,
            "operation": operation,
            "requires_confirmation": False,
        }

    # ---------------------------------------------------------
    # UPDATE / DELETE must contain a WHERE clause
    # ---------------------------------------------------------
    if operation in {"update", "delete"}:
        normalized_sql = re.sub(
            r"\s+",
            " ",
            sql.strip().lower(),
        )

        if " where " not in f" {normalized_sql} ":
            return {
                "allowed": False,
                "operation": operation,
                "requires_confirmation": False,
                "reason": (
                    f"{operation.upper()} operations require "
                    "a WHERE condition."
                ),
            }

    # ---------------------------------------------------------
    # NORMAL WRITE OPERATIONS
    # ---------------------------------------------------------
    if operation in WRITE_OPERATIONS:
        return {
            "allowed": True,
            "operation": operation,
            "requires_confirmation": True,
        }

    # ---------------------------------------------------------
    # DANGEROUS DATABASE OPERATIONS
    #
    # BG AI must NEVER execute destructive schema/database
    # operations through the conversational agent.
    # ---------------------------------------------------------
    if operation in DANGEROUS_OPERATIONS:
        return {
            "allowed": False,
            "operation": operation,
            "requires_confirmation": False,
            "dangerous": True,
            "reason": (
                f"{operation.upper()} operations are blocked "
                "for safety. BG AI only supports safe database "
                "read operations and controlled INSERT, UPDATE, "
                "and DELETE actions."
            ),
        }

    return {
        "allowed": False,
        "operation": operation,
        "reason": (
            f"{operation.upper()} operations are not supported."
        ),
        "requires_confirmation": False,
    }


def execute_query(sql: str, connection_id: Optional[str] = None):
    # Check if a non-SQL or specific connector is targeted
    target_conn = None
    try:
        from app.database.connection_context import get_request_user_id
        from app.connectors.registry import get_connection_registry
        uid = get_request_user_id()
        if uid:
            reg = get_connection_registry()
            target_conn = reg.get_connector(uid, connection_id) if connection_id else reg.get_active_connector(uid)
            if target_conn:
                if target_conn.category != "relational":
                    # Non-relational (MongoDB, Vector, etc.) handles its own query execution directly
                    res = target_conn.execute_query(sql)
                    return {
                        "success": res.success,
                        "columns": res.columns,
                        "rows": res.rows,
                        "rows_returned": res.rows_returned,
                        "operation": "query",
                        "database": target_conn.connector_type,
                        "affected_rows": res.affected_rows or 0,
                        "error": res.error,
                        "source_id": target_conn.connection_id,
                        "source_name": target_conn.name,
                    }
                elif target_conn.is_read_only:
                    # Enforce connector read-only check
                    first_w = _extract_first_operation(sql)
                    if first_w in WRITE_OPERATIONS:
                        try:
                            from app.intelligence.governance.security_events import SecurityEventManager
                            from app.intelligence.governance.models import SecurityEventType, SecurityEventSeverity
                            SecurityEventManager.log_security_event(
                                user_id=uid or "default_user",
                                database_identity=target_conn.connector_type,
                                event_type=SecurityEventType.UNAUTHORIZED_ACCESS,
                                severity=SecurityEventSeverity.HIGH,
                                source="connector_permission_guard",
                                resource=target_conn.name,
                                description=f"Blocked write attempt ({first_w.upper()}) on READ-ONLY connection '{target_conn.name}'.",
                                mitigation="Enforced read-only connector guardrail.",
                                metadata={"operation": first_w},
                            )
                        except Exception:
                            pass
                        return {
                            "success": False,
                            "columns": [],
                            "rows": [],
                            "error": f"Connection '{target_conn.name}' is configured as READ-ONLY. Write operations are blocked.",
                            "operation": first_w,
                            "database": target_conn.connector_type,
                        }
    except Exception:
        pass

    validation = validate_sql(sql)

    if not validation["allowed"]:
        try:
            from app.database.connection_context import get_request_user_id, get_request_client_ip
            from app.intelligence.governance.security_events import SecurityEventManager
            from app.intelligence.governance.models import SecurityEventType, SecurityEventSeverity
            uid = get_request_user_id() or "default_user"
            client_ip = get_request_client_ip() or "unknown"
            db_id = target_conn.connector_type if target_conn else get_current_db_type()

            if validation.get("dangerous"):
                SecurityEventManager.log_ip_threat(
                    user_id=uid,
                    database_identity=db_id,
                    event_type=SecurityEventType.DDL_BLOCKED,
                    severity=SecurityEventSeverity.CRITICAL,
                    source_ip=client_ip,
                    resource="DATABASE_SCHEMA",
                    description=f"Prohibited destructive DDL attempt ({validation['operation'].upper()}) originating from IP {client_ip}.",
                    mitigation="Blocked execution via SQL safety gate.",
                    metadata={"attempted_sql": validation['operation'].upper(), "source_ip": client_ip},
                )
            elif "Multiple SQL statements" in validation.get("reason", ""):
                SecurityEventManager.log_ip_threat(
                    user_id=uid,
                    database_identity=db_id,
                    event_type=SecurityEventType.INJECTION_PATTERN_DETECTED,
                    severity=SecurityEventSeverity.HIGH,
                    source_ip=client_ip,
                    resource="SQL_STATEMENT",
                    description=f"Multiple stacked SQL statements detected and blocked from IP {client_ip}.",
                    mitigation="Denied multi-statement query execution to prevent stacked SQL injection.",
                    metadata={"blocked_operation": validation.get("operation"), "source_ip": client_ip},
                )
        except Exception:
            pass

        return {
            "success": False,
            "columns": [],
            "rows": [],
            "error": validation["reason"],
            "operation": validation["operation"],
            "database": get_current_db_type(),
        }

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
        }

    try:
        operation = validation["operation"]

        # IMPORTANT:
        # Always use the engine created by database_manager.
        with engine.begin() as conn:

            result = conn.execute(text(sql))

            if operation in READ_ONLY:
                rows = [
                    dict(row._mapping)
                    for row in result
                ]

                columns = list(result.keys())

                return {
                    "success": True,
                    "columns": columns,
                    "rows": rows,
                    "rows_returned": len(rows),
                    "operation": operation,
                    "database": get_current_db_type(),
                    "affected_rows": 0,
                }

            affected_rows = result.rowcount

            return {
                "success": True,
                "columns": [],
                "rows": [],
                "rows_returned": 0,
                "operation": operation,
                "database": get_current_db_type(),
                "affected_rows": affected_rows,
            }

    except Exception as e:

        return {
            "success": False,
            "columns": [],
            "rows": [],
            "rows_returned": 0,
            "operation": validation["operation"],
            "database": get_current_db_type(),
            "affected_rows": 0,
            "error": str(e),
        }
