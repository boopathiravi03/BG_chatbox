from __future__ import annotations

from typing import Any

from app.crud import matcher, planner
from app.crud.resolver import find_text_columns, resolve_column, resolve_table


def execute_read(
    user_message: str,
    schema: dict,
    database_type: str,
) -> dict[str, Any] | None:
    table = resolve_table(user_message, schema)

    if not table:
        return {
            "type": "error",
            "message": "I could not determine which table you want to read from.",
            "requires_confirmation": False,
        }

    columns = list(schema.get(table, {}).keys())
    where_column = None
    where_value = None

    for column in columns:
        pattern = re.compile(
            rf"\b{re.escape(column)}\b.*?"
            rf"(?:=|is|equals|equal to|==)\s*['\"]?([^,'\"]+)['\"]?",
            re.IGNORECASE,
        )
        match = pattern.search(user_message)
        if match:
            where_column = column
            where_value = match.group(1).strip()
            break

    where_clause = None
    if where_column and where_value:
        where_clause = f'"{where_column}" = \'{where_value.replace(chr(39), chr(39)+chr(39))}\''

    preview = matcher.match_records(table, where_clause, schema)

    if not preview.get("success"):
        return {
            "type": "error",
            "message": preview.get("error", "Could not read from the database."),
            "requires_confirmation": False,
        }

    rows = preview.get("rows", [])
    columns = preview.get("columns", [])

    if not rows:
        return {
            "type": "result",
            "message": f"No records found in '{table}'.",
            "result": {
                "success": True,
                "columns": columns,
                "rows": [],
                "rows_returned": 0,
            },
            "requires_confirmation": False,
        }

    return {
        "type": "result",
        "message": f"Found {len(rows)} record(s) in '{table}'.",
        "result": {
            "success": True,
            "columns": columns,
            "rows": rows,
            "rows_returned": len(rows),
        },
        "requires_confirmation": False,
    }
