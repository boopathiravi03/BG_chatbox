from __future__ import annotations

from typing import Any

from app.crud.matcher import match_records, quote_identifier
from app.tools.execute_query import validate_sql


def preview_read(
    table: str,
    where_clause: str | None,
    schema: dict,
) -> dict[str, Any]:
    return match_records(table, where_clause, schema)


def preview_insert(
    table: str,
    values: dict[str, Any],
    schema: dict,
) -> dict[str, Any]:
    table_schema = schema.get(table, {})

    if not table_schema:
        return {
            "success": False,
            "error": f"Table '{table}' does not exist in the current schema.",
        }

    allowed = {
        column: value
        for column, value in values.items()
        if column in table_schema
    }

    if not allowed:
        return {
            "success": False,
            "error": "No valid columns were provided for the insert.",
        }

    columns = list(allowed.keys())
    column_sql = ", ".join(quote_identifier(column) for column in columns)
    value_sql = ", ".join(
        "NULL"
        if value is None
        else f"'{str(value).replace(chr(39), chr(39)+chr(39))}'"
        for value in [allowed[column] for column in columns]
    )

    sql = f"INSERT INTO {quote_identifier(table)} ({column_sql}) VALUES ({value_sql})"
    validation = validate_sql(sql)

    return {
        "success": True,
        "sql": sql,
        "validation": validation,
        "allowed_columns": columns,
        "values": allowed,
    }


def preview_update(
    table: str,
    where_clause: str,
    changes: dict[str, Any],
    schema: dict,
) -> dict[str, Any]:
    table_schema = schema.get(table, {})

    if not table_schema:
        return {
            "success": False,
            "error": f"Table '{table}' does not exist in the current schema.",
        }

    valid_changes = {
        column: value
        for column, value in changes.items()
        if column in table_schema
    }

    if not valid_changes:
        return {
            "success": False,
            "error": "No valid columns were provided for the update.",
        }

    set_parts = [
        f"{quote_identifier(column)} = \'{str(value).replace(chr(39), chr(39)+chr(39))}\'"
        for column, value in valid_changes.items()
    ]

    sql = (
        f"UPDATE {quote_identifier(table)} "
        f"SET {', '.join(set_parts)} "
        f"WHERE {where_clause}"
    )

    validation = validate_sql(sql)

    return {
        "success": True,
        "sql": sql,
        "validation": validation,
        "changes": valid_changes,
    }


def preview_delete(
    table: str,
    where_clause: str,
    schema: dict,
) -> dict[str, Any]:
    table_schema = schema.get(table, {})

    if not table_schema:
        return {
            "success": False,
            "error": f"Table '{table}' does not exist in the current schema.",
        }

    sql = f"DELETE FROM {quote_identifier(table)} WHERE {where_clause}"
    validation = validate_sql(sql)

    return {
        "success": True,
        "sql": sql,
        "validation": validation,
    }
