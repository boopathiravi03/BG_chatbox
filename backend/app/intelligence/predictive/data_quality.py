"""
backend/app/intelligence/predictive/data_quality.py

Phase 9.0: Time-Series Discovery & Data Quality Gate
Inspects schema, discovers temporal dimensions, extracts chronological series,
and evaluates observation density, missingness, and interval stability.

Strict Safety & Grounding:
- Read-only SQL queries only (SELECT + aggregation).
- Honest gatekeeping: returns structured INSUFFICIENT_DATA when evidence is inadequate.
- Never fabricates timestamps or missing observations.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text
from app.database.database_manager import get_engine, get_current_db_type
from app.intelligence.schema_analyzer import quote_identifier, analyze_schema
from app.intelligence.table_explorer import classify_semantic_type
from app.intelligence.ai_analyst.trend_analyzer import get_dialect_date_trunc
from app.intelligence.predictive.models import DataQualityStatus

logger = logging.getLogger("bgai.predictive.data_quality")

MIN_OBSERVATIONS_FOR_PREDICTION = 3
MIN_OBSERVATIONS_FOR_MODEL_SELECTION = 5


@dataclass
class TimeSeriesCandidate:
    table: str
    date_column: str
    metric_column: Optional[str]
    metric_name: str
    aggregation: str
    frequency: str
    observation_count: int
    min_date: str
    max_date: str


@dataclass
class DataQualityReport:
    is_sufficient: bool
    status: DataQualityStatus
    observation_count: int
    min_date: str = ""
    max_date: str = ""
    missing_value_count: int = 0
    clean_series: list[tuple[str, float]] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    sql_executed: str = ""


def discover_predictive_candidates(engine: Any, db_type: str) -> list[TimeSeriesCandidate]:
    """
    Discovers forecastable metrics and their associated date columns from the active database.
    Does not guess or assume tables; discovers from actual schema.
    """
    if engine is None or db_type == "none":
        return []

    schema_info = analyze_schema(engine, db_type)
    tables = schema_info.get("tables", {})
    if not tables:
        return []

    candidates: list[TimeSeriesCandidate] = []

    for table_name, table_meta in tables.items():
        columns = table_meta.get("columns", [])
        if not columns:
            continue

        date_cols: list[str] = []
        numeric_cols: list[dict[str, str]] = []

        for col in columns:
            c_name = col.get("name", "")
            c_type = str(col.get("type", "TEXT"))
            sem = classify_semantic_type(c_name, c_type)

            if sem in ("Date", "Timestamp") or any(
                term in c_name.lower() for term in ("date", "time", "created_at", "updated_at", "timestamp")
            ):
                date_cols.append(c_name)
            elif sem in ("Currency", "Quantity", "Numeric") or any(
                num_type in c_type.upper() for num_type in ("INT", "FLOAT", "NUMERIC", "DECIMAL", "REAL", "DOUBLE")
            ):
                if not any(id_suffix in c_name.lower() for id_suffix in ("id", "key", "guid", "code")):
                    numeric_cols.append({"name": c_name, "type": c_type})

        if not date_cols:
            continue

        primary_date_col = date_cols[0]

        # 1. Total row count / volume candidate
        clean_tbl = table_name.replace("_", " ").title()
        candidates.append(
            TimeSeriesCandidate(
                table=table_name,
                date_column=primary_date_col,
                metric_column=None,
                metric_name=f"Total {clean_tbl} Count",
                aggregation="COUNT",
                frequency="monthly",
                observation_count=0,
                min_date="",
                max_date="",
            )
        )

        # 2. Add candidates for valid numeric measure columns (up to 3 per table)
        for num_col in numeric_cols[:3]:
            col_name = num_col["name"]
            clean_col = col_name.replace("_", " ").title()
            candidates.append(
                TimeSeriesCandidate(
                    table=table_name,
                    date_column=primary_date_col,
                    metric_column=col_name,
                    metric_name=f"Total {clean_col}",
                    aggregation="SUM",
                    frequency="monthly",
                    observation_count=0,
                    min_date="",
                    max_date="",
                )
            )

    return candidates


def extract_and_evaluate_time_series(
    engine: Any,
    db_type: str,
    table: str,
    date_column: str,
    metric_column: Optional[str] = None,
    aggregation: str = "SUM",
    frequency: str = "monthly",
) -> DataQualityReport:
    """
    Extracts chronological series using dialect-safe grouping and validates quality.
    """
    if engine is None or db_type == "none":
        return DataQualityReport(
            is_sufficient=False,
            status=DataQualityStatus.INSUFFICIENT_DATA,
            observation_count=0,
            issues=["No active database is connected."],
        )

    t_quoted = quote_identifier(table, db_type)
    d_quoted = quote_identifier(date_column, db_type)

    interval_arg = "month" if frequency == "monthly" else "day"
    date_expr = get_dialect_date_trunc(d_quoted, db_type, interval=interval_arg)

    agg = aggregation.upper()
    if agg not in ("SUM", "AVG", "COUNT", "MAX", "MIN"):
        agg = "SUM"

    if metric_column:
        m_quoted = quote_identifier(metric_column, db_type)
        val_expr = f"{agg}({m_quoted})"
        where_clause = f"WHERE {d_quoted} IS NOT NULL AND {m_quoted} IS NOT NULL"
    else:
        val_expr = "COUNT(*)"
        where_clause = f"WHERE {d_quoted} IS NOT NULL"

    sql = f"""
        SELECT 
            {date_expr} AS period,
            {val_expr} AS metric_val
        FROM {t_quoted}
        {where_clause}
        GROUP BY {date_expr}
        ORDER BY {date_expr} ASC
    """

    try:
        with engine.connect() as conn:
            rows = conn.execute(text(sql)).fetchall()
    except Exception as e:
        logger.warning("Data quality time-series query error on %s: %s", table, str(e))
        return DataQualityReport(
            is_sufficient=False,
            status=DataQualityStatus.INSUFFICIENT_DATA,
            observation_count=0,
            issues=[f"Failed to query time-series from database: {str(e)}"],
            sql_executed=sql,
        )

    clean_points: list[tuple[str, float]] = []
    seen_periods = set()
    duplicate_periods = 0

    for r in rows:
        period_str = str(r[0]) if r[0] is not None else None
        if not period_str:
            continue

        if period_str in seen_periods:
            duplicate_periods += 1
            continue
        seen_periods.add(period_str)

        try:
            val = float(r[1]) if r[1] is not None else 0.0
            clean_points.append((period_str, val))
        except (ValueError, TypeError):
            continue

    n = len(clean_points)
    issues: list[str] = []

    if n < MIN_OBSERVATIONS_FOR_PREDICTION:
        issues.append(
            f"Insufficient historical data: found {n} chronological periods. "
            f"A minimum of {MIN_OBSERVATIONS_FOR_PREDICTION} distinct periods is required."
        )
        return DataQualityReport(
            is_sufficient=False,
            status=DataQualityStatus.INSUFFICIENT_DATA,
            observation_count=n,
            min_date=clean_points[0][0] if clean_points else "",
            max_date=clean_points[-1][0] if clean_points else "",
            clean_series=clean_points,
            issues=issues,
            sql_executed=sql,
        )

    if duplicate_periods > 0:
        issues.append(f"Detected and deduplicated {duplicate_periods} duplicate time bucket(s).")

    # Check for extreme zero density
    zero_count = sum(1 for _, v in clean_points if abs(v) < 1e-9)
    if zero_count / n > 0.5:
        issues.append("Over 50% of chronological observations are zero; trend stability is limited.")

    min_d = clean_points[0][0]
    max_d = clean_points[-1][0]

    return DataQualityReport(
        is_sufficient=True,
        status=DataQualityStatus.VALID,
        observation_count=n,
        min_date=min_d,
        max_date=max_d,
        clean_series=clean_points,
        issues=issues,
        sql_executed=sql,
    )
