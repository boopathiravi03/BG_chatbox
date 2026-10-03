"""
backend/app/intelligence/knowledge/metric_registry.py

Phase 9.1: Business Metric Registry & Context-Aware Calculation
Maintains enterprise metric definitions, binds confirmed business rules,
and resolves context-aware formulas with full calculation lineage.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from app.intelligence.schema_analyzer import analyze_schema, quote_identifier
from app.intelligence.business_intelligence.business_context import MEASURE_KEYWORDS, NUMERIC_TYPES
from app.intelligence.knowledge.models import (
    BusinessMetric,
    KnowledgeProvenance,
    KnowledgeStatus,
)
from app.intelligence.knowledge.knowledge_store import (
    save_metric,
    get_metric,
    list_metrics,
    list_rules,
)
from app.intelligence.knowledge.business_rules import get_active_filters_for_table

logger = logging.getLogger("bgai.knowledge.metric_registry")


def discover_and_sync_metrics(
    engine: Any,
    db_type: str,
    user_id: str,
    database_identity: str,
) -> list[BusinessMetric]:
    """
    Discovers candidate metrics from tables and numeric columns.
    Applies active confirmed rules to candidate metrics.
    Preserves user-defined or previously saved metrics.
    """
    if engine is None or db_type == "none":
        return list_metrics(user_id=user_id, database_identity=database_identity)

    schema_info = analyze_schema(engine, db_type)
    tables = schema_info.get("tables", {})
    if not tables:
        return list_metrics(user_id=user_id, database_identity=database_identity)

    existing_metrics = {f"{m.table_name}.{m.column_name or '*'}_{m.aggregation}": m for m in list_metrics(user_id=user_id, database_identity=database_identity)}
    discovered: list[BusinessMetric] = []

    for tbl_name, tbl_meta in tables.items():
        cols = tbl_meta.get("columns", [])
        active_filters = get_active_filters_for_table(tbl_name, user_id, database_identity)
        filter_expr = " AND ".join(active_filters) if active_filters else None

        # 1. Row count metric for the table
        count_key = f"{tbl_name}.*_COUNT"
        if count_key in existing_metrics:
            discovered.append(existing_metrics[count_key])
        else:
            m_count = BusinessMetric(
                metric_id=f"met_{tbl_name}_count",
                name=f"{tbl_name.replace('_', ' ').title()} Count",
                description=f"Total count of records in table '{tbl_name}'.",
                table_name=tbl_name,
                column_name=None,
                aggregation="COUNT",
                filter_expression=filter_expr,
                conditions=active_filters,
                rules_applied=[],
                version=1,
                provenance=KnowledgeProvenance.SCHEMA_DERIVED.value,
                status=KnowledgeStatus.PROPOSED.value,
                confidence=0.9,
                user_id=user_id,
                database_identity=database_identity,
            )
            saved = save_metric(m_count)
            discovered.append(saved)

        # 2. Measures from numeric columns
        for c in cols:
            c_name = c.get("name") if isinstance(c, dict) else str(c)
            c_type = c.get("type", "").lower() if isinstance(c, dict) else ""

            is_numeric = any(nt in c_type for nt in NUMERIC_TYPES) or any(mk in c_name.lower() for mk in MEASURE_KEYWORDS)
            if is_numeric and not c_name.lower().endswith(("_id", "id", "_key", "key")):
                sum_key = f"{tbl_name}.{c_name}_SUM"
                if sum_key in existing_metrics:
                    discovered.append(existing_metrics[sum_key])
                else:
                    metric_title = c_name.replace("_", " ").title()
                    if "revenue" in c_name.lower() or "amount" in c_name.lower():
                        display_name = f"Total {metric_title}"
                    else:
                        display_name = f"Sum of {metric_title}"

                    m_sum = BusinessMetric(
                        metric_id=f"met_{tbl_name}_{c_name}_sum",
                        name=display_name,
                        description=f"Sum of {c_name} in table '{tbl_name}'.",
                        table_name=tbl_name,
                        column_name=c_name,
                        aggregation="SUM",
                        filter_expression=filter_expr,
                        conditions=active_filters,
                        rules_applied=[],
                        version=1,
                        provenance=KnowledgeProvenance.SCHEMA_DERIVED.value,
                        status=KnowledgeStatus.PROPOSED.value,
                        confidence=0.85,
                        user_id=user_id,
                        database_identity=database_identity,
                    )
                    saved = save_metric(m_sum)
                    discovered.append(saved)

    return discovered


def resolve_metric_calculation(
    metric_id_or_name: str,
    table_name: str,
    column_name: Optional[str],
    user_id: str,
    database_identity: str,
    db_type: str = "sqlite",
) -> dict[str, Any]:
    """
    Resolves the exact SQL calculation expression for a metric, incorporating
    active confirmed business rules and detailing whether confirmed rules altered the formula.
    """
    # Look up defined metric if available
    defined_metric = get_metric(metric_id_or_name, user_id=user_id, database_identity=database_identity)
    if not defined_metric:
        # Search by name and table
        metrics = list_metrics(user_id=user_id, database_identity=database_identity, table_name=table_name)
        for m in metrics:
            if m.name.lower() == metric_id_or_name.lower() or (m.column_name == column_name and column_name is not None):
                defined_metric = m
                break

    target_table = defined_metric.table_name if defined_metric else table_name
    target_column = defined_metric.column_name if defined_metric else column_name
    aggregation = defined_metric.aggregation if defined_metric else "SUM"

    # Get active confirmed filters
    active_filters = get_active_filters_for_table(target_table, user_id=user_id, database_identity=database_identity)

    # Construct SQL expressions
    t_quoted = quote_identifier(target_table, db_type)
    if target_column:
        c_quoted = quote_identifier(target_column, db_type)
        base_expr = f"{aggregation}({c_quoted})"
        base_where = [f"{c_quoted} IS NOT NULL"]
    else:
        base_expr = "COUNT(*)"
        base_where = []

    rules_applied = []
    if active_filters:
        base_where.extend(active_filters)
        rules_applied = active_filters

    where_clause = f" WHERE {' AND '.join(base_where)}" if base_where else ""
    full_sql = f"SELECT {base_expr} AS metric_val FROM {t_quoted}{where_clause}"

    return {
        "metric_name": defined_metric.name if defined_metric else metric_id_or_name,
        "table_name": target_table,
        "column_name": target_column,
        "aggregation": aggregation,
        "sql_expression": full_sql,
        "filter_expression": " AND ".join(active_filters) if active_filters else None,
        "rules_applied": rules_applied,
        "has_confirmed_rules": len(rules_applied) > 0,
        "status": defined_metric.status if defined_metric else KnowledgeStatus.PROPOSED.value,
        "provenance": defined_metric.provenance if defined_metric else KnowledgeProvenance.SCHEMA_DERIVED.value,
        "version": defined_metric.version if defined_metric else 1,
    }
