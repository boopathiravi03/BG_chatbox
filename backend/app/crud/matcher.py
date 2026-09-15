from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.database.database_manager import get_engine


def quote_identifier(identifier: str) -> str:
    engine = get_engine()

    if engine is None:
        raise RuntimeError(
            "No database is currently connected."
        )

    return engine.dialect.identifier_preparer.quote(
        identifier
    )


def match_records(
    table: str,
    where_clause: str | None,
    schema: dict,
    limit: int = 100,
) -> dict[str, Any]:
    """
    Execute a SELECT against the live database to find
    records matching the requested WHERE condition.
    """

    engine = get_engine()

    if engine is None:
        return {
            "success": False,
            "error": "No database is currently connected.",
            "rows": [],
            "columns": [],
        }

    table_sql = _quote_identifier(table)
    sql = f"SELECT * FROM {table_sql}"

    if where_clause:
        sql += f" WHERE {where_clause}"

    sql += f" LIMIT {int(limit)}"

    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = [dict(row._mapping) for row in result]
            columns = list(result.keys()) if rows else []
            return {
                "success": True,
                "rows": rows,
                "columns": columns,
                "row_count": len(rows),
            }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "rows": [],
            "columns": [],
        }
