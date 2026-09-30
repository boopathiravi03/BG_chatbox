from __future__ import annotations

from typing import Any, Optional
from sqlalchemy import text
from app.database.database_manager import get_engine, get_current_db_type
from app.intelligence.schema_analyzer import quote_identifier
from app.intelligence.ai_analyst.metric_engine import calculate_growth_rate, calculate_percentage
from app.intelligence.ai_analyst.trend_analyzer import get_dialect_date_trunc


def perform_why_diagnostic(
    table_name: str,
    metric_col: Optional[str] = None,
    dimension_cols: Optional[list[str]] = None,
    date_col: Optional[str] = None,
    agg_func: str = "SUM",
) -> dict[str, Any]:
    """
    Performs evidence-driven diagnostic decomposition:
    - Analyzes metric distribution across dimensions
    - Identifies where variance or value is concentrated
    - Returns strictly statistical association without claiming causality
    """
    engine = get_engine()
    db_type = get_current_db_type()

    if engine is None or db_type == "none":
        return {"status": "error", "message": "No database connected."}

    t_quoted = quote_identifier(table_name, db_type)

    if metric_col:
        m_quoted = quote_identifier(metric_col, db_type)
        val_expr = f"{agg_func.upper()}({m_quoted})"
    else:
        val_expr = "COUNT(*)"

    # If no dimension column supplied, look for status/category columns
    target_dim = dimension_cols[0] if dimension_cols else None
    if not target_dim:
        return {
            "status": "insufficient_data",
            "message": f"No dimensional attribute (e.g. status, category, segment) found in '{table_name}' to diagnose breakdown.",
        }

    dim_quoted = quote_identifier(target_dim, db_type)

    # 1. Total metric
    sql_total = f"SELECT {val_expr} FROM {t_quoted} WHERE {dim_quoted} IS NOT NULL"

    # 2. Breakdown by dimension
    sql_breakdown = f"""
        SELECT 
            {dim_quoted} as category,
            {val_expr} as val,
            COUNT(*) as record_count
        FROM {t_quoted}
        WHERE {dim_quoted} IS NOT NULL
        GROUP BY {dim_quoted}
        ORDER BY val DESC
        LIMIT 10
    """

    try:
        with engine.connect() as conn:
            total_val = conn.execute(text(sql_total)).scalar()
            total_val = float(total_val) if total_val is not None else 0.0
            rows = conn.execute(text(sql_breakdown)).fetchall()
    except Exception as e:
        return {
            "status": "error",
            "message": f"Diagnostic query failed: {str(e)}",
            "sql": sql_breakdown,
        }

    if not rows:
        return {
            "status": "insufficient_data",
            "message": f"No variance records found in '{table_name}'.",
        }

    contributors = []
    labels = []
    values = []

    for r in rows:
        cat_name = str(r[0]) if r[0] is not None else "Unknown"
        val = round(float(r[1]), 2) if r[1] is not None else 0.0
        pct = calculate_percentage(val, total_val)
        labels.append(cat_name)
        values.append(val)
        contributors.append({
            "dimension": target_dim,
            "category": cat_name,
            "value": val,
            "percentage_of_total": pct,
        })

    # Diagnostic synthesis
    top_driver = contributors[0] if contributors else None
    driver_text = (
        f"The highest concentration of {metric_col or 'records'} is associated with '{top_driver['category']}' ({top_driver['percentage_of_total']}% of total)."
        if top_driver else "Evenly distributed."
    )

    causality_disclaimer = (
        "Statistical Note: This breakdown isolates where values are concentrated within the database. "
        "These factors are statistically associated with the observed outcome; the database does not prove direct causation."
    )

    return {
        "status": "success",
        "table": table_name,
        "metric_column": metric_col,
        "dimension_column": target_dim,
        "total_value": total_val,
        "contributors": contributors,
        "labels": labels,
        "values": values,
        "driver_summary": driver_text,
        "causality_disclaimer": causality_disclaimer,
        "sql": sql_breakdown,
        "chart": {
            "chart_type": "bar",
            "title": f"Breakdown by {target_dim.title()}",
            "labels": labels,
            "values": values,
        },
    }
