from app.agent.groq_agent import ask_groq
from app.tools.get_schema import get_schema
from app.tools.execute_query import execute_query
from app.tools.explain_data import explain_data
from app.tools.generate_chart import generate_chart
from app.tools.generate_flowchart import generate_flowchart
from app.tools.get_relationship_graph import get_relationship_graph
from app.tools.dashboard_data import get_dashboard_data as get_analytics_data


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


def run_agent(user_message: str):
    """
    Main AI Agent
    """

    message = user_message.lower()

    if any(x in message for x in [
        "er diagram",
        "flowchart",
        "schema diagram",
    ]):
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

    if any(x in message for x in [
        "relationship graph",
        "er graph",
        "database relationships",
        "visualize schema",
        "visualize my database",
        "show table connections",
        "table relationship",
    ]):
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

    if any(x in message for x in [
        "open analytics dashboard",
        "show analytics",
        "show dashboard",
        "dashboard",
        "business insights",
        "sales dashboard",
    ]):
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

    chart = generate_chart(user_message, result)

    explanation = explain_data(user_message, result)

    return {
        "generated_sql": sql,
        "result": result,
        "chart": chart,
        "diagram": None,
        "explanation": explanation,
        "followups": _get_followups(user_message),
    }
