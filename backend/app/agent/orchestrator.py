from app.agent.groq_agent import ask_groq
from app.tools.get_schema import get_schema
from app.tools.execute_query import execute_query, validate_sql
from app.tools.explain_data import explain_data
from app.tools.generate_chart import generate_chart
from app.tools.generate_flowchart import generate_flowchart
from app.tools.get_relationship_graph import get_relationship_graph
from app.tools.dashboard_data import get_dashboard_data as get_analytics_data
from app.tools.get_insert_fields import get_insert_fields
import json
import re
from difflib import get_close_matches

conversation_state = {}

_pending_insert = None

WRITE_OPERATIONS = {"insert", "update", "delete"}
READ_ONLY = {"select", "with", "pragma"}


def generate_suggestions(schema: dict, database_context: str) -> list[str]:
    tables = list(schema.keys())
    suggestions = []

    for table in tables[:3]:
        suggestions.append(f"Show all {table}")

    if len(tables) > 1:
        suggestions.append("Show table relationships")

    suggestions.append("ER Diagram")
    suggestions.append("Database Schema")

    return suggestions[:6]


def _get_followups(user_message: str) -> list[str]:
    try:
        schema = get_schema()
    except Exception:
        return []

    profile = None
    try:
        from app.main import get_database_profile
        profile = get_database_profile()
    except Exception:
        pass

    database_context = ""
    if profile and profile.analyzed:
        database_context = profile.to_context()

    return generate_suggestions(schema, database_context)


def _classify_intent(user_message: str) -> str:
    prompt = f"""You are an intent classifier for a database assistant.

Classify the user message into ONE category only.

Categories:
- chat: greetings, general questions, small talk, questions about the assistant itself, or anything not related to database operations
- sql: direct database queries like "show customers", "list orders", "find products", "highest sales month", "top customers", "how many X"
- chart: requests for charts, graphs, visualizations like "revenue chart", "sales graph", "plot monthly sales"
- dashboard: requests for the full analytics dashboard, business insights overview, or complete dashboard view
- relationship_graph: requests to visualize table relationships, schema connections
- er_diagram: requests for ER diagram, entity relationship diagram, schema diagram
- analytics: requests for analytics dashboard, business insights, overview

IMPORTANT RULES:
- If the user asks for a SPECIFIC metric, value, or record ("highest sales month", "top customer", "how many X"), classify as "sql"
- Only classify as "dashboard" or "analytics" if the user explicitly asks for the full dashboard or overview
- When in doubt between "sql" and "dashboard", choose "sql"

Return ONLY the category name, nothing else.

User: {user_message}
"""

    try:
        response = ask_groq(prompt).strip().lower()
        valid_intents = ["chat", "sql", "chart", "dashboard", "relationship_graph", "er_diagram", "analytics"]
        for intent in valid_intents:
            if intent in response:
                return intent
        return "sql"
    except Exception:
        return "sql"


def _handle_chat(user_message: str) -> dict:
    prompt = f"""You are BG AI, a friendly and enthusiastic AI database assistant.

You are having a conversation with the user. Be warm, natural, and engaging.

Guidelines:
- If the user says something positive like "nice", "great", "awesome", "wow", "thank you", "good job", accept the compliment warmly and briefly, then naturally pivot back to helping them with their database.
- Keep responses SHORT and conversational. 1-3 sentences max for simple replies.
- If the user asks about yourself, explain that you are BG AI, an AI-powered database assistant that can help with SQL queries, data analysis, charts, dashboards, and database visualization.
- If the user asks general questions, answer them naturally but keep it brief.
- Do NOT generate SQL unless the user explicitly asks for data from the database.
- Be helpful, not robotic. Sound like a real assistant.

User: {user_message}
"""

    try:
        explanation = ask_groq(prompt).strip()
    except Exception:
        explanation = "Thanks! I'm BG AI. Want me to show you something in your database?"

    return {
        "generated_sql": "",
        "result": {
            "success": True,
            "columns": [],
            "rows": [],
            "execution_time_ms": 0,
            "rows_returned": 0,
        },
        "diagram": None,
        "analytics": None,
        "explanation": explanation,
        "followups": _get_followups(user_message),
    }


def _get_table_columns(table_name: str, schema: dict) -> list[str]:
    return list(schema.get(table_name, {}).keys())


def _is_insert_request(message: str) -> bool:
    text = message.lower().strip()
    normalized = text.replace("-", " ")

    action_words = [
        "add",
        "create",
        "insert",
        "new",
        "register",
        "save",
    ]

    has_action = any(
        re.search(rf"\b{re.escape(word)}\b", normalized)
        for word in action_words
    )

    if not has_action:
        return False

    try:
        schema = get_schema()
    except Exception:
        return False

    tables = list(schema.keys())

    for table in tables:
        table_lower = table.lower()
        if re.search(rf"\b{re.escape(table_lower)}\b", normalized):
            return True

    return False


def _is_insert_followup(user_message: str) -> bool:
    message = user_message.lower().strip()

    field_patterns = [
        r"\bname\s*[:=-]",
        r"\bemail\s*[:=-]",
        r"\bmail\s*[:=-]",
        r"\bcity\s*[:=-]",
        r"\bphone\s*[:=-]",
        r"\baddress\s*[:=-]",
    ]

    matches = sum(
        1 for pattern in field_patterns
        if re.search(pattern, message)
    )

    return matches >= 2


def _parse_insert_values(user_message: str, columns: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}

    message = user_message.strip()
    normalized = re.sub(r"\s*,\s*", ", ", message)

    for column in columns:
        column_lower = column.lower()

        if (
            column_lower == "id"
            or column_lower.endswith("_id")
            or column_lower in {"created_at", "updated_at", "deleted_at"}
        ):
            continue

        label = column.replace("_", " ")

        pattern = rf"""
            \b{re.escape(label)}\b
            \s*[:=-]\s*
            (?P<value>
                [^,\n;]+
            )
        """

        match = re.search(pattern, normalized, re.IGNORECASE | re.VERBOSE)

        if match:
            value = match.group("value").strip()
            values[column] = value

    return values


def _handle_insert_followup(user_message: str, table: str, schema: dict) -> dict:
    global _pending_insert

    table_schema = schema.get(table, {})
    if not isinstance(table_schema, dict):
        table_schema = {}

    columns = _get_table_columns(table, schema)
    insert_columns = [
        column
        for column in columns
        if not (
            column.lower() == "id"
            or column.lower().endswith("_id")
            or column.lower() in {"created_at", "updated_at", "deleted_at"}
        )
    ]

    values = _parse_insert_values(user_message, insert_columns)

    if not values:
        return {
            "generated_sql": "",
            "result": {
                "success": False,
                "columns": [],
                "rows": [],
                "rows_returned": 0,
            },
            "chart": None,
            "diagram": None,
            "analytics": None,
            "explanation": (
                "I couldn't understand the values you provided. "
                "Please use the format: field: value, field: value"
            ),
            "followups": [],
        }

    sql = _create_insert_sql(table, insert_columns, values)

    _pending_insert = None

    validation = validate_sql(sql)

    if not validation["allowed"]:
        return {
            "generated_sql": sql,
            "result": {
                "success": False,
                "columns": [],
                "rows": [],
                "rows_returned": 0,
                "error": validation["reason"],
            },
            "chart": None,
            "diagram": None,
            "analytics": None,
            "explanation": (
                f"I could not prepare this database change.\n\n"
                f"{validation['reason']}"
            ),
            "followups": [],
        }

    if validation.get("requires_confirmation"):
        return {
            "generated_sql": sql,
            "result": {
                "success": True,
                "columns": [],
                "rows": [],
                "execution_time_ms": 0,
                "rows_returned": 0,
                "pending_confirmation": True,
                "operation": validation["operation"],
            },
            "chart": None,
            "diagram": None,
            "analytics": None,
            "requires_confirmation": True,
            "explanation": (
                "Database change requires confirmation.\n\n"
                f"Operation: `{validation['operation']}`\n\n"
                "Please review the generated SQL before "
                "continuing."
            ),
            "followups": [],
        }

    return {
        "generated_sql": sql,
        "result": {
            "success": True,
            "columns": [],
            "rows": [],
            "execution_time_ms": 0,
            "rows_returned": 0,
        },
        "chart": None,
        "diagram": None,
        "analytics": None,
        "explanation": "The record is ready to be added.",
        "followups": [],
    }


def _detect_insert_table(user_message: str, schema: dict) -> str:
    prompt = f"""You are a database assistant. The user wants to add/insert a record.

Database schema (table names only):
{', '.join(list(schema.keys()))}

User request: {user_message}

Which table are they referring to? Return ONLY the exact table name from the schema above. If none match, return an empty string."""

    try:
        response = ask_groq(prompt).strip()
        for table in schema.keys():
            if table.lower() in response.lower():
                return table
    except Exception:
        pass
    return ""


def _is_auto_generated_column(column: str, metadata: dict) -> bool:
    column_lower = column.lower()

    if metadata.get("primary_key"):
        default = metadata.get("default")

        if default is not None:
            return True

        if column_lower == "id" or column_lower.endswith("_id"):
            return True

    if column_lower in {
        "created_at",
        "updated_at",
        "deleted_at",
    }:
        return True

    return False


def _build_insert_request(table: str, schema: dict) -> dict:
    table_schema = schema.get(table, {})

    if not isinstance(table_schema, dict):
        table_schema = {}

    columns = [
        column
        for column in table_schema.keys()
        if not _is_auto_generated_column(column, table_schema[column])
    ]

    if not columns:
        return {
            "generated_sql": "",
            "result": {
                "success": False,
                "columns": [],
                "rows": [],
                "rows_returned": 0,
            },
            "input_request": None,
            "explanation": (
                f"I couldn't determine which fields can be added to "
                f"`{table}`."
            ),
            "followups": [],
        }

    fields = []
    for column in columns:
        column_lower = column.lower()
        column_meta = table_schema.get(column, {})
        column_type = str(column_meta.get("type", "")).lower()

        if "email" in column_lower:
            field_type = "email"
        elif any(word in column_lower for word in ["phone", "mobile", "contact"]):
            field_type = "tel"
        elif any(word in column_lower for word in ["date", "dob", "birth"]):
            field_type = "date"
        elif any(word in column_lower for word in [
            "price",
            "amount",
            "salary",
            "cgpa",
            "mark",
            "score",
            "quantity",
            "stock",
            "age",
        ]):
            field_type = "number"
        elif any(word in column_type for word in [
            "int",
            "float",
            "double",
            "decimal",
            "numeric",
        ]):
            field_type = "number"
        else:
            field_type = "text"

        fields.append({
            "name": column,
            "label": column.replace("_", " ").title(),
            "type": field_type,
            "required": not column_meta.get("nullable", True),
        })

    table_name = table.rstrip("s").title()

    return {
        "generated_sql": "",
        "result": {
            "success": True,
            "columns": [],
            "rows": [],
            "execution_time_ms": 0,
            "rows_returned": 0,
        },
        "input_request": {
            "type": "insert",
            "table": table,
            "title": f"Add New {table_name}",
            "message": f"Please provide the following details for the new {table_name.lower()}:",
            "fields": fields,
        },
        "explanation": (
            f"Sure! Let's add a new {table_name.lower()}. "
            f"Please provide the required details below."
        ),
        "followups": [],
    }


def _extract_table(user_message: str, schema: dict) -> str:
    prompt = f"""You are a database assistant. The user wants to perform a database operation.

Database schema (table names only):
{', '.join(list(schema.keys()))}

User request: {user_message}

Which table are they referring to? Return ONLY the exact table name from the schema above. If none match, return an empty string."""

    try:
        response = ask_groq(prompt).strip()
        for table in schema.keys():
            if table.lower() in response.lower():
                return table
    except Exception:
        pass
    return ""


def _get_database_context() -> str:
    from app.main import get_database_profile

    profile = get_database_profile()
    if profile is None or not profile.analyzed:
        return ""
    return profile.to_context()


def run_agent(user_message: str, session_id: str = "default"):
    schema = get_schema()
    database_context = _get_database_context()

    global _pending_insert

    if _pending_insert is not None:
        table = _pending_insert.get("table")

        if table:
            return _handle_insert_followup(
                user_message,
                table,
                schema,
            )

    if _is_insert_followup(user_message):
        table = _detect_insert_table(
            user_message,
            schema,
        )

        if table:
            return _handle_insert_followup(
                user_message,
                table,
                schema,
            )

    intent = _classify_intent(user_message)

    if intent == "chat":
        conversation_state.pop(session_id, None)
        return _handle_chat(user_message)

    if intent == "er_diagram":
        conversation_state.pop(session_id, None)
        return {
            "generated_sql": "",
            "result": {
                "success": True,
                "columns": [],
                "rows": [],
                "execution_time_ms": 0,
                "rows_returned": 0,
            },
            "diagram": generate_flowchart(),
            "explanation": "Here is the Entity Relationship Diagram of the database.",
            "followups": _get_followups(user_message),
        }

    if intent == "relationship_graph":
        conversation_state.pop(session_id, None)
        return {
            "generated_sql": "",
            "result": {
                "success": True,
                "columns": [],
                "rows": [],
                "execution_time_ms": 0,
                "rows_returned": 0,
            },
            "diagram": get_relationship_graph(),
            "explanation": "Here is the database relationship graph showing tables and their foreign key connections.",
            "followups": _get_followups(user_message),
        }

    if intent == "dashboard" or intent == "analytics":
        conversation_state.pop(session_id, None)
        return {
            "generated_sql": "",
            "result": {
                "success": True,
                "columns": [],
                "rows": [],
                "execution_time_ms": 0,
                "rows_returned": 0,
            },
            "analytics": get_analytics_data(),
            "explanation": "Here is the analytics dashboard.",
            "followups": _get_followups(user_message),
        }

    if intent in ("sql", "chart"):
        is_chart = intent == "chart"
        form_values = _parse_form_submission(user_message)
        if form_values:
            state = conversation_state.get(session_id, {})
            table = state.get("pending_insert_table")

            if table:
                insert_fields = get_insert_fields(table)
                fields = {}
                for field in insert_fields:
                    if field["name"] in form_values:
                        fields[field["name"]] = form_values[field["name"]]

                if fields:
                    sql = _generate_sql("insert", table, fields, "")
                    conversation_state.pop(session_id, None)

                    return {
                        "generated_sql": sql,
                        "result": {
                            "success": True,
                            "columns": [],
                            "rows": [],
                            "pending_confirmation": True,
                            "operation": "insert",
                        },
                        "chart": None,
                        "diagram": None,
                        "requires_confirmation": True,
                        "explanation": (
                            "Database change requires confirmation.\n\n"
                            f"Operation: `insert`\n\n"
                            f"```sql\n{sql}\n```\n\n"
                            "Please review the SQL before continuing."
                        ),
                        "followups": [],
                    }

        if _is_insert_request(user_message):
            table = _detect_insert_table(user_message, schema)
            if table:
                conversation_state[session_id] = {
                    "pending_insert_table": table,
                }
                return _build_insert_request(table, schema)

        write_result = _handle_write_operation(session_id, user_message, schema)
        if write_result is not None:
            return write_result

        database_context = _get_database_context()
        database_context_section = f"Database Analysis:\n{database_context}" if database_context else ""

        prompt = f"""
You are BG AI, an intelligent database assistant.

IMPORTANT DATABASE RULES:

1. The database shown below is the CURRENT ACTIVE DATABASE.
2. Use ONLY this database schema.
3. Never assume ecommerce.db exists.
4. Never assume tables such as customers, products, orders, students,
   employees, etc. exist unless they appear in the schema.
5. Never invent a table.
6. Never invent a column.
7. Analyze the schema before generating SQL.
8. Use the exact table and column names from the schema.
9. INSERT, UPDATE and DELETE must operate on the CURRENT ACTIVE DATABASE.
10. UPDATE and DELETE MUST contain a WHERE clause.
11. If the user's requested data does not exist in the schema,
    do not generate fake SQL. Explain that the requested table/column
    is unavailable.

CURRENT DATABASE SCHEMA:
{json.dumps(schema, indent=2, default=str)}

{database_context_section}

USER REQUEST:
{user_message}

Generate ONLY valid SQL.
Do not use markdown.
Do not use ```sql.
"""

        try:
            raw_sql = ask_groq(prompt).strip()

            sql = raw_sql
            if "```" in sql:
                sql = sql.split("```", 1)[1]
                sql = sql.split("```", 1)[0]
                sql = sql.replace("sql", "", 1).strip()
        except Exception as e:
            import traceback

            print("\n========== BG AI ERROR ==========")
            print(f"Error: {e}")
            traceback.print_exc()
            print("=================================\n")

            return {
                "generated_sql": "",
                "result": {
                    "success": False,
                    "columns": [],
                    "rows": [],
                    "rows_returned": 0,
                },
                "chart": None,
                "diagram": None,
                "input_request": None,
                "explanation": f"BG AI encountered an error: {str(e)}",
                "followups": [],
            }

        validation = validate_sql(sql)

        if not validation["allowed"]:
            return {
                "generated_sql": sql,
                "result": {
                    "success": False,
                    "columns": [],
                    "rows": [],
                    "error": validation["reason"],
                },
                "chart": None,
                "diagram": None,
                "analytics": None,
                "explanation": (
                    f"This operation cannot be executed.\n\n"
                    f"{validation['reason']}"
                ),
                "followups": _get_followups(user_message),
            }

        if validation.get("requires_confirmation"):
            return {
                "generated_sql": sql,
                "result": {
                    "success": True,
                    "columns": [],
                    "rows": [],
                    "pending_confirmation": True,
                    "operation": validation["operation"],
                },
                "chart": None,
                "diagram": None,
                "requires_confirmation": True,
                "explanation": (
                    "Database change requires confirmation.\n\n"
                    f"Operation: `{validation['operation']}`\n\n"
                    "Please review the SQL before continuing."
                ),
                "followups": _get_followups(user_message),
            }

        result = execute_query(sql)

        chart = None
        if is_chart:
            chart = generate_chart(user_message, result)

        explanation = explain_data(user_message, result)

        return {
            "generated_sql": sql,
            "result": result,
            "chart": chart,
            "diagram": None,
            "analytics": None,
            "explanation": explanation,
            "followups": _get_followups(user_message),
        }

    conversation_state.pop(session_id, None)
    return {
        "generated_sql": "",
        "result": {
            "success": True,
            "columns": [],
            "rows": [],
            "execution_time_ms": 0,
            "rows_returned": 0,
        },
        "chart": None,
        "diagram": None,
        "analytics": None,
        "explanation": "I'm not sure how to handle that request. Could you rephrase it?",
        "followups": _get_followups(user_message),
    }


def _create_insert_sql(table: str, columns: list[str], values: dict) -> str:
    def _quote(value):
        if isinstance(value, str):
            return "'" + value.replace("'", "''") + "'"
        return str(value)

    cols = [col for col in columns if col in values]
    vals = [_quote(values[col]) for col in cols]
    return f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(vals)})"


def _normalize_insert_key(raw_key: str, allowed_columns: list[str]) -> str | None:
    key = raw_key.lower().strip()

    if key in allowed_columns:
        return key

    close = get_close_matches(key, allowed_columns, n=1, cutoff=0.7)

    return close[0] if close else None


def _extract_insert_fields_from_message(user_message: str, allowed_columns: list[str]) -> dict[str, str]:
    prompt = f"""You are a data extraction assistant.

Allowed columns:
{', '.join(allowed_columns)}

User message:
{user_message}

Extract values from the user message and map them to the allowed columns.
Use fuzzy matching when the user misspells a column name.

Return ONLY a valid JSON object with column names as keys and extracted values as strings.

IMPORTANT:
- Return ONLY valid JSON.
- Do not use markdown.
- Do not generate SQL.
- Do not invent missing values.
- Do not return fields that are not in the allowed columns.

JSON:
"""

    try:
        response = ask_groq(prompt).strip()

        if "```" in response:
            response = response.replace("```json", "")
            response = response.replace("```", "")
            response = response.strip()

        extracted = json.loads(response)

        if not isinstance(extracted, dict):
            return {}

        cleaned = {}
        for raw_key, value in extracted.items():
            column = _normalize_insert_key(str(raw_key), allowed_columns)
            if not column:
                continue
            if value is None:
                continue
            value = str(value).strip()
            if not value:
                continue
            cleaned[column] = value

        return cleaned
    except Exception:
        return {}


def _handle_write_operation(session_id: str, user_message: str, schema: dict) -> dict | None:
    state = conversation_state.get(session_id, {})

    if state.get("step") == "collecting":
        operation = state.get("operation", "")
        table = state.get("table", "")
        fields = state.get("fields", {})
        current_field = state.get("current_field", "")
        normalized_input = user_message.strip().lower()

        if normalized_input in {"cancel", "never mind", "stop", "abort"}:
            conversation_state.pop(session_id, None)
            return {
                "generated_sql": "",
                "result": {
                    "success": True,
                    "columns": [],
                    "rows": [],
                    "pending_confirmation": False,
                    "operation": operation,
                },
                "chart": None,
                "diagram": None,
                "requires_confirmation": False,
                "explanation": "Operation cancelled. The query was not executed.",
                "followups": [],
            }

        if current_field:
            fields[current_field] = user_message.strip()
            state["fields"] = fields

        columns = _get_table_columns(table, schema)
        next_field = None
        for col in columns:
            if col.lower() in ("id", "created_at", "updated_at"):
                continue
            if col not in fields:
                next_field = col
                break

        if next_field:
            state["current_field"] = next_field
            conversation_state[session_id] = state
            return {
                "generated_sql": "",
                "result": {
                    "success": True,
                    "columns": [],
                    "rows": [],
                    "pending_confirmation": False,
                    "operation": operation,
                },
                "chart": None,
                "diagram": None,
                "requires_confirmation": False,
                "explanation": f"Got it\n\nI still need:\n\n• {next_field.replace('_', ' ').title()}",
                "followups": [],
            }

        where = state.get("where", "")
        sql = _generate_sql(operation, table, fields, where)

        if operation == "delete" and where:
            try:
                preview_result = execute_query(f"SELECT * FROM {table} WHERE {where}")
                if preview_result["success"] and preview_result["rows"]:
                    conversation_state.pop(session_id, None)
                    return {
                        "generated_sql": sql,
                        "result": {
                            "success": True,
                            "columns": preview_result["columns"],
                            "rows": preview_result["rows"],
                            "pending_confirmation": True,
                            "operation": "delete",
                        },
                        "chart": None,
                        "diagram": None,
                        "requires_confirmation": True,
                        "explanation": (
                            f"Delete confirmation\n\n"
                            f"I found {len(preview_result['rows'])} matching record(s).\n\n"
                            f"```sql\n{sql}\n```\n\n"
                            "This record will be permanently deleted.\n\n"
                            "Please confirm before this change is applied."
                        ),
                        "followups": [],
                    }
            except Exception:
                pass

        field_summary = "\n".join([f"{k}: {v}" for k, v in fields.items()])
        conversation_state.pop(session_id, None)
        return {
            "generated_sql": sql,
            "result": {
                "success": True,
                "columns": [],
                "rows": [],
                "pending_confirmation": True,
                "operation": operation,
            },
            "chart": None,
            "diagram": None,
            "requires_confirmation": True,
            "explanation": (
                f"I have all the required information.\n\n"
                f"{field_summary}\n\n"
                f"Please review the generated SQL below and confirm before I modify your database."
            ),
            "followups": [],
        }

    return None


def _handle_sql_intent(session_id: str, user_message: str, schema: dict) -> dict:
    state = conversation_state.get(session_id, {})

    if state.get("step") == "collecting":
        write_result = _handle_write_operation(session_id, user_message, schema)
        if write_result is not None:
            return write_result

    if not _is_insert_request(user_message):
        return {
            "generated_sql": "",
            "result": {
                "success": False,
                "columns": [],
                "rows": [],
                "error": "Not an insert request.",
            },
            "chart": None,
            "diagram": None,
            "explanation": "That doesn't look like an add/create request. If you want to insert data, try saying 'Add a record' or 'Create a new entry'.",
            "followups": [],
        }

    table = _detect_insert_table(user_message, schema)

    if not table:
        return {
            "generated_sql": "",
            "result": {
                "success": False,
                "columns": [],
                "rows": [],
                "error": "Could not determine which table to modify.",
            },
            "chart": None,
            "diagram": None,
            "explanation": "I couldn't determine which table you're referring to. Please specify the table name.",
            "followups": [],
        }

    return _build_insert_request(table, schema)


def _parse_form_submission(message: str) -> dict[str, str] | None:
    if "=" not in message:
        return None

    values: dict[str, str] = {}
    parts = message.split(",")

    for part in parts:
        part = part.strip()
        if "=" in part:
            key, value = part.split("=", 1)
            values[key.strip()] = value.strip()

    return values if values else None


def _get_insertable_columns(table: str, schema: dict) -> list[str]:
    columns = _get_table_columns(table, schema)

    ignored = {
        "id",
        "created_at",
        "updated_at",
        "deleted_at",
    }

    return [
        column
        for column in columns
        if column.lower() not in ignored
    ]


def clear_pending_insert():
    global _pending_insert
    _pending_insert = None


def _generate_sql(operation: str, table: str, fields: dict, where: str) -> str:
    def _quote(value):
        if isinstance(value, str):
            return "'" + value.replace("'", "''") + "'"
        return str(value)

    if operation == "insert":
        columns = list(fields.keys())
        values = [_quote(v) for v in fields.values()]
        return f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(values)})"

    if operation == "update":
        set_parts = [f"{k} = {_quote(v)}" for k, v in fields.items()]
        sql = f"UPDATE {table} SET {', '.join(set_parts)}"
        if where:
            sql += f" WHERE {where}"
        return sql

    if operation == "delete":
        sql = f"DELETE FROM {table}"
        if where:
            sql += f" WHERE {where}"
        return sql

    return ""
