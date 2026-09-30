from __future__ import annotations

from typing import Any, Optional
from sqlalchemy import text
from app.database.database_manager import get_engine, get_current_db_type
from app.intelligence.schema_analyzer import quote_identifier
from app.intelligence.ai_analyst.metric_engine import calculate_growth_rate


def get_dialect_date_trunc(col_quoted: str, db_type: str, interval: str = "month") -> str:
    """
    Returns dialect-safe date formatting expression across SQLite, MySQL, and PostgreSQL.
    """
    interval = interval.lower()
    if db_type == "sqlite":
        if interval == "day":
            return f"strftime('%Y-%m-%d', {col_quoted})"
        elif interval == "year":
            return f"strftime('%Y', {col_quoted})"
        return f"strftime('%Y-%m', {col_quoted})"

    elif db_type == "mysql":
        if interval == "day":
            return f"DATE_FORMAT({col_quoted}, '%Y-%m-%d')"
        elif interval == "year":
            return f"DATE_FORMAT({col_quoted}, '%Y')"
        return f"DATE_FORMAT({col_quoted}, '%Y-%m')"

    else:  # PostgreSQL
        if interval == "day":
            return f"TO_CHAR({col_quoted}, 'YYYY-MM-DD')"
        elif interval == "year":
            return f"TO_CHAR({col_quoted}, 'YYYY')"
        return f"TO_CHAR({col_quoted}, 'YYYY-MM')"


def analyze_trend(
    table_name: str,
    metric_col: Optional[str] = None,
    date_col: Optional[str] = None,
    agg_func: str = "SUM",
    interval: str = "month",
) -> dict[str, Any]:
    """
    Computes chronological trend over time:
    - Period values
    - Current vs previous period comparison
    - Absolute growth & percentage growth
    - Line chart labels & values
    """
    engine = get_engine()
    db_type = get_current_db_type()

    if engine is None or db_type == "none":
        return {"status": "error", "message": "No database connected."}

    if not date_col:
        return {
            "status": "unavailable",
            "message": "Time-series analysis is unavailable because no suitable date/time field was detected.",
        }

    t_quoted = quote_identifier(table_name, db_type)
    d_quoted = quote_identifier(date_col, db_type)

    date_expr = get_dialect_date_trunc(d_quoted, db_type, interval)

    if metric_col:
        m_quoted = quote_identifier(metric_col, db_type)
        val_expr = f"{agg_func.upper()}({m_quoted})"
    else:
        val_expr = "COUNT(*)"

    sql = f"""
        SELECT 
            {date_expr} as period,
            {val_expr} as val,
            COUNT(*) as record_count
        FROM {t_quoted}
        WHERE {d_quoted} IS NOT NULL
        GROUP BY period
        ORDER BY period ASC
        LIMIT 24
    """

    try:
        with engine.connect() as conn:
            cursor = conn.execute(text(sql))
            rows = cursor.fetchall()
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to execute time-series query: {str(e)}",
            "sql": sql,
        }

    if not rows:
        return {
            "status": "insufficient_data",
            "message": f"Table '{table_name}' contains no dated records for time-series analysis.",
            "sql": sql,
        }

    labels = [str(r[0]) for r in rows if r[0] is not None]
    values = [round(float(r[1]), 2) if r[1] is not None else 0.0 for r in rows if r[0] is not None]
    counts = [int(r[2]) for r in rows if r[0] is not None]

    if len(values) < 1:
        return {
            "status": "insufficient_data",
            "message": "Insufficient chronological data to establish a trend.",
        }

    current_val = values[-1]
    prev_val = values[-2] if len(values) >= 2 else current_val

    delta, growth_pct, direction = calculate_growth_rate(current_val, prev_val)

    breakdown = []
    for i, label in enumerate(labels):
        breakdown.append({
            "period": label,
            "value": values[i],
            "count": counts[i],
        })

    metric_label = f"{agg_func}({metric_col})" if metric_col else "Count"

    return {
        "status": "success",
        "table": table_name,
        "metric_column": metric_col,
        "date_column": date_col,
        "calculation": f"{agg_func}({metric_col})" if metric_col else f"COUNT({table_name})",
        "current_period": labels[-1],
        "current_value": current_val,
        "previous_period": labels[-2] if len(labels) >= 2 else None,
        "previous_value": prev_val if len(labels) >= 2 else None,
        "absolute_change": delta,
        "percentage_change": growth_pct,
        "direction": direction,
        "sample_count": sum(counts),
        "labels": labels,
        "values": values,
        "breakdown": breakdown,
        "sql": sql,
        "chart": {
            "chart_type": "line",
            "title": f"{metric_label} Trend Over Time",
            "labels": labels,
            "values": values,
        },
    }
