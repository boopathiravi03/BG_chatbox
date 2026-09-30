from __future__ import annotations

from typing import Any
from sqlalchemy import text
from app.intelligence.schema_analyzer import quote_identifier
from app.intelligence.models import DataQualitySummary


def audit_data_quality(engine, db_type: str, schema_info: dict[str, Any]) -> tuple[DataQualitySummary, dict[str, int], int]:
    """
    Safely audits row counts, null densities, empty tables, and orphan foreign keys.
    All operations are strictly READ-ONLY.
    Returns: (DataQualitySummary, table_row_counts_dict, total_rows)
    """
    tables_data = schema_info.get("tables", {})
    table_row_counts: dict[str, int] = {}
    total_rows = 0
    empty_tables: list[str] = []
    null_heavy_columns: list[dict[str, Any]] = []
    orphan_fks: list[dict[str, Any]] = []

    total_cells_checked = 0
    total_nulls_checked = 0

    table_schema_hashes: dict[tuple, list[str]] = {}

    with engine.connect() as conn:
        # 1. Fetch row count per table
        for table_name, meta in tables_data.items():
            t_sql = quote_identifier(table_name, db_type)
            row_count = 0
            try:
                sql = f"SELECT COUNT(*) FROM {t_sql}"
                res = conn.execute(text(sql)).scalar()
                row_count = int(res) if res is not None else 0
            except Exception:
                row_count = 0

            table_row_counts[table_name] = row_count
            meta["row_count"] = row_count
            total_rows += row_count

            if row_count == 0:
                empty_tables.append(table_name)

            # Check duplicate schema signature
            cols_signature = tuple(sorted([f"{c['name']}:{c['type']}" for c in meta.get("columns", [])]))
            if cols_signature:
                table_schema_hashes.setdefault(cols_signature, []).append(table_name)

            # 2. Check null ratios if table has rows (bounded to avoid huge table delays)
            if 0 < row_count <= 250000:
                for col in meta.get("columns", []):
                    c_name = col["name"]
                    c_sql = quote_identifier(c_name, db_type)
                    try:
                        null_sql = f"SELECT COUNT(*) FROM {t_sql} WHERE {c_sql} IS NULL"
                        null_count = int(conn.execute(text(null_sql)).scalar() or 0)
                        
                        total_cells_checked += row_count
                        total_nulls_checked += null_count

                        ratio = (null_count / row_count) * 100 if row_count > 0 else 0
                        if ratio >= 20.0:
                            null_heavy_columns.append({
                                "table": table_name,
                                "column": c_name,
                                "null_count": null_count,
                                "total_rows": row_count,
                                "null_percentage": round(ratio, 1),
                            })
                    except Exception:
                        pass
            elif row_count > 250000:
                # For very large tables, use a 5,000 row sample check
                for col in meta.get("columns", []):
                    c_name = col["name"]
                    c_sql = quote_identifier(c_name, db_type)
                    try:
                        sample_sql = f"SELECT COUNT(*) FROM (SELECT {c_sql} FROM {t_sql} LIMIT 5000) AS s WHERE {c_sql} IS NULL"
                        null_count = int(conn.execute(text(sample_sql)).scalar() or 0)
                        total_cells_checked += 5000
                        total_nulls_checked += null_count
                        ratio = (null_count / 5000) * 100
                        if ratio >= 20.0:
                            null_heavy_columns.append({
                                "table": table_name,
                                "column": c_name,
                                "null_count": null_count,
                                "total_rows": row_count,
                                "null_percentage": round(ratio, 1),
                                "is_sampled": True,
                            })
                    except Exception:
                        pass

        # 3. Detect Real Orphan Foreign Keys
        for rel in schema_info.get("relationships", []):
            src_table = rel.get("source_table")
            tgt_table = rel.get("target_table")
            src_cols = rel.get("source_columns") or []
            tgt_cols = rel.get("target_columns") or []

            if src_table and tgt_table and len(src_cols) == 1 and len(tgt_cols) == 1:
                # Check if target table actually exists
                if tgt_table in tables_data:
                    s_t_sql = quote_identifier(src_table, db_type)
                    t_t_sql = quote_identifier(tgt_table, db_type)
                    s_c_sql = quote_identifier(src_cols[0], db_type)
                    t_c_sql = quote_identifier(tgt_cols[0], db_type)

                    try:
                        orphan_sql = (
                            f"SELECT COUNT(*) FROM {s_t_sql} a "
                            f"WHERE a.{s_c_sql} IS NOT NULL "
                            f"AND NOT EXISTS (SELECT 1 FROM {t_t_sql} b WHERE b.{t_c_sql} = a.{s_c_sql})"
                        )
                        orphan_count = int(conn.execute(text(orphan_sql)).scalar() or 0)
                        if orphan_count > 0:
                            orphan_fks.append({
                                "source_table": src_table,
                                "foreign_key_column": src_cols[0],
                                "target_table": tgt_table,
                                "target_column": tgt_cols[0],
                                "orphan_count": orphan_count,
                            })
                    except Exception:
                        pass

    duplicate_schemas = [tables for tables in table_schema_hashes.values() if len(tables) > 1]
    overall_null_pct = round((total_nulls_checked / total_cells_checked) * 100, 2) if total_cells_checked > 0 else 0.0

    summary = DataQualitySummary(
        null_percentage=overall_null_pct,
        empty_tables=empty_tables,
        null_heavy_columns=null_heavy_columns,
        duplicate_table_schemas=duplicate_schemas,
        orphan_foreign_keys=orphan_fks,
    )

    return summary, table_row_counts, total_rows
