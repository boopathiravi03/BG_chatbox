from __future__ import annotations

from typing import Any

from app.agent.groq_agent import ask_groq


def parse_crud_intent(
    user_message: str,
    schema: dict,
    database_type: str = "unknown",
) -> dict | None:
    """
    Use the LLM to turn natural language into a structured
    CRUD intent, then validate every field against the live schema.

    This is the two-stage parser:

    natural language -> LLM structured intent -> schema validation
    """

    if not schema:
        return None

    schema_description = "\n".join(
        f"- {table}: {', '.join(columns.keys())}"
        for table, columns in schema.items()
        if isinstance(columns, dict)
    )

    prompt = f"""
You are BG AI's CRUD intent parser.

DATABASE TYPE: {database_type}

LIVE DATABASE SCHEMA:
{schema_description}

USER REQUEST:
{user_message}

Return ONLY JSON in this exact shape:

{{
  "operation": "create|read|update|delete|null",
  "table": "exact_table_name_or_null",
  "match": {{
    "column": "column_name_or_null",
    "value": "value_or_null"
  }},
  "changes": {{
    "column_name": "new_value"
  }},
  "confidence": "high|medium|low",
  "ambiguities": [
    "description of any ambiguity"
  ]
}}

Rules:
- NEVER invent a table or column.
- Use ONLY tables and columns from the LIVE DATABASE SCHEMA above.
- If the request does not map cleanly to one table/column, set operation to "null" and explain in ambiguities.
- For read requests, use operation "read".
- For INSERT/ADD/CREATE record requests, use operation "create".
- For UPDATE/CHANGE/MODIFY, use operation "update".
- For DELETE/REMOVE, use operation "delete".
- For requests that affect multiple possible tables or columns, prefer "null" and describe the ambiguity.
- If no table or column is clearly identifiable, return operation "null".
- Return JSON ONLY. No markdown. No explanation outside the JSON.
"""

    try:
        raw = ask_groq(prompt).strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        import json
        data = json.loads(raw)

        operation = str(data.get("operation", "")).strip().lower()

        if operation not in {"create", "read", "update", "delete"}:
            return None

        table = str(data.get("table", "")).strip() or None
        match = data.get("match") or {}
        changes = data.get("changes") or {}

        if table and table not in schema:
            return None

        validated: dict[str, Any] = {
            "operation": operation,
            "table": table,
            "match": {
                "column": str(match.get("column", "")).strip() or None,
                "value": str(match.get("value", "")).strip() or None,
            },
            "changes": {
                str(key).strip(): str(value).strip()
                for key, value in changes.items()
                if isinstance(key, str)
                and isinstance(value, str)
            },
            "confidence": str(data.get("confidence", "medium")).strip().lower(),
            "ambiguities": [
                str(item).strip()
                for item in (data.get("ambiguities") or [])
                if isinstance(item, str)
                and str(item).strip()
            ],
        }

        if validated["table"]:
            valid_columns = set(schema.get(validated["table"], {}).keys())

            if validated["match"].get("column") not in valid_columns:
                validated["match"]["column"] = None

            validated["changes"] = {
                key: value
                for key, value in validated["changes"].items()
                if key in valid_columns
            }

        if validated.get("confidence") == "low":
            return None

        if validated.get("ambiguities"):
            return None

        return validated

    except Exception:
        return None
