"""
backend/app/intelligence/business_intelligence/business_context.py

Phase 8.1: Deterministic Business Context Discovery Layer
Infers entity tables, temporal fields, measures, dimensions, and relationships
directly from the connected database without assuming a specific business domain.
"""
from __future__ import annotations

from typing import Any, Optional
from sqlalchemy import text
from app.intelligence.schema_analyzer import quote_identifier, analyze_schema
from app.intelligence.business_intelligence.models import BusinessContext


ENTITY_KEYWORDS = {
    "customer", "user", "client", "account", "member", "contact",
    "product", "item", "inventory", "catalog", "sku", "service",
    "order", "invoice", "payment", "transaction", "sale", "purchase",
    "employee", "staff", "worker", "agent", "vendor", "supplier",
    "subscription", "booking", "shipment", "delivery", "bill", "lead"
}

TIME_KEYWORDS = {
    "created_at", "updated_at", "order_date", "transaction_date", "date",
    "timestamp", "created_date", "sold_at", "payment_date", "invoice_date",
    "closed_at", "due_date", "created", "modified", "joined_date", "event_time"
}

TIME_TYPES = {"date", "datetime", "timestamp", "time"}

MEASURE_KEYWORDS = {
    "amount", "price", "revenue", "total", "cost", "quantity", "qty",
    "salary", "balance", "budget", "discount", "fee", "rate", "value",
    "score", "tax", "margin", "profit", "spend", "subtotal", "gross"
}

NUMERIC_TYPES = {"int", "integer", "float", "decimal", "numeric", "real", "double", "bigint", "smallint"}

DIMENSION_KEYWORDS = {
    "category", "status", "region", "city", "state", "country", "department",
    "type", "role", "tier", "segment", "brand", "channel", "plan", "group",
    "priority", "gender", "level", "division", "source", "medium", "state_code"
}


def discover_business_context(engine: Any, db_type: str, schema_info: Optional[dict[str, Any]] = None) -> BusinessContext:
    """
    Deterministically analyzes tables, columns, and row counts to infer business context.
    Returns a BusinessContext object with sufficiency evaluation.
    """
    if engine is None or db_type == "none":
        return BusinessContext(
            has_sufficient_data=False,
            reason="No database connected.",
        )

    if schema_info is None:
        try:
            schema_info = analyze_schema(engine, db_type)
        except Exception as e:
            return BusinessContext(
                has_sufficient_data=False,
                reason=f"Failed to inspect database schema: {str(e)}",
            )

    tables_data = schema_info.get("tables", {})
    if not tables_data:
        return BusinessContext(
            has_sufficient_data=False,
            reason="No database tables found.",
        )

    entity_tables: list[dict[str, Any]] = []
    time_columns: list[dict[str, Any]] = []
    measure_columns: list[dict[str, Any]] = []
    dimension_columns: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    total_records = 0

    table_row_counts: dict[str, int] = {}

    with engine.connect() as conn:
        for table_name, meta in tables_data.items():
            t_sql = quote_identifier(table_name, db_type)
            # Count rows safely
            try:
                count_res = conn.execute(text(f"SELECT COUNT(*) FROM {t_sql}")).scalar()
                row_count = int(count_res) if count_res is not None else 0
            except Exception:
                row_count = 0

            table_row_counts[table_name] = row_count
            total_records += row_count

            t_lower = table_name.lower()
            is_entity_name = any(kw in t_lower for kw in ENTITY_KEYWORDS)
            cols = meta.get("columns", [])
            pk_cols = meta.get("pk_columns", [])
            fk_list = meta.get("foreign_keys", [])

            # Add relationships
            for fk in fk_list:
                relationships.append({
                    "from_table": table_name,
                    "from_column": fk.get("constrained_columns", []),
                    "to_table": fk.get("referred_table"),
                    "to_column": fk.get("referred_columns", []),
                })

            table_measures = []
            table_times = []
            table_dims = []

            for col in cols:
                c_name = col.get("name", "")
                c_type = col.get("type", "").lower()
                c_lower = c_name.lower()

                # Check Temporal
                is_time_type = any(tt in c_type for tt in TIME_TYPES)
                is_time_name = any(kw in c_lower for kw in TIME_KEYWORDS) or c_lower.endswith("_at") or c_lower.endswith("_date")
                if is_time_type or is_time_name:
                    time_info = {
                        "table": table_name,
                        "column": c_name,
                        "type": c_type,
                    }
                    time_columns.append(time_info)
                    table_times.append(time_info)

                # Check Measure (Numeric + keyword or appropriate name, skip PK/FKs)
                is_numeric = any(nt in c_type for nt in NUMERIC_TYPES)
                is_pk_or_fk = c_lower == "id" or c_lower.endswith("_id") or c_name in pk_cols
                is_measure_name = any(kw in c_lower for kw in MEASURE_KEYWORDS)

                if is_numeric and not is_pk_or_fk and (is_measure_name or is_entity_name):
                    measure_info = {
                        "table": table_name,
                        "column": c_name,
                        "type": c_type,
                    }
                    measure_columns.append(measure_info)
                    table_measures.append(measure_info)

                # Check Dimension (Categorical / text or status)
                is_dim_name = any(kw in c_lower for kw in DIMENSION_KEYWORDS)
                is_text_type = any(st in c_type for st in ["char", "text", "varchar", "string"])
                if (is_dim_name or (is_text_type and not is_pk_or_fk)) and not is_time_name:
                    dim_info = {
                        "table": table_name,
                        "column": c_name,
                        "type": c_type,
                    }
                    dimension_columns.append(dim_info)
                    table_dims.append(dim_info)

            # Classify as entity table if matched name or has meaningful measures/dimensions with rows
            if is_entity_name or (row_count > 0 and (table_measures or table_dims)):
                entity_tables.append({
                    "table": table_name,
                    "row_count": row_count,
                    "measure_count": len(table_measures),
                    "time_columns": [t["column"] for t in table_times],
                    "dimension_columns": [d["column"] for d in table_dims],
                })

    # Evaluate sufficiency
    if total_records == 0:
        return BusinessContext(
            entity_tables=entity_tables,
            time_columns=time_columns,
            measure_columns=measure_columns,
            dimension_columns=dimension_columns,
            relationships=relationships,
            total_records=0,
            has_sufficient_data=False,
            reason="No records available for business intelligence.",
        )

    if total_records < 2:
        return BusinessContext(
            entity_tables=entity_tables,
            time_columns=time_columns,
            measure_columns=measure_columns,
            dimension_columns=dimension_columns,
            relationships=relationships,
            total_records=total_records,
            has_sufficient_data=False,
            reason="Database connected, but insufficient records for automatic business insights.",
        )

    if not measure_columns and not entity_tables:
        return BusinessContext(
            entity_tables=entity_tables,
            time_columns=time_columns,
            measure_columns=measure_columns,
            dimension_columns=dimension_columns,
            relationships=relationships,
            total_records=total_records,
            has_sufficient_data=False,
            reason="Insufficient business data for automatic insight generation.",
        )

    return BusinessContext(
        entity_tables=entity_tables,
        time_columns=time_columns,
        measure_columns=measure_columns,
        dimension_columns=dimension_columns,
        relationships=relationships,
        total_records=total_records,
        has_sufficient_data=True,
    )
