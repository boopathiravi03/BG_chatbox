from __future__ import annotations

from typing import Any

from app.agent.groq_agent import ask_groq
from app.crud.columns import (
    build_insert_form_fields,
    required_insert_columns,
)
from app.crud.confirmation import store_pending
from app.crud.deterministic import (
    build_deterministic_intent,
    detect_write_operation,
)
from app.crud.intent import parse_crud_intent
from app.crud.matcher import count_matching_records, match_records, quote_identifier
from app.crud.planner import (
    preview_delete,
    preview_insert,
    preview_update,
)
from app.crud.predicates import validate_and_build_where
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

    # ---------------------------------------------------------
    # HYPER-SPEED FAST PATH:
    # Check if the message contains any write operation verb.
    # If not, return None immediately (0.05 ms) without calling Groq LLM!
    # ---------------------------------------------------------
    write_op = detect_write_operation(message)
    if not write_op:
        return None

    # ---------------------------------------------------------
    # NON-RELATIONAL CONNECTOR HONEST SAFEGUARD:
    # SQL DML cannot be executed on document/vector engines.
    # ---------------------------------------------------------
    if database_type.lower() in {"mongodb", "mongo", "redis", "qdrant", "chroma"}:
        return {
            "type": "error",
            "message": f"Conversational CRUD is currently supported for relational SQL databases (SQLite, MySQL, PostgreSQL, MariaDB). Native {database_type.upper()} conversational mutations are planned.",
            "requires_confirmation": False,
        }

    # 1. Deterministic Intent Detection first (0.4 ms)
    # Handles straightforward requests like "add customer", "insert into users", etc.
    # ---------------------------------------------------------
    intent = build_deterministic_intent(
        user_message=message,
        schema=schema,
    )

    # 2. For UPDATE / DELETE where specific column matches or changes need parsing,
    # or if deterministic couldn't resolve the table, use LLM with focused schema
    target_table = intent.get("table") if intent else None
    if not intent or (intent.get("operation") in {"update", "delete"} and not intent.get("match", {}).get("column")):
        llm_intent = parse_crud_intent(
            user_message=message,
            schema=schema,
            database_type=database_type,
            target_table=target_table,
        )
        if llm_intent:
            intent = llm_intent

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

    # Auto-generated columns (integer primary keys, audit columns)
    # are omitted entirely by build_insert_form_fields.
    fields = build_insert_form_fields(table_schema)

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

    if table not in schema:
        return {
            "type": "error",
            "message": f"Table '{table}' does not exist in the active database schema.",
            "requires_confirmation": False,
        }

    # Gather conditions (compound or single match)
    conditions = intent.get("conditions") or []
    if not conditions:
        match = intent.get("match") or {}
        if match.get("column") and ("value" in match or match.get("operator")):
            conditions = [{
                "column": match.get("column"),
                "operator": match.get("operator", "="),
                "value": match.get("value"),
            }]

    where_result = validate_and_build_where(table, conditions, schema)
    if not where_result["valid"]:
        return {
            "type": "error",
            "message": where_result["error"] or "Invalid WHERE condition.",
            "requires_confirmation": False,
        }

    where_clause = where_result["where_clause"]
    normalized_conditions = where_result["normalized_conditions"]

    changes = intent.get("changes") or {}
    table_schema = schema.get(table, {})

    valid_changes = {
        column: value
        for column, value in changes.items()
        if column in table_schema
    }

    if not valid_changes:
        return {
            "type": "error",
            "message": "I understood which record you want to update, but no valid target column to change was recognized.",
            "requires_confirmation": False,
        }

    primary_keys = {
        column
        for column, info in table_schema.items()
        if info.get("primary_key")
    }

    for column in valid_changes:
        if column in primary_keys:
            return {
                "type": "error",
                "message": f"I cannot modify the primary key '{column}' through this operation.",
                "requires_confirmation": False,
            }

    # 1. Total affected rows count calculation (Mass-write safeguard)
    count_res = count_matching_records(table, where_clause, schema)
    total_matching = count_res.get("count") if count_res.get("success") else None

    # 2. Preview bounded records
    preview = match_records(table, where_clause, schema, limit=100)
    if not preview.get("success"):
        return {
            "type": "error",
            "message": preview.get("error", "Could not query records matching condition."),
            "requires_confirmation": False,
        }

    rows = preview.get("rows", [])
    if not rows and (total_matching is not None and total_matching == 0):
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

    # Evaluate mass-write risk (> 100 rows)
    estimated_affected = total_matching if total_matching is not None else len(rows)
    is_high_risk = estimated_affected > 100

    pending_record = store_pending(
        session_id=session_id,
        operation="update",
        table=table,
        sql=sql,
        preview_rows=rows,
        extra={
            "where_clause": where_clause,
            "conditions": normalized_conditions,
            "update_values": valid_changes,
            "estimated_affected_rows": estimated_affected,
            "is_high_risk": is_high_risk,
        },
    )

    explanation = (
        f"I found {estimated_affected} matching record(s) in '{table}'. "
        + ("⚠️ HIGH-RISK OPERATION: Over 100 records will be modified. Review carefully. " if is_high_risk else "")
        + "Review the proposed UPDATE and confirm before making the change."
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
        "estimated_affected_rows": estimated_affected,
        "is_high_risk": is_high_risk,
        "fingerprint": pending_record.get("fingerprint"),
        "explanation": explanation,
        "before_rows": rows,
        "proposed_changes": valid_changes,
        "conditions": normalized_conditions,
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

    if table not in schema:
        return {
            "type": "error",
            "message": f"Table '{table}' does not exist in the active database schema.",
            "requires_confirmation": False,
        }

    # Gather conditions (compound or single match)
    conditions = intent.get("conditions") or []
    if not conditions:
        match = intent.get("match") or {}
        if match.get("column") and ("value" in match or match.get("operator")):
            conditions = [{
                "column": match.get("column"),
                "operator": match.get("operator", "="),
                "value": match.get("value"),
            }]

    where_result = validate_and_build_where(table, conditions, schema)
    if not where_result["valid"]:
        return {
            "type": "error",
            "message": where_result["error"] or "Invalid WHERE condition.",
            "requires_confirmation": False,
        }

    where_clause = where_result["where_clause"]
    normalized_conditions = where_result["normalized_conditions"]

    # 1. Total affected rows count calculation (Mass-write safeguard)
    count_res = count_matching_records(table, where_clause, schema)
    total_matching = count_res.get("count") if count_res.get("success") else None

    # 2. Preview bounded records
    preview = match_records(table, where_clause, schema, limit=100)
    if not preview.get("success"):
        return {
            "type": "error",
            "message": preview.get("error", "Could not check records before deletion."),
            "requires_confirmation": False,
        }

    rows = preview.get("rows", [])
    if not rows and (total_matching is not None and total_matching == 0):
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

    # Evaluate mass-write risk (> 100 rows)
    estimated_affected = total_matching if total_matching is not None else len(rows)
    is_high_risk = estimated_affected > 100

    pending_record = store_pending(
        session_id=session_id,
        operation="delete",
        table=table,
        sql=sql,
        preview_rows=rows,
        extra={
            "where_clause": where_clause,
            "conditions": normalized_conditions,
            "estimated_affected_rows": estimated_affected,
            "is_high_risk": is_high_risk,
        },
    )

    explanation = (
        f"I found {estimated_affected} matching record(s). "
        + ("⚠️ HIGH-RISK DESTRUCTIVE OPERATION: Over 100 records will be permanently deleted! " if is_high_risk else "")
        + "Review the proposed DELETE and confirm before removing anything."
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
        "estimated_affected_rows": estimated_affected,
        "is_high_risk": is_high_risk,
        "fingerprint": pending_record.get("fingerprint"),
        "explanation": explanation,
        "before_rows": rows,
        "conditions": normalized_conditions,
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

    # Uses the same rules that built the form, so the form and its
    # validation can never disagree again.
    required_fields = required_insert_columns(table_schema)

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

    pending_record = store_pending(
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
        "fingerprint": pending_record.get("fingerprint"),
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
