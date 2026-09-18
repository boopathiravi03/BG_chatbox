from app.agent.groq_agent import ask_groq
from app.tools.get_schema import get_schema
from app.tools.execute_query import execute_query, validate_sql
from app.tools.explain_data import explain_data
from app.tools.generate_chart import generate_chart
from app.tools.generate_flowchart import generate_flowchart
from app.tools.get_relationship_graph import get_relationship_graph
from app.tools.dashboard_data import get_dashboard_data as get_analytics_data
from app.database.database_manager import (
    get_engine,
    get_current_db_type,
)
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
        from app.database.database_context import get_database_profile
        profile = get_database_profile()
    except Exception:
        pass

    database_context = ""

    if profile and profile.analyzed:
        database_context = profile.to_context()

    return generate_suggestions(
        schema,
        database_context
    )


def _classify_intent(user_message: str, schema: dict) -> str:

    message = user_message.lower().strip()

    if _looks_like_database_request(message):
        return "sql"

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
            "database_schema",
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


def _handle_no_database_request(user_message: str) -> dict:
    """
    Handle user requests when no database is currently connected.
    Accurately supports:
    1. Greetings & general conversation (natural AI chat)
    2. Database connection help & instructions
    3. Database-dependent operations (friendly guidance to connect first)
    """
    msg_clean = user_message.lower().strip()

    # Fast deterministic greeting detection
    greetings = {"hi", "hello", "hey", "hii", "heyy", "good morning", "good afternoon", "good evening", "howdy", "sup"}
    if msg_clean in greetings or re.match(r"^(hi|hello|hey|greetings|good morning|good afternoon|good evening)[!.\s]*$", msg_clean):
        explanation = (
            "Hello! 👋 I'm **BG AI**, your AI-powered database assistant.\n\n"
            "I can help you explore databases, generate SQL queries, analyze data, create visualizations, "
            "and understand database relationships using natural language.\n\n"
            "To get started, connect or upload your database using the **Connect the Database** button.\n\n"
            "Once connected, you can ask me questions about your data. How can I help you today?"
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
            "diagram": None,
            "analytics": None,
            "explanation": explanation,
            "followups": [
                "How do I connect a database?",
                "What databases do you support?",
                "What can BG AI do?",
                "What is SQL?",
            ],
        }

    # Use LLM for intelligent conversation without database connection
    prompt = f"""You are BG AI, a friendly, intelligent AI-powered database assistant.
IMPORTANT: Currently, NO database is connected to the application.

User's message: "{user_message}"

Respond naturally, professionally, and helpfully following these instructions:

1. GENERAL GREETINGS / CASUAL CHAT / COURTESY:
   - Greet the user warmly and introduce yourself as BG AI.
   - Mention your capabilities: conversational SQL generation, database exploration, data visualization, charts, ER diagrams, and CRUD workflows with safeguards.
   - Guide them to connect a database using the "Connect the Database" button when they are ready to explore data.

2. WHO ARE YOU / WHAT CAN YOU DO / ABOUT BG AI / HELP:
   - Explain what BG AI is: an AI-powered conversational database intelligence and visualization platform.
   - List key features: Natural Language Queries, AI SQL Generation, Data Visualization, ER Diagrams, and Multi-Database Support (SQLite, MySQL, PostgreSQL).
   - Explain how to get started (using "Connect the Database").

3. HOW TO CONNECT A DATABASE / SUPPORTED ENGINES:
   - Provide clear, actionable instructions:
     • SQLite: Click "Connect the Database" and upload a local .db, .sqlite, or .sqlite3 file.
     • MySQL: Click "Connect the Database" → MySQL tab and provide host (localhost), port (3306), database name, username, and password.
     • PostgreSQL: Click "Connect the Database" → PostgreSQL tab and provide host (localhost), port (5432), database name, username, and password.

4. DATABASE DATA OPERATIONS (e.g. "show all customers", "list products", "analyze my database", "show monthly sales", "add a customer", "delete record"):
   - Acknowledge what they want to do warmly (e.g. "I can help you retrieve customer records!").
   - Clearly explain that no database is currently connected.
   - Invite them to connect or upload their database using the "Connect the Database" button so you can run the query and visualize their data.
   - NEVER output technical error messages or stack traces.

5. EDUCATIONAL / GENERAL QUESTIONS (e.g. "what is SQL?", "what is a primary key?"):
   - Answer the educational question accurately, clearly, and concisely.

Keep responses friendly, helpful, well-formatted with Markdown, and free from robotic errors.
"""

    try:
        explanation = ask_groq(prompt).strip()
    except Exception:
        # Fallback if Groq is temporarily unreachable
        if any(w in msg_clean for w in ["connect", "upload", "mysql", "postgres", "sqlite", "how do i"]):
            explanation = (
                "You can connect or upload a database to BG AI in 3 ways:\n\n"
                "1. **SQLite**: Click **Connect the Database** and upload a `.db`, `.sqlite`, or `.sqlite3` file.\n"
                "2. **MySQL**: Click **Connect the Database** → **MySQL** tab and enter your host (`localhost`), port (`3306`), database name, and credentials.\n"
                "3. **PostgreSQL**: Click **Connect the Database** → **PostgreSQL** tab and enter your host, port (`5432`), database name, and credentials.\n\n"
                "Once connected, you can ask queries in natural language!"
            )
        elif any(w in msg_clean for w in ["who are you", "what can you do", "help", "what is bg ai", "explain bg ai"]):
            explanation = (
                "I am **BG AI**, an AI-powered conversational database assistant. I can help you:\n\n"
                "• Ask questions about your database using natural language\n"
                "• Automatically generate and optimize SQL queries\n"
                "• Visualize data through interactive charts and analytics dashboards\n"
                "• Explore schema structures and Entity Relationship (ER) diagrams\n"
                "• Perform safe insert, update, and delete operations with confirmation safeguards\n\n"
                "To get started, please connect or upload your database using the **Connect the Database** button!"
            )
        elif any(w in msg_clean for w in ["show", "list", "select", "find", "get", "analyze", "count", "sales", "customer", "order", "table"]):
            explanation = (
                "I'd be glad to help you with that! However, no database is currently connected.\n\n"
                "Please connect or upload your database using the **Connect the Database** button, "
                "and I'll help you explore and analyze your data."
            )
        else:
            explanation = (
                "Hello! 👋 I'm **BG AI**, your conversational database intelligence assistant. "
                "Connect or upload a database using the **Connect the Database** button to start querying and visualizing your data, "
                "or feel free to ask me general questions!"
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
        "diagram": None,
        "analytics": None,
        "explanation": explanation,
        "followups": [
            "How do I connect a database?",
            "What databases do you support?",
            "What can BG AI do?",
            "What is SQL?",
        ],
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


def _is_delete_action(message: str) -> bool:
    normalized = message.lower().strip()

    normalized = normalized.replace(
        "delet",
        "delete",
    )

    normalized = normalized.replace(
        "delte",
        "delete",
    )

    normalized = normalized.replace(
        "remve",
        "remove",
    )

    action_words = [
        "delete",
        "remove",
        "erase",
    ]

    return any(
        re.search(
            rf"\b{re.escape(word)}\b",
            normalized,
        )
        for word in action_words
    )


def _is_update_action(message: str) -> bool:
    normalized = message.lower().strip()

    action_words = [
        "update",
        "change",
        "modify",
        "edit",
        "set",
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



def _extract_table(user_message: str, schema: dict) -> str:

    if not schema:
        return ""

    # First try deterministic + typo-tolerant matching
    resolved = _resolve_table_from_message(
        user_message,
        schema
    )

    if resolved:
        return resolved

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

    # Find the first actual SQL statement.
    #
    # IMPORTANT: the statement keyword must be matched in a way that
    # cannot be satisfied by ordinary English. A bare \bWITH\b once
    # matched the prose "...I can help with that." and produced the
    # bogus statement "with that.". WITH is therefore only accepted
    # when it begins a real common table expression:
    #
    #     WITH recent_orders AS (
    #     WITH RECURSIVE tree AS (
    match = re.search(
        r"\bSELECT\b"
        r"|\bINSERT\b"
        r"|\bUPDATE\b"
        r"|\bDELETE\b"
        r"|\bPRAGMA\b"
        r"|\bWITH\s+(?:RECURSIVE\s+)?"
        r"[\"`\[]?[A-Za-z_][A-Za-z0-9_]*[\"`\]]?\s+AS\s*\(",
        sql,
        flags=re.IGNORECASE,
    )

    if match:
        sql = sql[match.start():]
        sql = re.split(
            r"\n\s*(Explanation|Here is|This query|Note:)\s*:",
            sql,
            flags=re.IGNORECASE,
        )[0]
        return sql.strip().rstrip(";").strip()

    # No SQL statement was found. The model replied with prose
    # (typically a clarification request). Return an empty string so
    # the caller can respond sensibly instead of executing the prose.
    return ""


def _normalize_sql_for_active_database(
    sql: str,
) -> str:
    """
    Normalize common identifier quoting mistakes
    produced by the LLM.

    This is a compatibility layer.
    The LIVE SQLAlchemy dialect remains the source of truth.
    """

    if not sql:
        return sql

    db_type = get_current_db_type()

    # ---------------------------------------------------------
    # MySQL
    # ---------------------------------------------------------

    if db_type == "mysql":

        # Convert:
        # "customers"
        # "customer_id"
        #
        # into:
        # `customers`
        # `customer_id`
        #
        # Only convert quoted identifier-like tokens.
        sql = re.sub(
            r'"([A-Za-z_][A-Za-z0-9_]*)"',
            r'`\1`',
            sql,
        )

    # ---------------------------------------------------------
    # PostgreSQL / SQLite
    # ---------------------------------------------------------

    elif db_type in {
        "postgres",
        "sqlite",
    }:

        # Convert MySQL-style identifiers:
        #
        # `customers`
        #
        # to:
        #
        # "customers"
        #
        sql = re.sub(
            r'`([A-Za-z_][A-Za-z0-9_]*)`',
            r'"\1"',
            sql,
        )

    return sql


def _build_compact_schema(schema: dict) -> str:
    """
    Create a small schema description for the LLM.

    Only table names and column names are sent.
    Detailed metadata is unnecessary for SELECT generation.
    """

    if not schema:
        return "No tables found."

    lines = []

    for table_name, columns in schema.items():

        if not isinstance(columns, dict):
            continue

        column_names = list(columns.keys())

        lines.append(
            f"{table_name}: {', '.join(column_names)}"
        )

    return "\n".join(lines)


def _looks_like_database_request(user_message: str) -> bool:
    message = user_message.lower().strip()

    database_words = [
        "show",
        "list",
        "find",
        "search",
        "get",
        "give",
        "display",
        "count",
        "how many",
        "how much",
        "total",
        "average",
        "sum",
        "maximum",
        "minimum",
        "details",
        "records",
        "data",
        "where",
        "filter",
        "compare",
    ]

    return any(
        re.search(
            rf"\b{re.escape(word)}\b",
            message
        )
        for word in database_words
    )


def _is_schema_request(user_message: str) -> bool:
    """
    Detect requests asking for the structure of the currently
    connected database.
    """

    message = user_message.lower().strip()

    corrections = {
        "databse": "database",
        "databses": "databases",
        "tabel": "table",
        "tabels": "tables",
        "tabl": "table",
        "scheema": "schema",
        "schem": "schema",
        "colum": "column",
        "colums": "columns",
        "colmn": "column",
    }

    words = message.split()

    normalized_words = [
        corrections.get(word, word)
        for word in words
    ]

    message = " ".join(normalized_words)

    patterns = [
        r"\bshow (me )?(the )?(database|tables|schema)\b",
        r"\blist (all )?(the )?(tables|databases)\b",
        r"\bwhat tables\b",
        r"\bwhich tables\b",
        r"\bshow table\b",
        r"\bshow schema\b",
        r"\bdatabase structure\b",
        r"\bdatabase details\b",
        r"\bdatabase information\b",
        r"\bmy database\b",
        r"\bconnected database\b",
        r"\bwhat is in (the )?database\b",
        r"\bwhat are the tables\b",
    ]

    return any(
        re.search(pattern, message)
        for pattern in patterns
    )


def _resolve_table_from_message(
    user_message: str,
    schema: dict
) -> str:

    if not schema:
        return ""

    message = user_message.lower()

    table_names = list(schema.keys())

    for table in table_names:
        if re.search(
            rf"\b{re.escape(table.lower())}\b",
            message
        ):
            return table

    for table in table_names:

        table_lower = table.lower()

        singular = (
            table_lower[:-1]
            if table_lower.endswith("s")
            else table_lower
        )

        if re.search(
            rf"\b{re.escape(singular)}\b",
            message
        ):
            return table

    user_words = re.findall(
        r"[a-zA-Z_][a-zA-Z0-9_]*",
        message
    )

    for word in user_words:

        matches = get_close_matches(
            word,
            [table.lower() for table in table_names],
            n=1,
            cutoff=0.65,
        )

        if matches:

            matched = matches[0]

            for table in table_names:
                if table.lower() == matched:
                    return table

    return ""


def _resolve_delete_request(user_message: str, schema: dict) -> dict | None:
    """
    Resolve DELETE requests using the LIVE database schema.

    Deterministic matching is performed first so simple requests
    do not depend on an LLM response.

    Examples:
        delete student with id 5
        delete student id 5
        remove student 5
        delete customer where id = 10
        delet student id 5
    """

    if not schema:
        return None

    message = user_message.strip()

    # ---------------------------------------------------------
    # Normalize common spelling mistakes
    # ---------------------------------------------------------
    normalized = message.lower()

    corrections = {
        "delet": "delete",
        "delte": "delete",
        "deleet": "delete",
        "remve": "remove",
        "studnt": "student",
        "studnts": "students",
        "custmer": "customer",
        "custmers": "customers",
    }

    for wrong, correct in corrections.items():
        normalized = re.sub(
            rf"\b{re.escape(wrong)}\b",
            correct,
            normalized,
        )

    # ---------------------------------------------------------
    # Find table deterministically
    # ---------------------------------------------------------
    table = None

    # 1. Exact table name
    for existing_table in schema.keys():
        if re.search(
            rf"\b{re.escape(existing_table.lower())}\b",
            normalized,
        ):
            table = existing_table
            break

    # 2. Singular/plural matching
    if table is None:
        for existing_table in schema.keys():

            table_lower = existing_table.lower()

            singular = (
                table_lower[:-1]
                if table_lower.endswith("s")
                else table_lower
            )

            if singular and re.search(
                rf"\b{re.escape(singular)}\b",
                normalized,
            ):
                table = existing_table
                break

    # 3. Common semantic matching
    if table is None:
        semantic_words = {
            "student": ["student", "students", "learner", "learners"],
            "customer": ["customer", "customers", "client", "clients"],
            "employee": ["employee", "employees", "staff", "worker"],
            "product": ["product", "products", "item", "items"],
            "order": ["order", "orders", "purchase", "purchases"],
            "teacher": ["teacher", "teachers", "faculty"],
        }

        for existing_table in schema.keys():

            table_lower = existing_table.lower()
            singular = (
                table_lower[:-1]
                if table_lower.endswith("s")
                else table_lower
            )

            candidates = [table_lower, singular]

            for entity, words in semantic_words.items():

                if any(
                    re.search(
                        rf"\b{re.escape(word)}\b",
                        normalized,
                    )
                    for word in words
                ):
                    if entity in candidates or any(
                        entity in candidate
                        for candidate in candidates
                    ):
                        table = existing_table
                        break

            if table:
                break

    # ---------------------------------------------------------
    # If no table was mentioned and only ONE table exists,
    # safely use that table.
    #
    # This allows:
    #     delete id 8
    # ---------------------------------------------------------
    if table is None and len(schema) == 1:
        table = list(schema.keys())[0]

    if table is None:
        return None

    # ---------------------------------------------------------
    # Get actual columns from LIVE schema
    # ---------------------------------------------------------
    columns = _get_table_columns(
        table,
        schema,
    )

    if not columns:
        return None

    # ---------------------------------------------------------
    # Find explicit WHERE condition
    #
    # Examples:
    #   where id = 5
    #   where id is 5
    #   with id 5
    #   id = 5
    # ---------------------------------------------------------

    # First find a column mentioned by the user.
    matched_column = None

    # Prefer ID columns
    for column in columns:

        if column.lower() == "id":
            if re.search(
                r"\bid\b",
                normalized,
            ):
                matched_column = column
                break

    # Otherwise search all columns
    if matched_column is None:

        for column in columns:

            if re.search(
                rf"\b{re.escape(column.lower())}\b",
                normalized,
            ):
                matched_column = column
                break

    if matched_column is None:
        return None

    # ---------------------------------------------------------
    # Extract value after the column
    #
    # Supports:
    #   id 5
    #   id = 5
    #   id is 5
    #   id: 5
    #   id = '5'
    # ---------------------------------------------------------

    column_pattern = re.escape(
        matched_column
    )

    value_match = re.search(
        rf"\b{column_pattern}\b"
        rf"\s*(?:=|is|:)?\s*"
        rf"(?:['\"]([^'\"]+)['\"]|([A-Za-z0-9_.@+\-]+))"
        rf"\b",
        normalized,
        flags=re.IGNORECASE,
    )

    value = None

    if value_match:
        value = (
            value_match.group(1)
            or value_match.group(2)
        )

    # ---------------------------------------------------------
    # If "delete student 5", extract number after table
    # ---------------------------------------------------------
    if value is None:

        table_pattern = re.escape(
            table.lower()
        )

        simple_match = re.search(
            rf"\b{table_pattern}\b"
            rf"(?:\s+with)?"
            rf"\s+(\d+)\b",
            normalized,
            flags=re.IGNORECASE,
        )

        if simple_match and "id" in [
            c.lower() for c in columns
        ]:
            matched_column = next(
                c for c in columns
                if c.lower() == "id"
            )
            value = simple_match.group(1)

    if value is None:
        return None

    # ---------------------------------------------------------
    # Safely quote the value
    # ---------------------------------------------------------
    if re.fullmatch(r"-?\d+(?:\.\d+)?", str(value)):
        formatted_value = str(value)
    else:
        formatted_value = (
            "'"
            + str(value).replace("'", "''")
            + "'"
        )

    where = (
        f"{matched_column} = {formatted_value}"
    )

    print("\n========== DELETE RESOLVER ==========")
    print("USER :", user_message)
    print("TABLE:", table)
    print("WHERE:", where)
    print("=====================================\n")

    return {
        "table": table,
        "where": where,
    }


def _resolve_update_request(user_message: str, schema: dict) -> dict | None:

    if not schema:
        return None

    prompt = f"""
You are BG AI's UPDATE request parser.

CURRENT LIVE DATABASE SCHEMA:
{schema}

USER REQUEST:
{user_message}

Understand the user's request.

Return ONLY valid JSON:

{{
  "table": "exact_existing_table_name",
  "fields": {{
    "existing_column": "new_value"
  }},
  "where": "safe SQL WHERE condition"
}}

Rules:

1. Use ONLY tables from the live schema.
2. Use ONLY columns from that table.
3. Correct spelling mistakes.
4. Understand natural language.
5. Never invent tables or columns.
6. UPDATE MUST have a WHERE condition.
7. Never generate an UPDATE affecting every row.
8. If information is missing, return empty values.
9. Return ONLY JSON.

Example:

"update student 5 name to Rahul"

=> {{
  "table": "students",
  "fields": {{
    "name": "Rahul"
  }},
  "where": "id = 5"
}}

Example:

"change customer 10 email to test@gmail.com"

=> {{
  "table": "customers",
  "fields": {{
    "email": "test@gmail.com"
  }},
  "where": "id = 10"
}}
"""

    try:
        raw = ask_groq(prompt).strip()

        raw = re.sub(r"```json", "", raw, flags=re.IGNORECASE)
        raw = raw.replace("```", "").strip()

        data = json.loads(raw)

        table = data.get("table", "")
        fields = data.get("fields", {})
        where = data.get("where", "")

        actual_table = None

        for existing_table in schema.keys():
            if existing_table.lower() == str(table).lower():
                actual_table = existing_table
                break

        if not actual_table:
            return None

        if not isinstance(fields, dict) or not fields:
            return None

        if not where:
            return None

        columns = _get_table_columns(actual_table, schema)

        validated_fields = {}

        for key, value in fields.items():

            actual_column = None

            for column in columns:
                if column.lower() == str(key).lower():
                    actual_column = column
                    break

            if actual_column:
                validated_fields[actual_column] = value

        if not validated_fields:
            return None

        where_lower = where.lower()

        has_known_column = any(
            re.search(
                rf"\b{re.escape(column.lower())}\b",
                where_lower
            )
            for column in columns
        )

        if not has_known_column:
            return None

        return {
            "table": actual_table,
            "fields": validated_fields,
            "where": where.strip(),
        }

    except Exception as e:
        print("UPDATE PARSER ERROR:", e)
        return None


def _handle_delete_operation(
    session_id: str,
    user_message: str,
    schema: dict
) -> dict | None:

    if not _is_delete_action(user_message):
        return None

    request = _resolve_delete_request(
        user_message,
        schema
    )

    if not request:
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
            "requires_confirmation": False,
            "explanation": (
                "I understood that you want to delete a record, "
                "but I couldn't safely determine the table and "
                "record to delete.\n\n"
                "Please specify the record, for example:\n"
                "• Delete student with id 5\n"
                "• Remove customer where id is 10"
            ),
            "followups": [],
        }

    table = request["table"]
    where = request["where"]

    if not where.strip():
        return {
            "generated_sql": "",
            "result": {
                "success": False,
                "error": "DELETE requires a WHERE condition.",
            },
            "explanation": (
                "I need to know which record you want to delete."
            ),
            "followups": [],
        }

    sql = _generate_sql(
        "delete",
        table,
        {},
        where
    )

    preview_sql = (
        f"SELECT * FROM "
        f"{_crud_quote_identifier(table)} "
        f"WHERE {where}"
    )

    try:
        preview = execute_query(preview_sql)

        if not preview.get("success"):
            return {
                "generated_sql": sql,
                "result": preview,
                "requires_confirmation": False,
                "explanation": (
                    "I couldn't find the records to delete."
                ),
                "followups": [],
            }

        rows = preview.get("rows", [])

        if not rows:
            return {
                "generated_sql": sql,
                "result": {
                    "success": True,
                    "columns": preview.get("columns", []),
                    "rows": [],
                    "rows_returned": 0,
                },
                "requires_confirmation": False,
                "explanation": (
                    f"I couldn't find any records in "
                    f"`{table}` matching that condition. "
                    "Nothing was deleted."
                ),
                "followups": [],
            }

        conversation_state[session_id] = {
            "operation": "delete",
            "table": table,
            "where": where,
            "sql": sql,
        }

        return {
            "generated_sql": sql,
            "result": {
                "success": True,
                "columns": preview.get("columns", []),
                "rows": rows,
                "rows_returned": len(rows),
                "pending_confirmation": True,
                "operation": "delete",
            },
            "chart": None,
            "diagram": None,
            "requires_confirmation": True,
            "explanation": (
                f"I found **{len(rows)} matching record(s)** "
                f"in `{table}`.\n\n"
                "Please review the records and confirm "
                "the deletion. The database has NOT been "
                "changed yet."
            ),
            "followups": [],
        }

    except Exception as e:
        return {
            "generated_sql": sql,
            "result": {
                "success": False,
                "error": str(e),
            },
            "requires_confirmation": False,
            "explanation": (
                f"I couldn't prepare the deletion: {str(e)}"
            ),
            "followups": [],
        }


def _handle_update_operation(
    session_id: str,
    user_message: str,
    schema: dict
) -> dict | None:

    if not _is_update_action(user_message):
        return None

    request = _resolve_update_request(
        user_message,
        schema
    )

    if not request:
        return {
            "generated_sql": "",
            "result": {
                "success": False,
                "columns": [],
                "rows": [],
                "rows_returned": 0,
            },
            "requires_confirmation": False,
            "explanation": (
                "I understood that you want to update a record, "
                "but I need enough information to safely determine "
                "what should change.\n\n"
                "Example:\n"
                "• Update student 5 name to Rahul\n"
                "• Change customer 10 email to test@gmail.com"
            ),
            "followups": [],
        }

    table = request["table"]
    fields = request["fields"]
    where = request["where"]

    if not where:
        return {
            "generated_sql": "",
            "result": {
                "success": False,
                "error": "UPDATE requires a WHERE condition.",
            },
            "requires_confirmation": False,
            "explanation": (
                "I need to know which record you want to update."
            ),
            "followups": [],
        }

    sql = _generate_sql(
        "update",
        table,
        fields,
        where
    )

    try:
        preview_sql = (
        f"SELECT * FROM "
        f"{_crud_quote_identifier(table)} "
        f"WHERE {where}"
    )

        preview = execute_query(preview_sql)

        if not preview.get("success"):
            return {
                "generated_sql": sql,
                "result": preview,
                "requires_confirmation": False,
                "explanation": (
                    "I couldn't find the record to update."
                ),
                "followups": [],
            }

        rows = preview.get("rows", [])

        if not rows:
            return {
                "generated_sql": sql,
                "result": {
                    "success": True,
                    "columns": preview.get("columns", []),
                    "rows": [],
                    "rows_returned": 0,
                },
                "requires_confirmation": False,
                "explanation": (
                    f"No records in `{table}` match "
                    "the specified condition. "
                    "Nothing was updated."
                ),
                "followups": [],
            }

        conversation_state[session_id] = {
            "operation": "update",
            "table": table,
            "fields": fields,
            "where": where,
            "sql": sql,
        }

        return {
            "generated_sql": sql,
            "result": {
                "success": True,
                "columns": preview.get("columns", []),
                "rows": rows,
                "rows_returned": len(rows),
                "pending_confirmation": True,
                "operation": "update",
            },
            "chart": None,
            "diagram": None,
            "requires_confirmation": True,
            "explanation": (
                f"I found **{len(rows)} matching record(s)** "
                f"in `{table}`.\n\n"
                "The following change is ready to be applied. "
                "Please review it and confirm."
            ),
            "followups": [],
        }

    except Exception as e:
        return {
            "generated_sql": sql,
            "result": {
                "success": False,
                "error": str(e),
            },
            "requires_confirmation": False,
            "explanation": (
                f"I couldn't prepare the update: {str(e)}"
            ),
            "followups": [],
        }



    """
    Detect database modification operation from natural language.
    """

    message = message.lower().strip()

    if re.search(r"\b(update|modify|change|edit)\b", message):
        return "update"

    if re.search(r"\b(delete|remove|erase)\b", message):
        return "delete"

    if re.search(r"\b(drop|remove table|delete table)\b", message):
        return "drop"

    if re.search(r"\b(truncate|empty table|clear table)\b", message):
        return "truncate"

    if re.search(
        r"\b(alter|add column|remove column|rename column|change column)\b",
        message,
    ):
        return "alter"

    return ""


def _build_modification_sql(
    operation: str,
    user_message: str,
    schema: dict,
) -> str:

    table = _extract_table(user_message, schema)

    if not table:
        return ""

    prompt = f"""
You are BG AI's database modification assistant.

CURRENT LIVE DATABASE SCHEMA:
{schema}

USER REQUEST:
{user_message}

OPERATION:
{operation}

RULES:

1. Use ONLY tables that exist in the schema.
2. Use ONLY columns that exist in the schema.
3. Never invent tables or columns.
4. Never modify another table.
5. Return exactly ONE SQL statement.
6. Return RAW SQL ONLY.
7. Do not use markdown.
8. Do not explain anything.

SAFETY:

For UPDATE:
- WHERE is mandatory.
- Never generate UPDATE without WHERE.

For DELETE:
- WHERE is mandatory.
- Never generate DELETE without WHERE.

For DROP:
- Generate DROP TABLE only for the identified existing table.

For TRUNCATE:
- Generate TRUNCATE TABLE only for the identified existing table.

For ALTER:
- Only perform the specific alteration requested by the user.
- Use only existing table/column names.

SQL:
"""

    try:
        raw_sql = ask_groq(prompt).strip()

        sql = _clean_generated_sql(raw_sql)

        sql = _normalize_sql_for_active_database(
            sql
        )

        return sql

    except Exception:
        return ""


def _handle_database_modification(
    user_message: str,
    schema: dict,
    session_id: str,
) -> dict | None:

    operation = _detect_operation(user_message)

    if not operation:
        return None

    # INSERT already has dedicated flow
    if operation == "insert":
        return None

    # ---------------------------------------------------------
    # Detect table
    # ---------------------------------------------------------

    table = _extract_table(user_message, schema)

    if not table:

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
            "requires_confirmation": False,
            "explanation": (
                f"I understood that you want to {operation}, "
                "but I couldn't safely determine which table "
                "you want to modify.\n\n"
                "Please specify the table.\n\n"
                "Examples:\n"
                "• Update student with id 5\n"
                "• Delete customer with id 10\n"
                "• Drop students table\n"
                "• Add email column to employees"
            ),
            "followups": [],
        }

    # ---------------------------------------------------------
    # Generate SQL
    # ---------------------------------------------------------

    sql = _build_modification_sql(
        operation,
        user_message,
        schema,
    )

    if not sql:

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
            "requires_confirmation": False,
            "explanation": (
                "I couldn't safely generate the database "
                "operation from your request."
            ),
            "followups": [],
        }

    # ---------------------------------------------------------
    # Validate generated SQL
    # ---------------------------------------------------------

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
            "requires_confirmation": False,
            "explanation": validation["reason"],
            "followups": [],
        }

    # ---------------------------------------------------------
    # EXTRA SAFETY
    # ---------------------------------------------------------

    if operation in {"update", "delete"}:

        if not re.search(
            r"\bWHERE\b",
            sql,
            flags=re.IGNORECASE,
        ):
            return {
                "generated_sql": sql,
                "result": {
                    "success": False,
                    "columns": [],
                    "rows": [],
                    "rows_returned": 0,
                },
                "chart": None,
                "diagram": None,
                "requires_confirmation": False,
                "explanation": (
                    f"For safety, {operation.upper()} requires "
                    "a WHERE condition."
                ),
                "followups": [],
            }

    # ---------------------------------------------------------
    # Preview DELETE / UPDATE
    # ---------------------------------------------------------

    preview_rows = []
    preview_columns = []

    if operation in {"delete", "update"}:

        match = re.search(
            r"^\s*(DELETE\s+FROM|UPDATE)\s+([A-Za-z_][A-Za-z0-9_]*)",
            sql,
            flags=re.IGNORECASE,
        )

        if match:

            preview_table = match.group(2)

            where_match = re.search(
                r"\bWHERE\b(.+)$",
                sql,
                flags=re.IGNORECASE | re.DOTALL,
            )

            if where_match:

                where_clause = where_match.group(1).strip()

                preview_sql = (
                    f"SELECT * FROM {preview_table} "
                    f"WHERE {where_clause}"
                )

                try:
                    preview = execute_query(preview_sql)

                    if preview["success"]:
                        preview_rows = preview["rows"]
                        preview_columns = preview["columns"]

                except Exception:
                    pass

    # ---------------------------------------------------------
    # Confirmation message
    # ---------------------------------------------------------

    dangerous = operation in {
        "drop",
        "alter",
        "truncate",
    }

    if dangerous:

        warning = {
            "drop": (
                f"This will permanently DROP the table "
                f"`{table}` and its data."
            ),
            "truncate": (
                f"This will permanently remove ALL rows "
                f"from `{table}`."
            ),
            "alter": (
                f"This will change the structure of "
                f"`{table}`."
            ),
        }.get(operation, "")

    else:

        warning = (
            f"This operation will modify `{table}`."
        )

    conversation_state[session_id] = {
        "pending_operation": operation,
        "pending_sql": sql,
        "pending_table": table,
    }

    return {
        "generated_sql": sql,
        "result": {
            "success": True,
            "columns": preview_columns,
            "rows": preview_rows,
            "rows_returned": len(preview_rows),
            "pending_confirmation": True,
            "operation": operation,
        },
        "chart": None,
        "diagram": None,
        "requires_confirmation": True,
        "dangerous": dangerous,
        "explanation": (
            f"### Confirm {operation.upper()}\n\n"
            f"{warning}\n\n"
            f"```sql\n{sql}\n```\n\n"
            "Please confirm before I apply this change."
        ),
        "followups": [],
    }


def _get_database_context() -> str:
    try:
        from app.database.database_context import get_database_profile

        profile = get_database_profile()

        if profile is None or not profile.analyzed:
            return ""

        return profile.to_context()

    except Exception:
        return ""


# =============================================================
# BG AI - UNIFIED CRUD SYSTEM
# =============================================================

def _handle_crud_operation(
    user_message: str,
    session_id: str,
    schema: dict,
    input_values: dict | None = None,
    pending_insert: bool = False,
) -> dict | None:
    from app.crud.router import handle_crud_request
    from app.database.database_manager import get_current_db_type

    return handle_crud_request(
        user_message=user_message,
        session_id=session_id,
        schema=schema,
        database_type=get_current_db_type(),
        input_values=input_values,
        pending_insert=pending_insert,
    )



# =============================================================
# OPERATION DETECTION
# =============================================================

def _detect_crud_operation(message: str) -> str | None:

    normalized = message.lower().strip()

    # DELETE
    delete_words = [
        "delete",
        "remove",
        "erase",
        "discard",
        "destroy record",
    ]

    if any(
        re.search(
            rf"\b{re.escape(word)}\b",
            normalized
        )
        for word in delete_words
    ):
        return "delete"

    # UPDATE
    update_words = [
        "update",
        "change",
        "modify",
        "edit",
        "set",
        "rename",
    ]

    if any(
        re.search(
            rf"\b{re.escape(word)}\b",
            normalized
        )
        for word in update_words
    ):
        return "update"

    # INSERT / CREATE RECORD
    insert_words = [
        "insert",
        "add",
        "create",
        "register",
        "new record",
        "add record",
    ]

    if any(
        re.search(
            rf"\b{re.escape(word)}\b",
            normalized
        )
        for word in insert_words
    ):
        return "insert"

    return None


# =============================================================
# TABLE RESOLUTION
# =============================================================

def _resolve_crud_table(
    user_message: str,
    schema: dict,
) -> str | None:

    if not schema:
        return None

    message = user_message.lower().strip()

    table_names = list(schema.keys())

    # =========================================================
    # 1. Exact table name
    # =========================================================

    for table in table_names:
        if re.search(
            rf"\b{re.escape(table.lower())}\b",
            message,
        ):
            return table

    # =========================================================
    # 2. Singular / plural
    # =========================================================

    for table in table_names:
        table_lower = table.lower()

        singular = (
            table_lower[:-1]
            if table_lower.endswith("s")
            else table_lower
        )

        if singular and re.search(
            rf"\b{re.escape(singular)}\b",
            message,
        ):
            return table

    # =========================================================
    # 3. Table with underscores
    # =========================================================

    for table in table_names:
        friendly = table.lower().replace("_", " ")

        if re.search(
            rf"\b{re.escape(friendly)}\b",
            message,
        ):
            return table

    # =========================================================
    # 4. Semantic table aliases
    # =========================================================

    aliases = {
        "customer": [
            "customer",
            "customers",
            "client",
            "clients",
        ],
        "student": [
            "student",
            "students",
            "learner",
            "learners",
        ],
        "employee": [
            "employee",
            "employees",
            "staff",
            "worker",
            "workers",
        ],
        "product": [
            "product",
            "products",
            "item",
            "items",
        ],
        "order": [
            "order",
            "orders",
            "purchase",
            "purchases",
        ],
    }

    for table in table_names:

        table_lower = table.lower()

        for group, words in aliases.items():

            if group not in table_lower:
                continue

            if any(
                re.search(
                    rf"\b{re.escape(word)}\b",
                    message,
                )
                for word in words
            ):
                return table

    # =========================================================
    # 5. IMPORTANT:
    # Infer table from columns used in the request.
    #
    # Example:
    # "update name of sanjay to sanjay s"
    #
    # If only customers contains "name", customers is selected.
    # =========================================================

    candidate_tables = []

    for table in table_names:

        columns = schema.get(table, {})

        if not isinstance(columns, dict):
            continue

        for column in columns.keys():

            column_lower = column.lower()
            friendly = column_lower.replace("_", " ")

            if re.search(
                rf"\b{re.escape(column_lower)}\b",
                message,
            ):
                candidate_tables.append(table)
                break

            if re.search(
                rf"\b{re.escape(friendly)}\b",
                message,
            ):
                candidate_tables.append(table)
                break

    candidate_tables = list(dict.fromkeys(candidate_tables))

    if len(candidate_tables) == 1:
        return candidate_tables[0]

    # =========================================================
    # 6. Fuzzy table matching
    # =========================================================

    words = re.findall(
        r"[a-zA-Z_][a-zA-Z0-9_]*",
        message,
    )

    for word in words:

        matches = get_close_matches(
            word.lower(),
            [t.lower() for t in table_names],
            n=1,
            cutoff=0.75,
        )

        if matches:

            matched = matches[0]

            for table in table_names:

                if table.lower() == matched:
                    return table

    return None


# =============================================================
# COLUMN RESOLUTION
# =============================================================

def _resolve_crud_column(
    value: str,
    columns: list[str],
) -> str | None:

    normalized = re.sub(
        r"[^a-z0-9]",
        "_",
        value.lower(),
    ).strip("_")

    if not normalized:
        return None

    # Exact
    for column in columns:

        if column.lower() == normalized:
            return column

    # Remove underscores
    compact = normalized.replace("_", "")

    for column in columns:

        if column.lower().replace("_", "") == compact:
            return column

    # Fuzzy
    matches = get_close_matches(
        normalized,
        [column.lower() for column in columns],
        n=1,
        cutoff=0.70,
    )

    if matches:

        for column in columns:

            if column.lower() == matches[0]:
                return column

    return None


# =============================================================
# IDENTIFIER QUOTING
# =============================================================

def _crud_quote_identifier(
    identifier: str,
) -> str:
    """
    Quote a database identifier using the ACTIVE SQLAlchemy dialect.

    MySQL      -> `table`
    PostgreSQL -> "table"
    SQLite     -> "table"
    """

    engine = get_engine()

    if engine is None:
        raise RuntimeError(
            "No database is currently connected."
        )

    return engine.dialect.identifier_preparer.quote(
        identifier
    )


# =============================================================
# VALUE QUOTING
# =============================================================

def _crud_quote_value(value) -> str:

    if value is None:
        return "NULL"

    if isinstance(value, bool):
        return "1" if value else "0"

    if isinstance(value, (int, float)):
        return str(value)

    text_value = str(value)

    escaped = text_value.replace(
        "'",
        "''",
    )

    return f"'{escaped}'"


# =============================================================
# REQUIRED INSERT FIELDS
# =============================================================

def _crud_required_insert_fields(
    table: str,
    schema: dict,
) -> list[str]:

    table_schema = schema.get(
        table,
        {},
    )

    required = []

    for column_name, metadata in table_schema.items():

        name = column_name.lower()

        # Ignore automatically generated fields
        if name in {
            "created_at",
            "updated_at",
            "deleted_at",
        }:
            continue

        # Primary key with default/generated value
        if metadata.get("primary_key"):

            default = metadata.get(
                "default"
            )

            if default is not None:
                continue

            column_type = str(
                metadata.get(
                    "type",
                    "",
                )
            ).lower()

            # Common auto-increment IDs
            if (
                "int" in column_type
                and name.endswith("id")
            ):
                continue

        nullable = metadata.get(
            "nullable",
            True,
        )

        default = metadata.get(
            "default"
        )

        if (
            not nullable
            and default is None
        ):
            required.append(column_name)

    return required


# =============================================================
# INSERT REQUEST
# =============================================================

def _handle_crud_insert_request(
    user_message: str,
    session_id: str,
    schema: dict,
) -> dict:

    table = _resolve_crud_table(
        user_message,
        schema,
    )

    if not table:

        return {
            "type": "input_request",
            "generated_sql": "",
            "result": {
                "success": True,
                "columns": [],
                "rows": [],
                "rows_returned": 0,
            },
            "input_request": {
                "type": "insert",
                "message": (
                    "Which table should I add the new record to?"
                ),
                "tables": list(schema.keys()),
            },
            "explanation": (
                "I could not determine the target table "
                "from your request."
            ),
            "followups": [],
        }

    table_schema = schema[table]

    fields = []

    required_fields = _crud_required_insert_fields(
        table,
        schema,
    )

    for column_name, metadata in table_schema.items():

        name = column_name.lower()

        if name in {
            "created_at",
            "updated_at",
            "deleted_at",
        }:
            continue

        if (
            metadata.get("primary_key")
            and metadata.get("default") is not None
        ):
            continue

        column_type = str(
            metadata.get(
                "type",
                "",
            )
        ).lower()

        field_type = "text"

        if "int" in column_type:
            field_type = "number"

        elif any(
            x in column_type
            for x in [
                "decimal",
                "numeric",
                "float",
                "double",
                "real",
            ]
        ):
            field_type = "number"

        elif "bool" in column_type:
            field_type = "boolean"

        elif any(
            x in column_type
            for x in [
                "date",
                "time",
            ]
        ):
            field_type = "date"

        if "email" in name:
            field_type = "email"

        fields.append({
            "name": column_name,
            "label": column_name.replace(
                "_",
                " ",
            ).title(),
            "type": field_type,
            "required": (
                column_name in required_fields
            ),
        })

    conversation_state[session_id] = {
        "pending_insert_table": table,
    }

    return {
        "type": "input_request",
        "generated_sql": "",
        "result": {
            "success": True,
            "columns": [],
            "rows": [],
            "rows_returned": 0,
        },
        "input_request": {
            "type": "insert",
            "table": table,
            "title": (
                f"Add record to "
                f"{table.replace('_', ' ').title()}"
            ),
            "message": (
                "Please provide the record details. "
                "Only fields that exist in the database "
                "will be accepted."
            ),
            "fields": fields,
        },
        "explanation": (
            f"I found the '{table}' table. "
            "Please provide the requested details."
        ),
        "followups": [],
    }


# =============================================================
# INSERT FORM PROCESSING
# =============================================================

def _handle_crud_insert_form(
    session_id: str,
    schema: dict,
    input_values: dict,
) -> dict:

    state = conversation_state.get(
        session_id,
        {},
    )

    table = state.get(
        "pending_insert_table"
    )

    if not table or table not in schema:

        conversation_state.pop(
            session_id,
            None,
        )

        return {
            "type": "error",
            "message": (
                "The insert session expired. "
                "Please start the add-record request again."
            ),
        }

    table_schema = schema[table]

    allowed_values = {}

    # ---------------------------------------------------------
    # Accept ONLY real columns
    # ---------------------------------------------------------

    for supplied_column, value in input_values.items():

        real_column = _resolve_crud_column(
            supplied_column,
            list(table_schema.keys()),
        )

        if not real_column:
            continue

        if value is None:
            continue

        if isinstance(value, str):

            value = value.strip()

            if not value:
                continue

        allowed_values[real_column] = value

    required_fields = _crud_required_insert_fields(
        table,
        schema,
    )

    missing = [
        field
        for field in required_fields
        if field not in allowed_values
    ]

    if missing:

        return {
            "type": "input_request",
            "message": (
                "Please provide all required fields."
            ),
            "table": table,
            "missing_fields": missing,
            "fields": _handle_crud_insert_request(
                user_message=f"add record to {table}",
                session_id=session_id,
                schema=schema,
            ).get(
                "input_request",
                {},
            ).get(
                "fields",
                [],
            ),
        }

    columns = list(
        allowed_values.keys()
    )

    values = [
        allowed_values[column]
        for column in columns
    ]

    quoted_columns = ", ".join(
        _crud_quote_identifier(column)
        for column in columns
    )

    quoted_values = ", ".join(
        _crud_quote_value(value)
        for value in values
    )

    sql = (
        f"INSERT INTO "
        f"{_crud_quote_identifier(table)} "
        f"({quoted_columns}) "
        f"VALUES ({quoted_values})"
    )

    validation = validate_sql(sql)

    if not validation.get("allowed"):

        return {
            "type": "error",
            "message": validation.get(
                "reason",
                "The INSERT operation was rejected.",
            ),
        }

    conversation_state[session_id][
        "pending_insert_sql"
    ] = sql

    return {
        "type": "confirmation",
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
        "operation": "insert",
        "table": table,
        "values": allowed_values,
        "explanation": (
            "The new record is ready. "
            "Please review and confirm before "
            "I modify the database."
        ),
        "followups": [],
    }


# =============================================================
# NATURAL-LANGUAGE WHERE EXTRACTION
# =============================================================

def _crud_extract_where(
    user_message: str,
    table: str,
    schema: dict,
) -> str | None:

    columns = list(
        schema.get(table, {}).keys()
    )

    if not columns:
        return None

    message = user_message.strip()

    # =========================================================
    # Helper
    # =========================================================

    def make_condition(column, value):

        value = str(value).strip()

        if not value:
            return None

        return (
            f"{_crud_quote_identifier(column)} "
            f"= "
            f"{_crud_quote_value(value)}"
        )

    # =========================================================
    # 1. column = value
    #
    # id = 10
    # name = sanjay
    # =========================================================

    for column in columns:

        friendly = column.replace("_", " ")

        patterns = [
            rf"\b{re.escape(column)}\s*"
            rf"(?:=|is|equals|equal to)\s*"
            rf"['\"]?([^,'\"]+)['\"]?",

            rf"\b{re.escape(friendly)}\s*"
            rf"(?:=|is|equals|equal to)\s*"
            rf"['\"]?([^,'\"]+)['\"]?",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                message,
                re.IGNORECASE,
            )

            if match:

                value = match.group(1).strip()

                condition = make_condition(
                    column,
                    value,
                )

                if condition:
                    return condition

    # =========================================================
    # 2. column value
    #
    # customer id 10
    # customer_id 10
    # =========================================================

    for column in columns:

        friendly = column.replace("_", " ")

        patterns = [
            rf"\b{re.escape(column)}\s+"
            rf"['\"]?([0-9]+|[^,\s]+)['\"]?",

            rf"\b{re.escape(friendly)}\s+"
            rf"['\"]?([0-9]+|[^,\s]+)['\"]?",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                message,
                re.IGNORECASE,
            )

            if match:

                value = match.group(1).strip()

                # Don't treat the update value as WHERE.
                # Only use this for phrases that clearly
                # identify a record.
                prefix = message[:match.start()].lower()

                if any(
                    word in prefix
                    for word in [
                        "delete",
                        "remove",
                        "erase",
                        "where",
                        "with",
                        "customer",
                        "student",
                        "employee",
                        "record",
                    ]
                ):

                    condition = make_condition(
                        column,
                        value,
                    )

                    if condition:
                        return condition

    # =========================================================
    # 3. with id 10
    # with customer_id 10
    # =========================================================

    match = re.search(
        r"\bwith\s+"
        r"([a-zA-Z_][a-zA-Z0-9_]*)"
        r"\s*(?:=|is|equals|equal to)?\s*"
        r"['\"]?([^,'\"]+)['\"]?",
        message,
        re.IGNORECASE,
    )

    if match:

        requested_column = match.group(1)
        value = match.group(2).strip()

        column = _resolve_crud_column(
            requested_column,
            columns,
        )

        if column:
            return make_condition(
                column,
                value,
            )

    # =========================================================
    # 4. "of sanjay"
    #
    # update name of sanjay to sanjay s
    #
    # We interpret:
    #
    # SET name = sanjay s
    # WHERE name = sanjay
    #
    # only when the same column is clearly involved.
    # =========================================================

    of_pattern = re.search(
        r"\b([a-zA-Z_][a-zA-Z0-9_]*)"
        r"\s+of\s+"
        r"['\"]?([^'\"]+?)['\"]?"
        r"\s+(?:to|as|=)\s+",
        message,
        re.IGNORECASE,
    )

    if of_pattern:

        requested_column = of_pattern.group(1)
        old_value = of_pattern.group(2).strip()

        column = _resolve_crud_column(
            requested_column,
            columns,
        )

        if column and old_value:

            return make_condition(
                column,
                old_value,
            )

    # =========================================================
    # 5. "where name sanjay"
    # =========================================================

    where_match = re.search(
        r"\bwhere\s+"
        r"([a-zA-Z_][a-zA-Z0-9_]*)"
        r"\s*(?:=|is|equals|equal to)?\s*"
        r"['\"]?([^,'\"]+)['\"]?",
        message,
        re.IGNORECASE,
    )

    if where_match:

        requested_column = where_match.group(1)
        value = where_match.group(2).strip()

        column = _resolve_crud_column(
            requested_column,
            columns,
        )

        if column:
            return make_condition(
                column,
                value,
            )

    return None


# =============================================================
# UPDATE FIELD EXTRACTION
# =============================================================

def _crud_extract_update_values(
    user_message: str,
    table: str,
    schema: dict,
) -> dict:

    columns = list(
        schema.get(table, {}).keys()
    )

    values = {}

    # =========================================================
    # 1. Standard:
    #
    # name to Arun
    # name = Arun
    # name as Arun
    # =========================================================

    for column in columns:

        friendly = column.replace("_", " ")

        patterns = [
            rf"\b{re.escape(column)}\s*"
            rf"(?:=|to|as)\s*"
            rf"['\"]?([^,]+?)['\"]?"
            rf"(?=\s+and\s+|\s*,|$)",

            rf"\b{re.escape(friendly)}\s*"
            rf"(?:=|to|as)\s*"
            rf"['\"]?([^,]+?)['\"]?"
            rf"(?=\s+and\s+|\s*,|$)",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                user_message,
                re.IGNORECASE,
            )

            if match:

                value = match.group(1).strip()

                value = re.sub(
                    r"\s+(where|for|with)\s*$",
                    "",
                    value,
                    flags=re.IGNORECASE,
                )

                if value:
                    values[column] = value
                    break

    # =========================================================
    # 2. Special:
    #
    # update name of sanjay to sanjay s
    #
    # Extract:
    # name -> sanjay s
    # =========================================================

    special = re.search(
        r"\b([a-zA-Z_][a-zA-Z0-9_]*)"
        r"\s+of\s+"
        r"['\"]?[^'\"]+?['\"]?"
        r"\s+(?:to|as|=)\s+"
        r"['\"]?(.+?)['\"]?"
        r"\s*$",
        user_message,
        re.IGNORECASE,
    )

    if special:

        requested_column = special.group(1)
        new_value = special.group(2).strip()

        column = _resolve_crud_column(
            requested_column,
            columns,
        )

        if column and new_value:
            values[column] = new_value

    return values


# =============================================================
# UPDATE REQUEST
# =============================================================

# =============================================================
# NATURAL-LANGUAGE UPDATE PARSER
# =============================================================

def _crud_extract_natural_update(
    user_message: str,
    table: str,
    schema: dict,
) -> dict | None:
    """
    Understand natural-language updates such as:

        update the customer sanjay to sanjays
        change customer sanjay to sanjays
        update the student arun to arun kumar
        change employee john to john smith

    Returns:
        {
            "where_column": "name",
            "where_value": "sanjay",
            "updates": {
                "name": "sanjays"
            }
        }

    Only works when the table has a suitable text column,
    normally 'name', 'full_name', etc.
    """

    columns = list(
        schema.get(table, {}).keys()
    )

    if not columns:
        return None

    message = user_message.strip()

    # ---------------------------------------------------------
    # Match:
    #
    # update the customer sanjay to sanjays
    #
    # change customer sanjay to sanjays
    # ---------------------------------------------------------

    pattern = re.compile(
        r"^\s*"
        r"(?:update|change|modify|edit|rename)"
        r"\s+(?:the\s+)?"
        r"(?P<table_word>[a-zA-Z_][a-zA-Z0-9_\s-]*)?"
        r"\s*"
        r"(?P<old>[^,\s]+)"
        r"\s+"
        r"(?:to|as)"
        r"\s+"
        r"(?P<new>.+?)"
        r"\s*$",
        re.IGNORECASE,
    )

    match = pattern.match(message)

    if not match:
        return None

    old_value = match.group("old").strip()
    new_value = match.group("new").strip()

    if not old_value or not new_value:
        return None

    # Remove quotes
    old_value = old_value.strip("'\"")
    new_value = new_value.strip("'\"")

    # ---------------------------------------------------------
    # Find a suitable name column
    # ---------------------------------------------------------

    preferred_columns = [
        "name",
        "full_name",
        "customer_name",
        "student_name",
        "employee_name",
        "product_name",
        "username",
        "display_name",
    ]

    where_column = None

    # Exact preferred column
    for preferred in preferred_columns:
        for column in columns:
            if column.lower() == preferred:
                where_column = column
                break

        if where_column:
            break

    # ---------------------------------------------------------
    # If there is no standard name column, find a text column.
    # ---------------------------------------------------------

    if where_column is None:

        for column in columns:

            column_info = schema.get(table, {}).get(
                column,
                {},
            )

            column_type = str(
                column_info.get("type", "")
            ).lower()

            if any(
                text_type in column_type
                for text_type in [
                    "char",
                    "text",
                    "varchar",
                    "string",
                ]
            ):

                if not column_info.get(
                    "primary_key",
                    False,
                ):
                    where_column = column
                    break

    if where_column is None:
        return None

    return {
        "where_column": where_column,
        "where_value": old_value,
        "updates": {
            where_column: new_value,
        },
    }


# =============================================================
# NATURAL-LANGUAGE UPDATE PARSER
# =============================================================

def _crud_extract_natural_update(
    user_message: str,
    table: str,
    schema: dict,
) -> dict | None:
    """
    Understand natural-language updates such as:

        update the customer sanjay to sanjays
        change customer sanjay to sanjays
        update the student arun to arun kumar
        change employee john to john smith

    Returns:
        {
            "where_column": "name",
            "where_value": "sanjay",
            "updates": {
                "name": "sanjays"
            }
        }

    Only works when the table has a suitable text column,
    normally 'name', 'full_name', etc.
    """

    columns = list(
        schema.get(table, {}).keys()
    )

    if not columns:
        return None

    message = user_message.strip()

    # ---------------------------------------------------------
    # Match:
    #
    # update the customer sanjay to sanjays
    #
    # change customer sanjay to sanjays
    # ---------------------------------------------------------

    pattern = re.compile(
        r"^\s*"
        r"(?:update|change|modify|edit|rename)"
        r"\s+(?:the\s+)?"
        r"(?P<table_word>[a-zA-Z_][a-zA-Z0-9_\s-]*)?"
        r"\s*"
        r"(?P<old>[^,\s]+)"
        r"\s+"
        r"(?:to|as)"
        r"\s+"
        r"(?P<new>.+?)"
        r"\s*$",
        re.IGNORECASE,
    )

    match = pattern.match(message)

    if not match:
        return None

    old_value = match.group("old").strip()
    new_value = match.group("new").strip()

    if not old_value or not new_value:
        return None

    # Remove quotes
    old_value = old_value.strip("'\"")
    new_value = new_value.strip("'\"")

    # ---------------------------------------------------------
    # Find a suitable name column
    # ---------------------------------------------------------

    preferred_columns = [
        "name",
        "full_name",
        "customer_name",
        "student_name",
        "employee_name",
        "product_name",
        "username",
        "display_name",
    ]

    where_column = None

    # Exact preferred column
    for preferred in preferred_columns:
        for column in columns:
            if column.lower() == preferred:
                where_column = column
                break

        if where_column:
            break

    # ---------------------------------------------------------
    # If there is no standard name column, find a text column.
    # ---------------------------------------------------------

    if where_column is None:

        for column in columns:

            column_info = schema.get(table, {}).get(
                column,
                {},
            )

            column_type = str(
                column_info.get("type", "")
            ).lower()

            if any(
                text_type in column_type
                for text_type in [
                    "char",
                    "text",
                    "varchar",
                    "string",
                ]
            ):

                if not column_info.get(
                    "primary_key",
                    False,
                ):
                    where_column = column
                    break

    if where_column is None:
        return None

    return {
        "where_column": where_column,
        "where_value": old_value,
        "updates": {
            where_column: new_value,
        },
    }


# =============================================================
# UPDATE REQUEST
# =============================================================

def _handle_crud_update_request(
    user_message: str,
    session_id: str,
    schema: dict,
) -> dict:

    table = _resolve_crud_table(
        user_message,
        schema,
    )

    if not table:

        return {
            "type": "error",
            "message": (
                "I could not determine which table "
                "you want to update."
            ),
            "requires_confirmation": False,
        }

    # ---------------------------------------------------------
    # Try natural-language update first
    # ---------------------------------------------------------

    natural_update = _crud_extract_natural_update(
        user_message=user_message,
        table=table,
        schema=schema,
    )

    if natural_update:

        where_column = natural_update[
            "where_column"
        ]

        where_value = natural_update[
            "where_value"
        ]

        update_values = natural_update[
            "updates"
        ]

        where_clause = (
            f"{_crud_quote_identifier(where_column)} "
            f"= "
            f"{_crud_quote_value(where_value)}"
        )

    else:

        # -----------------------------------------------------
        # Existing explicit WHERE parser
        # -----------------------------------------------------

        where_clause = _crud_extract_where(
            user_message=user_message,
            table=table,
            schema=schema,
        )

        if not where_clause:

            return {
                "type": "error",
                "message": (
                    "For safety, UPDATE requires a "
                    "WHERE condition identifying the "
                    "record(s) you want to change."
                ),
                "requires_confirmation": False,
            }

        update_values = (
            _crud_extract_update_values(
                user_message=user_message,
                table=table,
                schema=schema,
            )
        )

    # ---------------------------------------------------------
    # Validate update fields
    # ---------------------------------------------------------

    real_columns = set(
        schema.get(table, {}).keys()
    )

    update_values = {
        column: value
        for column, value in update_values.items()
        if column in real_columns
    }

    if not update_values:

        return {
            "type": "error",
            "message": (
                "I understood which record you want "
                "to update, but I could not determine "
                "which field should be changed."
            ),
            "requires_confirmation": False,
        }

    # ---------------------------------------------------------
    # Never update primary key
    # ---------------------------------------------------------

    primary_keys = {
        column
        for column, info
        in schema.get(table, {}).items()
        if info.get("primary_key")
    }

    for column in update_values:

        if column in primary_keys:

            return {
                "type": "error",
                "message": (
                    f"I cannot modify the primary key "
                    f"'{column}' through this operation."
                ),
                "requires_confirmation": False,
            }

    # ---------------------------------------------------------
    # Preview affected records
    # ---------------------------------------------------------

    preview_sql = (
        f"SELECT * FROM "
        f"{_crud_quote_identifier(table)} "
        f"WHERE {where_clause}"
    )

    preview_result = execute_query(
        preview_sql
    )

    if not preview_result.get("success"):

        return {
            "type": "error",
            "message": (
                preview_result.get(
                    "error"
                )
                or "Could not find the matching record."
            ),
            "requires_confirmation": False,
        }

    rows = preview_result.get(
        "rows",
        [],
    )

    if not rows:

        return {
            "type": "error",
            "message": (
                "I could not find any record in "
                f"'{table}' matching the specified condition."
            ),
            "requires_confirmation": False,
        }

    # ---------------------------------------------------------
    # Build UPDATE
    # ---------------------------------------------------------

    set_parts = []

    for column, value in update_values.items():

        set_parts.append(
            f"{_crud_quote_identifier(column)} = "
            f"{_crud_quote_value(value)}"
        )

    sql = (
        f"UPDATE "
        f"{_crud_quote_identifier(table)} "
        f"SET "
        f"{', '.join(set_parts)} "
        f"WHERE {where_clause}"
    )

    # ---------------------------------------------------------
    # Validate SQL
    # ---------------------------------------------------------

    validation = validate_sql(
        sql
    )

    if not validation.get("allowed"):

        return {
            "type": "error",
            "message": validation.get(
                "reason",
                "The update was rejected.",
            ),
            "requires_confirmation": False,
        }

    # ---------------------------------------------------------
    # Store pending operation
    # ---------------------------------------------------------

    conversation_state[
        session_id
    ] = {
        "pending_sql": sql,
        "operation": "update",
        "table": table,
        "preview_rows": rows,
        "where_column": where_column,
        "where_value": where_value,
        "update_values": update_values,
    }

    # ---------------------------------------------------------
    # Confirmation response
    # ---------------------------------------------------------

    return {
        "type": "confirmation",
        "operation": "update",
        "table": table,

        "generated_sql": sql,
        "sql": sql,

        "result": {
            "success": True,
            "columns": (
                list(rows[0].keys())
                if rows
                and isinstance(rows[0], dict)
                else []
            ),
            "rows": rows,
            "rows_returned": len(rows),
            "pending_confirmation": True,
            "operation": "update",
        },

        "requires_confirmation": True,

        "affected_rows_preview": len(rows),

        "explanation": (
            f"I found {len(rows)} matching "
            f"record(s) in '{table}'. "
            "Review the proposed UPDATE and "
            "confirm before making the change."
        ),

        "before_rows": rows,

        "proposed_changes": update_values,

        "followups": [],
    }


# =============================================================
# DELETE REQUEST
# =============================================================

def _handle_crud_delete_request(
    user_message: str,
    session_id: str,
    schema: dict,
) -> dict:

    table = _resolve_crud_table(
        user_message,
        schema,
    )

    if not table:

        return {
            "type": "error",
            "message": (
                "I could not determine which table "
                "you want to delete from."
            ),
        }

    where = _crud_extract_where(
        user_message,
        table,
        schema,
    )

    if not where:

        return {
            "type": "error",
            "message": (
                "For safety, DELETE requires a WHERE "
                "condition identifying the record(s) "
                "you want to remove."
            ),
        }

    # ---------------------------------------------------------
    # Preview record
    # ---------------------------------------------------------

    preview_sql = (
        f"SELECT * FROM "
        f"{_crud_quote_identifier(table)} "
        f"WHERE {where}"
    )

    preview = execute_query(
        preview_sql
    )

    if not preview.get("success"):

        return {
            "type": "error",
            "message": (
                "I could not check the record "
                "before deletion."
            ),
            "technical_details": preview.get(
                "error",
                "",
            ),
        }

    rows = preview.get(
        "rows",
        [],
    )

    if not rows:

        return {
            "type": "error",
            "message": (
                "No matching record was found. "
                "Nothing was deleted."
            ),
        }

    sql = (
        f"DELETE FROM "
        f"{_crud_quote_identifier(table)} "
        f"WHERE {where}"
    )

    validation = validate_sql(
        sql
    )

    if not validation.get("allowed"):

        return {
            "type": "error",
            "message": validation.get(
                "reason",
                "The DELETE operation was rejected.",
            ),
        }

    conversation_state[session_id] = {
        "pending_sql": sql,
        "operation": "delete",
        "table": table,
    }

    return {
        "type": "confirmation",
        "generated_sql": sql,
        "sql": sql,
        "result": {
            "success": True,
            "columns": list(
                rows[0].keys()
            ) if rows else [],
            "rows": rows,
            "rows_returned": len(rows),
            "pending_confirmation": True,
            "operation": "delete",
        },
        "requires_confirmation": True,
        "operation": "delete",
        "table": table,
        "affected_rows_preview": len(rows),
        "explanation": (
            f"I found {len(rows)} matching record(s). "
            "Review the proposed DELETE and confirm "
            "before removing anything."
        ),
        "followups": [],
    }


def run_agent(
    user_message: str,
    session_id: str = "default",
    input_values: dict | None = None,
    pending_insert: bool = False,
):
    try:
        schema = get_schema()
    except Exception:
        schema = None

    if schema is None:
        return _handle_no_database_request(user_message)

    if not schema:
        msg_clean = user_message.lower().strip()
        greetings = {"hi", "hello", "hey", "hii", "heyy", "good morning", "good afternoon", "good evening", "howdy", "sup"}
        if msg_clean in greetings or re.match(r"^(hi|hello|hey|greetings|good morning|good afternoon|good evening)[!.\s]*$", msg_clean):
            return _handle_no_database_request(user_message)

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
                "No usable tables were found in the currently "
                "connected database."
            ),
            "followups": [],
        }

    # ---------------------------------------------------------
    # DATABASE STRUCTURE REQUEST
    # ---------------------------------------------------------
    # Handle locally. Do NOT ask the LLM to generate
    # information_schema queries.
    # ---------------------------------------------------------

    if _is_schema_request(user_message):

        conversation_state.pop(session_id, None)

        schema_rows = []

        for table_name, columns in schema.items():

            for column_name, metadata in columns.items():

                schema_rows.append({
                    "table_name": table_name,
                    "column_name": column_name,
                    "data_type": metadata.get("type", ""),
                    "nullable": metadata.get("nullable", True),
                    "primary_key": metadata.get(
                        "primary_key",
                        False
                    ),
                })

        return {
            "generated_sql": "",
            "result": {
                "success": True,
                "columns": [
                    "table_name",
                    "column_name",
                    "data_type",
                    "nullable",
                    "primary_key",
                ],
                "rows": schema_rows,
                "execution_time_ms": 0,
                "rows_returned": len(schema_rows),
            },
            "chart": None,
            "diagram": None,
            "analytics": None,
            "explanation": (
                "Here is the structure of your connected database."
            ),
            "followups": _get_followups(user_message),
        }

    # =========================================================
    # BG AI CRUD ROUTER
    #
    # IMPORTANT:
    # CRUD requests are handled BEFORE AI intent
    # classification. Otherwise the LLM may classify a
    # DELETE/UPDATE/INSERT request as normal chat.
    # =========================================================

    crud_result = _handle_crud_operation(
        user_message=user_message,
        session_id=session_id,
        schema=schema,
        input_values=input_values,
        pending_insert=pending_insert,
    )

    if crud_result is not None:
        return crud_result

    database_context = _get_database_context()

    intent = _classify_intent(
        user_message,
        schema
    )

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
        # Generic SQL path: only for SELECT / READ operations.
        # INSERT / UPDATE / DELETE must be handled above.
        # ---------------------------------------------------------
        compact_schema = _build_compact_schema(schema)

        database_context = _get_database_context()

        if not database_context:
            database_context = "No additional database profile is available."

        db_type = get_current_db_type()

        dialect_instructions = {
            "mysql": """
- Generate MySQL-compatible SQL.
- Use backticks for table and column identifiers when quoting is needed.
- Example: SELECT * FROM `customers` LIMIT 100
- NEVER use double quotes around MySQL identifiers.
""",
            "postgres": """
- Generate PostgreSQL-compatible SQL.
- Use double quotes for identifiers when quoting is needed.
- Example: SELECT * FROM "customers" LIMIT 100
""",
            "sqlite": """
- Generate SQLite-compatible SQL.
- Use double quotes for identifiers when quoting is needed.
- Example: SELECT * FROM "customers" LIMIT 100
""",
        }.get(
            db_type,
            """
- Generate SQL compatible with the currently connected database.
""",
        )

        prompt = f"""
You are BG AI, an intelligent database assistant.

Your job is to understand the user's natural-language request
and generate SQL ONLY when the request requires database data.

IMPORTANT:
- The connected database may belong to ANY domain.
- Never assume the database is ecommerce.
- Never assume tables such as customers, products, orders, students,
  employees, patients, etc.
- Use ONLY tables and columns that exist in the LIVE DATABASE SCHEMA.
- Correct obvious spelling mistakes in the user's request.
- Match natural-language terms to the closest real table/column.
- Never invent a table.
- Never invent a column.
- Never invent a value.
- If the request is ambiguous, ask for clarification instead of guessing.

LIVE DATABASE SCHEMA:
{compact_schema}

DATABASE INTELLIGENCE PROFILE:
{database_context}

DATABASE DIALECT:
{db_type}

DIALECT RULES:
{dialect_instructions}

USER REQUEST:
{user_message}

SQL RULES:
1. Generate one SQL statement only.
2. For read requests, generate SELECT SQL.
3. Never use INSERT, UPDATE, or DELETE here.
4. Use the actual table and column names from the live schema.
5. Respect relationships between tables when joins are required.
6. Do not use columns that do not exist.
7. Use the SQL syntax of the active database dialect.
8. Return SQL only.
"""

        try:
            raw_sql = ask_groq(prompt).strip()

            print("\n========== BG AI SQL ==========")
            print("USER:", user_message)
            print("RAW :", raw_sql)

            sql = _clean_generated_sql(raw_sql)

            sql = _normalize_sql_for_active_database(
                sql
            )

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

        # ---------------------------------------------------------
        # No SQL statement was produced.
        #
        # The model replied in prose (normally asking for
        # clarification). Never pass that prose to the validator:
        # its first word would be reported as an unsupported
        # "operation".
        #
        # Write requests are handled deterministically before this
        # point, so reaching here means the request was a read
        # request the model could not translate.
        # ---------------------------------------------------------
        if not sql:
            return {
                "generated_sql": "",
                "result": {
                    "success": False,
                    "columns": [],
                    "rows": [],
                    "rows_returned": 0,
                    "error": (
                        "I could not turn that request into a "
                        "database query."
                    ),
                },
                "chart": None,
                "diagram": None,
                "analytics": None,
                "input_request": None,
                "explanation": (
                    "I couldn't turn that into a database query.\n\n"
                    "**To read data, try:**\n"
                    "• *show all customers*\n\n"
                    "**To change data, try:**\n"
                    "• *add a new customer*\n"
                    "• *update customer 1 city to Salem*\n"
                    "• *delete customer 3*"
                ),
                "followups": _get_followups(user_message),
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
            f"INSERT INTO "
            f"{_crud_quote_identifier(table)} "
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
                f"{_crud_quote_identifier(key)} = {_quote(value)}"
            )

        return (
            f"UPDATE "
            f"{_crud_quote_identifier(table)} "
            f"SET {', '.join(set_parts)} "
            f"WHERE {where}"
        )

    if operation == "delete":

        if not where:
            raise ValueError(
                "DELETE requires a WHERE condition."
            )

        return (
            f"DELETE FROM "
            f"{_crud_quote_identifier(table)} "
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
