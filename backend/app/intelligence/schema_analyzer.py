from __future__ import annotations

from typing import Any
from sqlalchemy import inspect, text
from app.database.database_manager import get_engine, get_current_db_type


def quote_identifier(ident: str, db_type: str | None = None) -> str:
    """Safely quote table/column identifiers across SQLite, MySQL, and PostgreSQL."""
    if db_type == "mysql":
        escaped = ident.replace("`", "``")
        return f"`{escaped}`"
    escaped = ident.replace('"', '""')
    return f'"{escaped}"'


def analyze_schema(engine, db_type: str) -> dict[str, Any]:
    """
    Safely discovers tables, columns, primary keys, foreign keys, and indexes.
    Returns schema summary and relationship mappings without running heavy data scans.
    """
    inspector = inspect(engine)
    try:
        tables = inspector.get_table_names()
    except Exception as e:
        return {
            "tables": {},
            "total_tables": 0,
            "total_columns": 0,
            "total_relationships": 0,
            "relationships": [],
            "error": str(e),
        }

    schema_details = {}
    total_columns = 0
    all_relationships = []

    for table_name in tables:
        try:
            columns = inspector.get_columns(table_name)
        except Exception:
            columns = []

        try:
            pk_constraint = inspector.get_pk_constraint(table_name)
            pk_cols = set(pk_constraint.get("constrained_columns") or [])
        except Exception:
            pk_cols = set()

        try:
            fks = inspector.get_foreign_keys(table_name)
        except Exception:
            fks = []

        try:
            indexes = inspector.get_indexes(table_name)
        except Exception:
            indexes = []

        col_details = []
        for col in columns:
            c_name = col.get("name", "")
            c_type = str(col.get("type", "TEXT"))
            is_pk = c_name in pk_cols
            nullable = col.get("nullable", True)

            col_details.append({
                "name": c_name,
                "type": c_type,
                "is_pk": is_pk,
                "nullable": nullable,
            })
            total_columns += 1

        for fk in fks:
            referred_table = fk.get("referred_table")
            constrained_cols = fk.get("constrained_columns", [])
            referred_cols = fk.get("referred_columns", [])
            if referred_table:
                all_relationships.append({
                    "source_table": table_name,
                    "source_columns": constrained_cols,
                    "target_table": referred_table,
                    "target_columns": referred_cols,
                })

        schema_details[table_name] = {
            "columns": col_details,
            "pk_columns": list(pk_cols),
            "foreign_keys": fks,
            "indexes": indexes,
        }

    return {
        "tables": schema_details,
        "total_tables": len(tables),
        "total_columns": total_columns,
        "total_relationships": len(all_relationships),
        "relationships": all_relationships,
    }
