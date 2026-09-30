from __future__ import annotations

import re
from typing import Any, Optional
from sqlalchemy import text
from app.database.database_manager import get_engine, get_current_db_type
from app.intelligence.schema_analyzer import quote_identifier
from app.intelligence.table_explorer import classify_semantic_type
from app.intelligence.scanner import get_cached_report, run_database_intelligence_scan
from app.intelligence.forecasting.models import ForecastCandidate
from app.intelligence.ai_analyst.trend_analyzer import get_dialect_date_trunc


def detect_forecast_candidates() -> tuple[list[ForecastCandidate], Optional[str]]:
    """
    Inspects connected database schema to discover valid time-series candidates:
    - Tables with at least one Date/Timestamp column
    - Numeric measure columns (Currency, Quantity, Numeric) or record counts
    - Validates minimum historical observations (>= 3 distinct periods)
    - Returns list of eligible candidates, or explanation message if none exist.
    """
    engine = get_engine()
    db_type = get_current_db_type()

    if engine is None or db_type == "none":
        return [], "No database is currently connected."

    report = get_cached_report()
    if report is None:
        report = run_database_intelligence_scan(force_refresh=False)

    if not report or not report.schema_summary:
        return [], "Forecasting unavailable: database schema could not be inspected."

    candidates: list[ForecastCandidate] = []

    for table_name, table_meta in report.schema_summary.items():
        cols = table_meta.get("columns", [])
        row_count = table_meta.get("row_count", 0)

        if row_count < 3:
            continue

        date_cols: list[str] = []
        numeric_cols: list[dict[str, str]] = []

        for col in cols:
            c_name = col.get("name", "")
            c_type = col.get("type", "TEXT")
            sem_type = classify_semantic_type(c_name, c_type)

            if sem_type in ("Date", "Timestamp"):
                date_cols.append(c_name)
            elif sem_type in ("Currency", "Quantity", "Numeric"):
                numeric_cols.append({"name": c_name, "semantic_type": sem_type})

        if not date_cols:
            continue

        # For each date column, evaluate distinct chronological periods
        for d_col in date_cols[:2]:  # Test up to first 2 date columns
            t_quoted = quote_identifier(table_name, db_type)
            d_quoted = quote_identifier(d_col, db_type)

            # Check min date, max date, and distinct months
            month_expr = get_dialect_date_trunc(d_quoted, db_type, interval="month")
            day_expr = get_dialect_date_trunc(d_quoted, db_type, interval="day")

            sql = f"""
                SELECT 
                    COUNT(DISTINCT {month_expr}) as distinct_months,
                    COUNT(DISTINCT {day_expr}) as distinct_days,
                    MIN({d_quoted}) as min_val,
                    MAX({d_quoted}) as max_val
                FROM {t_quoted}
                WHERE {d_quoted} IS NOT NULL
            """

            try:
                with engine.connect() as conn:
                    res = conn.execute(text(sql)).fetchone()
            except Exception:
                continue

            if not res or res[0] is None:
                continue

            distinct_months = int(res[0] or 0)
            distinct_days = int(res[1] or 0)
            min_date = str(res[2] or "")[:10]
            max_date = str(res[3] or "")[:10]

            # Choose frequency based on density
            if distinct_months >= 3:
                freq = "monthly"
                hist_points = distinct_months
            elif distinct_days >= 5:
                freq = "daily"
                hist_points = distinct_days
            else:
                continue

            # Candidate A: Numeric measures (SUM)
            for num_col in numeric_cols:
                col_name = num_col["name"]
                calc_name = f"SUM({col_name})"
                metric_label = f"{col_name.replace('_', ' ').title()}"

                candidates.append(
                    ForecastCandidate(
                        table=table_name,
                        date_column=d_col,
                        metric_column=col_name,
                        metric_label=metric_label,
                        calculation=calc_name,
                        frequency=freq,
                        historical_points_count=hist_points,
                        min_date=min_date,
                        max_date=max_date,
                    )
                )

            # Candidate B: Volume / Activity count (COUNT(*))
            candidates.append(
                ForecastCandidate(
                    table=table_name,
                    date_column=d_col,
                    metric_column=None,
                    metric_label=f"Total {table_name.title()} Volume",
                    calculation=f"COUNT(*)",
                    frequency=freq,
                    historical_points_count=hist_points,
                    min_date=min_date,
                    max_date=max_date,
                )
            )

    if not candidates:
        return [], "Forecasting unavailable: no suitable time-series data was detected."

    return candidates, None
