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
            "reason": "No SQL operation was detected.",
        }

    if has_multiple_statements(sql):
        return {
            "allowed": False,
            "operation": operation,
            "reason": "Multiple SQL statements are not allowed.",
        }

    if operation in DANGEROUS_OPERATIONS:
        return {
            "allowed": False,
            "operation": operation,
            "reason": (
                f"{operation.upper()} operations are disabled for safety."
            ),
        }

    if operation in READ_ONLY:
        return {
            "allowed": True,
            "operation": operation,
            "requires_confirmation": False,
        }

    if operation in WRITE_OPERATIONS:
        return {
            "allowed": True,
            "operation": operation,
            "requires_confirmation": True,
        }

    return {
        "allowed": False,
        "operation": operation,
        "reason": (
            f"{operation.upper()} operations are not supported."
        ),
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
        }

    try:

        # IMPORTANT:
        # Always use the currently connected database.
        engine = get_engine()

        if engine is None:
            return {
                "success": False,
                "columns": [],
                "rows": [],
                "error": "No database is currently connected.",
                "operation": validation["operation"],
            }

        db_type = get_current_db_type()

        if db_type == "none":
            return {
                "success": False,
                "columns": [],
                "rows": [],
                "error": "No database is currently connected.",
                "operation": validation["operation"],
            }

        print(
            f"[BG AI] Executing {validation['operation'].upper()} "
            f"on {db_type.upper()} | "
            f"URL={engine.url.render_as_string(hide_password=True)}"
        )

        with engine.begin() as conn:

            result = conn.execute(text(sql))

            operation = validation["operation"]

            # SELECT / WITH
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
                    "operation": operation,
                    "database": db_type,
                    "affected_rows": len(rows),
                }

            # INSERT / UPDATE / DELETE
            return {
                "success": True,
                "columns": [],
                "rows": [],
                "operation": operation,
                "database": db_type,
                "affected_rows": result.rowcount,
            }

    except Exception as e:

        print(
            f"[BG AI] Database execution error: "
            f"{type(e).__name__}: {e}"
        )

        return {
            "success": False,
            "columns": [],
            "rows": [],
            "error": str(e),
            "operation": validation["operation"],
            "database": get_current_db_type(),
        }
