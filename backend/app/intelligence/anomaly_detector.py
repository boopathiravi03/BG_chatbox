from __future__ import annotations

from typing import Any
from app.intelligence.models import (
    AttentionItem,
    DataQualitySummary,
    PerformanceFinding,
    BusinessMetric,
)


def synthesize_attention_items(
    schema_info: dict[str, Any],
    data_quality: DataQualitySummary,
    performance_findings: list[PerformanceFinding],
    business_metrics: list[BusinessMetric],
    table_row_counts: dict[str, int],
) -> list[AttentionItem]:
    """
    Synthesizes findings from schema, data quality, performance, and business analysis
    into a prioritized list of actionable Attention Items for the Command Center.
    Categories: critical (🔴), warning (🟠), performance (🟡), insight (🔵), healthy (🟢)
    """
    items: list[AttentionItem] = []

    # 1. Critical Items: Orphan Foreign Keys & Broken Referential Integrity
    for orphan in data_quality.orphan_foreign_keys:
        items.append(
            AttentionItem(
                id=f"crit_orphan_{orphan['source_table']}_{orphan['foreign_key_column']}",
                category="critical",
                title=f"Referential Integrity Breach: {orphan['orphan_count']} Orphan Records",
                description=(
                    f"Table '{orphan['source_table']}' contains {orphan['orphan_count']} records where "
                    f"'{orphan['foreign_key_column']}' does not exist in target table '{orphan['target_table']}'."
                ),
                table=orphan["source_table"],
                column=orphan["foreign_key_column"],
                target_module="health",
            )
        )

    # 2. Critical Items: Missing Primary Keys
    for perf in performance_findings:
        if perf.type == "missing_primary_key":
            items.append(
                AttentionItem(
                    id=f"crit_pk_{perf.table}",
                    category="critical",
                    title=f"Missing Primary Key on '{perf.table}'",
                    description=perf.description,
                    table=perf.table,
                    target_module="health",
                )
            )

    # 3. Warnings: Null-heavy columns (>20% null)
    for nh in data_quality.null_heavy_columns:
        items.append(
            AttentionItem(
                id=f"warn_null_{nh['table']}_{nh['column']}",
                category="warning",
                title=f"High NULL Density: '{nh['table']}.{nh['column']}' ({nh['null_percentage']}%)",
                description=(
                    f"Column '{nh['column']}' in table '{nh['table']}' has {nh['null_count']:,} NULL values "
                    f"out of {nh['total_rows']:,} records."
                ),
                table=nh["table"],
                column=nh["column"],
                target_module="health",
            )
        )

    # 4. Warnings: Empty tables
    for empty_t in data_quality.empty_tables:
        items.append(
            AttentionItem(
                id=f"warn_empty_{empty_t}",
                category="warning",
                title=f"Empty Entity Table: '{empty_t}' (0 rows)",
                description=f"Table '{empty_t}' is defined in the schema but contains zero records.",
                table=empty_t,
                target_module="explorer",
            )
        )

    # 5. Performance Signals: Unindexed Foreign Keys
    for perf in performance_findings:
        if perf.type == "unindexed_foreign_key":
            items.append(
                AttentionItem(
                    id=f"perf_idx_{perf.table}_{perf.column}",
                    category="performance",
                    title=f"Unindexed Foreign Key on '{perf.table}.{perf.column}'",
                    description=perf.description,
                    table=perf.table,
                    column=perf.column,
                    target_module="sqllab",
                )
            )

    # 6. Insights: Business metrics discovered
    for bm in business_metrics[:3]:
        items.append(
            AttentionItem(
                id=f"insight_metric_{bm.table}_{bm.column}",
                category="insight",
                title=f"{bm.label}: {bm.value}",
                description=f"Discovered measurable metric from '{bm.table}.{bm.column}' computed via {bm.calculation}.",
                table=bm.table,
                column=bm.column,
                target_module="analytics",
            )
        )

    # 7. Healthy State: If no critical or warning issues detected
    critical_or_warnings = [i for i in items if i.category in ["critical", "warning"]]
    if not critical_or_warnings:
        items.append(
            AttentionItem(
                id="health_ok_integrity",
                category="healthy",
                title="Referential & Structural Integrity Verified",
                description="All table primary keys and foreign key references are intact with no broken constraints.",
                target_module="health",
            )
        )

    return items
