from __future__ import annotations

from typing import Any
from sqlalchemy import text
from app.intelligence.schema_analyzer import quote_identifier
from app.intelligence.models import BusinessMetric


MEASURE_KEYWORDS = {
    "price", "amount", "total", "cost", "revenue", "sales", "fee", "rate",
    "quantity", "qty", "balance", "discount", "tax", "salary", "budget", "value"
}


def discover_business_metrics(engine, db_type: str, schema_info: dict[str, Any], table_row_counts: dict[str, int]) -> list[BusinessMetric]:
    """
    Identifies numeric measure columns and executes safe, bounded read-only aggregates (SUM, AVG).
    Never invents numbers; returns only verified calculations from the connected database.
    """
    metrics: list[BusinessMetric] = []
    tables_data = schema_info.get("tables", {})

    with engine.connect() as conn:
        for table_name, meta in tables_data.items():
            row_count = table_row_counts.get(table_name, 0)
            if row_count == 0:
                continue

            for col in meta.get("columns", []):
                col_name = col.get("name", "")
                col_type = col.get("type", "").lower()
                c_lower = col_name.lower()

                # Check if column is a numeric measurement
                is_numeric_type = any(t in col_type for t in ["int", "float", "decimal", "numeric", "real", "double"])
                has_measure_name = any(kw in c_lower for kw in MEASURE_KEYWORDS)

                # Skip obvious IDs or timestamps
                if c_lower.endswith("_id") or c_lower == "id" or "date" in c_lower or "time" in c_lower:
                    continue

                if is_numeric_type and has_measure_name:
                    t_sql = quote_identifier(table_name, db_type)
                    c_sql = quote_identifier(col_name, db_type)

                    try:
                        sql = f"SELECT SUM({c_sql}), AVG({c_sql}) FROM {t_sql}"
                        row = conn.execute(text(sql)).fetchone()
                        if row and row[0] is not None:
                            val_sum = float(row[0])
                            val_avg = float(row[1]) if row[1] is not None else 0.0

                            friendly_name = col_name.replace("_", " ").title()
                            metrics.append(
                                BusinessMetric(
                                    label=f"Total {friendly_name}",
                                    value=f"{val_sum:,.2f}",
                                    table=table_name,
                                    column=col_name,
                                    calculation=f"SUM({table_name}.{col_name})",
                                )
                            )

                            if row_count > 1 and val_avg > 0:
                                metrics.append(
                                    BusinessMetric(
                                        label=f"Avg {friendly_name}",
                                        value=f"{val_avg:,.2f}",
                                        table=table_name,
                                        column=col_name,
                                        calculation=f"AVG({table_name}.{col_name})",
                                    )
                                )

                    except Exception:
                        pass

    return metrics[:10]  # Cap at top 10 relevant measures
