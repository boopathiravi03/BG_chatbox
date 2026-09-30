from __future__ import annotations

from typing import Any, Optional
from sqlalchemy import text
from app.database.database_manager import get_engine, get_current_db_type
from app.intelligence.schema_analyzer import quote_identifier
from app.intelligence.table_explorer import classify_semantic_type


def discover_metrics_in_schema(schema_summary: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Scans tables and columns to discover quantitative measures,
    status dimensions, and temporal columns for analytics.
    """
    discovered = []
    for table_name, table_meta in schema_summary.items():
        cols = table_meta.get("columns", [])
        row_count = table_meta.get("row_count", 0)

        numeric_cols = []
        date_cols = []
        category_cols = []

        for col in cols:
            c_name = col.get("name", "")
            c_type = col.get("type", "TEXT")
            sem_type = classify_semantic_type(c_name, c_type)

            if sem_type in ("Currency", "Quantity", "Numeric"):
                numeric_cols.append({"name": c_name, "type": c_type, "semantic_type": sem_type})
            elif sem_type in ("Date", "Timestamp"):
                date_cols.append({"name": c_name, "type": c_type, "semantic_type": sem_type})
            elif sem_type in ("Status", "Text") and not col.get("is_pk", False):
                category_cols.append({"name": c_name, "type": c_type, "semantic_type": sem_type})

        if row_count > 0:
            discovered.append({
                "table": table_name,
                "row_count": row_count,
                "numeric_columns": numeric_cols,
                "date_columns": date_cols,
                "category_columns": category_cols,
                "primary_keys": table_meta.get("pk_columns", []),
            })

    return discovered


def compute_column_aggregate(
    table_name: str,
    column_name: str,
    func: str = "SUM",
    where_clause: Optional[str] = None,
) -> Optional[float]:
    """
    Safely computes an aggregate (SUM, AVG, MIN, MAX, COUNT) on a numeric column.
    Guarantees read-only execution, dialect quoting, and null safety.
    """
    engine = get_engine()
    db_type = get_current_db_type()
    if engine is None or db_type == "none":
        return None

    func_clean = func.upper().strip()
    if func_clean not in ("SUM", "AVG", "MIN", "MAX", "COUNT"):
        func_clean = "SUM"

    t_quoted = quote_identifier(table_name, db_type)
    c_quoted = quote_identifier(column_name, db_type)

    where_sql = f"WHERE {where_clause}" if where_clause else f"WHERE {c_quoted} IS NOT NULL"
    sql = f"SELECT {func_clean}({c_quoted}) FROM {t_quoted} {where_sql}"

    try:
        with engine.connect() as conn:
            res = conn.execute(text(sql)).scalar()
            if res is not None:
                return round(float(res), 2)
            return 0.0
    except Exception as e:
        print(f"Error computing aggregate {func} for {table_name}.{column_name}: {e}")
        return None


def calculate_percentage(part: float, total: float) -> float:
    """Computes percentage with division-by-zero protection."""
    if total == 0:
        return 0.0
    return round((part / total) * 100, 2)


def calculate_growth_rate(current: float, previous: float) -> tuple[float, float, str]:
    """
    Calculates absolute delta and percentage growth rate.
    Returns: (absolute_change, percentage_growth, direction)
    """
    delta = round(current - previous, 2)
    if previous == 0:
        pct = 100.0 if current > 0 else 0.0
    else:
        pct = round(((current - previous) / abs(previous)) * 100, 2)

    if delta > 0:
        direction = "up"
    elif delta < 0:
        direction = "down"
    else:
        direction = "flat"

    return delta, pct, direction
