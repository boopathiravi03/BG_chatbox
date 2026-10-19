from __future__ import annotations

from typing import Any

from app.agent.groq_agent import ask_groq


def parse_crud_intent(
    user_message: str,
    schema: dict,
    database_type: str = "unknown",
    target_table: Optional[str] = None,
) -> dict | None:
    """
    Use the LLM to turn natural language into a structured
    CRUD intent, then validate every field against the live schema.

    This is the two-stage parser:

    natural language -> LLM structured intent -> schema validation
    """

    if not schema:
        return None

    # Focus schema on target table if known, or tables mentioned in message
    if target_table and target_table in schema and isinstance(schema[target_table], dict):
        schema_description = f"- {target_table}: {', '.join(schema[target_table].keys())}"
    else:
        msg_lower = user_message.lower()
        matching_tables = [
            t for t in schema.keys()
            if t.lower() in msg_lower or t.lower()[:-1] in msg_lower
        ]
        subset = {t: schema[t] for t in matching_tables} if matching_tables else schema
        schema_description = "\n".join(
            f"- {table}: {', '.join(columns.keys())}"
            for table, columns in subset.items()
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
  "conditions": [
    {{
      "column": "column_name",
      "operator": "=|!=|>|>=|<|<=|like|ilike|is null|is not null",
      "value": "value_or_null"
    }}
  ],
  "match": {{
    "column": "primary_condition_column_or_null",
    "value": "primary_condition_value_or_null"
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
- Support single and compound conditions. If the user specifies multiple filters (e.g. "customers in Chennai whose status is pending"), return all of them in the "conditions" array joined by AND.
- For NULL checks (e.g. "where email is empty/null"), use operator "is null" or "is not null" with value null.
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
        raw_conditions = data.get("conditions") or []
        match = data.get("match") or {}
        changes = data.get("changes") or {}

        if table and table not in schema:
            return None

        validated_conditions = []
        if isinstance(raw_conditions, list):
            for cond in raw_conditions:
                if isinstance(cond, dict) and cond.get("column"):
                    validated_conditions.append({
                        "column": str(cond.get("column", "")).strip(),
                        "operator": str(cond.get("operator", "=")).strip(),
                        "value": cond.get("value"),
                    })

        # Backward compatibility with single match
        if not validated_conditions and match.get("column"):
            validated_conditions.append({
                "column": str(match.get("column", "")).strip(),
                "operator": "=",
                "value": match.get("value"),
            })

        validated: dict[str, Any] = {
            "operation": operation,
            "table": table,
            "conditions": validated_conditions,
            "match": {
                "column": str(match.get("column", "")).strip() or (validated_conditions[0]["column"] if validated_conditions else None),
                "value": match.get("value") if match.get("column") else (validated_conditions[0]["value"] if validated_conditions else None),
            },
            "changes": {
                str(key).strip(): str(value).strip() if value is not None else None
                for key, value in changes.items()
                if isinstance(key, str)
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

            # Filter conditions to valid columns
            validated["conditions"] = [
                c for c in validated["conditions"]
                if c["column"] in valid_columns
            ]

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
