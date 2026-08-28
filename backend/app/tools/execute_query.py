import re
from sqlalchemy import text

from app.database.database_manager import get_engine


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
    normalized = sql.strip()

    if not normalized:
        return False

    if normalized.endswith(";"):
        normalized = normalized[:-1]

    return ";" in normalized


def _has_where_clause(sql: str) -> bool:
    cleaned = re.sub(
        r"/\*.*?\*/",
        " ",
        sql,
        flags=re.DOTALL,
    )

    cleaned = re.sub(
        r"--[^\n]*",
        " ",
        cleaned,
    )

    return bool(
        re.search(
            r"\bwhere\b",
            cleaned,
            re.IGNORECASE,
        )
    )


def validate_sql(sql: str):

    if not sql or not sql.strip():
        return {
            "allowed": False,
            "operation": "",
            "reason": "SQL query is empty.",
        }

    operation = _extract_first_operation(sql)

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
                f"{operation.upper()} operations are disabled "
                "for safety."
            ),
        }

    if operation in READ_ONLY:
        return {
            "allowed": True,
            "operation": operation,
            "requires_confirmation": False,
        }

    if operation in WRITE_OPERATIONS:

        if operation in {"update", "delete"}:
            if not _has_where_clause(sql):
                return {
                    "allowed": False,
                    "operation": operation,
                    "reason": (
                        f"{operation.upper()} requires a WHERE condition. "
                        "BG AI will not modify all records."
                    ),
                }

        return {
            "allowed": True,
            "operation": operation,
            "requires_confirmation": True,
        }

    return {
        "allowed": False,
        "operation": operation,
        "reason": (
            f"{operation or 'Unknown'} operations "
            "are not supported."
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
        # Always obtain the CURRENT connected database engine.
        engine = get_engine()

        if engine is None:
            return {
                "success": False,
                "columns": [],
                "rows": [],
                "error": (
                    "No database is currently connected. "
                    "Please connect a database first."
                ),
                "operation": validation["operation"],
            }

        with engine.begin() as conn:

            result = conn.execute(text(sql))

            operation = validation["operation"]

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
                    "affected_rows": len(rows),
                }

            return {
                "success": True,
                "columns": [],
                "rows": [],
                "operation": operation,
                "affected_rows": (
                    result.rowcount
                    if result.rowcount is not None
                    else 0
                ),
            }

    except Exception as e:

        return {
            "success": False,
            "columns": [],
            "rows": [],
            "error": str(e),
            "operation": validation["operation"],
        }
