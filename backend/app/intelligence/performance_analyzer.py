from __future__ import annotations

from typing import Any
from app.intelligence.models import PerformanceFinding


def analyze_performance(schema_info: dict[str, Any], table_row_counts: dict[str, int]) -> list[PerformanceFinding]:
    """
    Identifies database performance signals such as unindexed foreign keys,
    missing primary keys, and large unindexed tables.
    """
    findings: list[PerformanceFinding] = []
    tables_data = schema_info.get("tables", {})

    for table_name, meta in tables_data.items():
        row_count = table_row_counts.get(table_name, 0)
        pk_columns = meta.get("pk_columns", [])
        indexes = meta.get("indexes", [])
        fks = meta.get("foreign_keys", [])

        # 1. Missing Primary Key
        if not pk_columns:
            findings.append(
                PerformanceFinding(
                    type="missing_primary_key",
                    table=table_name,
                    column=None,
                    description=f"Table '{table_name}' has no defined Primary Key. Row identity and clustered indexing are disabled.",
                    recommendation=f"Add a primary key identifier to '{table_name}' for faster lookups and deterministic updates.",
                )
            )

        # 2. Unindexed Foreign Keys
        # Build set of indexed columns
        indexed_cols: set[str] = set()
        for idx in indexes:
            for c in idx.get("column_names") or []:
                if c:
                    indexed_cols.add(c)
        # Primary keys are usually implicitly indexed
        for pk in pk_columns:
            indexed_cols.add(pk)

        for fk in fks:
            for src_col in fk.get("constrained_columns", []):
                if src_col not in indexed_cols:
                    findings.append(
                        PerformanceFinding(
                            type="unindexed_foreign_key",
                            table=table_name,
                            column=src_col,
                            description=f"Foreign key '{table_name}.{src_col}' has no index. JOIN and constraint verification queries will perform full table scans.",
                            recommendation=f"CREATE INDEX idx_{table_name}_{src_col} ON {table_name} ({src_col});",
                        )
                    )

        # 3. Large Table Scanning Warning
        if row_count > 500000 and len(indexes) <= 1:
            findings.append(
                PerformanceFinding(
                    type="table_scan_risk",
                    table=table_name,
                    column=None,
                    description=f"Table '{table_name}' contains {row_count:,} rows with minimal index coverage ({len(indexes)} index).",
                    recommendation=f"Analyze frequent filter columns on '{table_name}' and establish composite or B-tree indexes.",
                )
            )

    return findings
