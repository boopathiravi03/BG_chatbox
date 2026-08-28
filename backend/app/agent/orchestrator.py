from app.agent.groq_agent import ask_groq
from app.tools.get_schema import get_schema
from app.tools.execute_query import execute_query, validate_sql
from app.tools.explain_data import explain_data
from app.tools.generate_chart import generate_chart
from app.tools.generate_flowchart import generate_flowchart
from app.tools.get_relationship_graph import get_relationship_graph
from app.tools.dashboard_data import get_dashboard_data as get_analytics_data
import json
import re
from difflib import get_close_matches

conversation_state = {}


def clear_pending_insert():
    """
    Clear all pending database-operation conversation state.

    Used when:
    - database is disconnected
    - a database connection changes
    - a pending insert/update/delete must be cancelled
    """
    conversation_state.clear()


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


def _classify_intent(user_message: str, schema: dict) -> str:

    table_names = list(schema.keys())

    prompt = f"""
You are the intent classifier for BG AI.

BG AI is connected to a LIVE database.

CURRENT DATABASE TABLES:
{table_names}

USER REQUEST:
{user_message}

Classify the request into exactly ONE category:

chat
sql
chart
dashboard
relationship_graph
er_diagram
analytics

IMPORTANT:

- Any request asking to see, list, find, search, count,
  compare, filter, calculate, inspect or retrieve database
  information is SQL.

- Natural language does NOT need to contain the exact
  table name.

- "show student"
- "show me students"
- "student details"
- "give student records"
- "list students"

are all database SQL requests if the connected schema
contains a matching student-related table.

- If the user asks for specific database data, ALWAYS
  choose sql.

- Only choose chat for genuine conversation unrelated
  to database data.

Return ONLY the category.
"""

    try:
        response = ask_groq(prompt).strip().lower()

        valid_intents = [
            "chat",
            "sql",
            "chart",
            "dashboard",
            "relationship_graph",
            "er_diagram",
            "analytics",
        ]

        for intent in valid_intents:
            if response == intent:
                return intent

        # Important fallback
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


def _is_insert_action(message: str) -> bool:
    """
    Detect whether the user is asking to create/add/insert/register
    a new database record.

    This intentionally does NOT require the table name to appear.
    Table detection is handled separately.
    """
    normalized = message.lower().strip().replace("-", " ")

    action_words = [
        "add",
        "create",
        "insert",
        "register",
    ]

    return any(
        re.search(rf"\b{re.escape(word)}\b", normalized)
        for word in action_words
    )


def _detect_insert_table(user_message: str, schema: dict) -> str:
    """
    Detect the table the user wants to insert into.

    Uses deterministic matching first, then Groq only when necessary.
    Never invents a table.
    """

    if not schema:
        return ""

    message = user_message.lower().strip()

    # ---------------------------------------------------------
    # 1. Exact table name
    # ---------------------------------------------------------
    for table in schema.keys():
        if re.search(
            rf"\b{re.escape(table.lower())}\b",
            message
        ):
            return table

    # ---------------------------------------------------------
    # 2. Singular/plural matching
    # ---------------------------------------------------------
    for table in schema.keys():

        table_lower = table.lower()

        singular = (
            table_lower[:-1]
            if table_lower.endswith("s")
            else table_lower
        )

        if singular and re.search(
            rf"\b{re.escape(singular)}\b",
            message
        ):
            return table

    # ---------------------------------------------------------
    # 3. Common natural-language variants
    # ---------------------------------------------------------
    for table in schema.keys():

        table_lower = table.lower()

        words = {
            table_lower,
            table_lower.rstrip("s"),
            table_lower.replace("_", " "),
            table_lower.rstrip("s").replace("_", " "),
        }

        if any(
            word and re.search(
                rf"\b{re.escape(word)}\b",
                message
            )
            for word in words
        ):
            return table

    # ---------------------------------------------------------
    # 4. Ask AI only to select from existing tables
    # ---------------------------------------------------------
    prompt = f"""
You are selecting a database table.

IMPORTANT:
- You may ONLY choose a table from the provided schema.
- Never invent a table.
- Return ONLY the exact table name.
- If no table matches, return an empty string.

Available tables:
{", ".join(schema.keys())}

User request:
{user_message}
"""

    try:
        response = ask_groq(prompt).strip().lower()

        for table in schema.keys():
            if table.lower() == response:
                return table

        for table in schema.keys():
            if table.lower() in response:
                return table

    except Exception:
        pass

    return ""


def _get_required_insert_fields(table: str, schema: dict) -> list[str]:
    table_schema = schema.get(table, {})

    required = []

    for column, metadata in table_schema.items():
        metadata = metadata or {}

        column_lower = column.lower()

        if column_lower in {
            "created_at",
            "updated_at",
            "deleted_at",
        }:
            continue

        primary_key = bool(
            metadata.get("primary_key", False)
        )

        nullable = metadata.get(
            "nullable",
            True
        )

        default = metadata.get("default")

        column_type = str(
            metadata.get("type", "")
        ).lower()

        auto_generated = (
            primary_key
            and "int" in column_type
            and default is None
        )

        if auto_generated:
            continue

        if nullable is False and default is None:
            required.append(column)

    return required


def _build_insert_request(table: str, schema: dict) -> dict:
    """
    Build a dynamic form request from the LIVE database schema.

    BG AI must ask the user for values.
    It must NEVER invent values.
    """

    table_schema = schema.get(table, {})

    if not isinstance(table_schema, dict):
        table_schema = {}

    fields = []

    for column, metadata in table_schema.items():

        metadata = metadata or {}

        column_lower = column.lower()

        primary_key = bool(
            metadata.get("primary_key", False)
        )

        nullable = metadata.get(
            "nullable",
            True
        )

        default = metadata.get("default")

        column_type = str(
            metadata.get("type", "")
        ).lower()

        # -----------------------------------------------------
        # Detect likely database-generated ID
        # -----------------------------------------------------
        auto_generated = (
            primary_key
            and "int" in column_type
            and default is None
        )

        # Skip timestamp fields generated by database
        if column_lower in {
            "created_at",
            "updated_at",
            "deleted_at",
        }:
            continue

        # Skip auto-generated primary key
        if auto_generated:
            continue

        # -----------------------------------------------------
        # Determine input type
        # -----------------------------------------------------
        if "email" in column_lower:
            field_type = "email"

        elif any(
            keyword in column_lower
            for keyword in [
                "price",
                "amount",
                "quantity",
                "stock",
                "salary",
                "marks",
                "mark",
                "cgpa",
                "age",
                "year",
                "count",
            ]
        ):
            field_type = "number"

        elif any(
            keyword in column_lower
            for keyword in [
                "date",
                "dob",
                "birth",
            ]
        ):
            field_type = "date"

        else:
            field_type = "text"

        # -----------------------------------------------------
        # Required means:
        #
        # NOT NULL + no database default
        # -----------------------------------------------------
        required = (
            nullable is False
            and default is None
        )

        fields.append({
            "name": column,
            "label": column.replace(
                "_",
                " "
            ).title(),
            "type": field_type,
            "required": required,
        })

    if not fields:
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
                f"I couldn't determine the fields required "
                f"to create a record in `{table}`."
            ),
            "followups": [],
        }

    table_name = (
        table.rstrip("s").replace("_", " ").title()
    )

    required_fields = [
        field
        for field in fields
        if field["required"]
    ]

    optional_fields = [
        field
        for field in fields
        if not field["required"]
    ]

    required_text = ", ".join(
        field["label"]
        for field in required_fields
    )

    optional_text = ", ".join(
        field["label"]
        for field in optional_fields
    )

    message = (
        f"Please provide the required details "
        f"for the new {table_name.lower()}."
    )

    if required_text:
        message += (
            f"\n\nRequired: {required_text}"
        )

    if optional_text:
        message += (
            f"\n\nOptional: {optional_text}"
        )

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
            "message": message,
            "fields": fields,
        },

        "explanation": (
            f"Sure! Let's add a new "
            f"{table_name.lower()}.\n\n"
            f"{message}"
        ),

        "followups": [],
    }


def _extract_table(user_message: str, schema: dict) -> str:

    if not schema:
        return ""

    # Deterministic exact match first
    message = user_message.lower()

    for table in schema.keys():
        if re.search(
            rf"\b{re.escape(table.lower())}\b",
            message
        ):
            return table

    # Give AI full schema information
    schema_description = "\n".join(
        f"- {table}: {', '.join(columns.keys())}"
        for table, columns in schema.items()
        if isinstance(columns, dict)
    )

    prompt = f"""
You are a database table resolver.

LIVE DATABASE SCHEMA:

{schema_description}

USER REQUEST:
{user_message}

Determine which existing table best matches the user's
meaning.

Rules:
- Never invent a table.
- Use semantic meaning, not only exact spelling.
- "student" can match "students".
- "employee" can match "employees".
- "customer details" can match "customers".
- If no table is reasonably related, return NONE.

Return ONLY the exact existing table name.
"""

    try:
        response = ask_groq(prompt).strip()

        for table in schema.keys():
            if response.lower() == table.lower():
                return table

        # Fuzzy fallback
        matches = get_close_matches(
            response.lower(),
            [t.lower() for t in schema.keys()],
            n=1,
            cutoff=0.65,
        )

        if matches:
            for table in schema.keys():
                if table.lower() == matches[0]:
                    return table

    except Exception:
        pass

    return ""


def _clean_generated_sql(raw_sql: str) -> str:
    """
    Convert an LLM response into clean executable SQL.

    Handles:
    - ```sql ... ```
    - ``` ... ```
    - explanations before/after SQL
    - trailing semicolons
    """

    if not raw_sql:
        return ""

    sql = raw_sql.strip()

    # Remove markdown code fences
    sql = re.sub(r"```(?:sql|mysql|postgresql)?", "", sql, flags=re.IGNORECASE)
    sql = sql.replace("```", "").strip()

    # Find the first actual SQL statement
    match = re.search(
        r"\b(SELECT|WITH|INSERT|UPDATE|DELETE|PRAGMA)\b",
        sql,
        flags=re.IGNORECASE,
    )

    if match:
        sql = sql[match.start():]

    # Remove common trailing explanation
    sql = re.split(
        r"\n\s*(Explanation|Here is|This query|Note:)\s*:",
        sql,
        flags=re.IGNORECASE,
    )[0]

    return sql.strip().rstrip(";").strip()


def _get_database_context() -> str:
    from app.main import get_database_profile

    profile = get_database_profile()
    if profile is None or not profile.analyzed:
        return ""
    return profile.to_context()


def run_agent(user_message: str, session_id: str = "default"):
    schema = get_schema()
    database_context = _get_database_context()

    intent = _classify_intent(user_message, schema)

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

        # ---------------------------------------------------------
        # INSERT: never let the generic SQL generator invent values.
        # Intercept CREATE/ADD/INSERT requests before the LLM sees
        # the generic SQL prompt.
        # ---------------------------------------------------------
        if _is_insert_action(user_message):
            table = _detect_insert_table(user_message, schema)
            if table:
                conversation_state[session_id] = {
                    "pending_insert_table": table,
                }
                return _build_insert_request(table, schema)

        # ---------------------------------------------------------
        # Form submission path: validate required fields before
        # generating INSERT SQL.
        # ---------------------------------------------------------
        form_values = _parse_form_submission(user_message)
        if form_values:
            state = conversation_state.get(session_id, {})
            table = state.get("pending_insert_table")

            if table:
                required_fields = _get_required_insert_fields(
                    table,
                    schema,
                )

                fields = {}
                for field in required_fields:
                    if field in form_values:
                        fields[field] = form_values[field]

                missing_fields = [
                    field
                    for field in required_fields
                    if field not in fields
                    or not str(fields[field]).strip()
                ]

                if missing_fields:
                    missing_labels = [
                        field.replace("_", " ").title()
                        for field in missing_fields
                    ]

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
                        "input_request": {
                            "type": "insert",
                            "table": table,
                            "title": (
                                f"Complete {table.replace('_', ' ').title()} Details"
                            ),
                            "message": (
                                "I still need the following required details:"
                            ),
                            "fields": [
                                {
                                    "name": field,
                                    "label": field.replace(
                                        "_",
                                        " "
                                    ).title(),
                                    "type": "text",
                                    "required": True,
                                }
                                for field in missing_fields
                            ],
                        },
                        "explanation": (
                            "I can't create the record yet because "
                            "some required fields are missing.\n\n"
                            + "\n".join(
                                f"• {field.replace('_', ' ').title()}"
                                for field in missing_fields
                            )
                        ),
                        "followups": [],
                    }

                sql = _generate_sql(
                    "insert",
                    table,
                    fields,
                    ""
                )

                conversation_state.pop(
                    session_id,
                    None
                )

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
                        "I have all the required information.\n\n"
                        "Please review the generated SQL "
                        "before modifying the database."
                    ),
                    "followups": [],
                }

        write_result = _handle_write_operation(session_id, user_message, schema)
        if write_result is not None:
            return write_result

        # ---------------------------------------------------------
        # Generic SQL path: only for SELECT / READ operations.
        # INSERT must be handled above.
        # ---------------------------------------------------------
        database_context = _get_database_context()
        database_context_section = f"Database Analysis:\n{database_context}" if database_context else ""

        prompt = f"""
You are BG AI, an intelligent database assistant.

Your job is to understand what the user means in natural language
and answer using ONLY the CURRENTLY CONNECTED DATABASE.

================ DATABASE SCHEMA ================
{schema}

================ DATABASE CONTEXT ================
{database_context_section}

================ USER REQUEST ================
{user_message}

================ RULES ================

1. First understand the user's meaning.

2. Use ONLY tables and columns that actually exist in the
   database schema above.

3. NEVER assume a fixed database such as customers,
   products, students, orders, etc.

4. The connected database may contain ANY domain:
   students, employees, hospital records, products,
   customers, finance, attendance, etc.

5. Map natural language to the closest matching table
   and columns from the LIVE schema.

6. Examples:
   "show students"
   -> SELECT ... FROM the actual student table

   "show student details"
   -> SELECT ... FROM the actual student-related table

   "show all customers"
   -> SELECT ... FROM the actual customer table

   "how many students are there"
   -> SELECT COUNT(*) FROM the actual student table

7. If the requested entity does NOT exist in the schema,
   do NOT invent a table.

8. For SELECT requests, return a SELECT query.

9. For UPDATE and DELETE, a WHERE condition is mandatory.

10. For INSERT, use only actual columns from the schema.

11. Return ONLY raw SQL.

12. NEVER return:
   - explanations
   - markdown
   - ```sql
   - ``` 
   - comments
   - "Here is the query"

USER REQUEST:
{user_message}

RAW SQL ONLY:
"""

        try:
            raw_sql = ask_groq(prompt).strip()

            print("\n========== BG AI SQL ==========")
            print("USER:", user_message)
            print("RAW :", raw_sql)

            sql = _clean_generated_sql(raw_sql)

            print("SQL :", sql)
            print("================================\n")
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


def _generate_sql(
    operation: str,
    table: str,
    fields: dict,
    where: str
) -> str:

    def _quote(value):
        if value is None:
            return "NULL"

        if isinstance(value, bool):
            return "1" if value else "0"

        if isinstance(value, (int, float)):
            return str(value)

        value = str(value)

        return "'" + value.replace("'", "''") + "'"

    # Safety: table must be a simple identifier
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", table):
        raise ValueError("Invalid table name.")

    if operation == "insert":

        if not fields:
            raise ValueError("No values supplied for INSERT.")

        columns = []

        values = []

        for key, value in fields.items():

            if not re.match(
                r"^[A-Za-z_][A-Za-z0-9_]*$",
                key
            ):
                raise ValueError(
                    f"Invalid column name: {key}"
                )

            columns.append(key)
            values.append(_quote(value))

        sql = (
            f"INSERT INTO {table} "
            f"({', '.join(columns)}) "
            f"VALUES ({', '.join(values)})"
        )

        return sql

    if operation == "update":

        if not fields:
            raise ValueError("No fields supplied for UPDATE.")

        if not where:
            raise ValueError(
                "UPDATE requires a WHERE condition."
            )

        set_parts = []

        for key, value in fields.items():

            if not re.match(
                r"^[A-Za-z_][A-Za-z0-9_]*$",
                key
            ):
                raise ValueError(
                    f"Invalid column name: {key}"
                )

            set_parts.append(
                f"{key} = {_quote(value)}"
            )

        return (
            f"UPDATE {table} "
            f"SET {', '.join(set_parts)} "
            f"WHERE {where}"
        )

    if operation == "delete":

        if not where:
            raise ValueError(
                "DELETE requires a WHERE condition."
            )

        return (
            f"DELETE FROM {table} "
            f"WHERE {where}"
        )

    raise ValueError(
        f"Unsupported operation: {operation}"
    )


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
