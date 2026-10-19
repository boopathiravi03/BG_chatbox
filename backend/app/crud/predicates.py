from __future__ import annotations

import re
from typing import Any, List, Optional, Tuple
from app.crud.matcher import quote_identifier

ALLOWED_OPERATORS = {
    "=": "=",
    "==": "=",
    "!=": "!=",
    "<>": "!=",
    ">": ">",
    ">=": ">=",
    "<": "<",
    "<=": "<=",
    "like": "LIKE",
    "ilike": "ILIKE",
    "is null": "IS NULL",
    "is not null": "IS NOT NULL",
}


def quote_value(value: Any) -> str:
    """
    Safely convert a Python value to an escaped SQL literal.
    - None -> NULL
    - bool -> 1 / 0
    - int/float -> numeric representation
    - text -> escaped single-quoted string
    """
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def normalize_condition(cond: Any) -> Optional[dict[str, Any]]:
    """
    Normalizes varied condition representations into a standard dictionary:
    {"column": str, "operator": str, "value": Any}
    Supports:
    - dict with keys: column/col, operator/op, value/val
    - tuple/list: (col, val) or (col, op, val)
    """
    if isinstance(cond, dict):
        col = cond.get("column") or cond.get("col")
        op = cond.get("operator") or cond.get("op") or "="
        val = cond.get("value") if "value" in cond else cond.get("val")
        if not col:
            return None
        return {"column": str(col).strip(), "operator": str(op).strip(), "value": val}

    if isinstance(cond, (list, tuple)):
        if len(cond) == 2:
            return {"column": str(cond[0]).strip(), "operator": "=", "value": cond[1]}
        elif len(cond) == 3:
            return {"column": str(cond[0]).strip(), "operator": str(cond[1]).strip(), "value": cond[2]}

    return None


def validate_and_build_where(
    table: str,
    conditions: List[Any],
    schema: dict[str, Any],
) -> dict[str, Any]:
    """
    Validates a list of conditions against the live table schema and builds a dialect-safe WHERE clause.
    All conditions are joined with AND.

    Returns:
    {
        "valid": bool,
        "error": Optional[str],
        "where_clause": Optional[str],
        "normalized_conditions": List[dict],
    }
    """
    if not table or table not in schema:
        return {
            "valid": False,
            "error": f"Table '{table}' does not exist in the active database schema.",
            "where_clause": None,
            "normalized_conditions": [],
        }

    table_schema = schema.get(table, {})
    if not isinstance(table_schema, dict):
        table_schema = {}

    table_columns = set(table_schema.keys())

    if not conditions:
        return {
            "valid": False,
            "error": "For safety, a WHERE condition identifying target records is required.",
            "where_clause": None,
            "normalized_conditions": [],
        }

    normalized_list = []
    sql_parts = []

    for idx, raw_cond in enumerate(conditions):
        norm = normalize_condition(raw_cond)
        if not norm:
            return {
                "valid": False,
                "error": f"Condition #{idx + 1} is malformed or missing a column.",
                "where_clause": None,
                "normalized_conditions": [],
            }

        col = norm["column"]
        op_raw = norm["operator"].lower().strip()
        val = norm["value"]

        # 1. Validate column exists in table schema
        if col not in table_columns:
            return {
                "valid": False,
                "error": f"Column '{col}' does not exist on table '{table}'.",
                "where_clause": None,
                "normalized_conditions": [],
            }

        # 2. Handle NULL checks
        if val is None and op_raw in ("=", "==", "is", "is null"):
            op_sql = "IS NULL"
            val_sql = ""
            norm["operator"] = "IS NULL"
            norm["value"] = None
        elif val is None and op_raw in ("!=", "<>", "is not", "is not null"):
            op_sql = "IS NOT NULL"
            val_sql = ""
            norm["operator"] = "IS NOT NULL"
            norm["value"] = None
        else:
            if op_raw not in ALLOWED_OPERATORS:
                return {
                    "valid": False,
                    "error": f"Unsupported operator '{op_raw}' on column '{col}'. Allowed: {', '.join(sorted(ALLOWED_OPERATORS.keys()))}",
                    "where_clause": None,
                    "normalized_conditions": [],
                }
            op_sql = ALLOWED_OPERATORS[op_raw]
            val_sql = " " + quote_value(val)
            norm["operator"] = op_sql

        quoted_col = quote_identifier(col)
        if op_sql in ("IS NULL", "IS NOT NULL"):
            sql_parts.append(f"{quoted_col} {op_sql}")
        else:
            sql_parts.append(f"{quoted_col} {op_sql}{val_sql}")

        normalized_list.append(norm)

    where_clause = " AND ".join(sql_parts)
    return {
        "valid": True,
        "error": None,
        "where_clause": where_clause,
        "normalized_conditions": normalized_list,
    }

