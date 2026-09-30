"""
backend/app/intelligence/business_intelligence/metric_discovery.py

Phase 8.1: Deterministic Metric Discovery Layer
Discovers and computes meaningful business metrics (revenue, order counts,
average order value, etc.) directly using read-only SQL queries. Never calls Groq for math.
"""
from __future__ import annotations

from typing import Any
from sqlalchemy import text
from app.intelligence.schema_analyzer import quote_identifier
from app.intelligence.business_intelligence.models import BusinessContext, DiscoveredMetric


def discover_business_metrics(engine: Any, db_type: str, context: BusinessContext) -> list[DiscoveredMetric]:
    """
    Computes volume and aggregation metrics for discovered measures and entity tables.
    Returns a list of DiscoveredMetric objects with deterministic SQL expressions and values.
    """
    if engine is None or not context.has_sufficient_data:
        return []

    metrics: list[DiscoveredMetric] = []
    seen_metrics = set()

    with engine.connect() as conn:
        # 1. Entity Record Counts (Volumes)
        for entity in context.entity_tables:
            table_name = entity.get("table", "")
            row_count = entity.get("row_count", 0)
            if row_count <= 0:
                continue

            t_sql = quote_identifier(table_name, db_type)
            count_sql = f"SELECT COUNT(*) FROM {t_sql}"
            try:
                val = conn.execute(text(count_sql)).scalar()
                if val is not None:
                    count_val = float(val)
                    clean_name = table_name.rstrip("s").replace("_", " ").title()
                    metric_name = f"Total {clean_name}s" if not clean_name.endswith("s") else f"Total {clean_name}"
                    
                    time_col = entity.get("time_columns", [None])[0] if entity.get("time_columns") else None

                    metrics.append(
                        DiscoveredMetric(
                            name=metric_name,
                            source_table=table_name,
                            source_columns=["*"],
                            sql=count_sql,
                            current_value=count_val,
                            calculation_method="COUNT(*)",
                            timestamp_col=time_col,
                            confidence=1.0,
                        )
                    )
            except Exception:
                pass

        # 2. Measure Column Aggregations (SUM, AVG)
        for measure in context.measure_columns:
            table_name = measure.get("table", "")
            col_name = measure.get("column", "")
            key = (table_name, col_name)
            if key in seen_metrics:
                continue
            seen_metrics.add(key)

            t_sql = quote_identifier(table_name, db_type)
            c_sql = quote_identifier(col_name, db_type)

            # Find matching time column in table if any
            matching_time_col = None
            for tc in context.time_columns:
                if tc.get("table") == table_name:
                    matching_time_col = tc.get("column")
                    break

            # Safe aggregation SQL
            sum_sql = f"SELECT SUM({c_sql}) FROM {t_sql} WHERE {c_sql} IS NOT NULL"
            avg_sql = f"SELECT AVG({c_sql}) FROM {t_sql} WHERE {c_sql} IS NOT NULL"

            col_friendly = col_name.replace("_", " ").title()

            try:
                sum_res = conn.execute(text(sum_sql)).scalar()
                if sum_res is not None:
                    sum_val = round(float(sum_res), 2)
                    metrics.append(
                        DiscoveredMetric(
                            name=f"Total {col_friendly}",
                            source_table=table_name,
                            source_columns=[col_name],
                            sql=sum_sql,
                            current_value=sum_val,
                            calculation_method=f"SUM({col_name})",
                            timestamp_col=matching_time_col,
                            confidence=1.0,
                        )
                    )
            except Exception:
                pass

            try:
                avg_res = conn.execute(text(avg_sql)).scalar()
                if avg_res is not None:
                    avg_val = round(float(avg_res), 2)
                    metrics.append(
                        DiscoveredMetric(
                            name=f"Average {col_friendly}",
                            source_table=table_name,
                            source_columns=[col_name],
                            sql=avg_sql,
                            current_value=avg_val,
                            calculation_method=f"AVG({col_name})",
                            timestamp_col=matching_time_col,
                            confidence=1.0,
                        )
                    )
            except Exception:
                pass

    return metrics
