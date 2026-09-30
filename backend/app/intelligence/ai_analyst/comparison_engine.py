from __future__ import annotations

from typing import Any, Optional
from sqlalchemy import text
from app.database.database_manager import get_engine, get_current_db_type
from app.intelligence.schema_analyzer import quote_identifier
from app.intelligence.ai_analyst.metric_engine import calculate_percentage


def analyze_ranking(
    table_name: str,
    dimension_col: str,
    metric_col: Optional[str] = None,
    agg_func: str = "SUM",
    limit: int = 10,
    ascending: bool = False,
) -> dict[str, Any]:
    """
    Computes Top-N or Bottom-N ranking of entities/categories by quantitative measure.
    """
    engine = get_engine()
    db_type = get_current_db_type()

    if engine is None or db_type == "none":
        return {"status": "error", "message": "No database connected."}

    t_quoted = quote_identifier(table_name, db_type)
    d_quoted = quote_identifier(dimension_col, db_type)

    if metric_col:
        m_quoted = quote_identifier(metric_col, db_type)
        val_expr = f"{agg_func.upper()}({m_quoted})"
    else:
        val_expr = "COUNT(*)"

    sort_order = "ASC" if ascending else "DESC"
    safe_limit = min(max(1, limit), 50)

    sql = f"""
        SELECT 
            {d_quoted} as category,
            {val_expr} as val,
            COUNT(*) as record_count
        FROM {t_quoted}
        WHERE {d_quoted} IS NOT NULL
        GROUP BY {d_quoted}
        ORDER BY val {sort_order}
        LIMIT {safe_limit}
    """

    try:
        with engine.connect() as conn:
            rows = conn.execute(text(sql)).fetchall()
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ranking query failed: {str(e)}",
            "sql": sql,
        }

    if not rows:
        return {
            "status": "insufficient_data",
            "message": f"No data found in '{table_name}' for ranking by '{dimension_col}'.",
            "sql": sql,
        }

    labels = [str(r[0]) for r in rows if r[0] is not None]
    values = [round(float(r[1]), 2) if r[1] is not None else 0.0 for r in rows if r[0] is not None]
    total_val = sum(values)

    breakdown = []
    for i, label in enumerate(labels):
        pct = calculate_percentage(values[i], total_val)
        breakdown.append({
            "rank": i + 1,
            "category": label,
            "value": values[i],
            "percentage": pct,
        })

    metric_title = f"{agg_func}({metric_col})" if metric_col else "Count"
    rank_type = "Bottom" if ascending else "Top"

    return {
        "status": "success",
        "table": table_name,
        "dimension_column": dimension_col,
        "metric_column": metric_col,
        "calculation": f"{agg_func}({metric_col})" if metric_col else f"COUNT({table_name})",
        "labels": labels,
        "values": values,
        "total_value": total_val,
        "breakdown": breakdown,
        "sql": sql,
        "chart": {
            "chart_type": "bar",
            "title": f"{rank_type} {len(labels)} {dimension_col.title()} by {metric_title}",
            "labels": labels,
            "values": values,
        },
    }


def analyze_distribution(
    table_name: str,
    category_col: str,
    limit: int = 15,
) -> dict[str, Any]:
    """
    Computes categorical distribution and percentage share.
    """
    engine = get_engine()
    db_type = get_current_db_type()

    if engine is None or db_type == "none":
        return {"status": "error", "message": "No database connected."}

    t_quoted = quote_identifier(table_name, db_type)
    c_quoted = quote_identifier(category_col, db_type)
    safe_limit = min(max(1, limit), 50)

    sql = f"""
        SELECT 
            {c_quoted} as category,
            COUNT(*) as cnt
        FROM {t_quoted}
        WHERE {c_quoted} IS NOT NULL
        GROUP BY {c_quoted}
        ORDER BY cnt DESC
        LIMIT {safe_limit}
    """

    try:
        with engine.connect() as conn:
            rows = conn.execute(text(sql)).fetchall()
    except Exception as e:
        return {
            "status": "error",
            "message": f"Distribution query failed: {str(e)}",
            "sql": sql,
        }

    if not rows:
        return {
            "status": "insufficient_data",
            "message": f"No records found in '{table_name}' for distribution of '{category_col}'.",
            "sql": sql,
        }

    labels = [str(r[0]) for r in rows if r[0] is not None]
    counts = [int(r[1]) for r in rows if r[0] is not None]
    total_records = sum(counts)

    breakdown = []
    for i, label in enumerate(labels):
        pct = calculate_percentage(counts[i], total_records)
        breakdown.append({
            "category": label,
            "count": counts[i],
            "percentage": pct,
        })

    return {
        "status": "success",
        "table": table_name,
        "category_column": category_col,
        "total_records": total_records,
        "labels": labels,
        "values": counts,
        "breakdown": breakdown,
        "sql": sql,
        "chart": {
            "chart_type": "pie",
            "title": f"Distribution by {category_col.title()}",
            "labels": labels,
            "values": counts,
        },
    }
