from app.agent.groq_agent import ask_groq
from app.tools.get_schema import get_schema
from app.tools.execute_query import execute_query
from app.tools.explain_data import explain_data
from app.tools.generate_chart import generate_chart
from app.tools.generate_flowchart import generate_flowchart
from app.tools.get_relationship_graph import get_relationship_graph
from app.tools.dashboard_data import get_dashboard_data as get_analytics_data
import json
import re


def _get_followups(user_message: str) -> list[str]:
    message = user_message.lower()
    if any(x in message for x in ["customer", "customers"]):
        return [
            "Show customer orders",
            "Top customers",
            "Customer locations",
            "Customer revenue",
        ]
    if any(x in message for x in ["product", "products"]):
        return [
            "Low stock products",
            "Most sold products",
            "Product categories",
            "Product prices",
        ]
    if any(x in message for x in ["order", "orders"]):
        return [
            "Pending orders",
            "Delivered orders",
            "Orders by month",
            "Top customers",
        ]
    if any(x in message for x in ["sales", "revenue", "chart"]):
        return [
            "Revenue chart",
            "Sales trend",
            "Highest sales month",
            "Download sales report",
        ]
    if any(x in message for x in ["er diagram", "flowchart", "schema"]):
        return [
            "Relationship Graph",
            "Database Schema",
            "Show Tables",
            "Analytics Dashboard",
        ]
    return [
        "Show all customers",
        "Monthly sales",
        "Revenue chart",
        "ER Diagram",
    ]


def _classify_intent(user_message: str) -> str:
    prompt = f"""You are an intent classifier for a database assistant.

Classify the user message into ONE category only.

Categories:
- chat: greetings, general questions, small talk, questions about the assistant itself, or anything not related to database operations
- sql: direct database queries like "show customers", "list orders", "find products"
- chart: requests for charts, graphs, visualizations like "revenue chart", "sales graph"
- dashboard: requests for analytics dashboard, business insights, overview
- relationship_graph: requests to visualize table relationships, schema connections
- er_diagram: requests for ER diagram, entity relationship diagram, schema diagram
- analytics: requests for analytics, metrics, statistics

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
    prompt = f"""You are BG AI, a friendly AI database assistant.

You are having a conversation with the user. Answer naturally and helpfully.

If the user asks about yourself, explain that you are BG AI, an AI-powered database assistant that can help with SQL queries, data analysis, charts, dashboards, and database visualization.

If the user asks general questions, answer them naturally.

Do NOT generate SQL unless the user explicitly asks for data from the database.

User: {user_message}
"""

    try:
        explanation = ask_groq(prompt).strip()
    except Exception:
        explanation = "Hello! 👋 I'm BG AI. How can I help you with your database today?"

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


def run_agent(user_message: str):
    """
    Main AI Agent with Groq-based intent classification
    """
    intent = _classify_intent(user_message)

    if intent == "chat":
        return _handle_chat(user_message)

    if intent == "er_diagram":
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

    schema = get_schema()

    prompt = f"""
You are an AI SQL assistant.

Database Schema:
{schema}

User Question:
{user_message}

Generate ONLY a valid SQLite SQL query.
Do not explain.
Do NOT wrap the SQL in code fences or markdown.
Output must be raw SQL only.
"""

    raw_sql = ask_groq(prompt).strip()

    sql = raw_sql
    if "```" in sql:
        sql = sql.split("```", 1)[1]
        sql = sql.split("```", 1)[0]
        sql = sql.replace("sql", "", 1).strip()

    result = execute_query(sql)

    chart = None
    if intent == "chart":
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
