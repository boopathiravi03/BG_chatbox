from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.database.database_manager import get_engine


def quote_identifier(identifier: str) -> str:
    engine = get_engine()

    if engine is not None:
        try:
            return engine.dialect.identifier_preparer.quote(
                identifier
            )
        except Exception:
            pass

    try:
        from app.database.connection_context import get_request_user_id
        from app.connectors.registry import get_connection_registry
        uid = get_request_user_id()
        if uid:
            conn = get_connection_registry().get_active_connector(uid)
            if conn and hasattr(conn, "_quote_id"):
                return conn._quote_id(identifier)
    except Exception:
        pass

    return f'"{identifier}"'


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

    if engine is not None:
        table_sql = quote_identifier(table)
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

    # Fallback to active connector (e.g. MongoDB)
    try:
        from app.database.connection_context import get_request_user_id
        from app.connectors.registry import get_connection_registry
        uid = get_request_user_id()
        if uid:
            conn = get_connection_registry().get_active_connector(uid)
            if conn:
                res = conn.get_records(table=table, limit=limit)
                records = res.get("records", [])
                cols = res.get("columns", [])
                return {
                    "success": True,
                    "rows": records,
                    "columns": cols,
                    "row_count": len(records),
                }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "rows": [],
            "columns": [],
        }

    return {
        "success": False,
        "error": "No database is currently connected.",
        "rows": [],
        "columns": [],
    }
