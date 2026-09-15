from __future__ import annotations

from typing import Any

from app.agent.groq_agent import ask_groq
from app.crud.confirmation import store_pending
from app.crud.intent import parse_crud_intent
from app.crud.matcher import match_records, quote_identifier
from app.crud.planner import (
    preview_delete,
    preview_insert,
    preview_update,
)
from app.crud.resolver import find_text_columns, resolve_table
from app.tools.execute_query import validate_sql


def _quote_value(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def handle_crud_request(
    user_message: str,
    session_id: str,
    schema: dict,
    database_type: str,
    input_values: dict | None = None,
    pending_insert: bool = False,
) -> dict[str, Any] | None:
    message = user_message.strip()

    if not message:
        return None

    if message.lower() in {
        "cancel",
        "cancel operation",
        "never mind",
        "stop",
        "abort",
    }:
        from app.agent.orchestrator import conversation_state
        conversation_state.pop(session_id, None)
        return {
            "type": "cancelled",
            "generated_sql": "",
            "result": {
                "success": True,
                "columns": [],
                "rows": [],
                "rows_returned": 0,
            },
            "explanation": "The database operation was cancelled.",
            "followups": [],
        }

    if pending_insert and input_values:
        return _handle_insert_form(
            session_id=session_id,
            schema=schema,
            input_values=input_values,
        )

    intent = parse_crud_intent(
        user_message=message,
        schema=schema,
        database_type=database_type,
    )

    if not intent:
        return None

    operation = intent["operation"]
    table = intent["table"]

    if operation == "read":
        # Normal read queries are handled by the
        # main SQL/chart intelligence pipeline.
        return None

    if operation == "create":
        return _handle_create(
            user_message=message,
            session_id=session_id,
            schema=schema,
            intent=intent,
        )

    if operation == "update":
        return _handle_update(
            user_message=message,
            session_id=session_id,
            schema=schema,
            intent=intent,
        )

    if operation == "delete":
        return _handle_delete(
            user_message=message,
            session_id=session_id,
            schema=schema,
            intent=intent,
        )

    return None


def _handle_read(
    user_message: str,
    schema: dict,
    intent: dict[str, Any],
) -> dict[str, Any]:
    table = intent.get("table")
    if not table:
        return {
            "type": "error",
            "message": "I could not determine which table you want to read from.",
            "requires_confirmation": False,
        }

    match = intent.get("match") or {}
    where_column = match.get("column")
    where_value = match.get("value")

    where_clause = None
    if where_column and where_value:
        where_clause = f"{_quote_identifier(where_column)} = {_quote_value(where_value)}"

    preview = match_records(table, where_clause, schema)

    if not preview.get("success"):
        return {
            "type": "error",
            "message": preview.get("error", "Could not read from the database."),
            "requires_confirmation": False,
        }

    rows = preview.get("rows", [])
    columns = preview.get("columns", [])

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


def _handle_create(
    user_message: str,
    session_id: str,
    schema: dict,
    intent: dict[str, Any],
) -> dict[str, Any]:
    table = intent.get("table")
    if not table:
        return {
            "type": "input_request",
            "message": "Which table should I add the new record to?",
            "input_request": {
                "type": "insert",
                "message": "Which table should I add the new record to?",
                "tables": list(schema.keys()),
            },
            "requires_confirmation": False,
        }

    table_schema = schema.get(table, {})
    fields = []

    for column_name, metadata in table_schema.items():
        name = column_name.lower()
        if name in {"created_at", "updated_at", "deleted_at"}:
            continue
        if metadata.get("primary_key") and metadata.get("default") is not None:
            continue

        column_type = str(metadata.get("type", "")).lower()
        field_type = "text"
        if "int" in column_type:
            field_type = "number"
        elif any(x in column_type for x in ["decimal", "numeric", "float", "double", "real"]):
            field_type = "number"
        elif "bool" in column_type:
            field_type = "boolean"
        elif any(x in column_type for x in ["date", "time"]):
            field_type = "date"
        if "email" in name:
            field_type = "email"

        fields.append({
            "name": column_name,
            "label": column_name.replace("_", " ").title(),
            "type": field_type,
            "required": not metadata.get("nullable", True) and metadata.get("default") is None,
        })

    from app.agent.orchestrator import conversation_state

    conversation_state[session_id] = {
        "pending_insert_table": table,
    }

    return {
        "type": "input_request",
        "message": f"Please provide the record details for '{table}'.",
        "input_request": {
            "type": "insert",
            "table": table,
            "title": f"Add record to {table.replace('_', ' ').title()}",
            "message": "Please provide the record details. Only fields that exist in the database will be accepted.",
            "fields": fields,
        },
        "requires_confirmation": False,
    }


def _handle_update(
    user_message: str,
    session_id: str,
    schema: dict,
    intent: dict[str, Any],
) -> dict[str, Any]:
    table = intent.get("table")
    if not table:
        return {
            "type": "error",
            "message": "I could not determine which table you want to update.",
            "requires_confirmation": False,
        }

    match = intent.get("match") or {}
    where_column = match.get("column")
    where_value = match.get("value")
    changes = intent.get("changes") or {}

    if not where_column or not where_value:
        return {
            "type": "error",
            "message": "For safety, UPDATE requires a WHERE condition identifying the record(s) you want to change.",
            "requires_confirmation": False,
        }

    where_clause = f"{_quote_identifier(where_column)} = {_quote_value(where_value)}"

    valid_changes = {
        column: value
        for column, value in changes.items()
        if column in schema.get(table, {})
    }

    if not valid_changes:
        return {
            "type": "error",
            "message": "I understood which record you want to update, but I could not determine which field should be changed.",
            "requires_confirmation": False,
        }

    primary_keys = {
        column
        for column, info in schema.get(table, {}).items()
        if info.get("primary_key")
    }

    for column in valid_changes:
        if column in primary_keys:
            return {
                "type": "error",
                "message": f"I cannot modify the primary key '{column}' through this operation.",
                "requires_confirmation": False,
            }

    preview = match_records(table, where_clause, schema)

    if not preview.get("success"):
        return {
            "type": "error",
            "message": preview.get("error", "Could not find the matching record."),
            "requires_confirmation": False,
        }

    rows = preview.get("rows", [])

    if not rows:
        return {
            "type": "error",
            "message": "I could not find any record matching the specified condition.",
            "requires_confirmation": False,
        }

    planned = preview_update(table, where_clause, valid_changes, schema)

    if not planned.get("success"):
        return {
            "type": "error",
            "message": planned.get("error", "Could not plan the update."),
            "requires_confirmation": False,
        }

    sql = planned["sql"]
    validation = validate_sql(sql)

    if not validation.get("allowed"):
        return {
            "type": "error",
            "message": validation.get("reason", "The update was rejected."),
            "requires_confirmation": False,
        }

    store_pending(
        session_id=session_id,
        operation="update",
        table=table,
        sql=sql,
        preview_rows=rows,
        extra={
            "where_column": where_column,
            "where_value": where_value,
            "update_values": valid_changes,
        },
    )

    return {
        "type": "confirmation",
        "operation": "update",
        "table": table,
        "generated_sql": sql,
        "sql": sql,
        "result": {
            "success": True,
            "columns": list(rows[0].keys()) if rows else [],
            "rows": rows,
            "rows_returned": len(rows),
            "pending_confirmation": True,
            "operation": "update",
        },
        "requires_confirmation": True,
        "affected_rows_preview": len(rows),
        "explanation": f"I found {len(rows)} matching record(s) in '{table}'. Review the proposed UPDATE and confirm before making the change.",
        "before_rows": rows,
        "proposed_changes": valid_changes,
        "followups": [],
    }


def _handle_delete(
    user_message: str,
    session_id: str,
    schema: dict,
    intent: dict[str, Any],
) -> dict[str, Any]:
    table = intent.get("table")
    if not table:
        return {
            "type": "error",
            "message": "I could not determine which table you want to delete from.",
            "requires_confirmation": False,
        }

    match = intent.get("match") or {}
    where_column = match.get("column")
    where_value = match.get("value")

    if not where_column or not where_value:
        return {
            "type": "error",
            "message": "For safety, DELETE requires a WHERE condition identifying the record(s) you want to remove.",
            "requires_confirmation": False,
        }

    where_clause = f"{_quote_identifier(where_column)} = {_quote_value(where_value)}"

    preview = match_records(table, where_clause, schema)

    if not preview.get("success"):
        return {
            "type": "error",
            "message": preview.get("error", "Could not check the record before deletion."),
            "requires_confirmation": False,
        }

    rows = preview.get("rows", [])

    if not rows:
        return {
            "type": "error",
            "message": "No matching record was found. Nothing was deleted.",
            "requires_confirmation": False,
        }

    planned = preview_delete(table, where_clause, schema)

    if not planned.get("success"):
        return {
            "type": "error",
            "message": planned.get("error", "Could not plan the delete."),
            "requires_confirmation": False,
        }

    sql = planned["sql"]
    validation = validate_sql(sql)

    if not validation.get("allowed"):
        return {
            "type": "error",
            "message": validation.get("reason", "The delete was rejected."),
            "requires_confirmation": False,
        }

    store_pending(
        session_id=session_id,
        operation="delete",
        table=table,
        sql=sql,
        preview_rows=rows,
        extra={
            "where_column": where_column,
            "where_value": where_value,
        },
    )

    return {
        "type": "confirmation",
        "operation": "delete",
        "table": table,
        "generated_sql": sql,
        "sql": sql,
        "result": {
            "success": True,
            "columns": list(rows[0].keys()) if rows else [],
            "rows": rows,
            "rows_returned": len(rows),
            "pending_confirmation": True,
            "operation": "delete",
        },
        "requires_confirmation": True,
        "affected_rows_preview": len(rows),
        "explanation": f"I found {len(rows)} matching record(s). Review the proposed DELETE and confirm before removing anything.",
        "before_rows": rows,
        "followups": [],
    }


def _handle_insert_form(
    session_id: str,
    schema: dict,
    input_values: dict,
) -> dict[str, Any]:
    from app.agent.orchestrator import conversation_state

    state = conversation_state.get(session_id, {})
    table = state.get("pending_insert_table")

    if not table or table not in schema:
        conversation_state.pop(session_id, None)
        return {
            "type": "error",
            "message": "The insert session expired. Please start the add-record request again.",
            "requires_confirmation": False,
        }

    table_schema = schema[table]
    allowed_values = {}

    for supplied_column, value in input_values.items():
        if supplied_column not in table_schema:
            continue
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if not value:
                continue
        allowed_values[supplied_column] = value

    required_fields = [
        column
        for column, metadata in table_schema.items()
        if not metadata.get("nullable", True)
        and metadata.get("default") is None
        and column.lower() not in {"created_at", "updated_at", "deleted_at"}
    ]

    missing = [field for field in required_fields if field not in allowed_values]

    if missing:
        return {
            "type": "input_request",
            "message": "Please provide all required fields.",
            "table": table,
            "missing_fields": missing,
            "requires_confirmation": False,
        }

    planned = preview_insert(table, allowed_values, schema)

    if not planned.get("success"):
        return {
            "type": "error",
            "message": planned.get("error", "Could not plan the insert."),
            "requires_confirmation": False,
        }

    sql = planned["sql"]
    validation = validate_sql(sql)

    if not validation.get("allowed"):
        return {
            "type": "error",
            "message": validation.get("reason", "The insert was rejected."),
            "requires_confirmation": False,
        }

    store_pending(
        session_id=session_id,
        operation="insert",
        table=table,
        sql=sql,
        extra={"values": allowed_values},
    )

    return {
        "type": "confirmation",
        "operation": "insert",
        "table": table,
        "generated_sql": sql,
        "sql": sql,
        "result": {
            "success": True,
            "columns": [],
            "rows": [],
            "rows_returned": 0,
            "pending_confirmation": True,
            "operation": "insert",
        },
        "requires_confirmation": True,
        "explanation": "The new record is ready. Please review and confirm before I modify the database.",
        "values": allowed_values,
        "followups": [],
    }
