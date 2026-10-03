"""
backend/app/intelligence/outcome_optimization/baseline_engine.py

Phase 8.9: Baseline Measurement Engine
Computes pre-action baseline values for metrics using real database data.
Supports: full_history aggregation and current-state snapshots.

Safety:
- Read-only SQL only (SELECT + aggregation).
- Never writes to the user database.
- Returns None / empty if data is insufficient.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import text
from app.intelligence.schema_analyzer import quote_identifier, analyze_schema
from app.intelligence.business_intelligence.business_context import discover_business_context
from app.intelligence.business_intelligence.metric_discovery import discover_business_metrics

logger = logging.getLogger("bgai.outcome_optimization.baseline")

MIN_ROWS_FOR_BASELINE = 3


def _safe_query_scalar(engine: Any, sql: str) -> Optional[float]:
    """Execute a single-value SELECT safely and return a float scalar."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql)).scalar()
            if result is None:
                return None
            return float(result)
    except Exception as e:
        logger.debug("Baseline query error: %s | SQL: %s", str(e), sql)
        return None


def _safe_query_count(engine: Any, sql: str) -> int:
    """Execute a COUNT query safely and return an integer."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql)).scalar()
            return int(result) if result is not None else 0
    except Exception:
        return 0


def compute_baseline_for_metric(
    engine: Any,
    db_type: str,
    source_table: str,
    source_column: str,
    aggregation: str = "SUM",
) -> dict[str, Any]:
    """
    Compute a baseline value for a metric column.

    Returns:
        {
          "baseline_value": float | None,
          "baseline_period": str,
          "baseline_sample_size": int,
          "sql_used": str,
          "sufficient": bool,
        }
    """
    t_sql = quote_identifier(source_table, db_type)

    # Count rows available
    count_sql = f"SELECT COUNT(*) FROM {t_sql}"
    row_count = _safe_query_count(engine, count_sql)

    if row_count < MIN_ROWS_FOR_BASELINE:
        return {
            "baseline_value": None,
            "baseline_period": "insufficient_data",
            "baseline_sample_size": row_count,
            "sql_used": count_sql,
            "sufficient": False,
        }

    agg = aggregation.upper()
    if agg not in ("SUM", "AVG", "COUNT", "MAX", "MIN"):
        agg = "SUM"

    if agg == "COUNT" or not source_column:
        agg_sql = f"SELECT COUNT(*) FROM {t_sql}"
    else:
        c_sql = quote_identifier(source_column, db_type)
        count_sql = f"SELECT COUNT(*) FROM {t_sql} WHERE {c_sql} IS NOT NULL"
        row_count = _safe_query_count(engine, count_sql)
        if row_count < MIN_ROWS_FOR_BASELINE:
            return {
                "baseline_value": None,
                "baseline_period": "insufficient_data",
                "baseline_sample_size": row_count,
                "sql_used": count_sql,
                "sufficient": False,
            }
        agg_sql = f"SELECT {agg}({c_sql}) FROM {t_sql} WHERE {c_sql} IS NOT NULL"

    baseline_val = _safe_query_scalar(engine, agg_sql)

    return {
        "baseline_value": round(baseline_val, 4) if baseline_val is not None else None,
        "baseline_period": f"full_history_{agg.lower()}",
        "baseline_sample_size": row_count,
        "sql_used": agg_sql,
        "sufficient": baseline_val is not None,
    }


def discover_measurable_metrics(
    engine: Any, db_type: str
) -> list[dict[str, Any]]:
    """
    Discover measurable metrics for the connected database.
    Reuses Phase 8.1 business_context + metric_discovery.

    Returns a list of metric descriptors:
    [
      {
        "metric_name": str,
        "source_table": str,
        "source_column": str,
        "aggregation": str,    # SUM, AVG, COUNT
        "current_value": float | None,
        "sql": str,
        "timestamp_col": str | None,
      }
    ]
    """
    if engine is None:
        return []

    try:
        schema_info = analyze_schema(engine, db_type)
        context = discover_business_context(engine, db_type, schema_info)
        metrics = discover_business_metrics(engine, db_type, context)
    except Exception as e:
        logger.debug("Metric discovery error: %s", str(e))
        return []

    result = []
    for m in metrics:
        # Determine aggregation from calculation_method
        agg = "SUM"
        if m.calculation_method:
            upper_cm = m.calculation_method.upper()
            if upper_cm.startswith("AVG"):
                agg = "AVG"
            elif upper_cm.startswith("COUNT"):
                agg = "COUNT"

        source_col = ""
        if m.source_columns and m.source_columns[0] != "*":
            source_col = m.source_columns[0]

        result.append({
            "metric_name": m.name,
            "source_table": m.source_table,
            "source_column": source_col,
            "aggregation": agg,
            "current_value": m.current_value,
            "sql": m.sql or "",
            "timestamp_col": getattr(m, "timestamp_col", None),
        })

    return result
