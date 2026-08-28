import re
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
    if operation in READ_ONLY:
        return {
            "allowed": True,
            "operation": operation,
            "requires_confirmation": False,
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
    # These are allowed ONLY after explicit confirmation.
    # ---------------------------------------------------------
    if operation in DANGEROUS_OPERATIONS:
        return {
            "allowed": True,
            "operation": operation,
            "requires_confirmation": True,
            "dangerous": True,
        }

    return {
        "allowed": False,
        "operation": operation,
        "reason": (
            f"{operation.upper()} operations are not supported."
        ),
        "requires_confirmation": False,
    }


def execute_query(sql: str):
    validation = validate_sql(sql)

    if not validation["allowed"]:
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "error": validation["reason"],
            "operation": validation["operation"],
            "database": get_current_db_type(),
        }

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
