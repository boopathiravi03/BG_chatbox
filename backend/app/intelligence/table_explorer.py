from __future__ import annotations

import re
from datetime import datetime, date
from typing import Any
from sqlalchemy import text
from app.database.database_manager import get_engine, get_current_db_type
from app.intelligence.schema_analyzer import quote_identifier
from app.intelligence.scanner import get_cached_report, run_database_intelligence_scan


def classify_semantic_type(column_name: str, sql_type: str) -> str:
    """
    Classifies a column into semantic business/data categories
    based on column name patterns and underlying SQL data types.
    Strictly deterministic and non-destructive.
    """
    c_lower = column_name.lower()
    t_upper = sql_type.upper()

    # 1. Primary / Foreign Identifiers
    if c_lower in ("id", "uuid", "guid", "code", "sku") or c_lower.endswith("_id") or c_lower.endswith("_uuid"):
        return "Identifier"

    # 2. Boolean flags
    if (
        c_lower.startswith("is_")
        or c_lower.startswith("has_")
        or c_lower.startswith("can_")
        or c_lower in ("active", "enabled", "archived", "deleted", "flag")
        or "BOOL" in t_upper
        or t_upper == "TINYINT(1)"
    ):
        return "Boolean"

    # 3. Email
    if "email" in c_lower or "e_mail" in c_lower:
        return "Email"

    # 4. Phone
    if any(k in c_lower for k in ("phone", "mobile", "telephone", "tel", "fax")):
        return "Phone"

    # 5. Address / Location
    if any(k in c_lower for k in ("address", "city", "state", "country", "postal", "zip", "street", "province", "latitude", "longitude", "lat", "lng")):
        return "Address"

    # 6. Currency / Monetary
    if any(k in c_lower for k in ("price", "amount", "revenue", "cost", "salary", "total", "subtotal", "tax", "discount", "fee", "budget", "balance")):
        return "Currency"

    # 7. Quantity / Volume
    if any(k in c_lower for k in ("qty", "quantity", "count", "stock", "inventory", "units", "items", "views", "clicks")):
        return "Quantity"

    # 8. Date / Timestamp
    if (
        "TIME" in t_upper
        or "DATE" in t_upper
        or any(c_lower.endswith(k) for k in ("_at", "_date", "_time", "timestamp"))
        or c_lower in ("created_at", "updated_at", "deleted_at", "published_at", "start_date", "end_date", "dob", "birth_date")
    ):
        return "Timestamp" if "TIME" in t_upper or c_lower.endswith("_at") else "Date"

    # 9. Status / Stage
    if any(k in c_lower for k in ("status", "stage", "state", "category", "type", "role", "priority", "level", "tier")):
        return "Status"

    # 10. Long text / Description
    if any(k in c_lower for k in ("desc", "description", "comment", "note", "notes", "body", "content", "summary", "text", "bio", "details")):
        return "Description"

    # 11. Name
    if any(k in c_lower for k in ("name", "first_name", "last_name", "full_name", "username", "title")):
        return "Name"

    # 12. Generic type fallbacks
    if any(k in t_upper for k in ("INT", "FLOAT", "DOUBLE", "DECIMAL", "NUMERIC", "REAL", "BIGINT")):
        return "Numeric"

    if any(k in t_upper for k in ("CHAR", "VARCHAR", "TEXT", "CLOB", "STRING")):
        return "Text"

    return "Unknown"


def get_table_profile(table_name: str) -> dict[str, Any]:
    """
    Returns an enriched profile for a specific table:
    - Metadata (columns, PKs, FKs, types)
    - Row count & column count
    - Column breakdown (numeric, text, date, boolean, nullable)
    - Relationships (incoming and outgoing)
    - Health status and reasons derived from Phase 1 intelligence
    - Accurate, non-hallucinated summary
    """
    report = get_cached_report()
    if report is None or not report.schema_summary:
        report = run_database_intelligence_scan(force_refresh=False)

    tables_meta = report.schema_summary
    if table_name not in tables_meta:
        raise ValueError(f"Table '{table_name}' does not exist in the connected database.")

    t_meta = tables_meta[table_name]
    raw_columns = t_meta.get("columns", [])
    pk_columns = t_meta.get("pk_columns", [])
    outgoing_fks = t_meta.get("foreign_keys", [])

    # Find incoming foreign keys across other tables
    incoming_fks = []
    for other_table, other_meta in tables_meta.items():
        if other_table == table_name:
            continue
        for fk in other_meta.get("foreign_keys", []):
            if fk.get("referred_table") == table_name:
                incoming_fks.append({
                    "referencing_table": other_table,
                    "foreign_key_columns": fk.get("constrained_columns", []),
                    "referenced_columns": fk.get("referred_columns", []),
                })

    # Prepare quick lookup for outgoing FKs: col_name -> target
    fk_targets: dict[str, str] = {}
    formatted_outgoing_fks = []
    for fk in outgoing_fks:
        ref_table = fk.get("referred_table", "")
        c_cols = fk.get("constrained_columns", [])
        r_cols = fk.get("referred_columns", [])
        if ref_table and c_cols:
            for i, col in enumerate(c_cols):
                target_col = r_cols[i] if i < len(r_cols) else "id"
                fk_targets[col] = f"{ref_table}.{target_col}"
            formatted_outgoing_fks.append({
                "foreign_key_columns": c_cols,
                "referred_table": ref_table,
                "referred_columns": r_cols,
            })

    # Find data quality & attention findings affecting this table
    health_reasons: list[str] = []
    has_critical = False
    has_warning = False

    for item in report.attention_items:
        if getattr(item, "table", None) == table_name:
            health_reasons.append(item.description)
            if item.category == "critical":
                has_critical = True
            elif item.category in ("warning", "performance"):
                has_warning = True

    if has_critical:
        health_status = "critical"
    elif has_warning:
        health_status = "warning"
    else:
        health_status = "healthy"

    # Pre-map null heavy columns for this table from Phase 1 data quality
    null_heavy_map: dict[str, float] = {}
    for nh in getattr(report.data_quality, "null_heavy_columns", []):
        if nh.get("table") == table_name:
            null_heavy_map[nh.get("column", "")] = nh.get("null_percentage", 0.0)

    # Column breakdown
    breakdown = {
        "numeric": 0,
        "text": 0,
        "datetime": 0,
        "boolean": 0,
        "nullable": 0,
    }

    columns_enriched = []
    for col in raw_columns:
        c_name = col.get("name", "")
        c_type = col.get("type", "TEXT")
        is_pk = col.get("is_pk", False) or c_name in pk_columns
        is_fk = c_name in fk_targets
        nullable = col.get("nullable", True)
        sem_type = classify_semantic_type(c_name, c_type)

        if nullable:
            breakdown["nullable"] += 1

        if sem_type in ("Numeric", "Currency", "Quantity"):
            breakdown["numeric"] += 1
        elif sem_type in ("Text", "Email", "Phone", "Address", "Description", "Name", "Status"):
            breakdown["text"] += 1
        elif sem_type in ("Date", "Timestamp"):
            breakdown["datetime"] += 1
        elif sem_type == "Boolean":
            breakdown["boolean"] += 1

        null_pct = null_heavy_map.get(c_name, 0.0)

        columns_enriched.append({
            "name": c_name,
            "type": c_type,
            "semantic_type": sem_type,
            "is_pk": is_pk,
            "is_fk": is_fk,
            "fk_target": fk_targets.get(c_name),
            "nullable": nullable,
            "default": str(col.get("default", "")) if col.get("default") is not None else None,
            "null_percentage": null_pct,
        })

    row_count = t_meta.get("row_count", 0)

    # Build factual AI summary
    summary_parts = []
    summary_parts.append(
        f"`{table_name}` contains {row_count:,} records across {len(raw_columns)} defined columns."
    )
    if pk_columns:
        summary_parts.append(f"Primary key is `{', '.join(pk_columns)}`.")
    else:
        summary_parts.append("No primary key is explicitly defined on this table.")

    if outgoing_fks:
        targets = [fk.get('referred_table') for fk in outgoing_fks if fk.get('referred_table')]
        if targets:
            summary_parts.append(f"It establishes relationships with {', '.join(set(targets))}.")

    if incoming_fks:
        sources = [fk.get('referencing_table') for fk in incoming_fks if fk.get('referencing_table')]
        if sources:
            summary_parts.append(f"It is referenced by {', '.join(set(sources))}.")

    if health_status == "healthy":
        summary_parts.append("The table passes all referential integrity and data quality health checks.")
    else:
        top_reasons = "; ".join(health_reasons[:2])
        summary_parts.append(f"Attention needed: {top_reasons}.")

    ai_summary = " ".join(summary_parts)

    return {
        "table_name": table_name,
        "database": report.database_name,
        "database_type": report.database_type,
        "row_count": row_count,
        "column_count": len(raw_columns),
        "primary_keys": pk_columns,
        "outgoing_foreign_keys": formatted_outgoing_fks,
        "incoming_foreign_keys": incoming_fks,
        "health_status": health_status,
        "health_reasons": health_reasons,
        "column_type_breakdown": breakdown,
        "columns": columns_enriched,
        "ai_summary": ai_summary,
    }


def get_table_sample(
    table_name: str,
    limit: int = 25,
    offset: int = 0,
    sort_by: str | None = None,
    sort_dir: str = "asc",
    search: str | None = None,
) -> dict[str, Any]:
    """
    Safely retrieves a paginated sample of records for the specified table.
    Enforces strict read-only constraints, identifier quoting, and limits.
    """
    engine = get_engine()
    db_type = get_current_db_type()

    if engine is None or db_type == "none":
        raise ValueError("No database is currently connected.")

    # Validate table existence in schema
    report = get_cached_report()
    if report is None or not report.schema_summary:
        report = run_database_intelligence_scan(force_refresh=False)

    if table_name not in report.schema_summary:
        raise ValueError(f"Table '{table_name}' does not exist.")

    table_meta = report.schema_summary[table_name]
    valid_cols = [c.get("name") for c in table_meta.get("columns", [])]
    total_table_rows = table_meta.get("row_count", 0)

    # Sanitize pagination parameters
    safe_limit = min(max(1, limit), 100)
    safe_offset = max(0, offset)
    safe_sort_dir = "ASC" if str(sort_dir).lower() == "asc" else "DESC"

    t_quoted = quote_identifier(table_name, db_type)

    # Build SQL query safely
    params: dict[str, Any] = {"limit": safe_limit, "offset": safe_offset}
    where_clauses = []

    # Safe text search across string/text columns
    if search and search.strip():
        search_term = f"%{search.strip()}%"
        params["search_term"] = search_term
        text_cols = [
            c["name"] for c in table_meta.get("columns", [])
            if any(k in c.get("type", "").upper() for k in ("CHAR", "VARCHAR", "TEXT", "CLOB", "STRING"))
        ]
        if text_cols:
            or_parts = []
            for col in text_cols[:5]:  # limit to top 5 text cols to keep query performant
                col_quoted = quote_identifier(col, db_type)
                or_parts.append(f"{col_quoted} LIKE :search_term")
            if or_parts:
                where_clauses.append(f"({' OR '.join(or_parts)})")

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    order_by_sql = ""
    if sort_by and sort_by in valid_cols:
        col_quoted = quote_identifier(sort_by, db_type)
        order_by_sql = f"ORDER BY {col_quoted} {safe_sort_dir}"

    sql = f"SELECT * FROM {t_quoted} {where_sql} {order_by_sql} LIMIT :limit OFFSET :offset"

    # Count query if filter applied
    total_matching_rows = total_table_rows
    with engine.connect() as conn:
        if where_clauses:
            count_sql = f"SELECT COUNT(*) FROM {t_quoted} {where_sql}"
            try:
                res_count = conn.execute(text(count_sql), {"search_term": params.get("search_term")}).scalar()
                total_matching_rows = int(res_count or 0)
            except Exception:
                total_matching_rows = total_table_rows

        cursor = conn.execute(text(sql), params)
        cols = list(cursor.keys())
        raw_rows = cursor.fetchall()

    # Serialize rows safely (handle dates, timestamps, bytes, decimals)
    serialized_rows = []
    for r in raw_rows:
        row_list = []
        for val in r:
            if val is None:
                row_list.append(None)
            elif isinstance(val, (datetime, date)):
                row_list.append(val.isoformat())
            elif isinstance(val, bytes):
                row_list.append(f"<blob {len(val)} bytes>")
            elif isinstance(val, (int, float, bool, str)):
                row_list.append(val)
            else:
                row_list.append(str(val))
        serialized_rows.append(row_list)

    return {
        "table_name": table_name,
        "total_rows": total_matching_rows,
        "limit": safe_limit,
        "offset": safe_offset,
        "columns": cols,
        "rows": serialized_rows,
    }


def get_column_profile(table_name: str, column_name: str) -> dict[str, Any]:
    """
    Computes bounded, type-specific statistical profiles for a specific column.
    All queries are strictly READ-ONLY and bounded to avoid hanging on large tables.
    """
    engine = get_engine()
    db_type = get_current_db_type()

    if engine is None or db_type == "none":
        raise ValueError("No database is currently connected.")

    report = get_cached_report()
    if report is None or not report.schema_summary:
        report = run_database_intelligence_scan(force_refresh=False)

    if table_name not in report.schema_summary:
        raise ValueError(f"Table '{table_name}' does not exist.")

    table_meta = report.schema_summary[table_name]
    col_meta = next((c for c in table_meta.get("columns", []) if c.get("name") == column_name), None)

    if not col_meta:
        raise ValueError(f"Column '{column_name}' does not exist in table '{table_name}'.")

    c_type = col_meta.get("type", "TEXT")
    sem_type = classify_semantic_type(column_name, c_type)
    t_quoted = quote_identifier(table_name, db_type)
    c_quoted = quote_identifier(column_name, db_type)

    total_table_rows = table_meta.get("row_count", 0)

    # Base profile dictionary
    profile: dict[str, Any] = {
        "table_name": table_name,
        "column_name": column_name,
        "sql_type": c_type,
        "semantic_type": sem_type,
        "nullable": col_meta.get("nullable", True),
        "is_pk": col_meta.get("is_pk", False),
        "total_rows": total_table_rows,
        "null_count": None,
        "null_percentage": None,
        "distinct_count": None,
        "statistics": {},
    }

    if total_table_rows == 0:
        profile["null_count"] = 0
        profile["null_percentage"] = 0.0
        profile["distinct_count"] = 0
        return profile

    with engine.connect() as conn:
        # 1. Null count & Distinct count (bounded)
        try:
            sql_counts = f"""
                SELECT 
                    COUNT(*) as total_c,
                    COUNT({c_quoted}) as non_null_c,
                    COUNT(DISTINCT {c_quoted}) as distinct_c
                FROM {t_quoted}
            """
            res = conn.execute(text(sql_counts)).mappings().first()
            if res:
                total_c = res["total_c"]
                non_null_c = res["non_null_c"]
                null_c = total_c - non_null_c
                profile["null_count"] = null_c
                profile["null_percentage"] = round((null_c / total_c) * 100, 2) if total_c > 0 else 0.0
                profile["distinct_count"] = res["distinct_c"]
        except Exception:
            profile["null_count"] = "Not calculated"
            profile["null_percentage"] = "Not calculated"
            profile["distinct_count"] = "Not calculated"

        # 2. Type-specific deep statistics
        stats: dict[str, Any] = {}

        # Numeric statistics (Min, Max, Avg)
        if sem_type in ("Numeric", "Currency", "Quantity"):
            try:
                num_sql = f"""
                    SELECT 
                        MIN({c_quoted}) as min_val,
                        MAX({c_quoted}) as max_val,
                        AVG({c_quoted}) as avg_val
                    FROM {t_quoted}
                    WHERE {c_quoted} IS NOT NULL
                """
                row = conn.execute(text(num_sql)).mappings().first()
                if row:
                    min_val = row["min_val"]
                    max_val = row["max_val"]
                    avg_val = row["avg_val"]
                    stats["min"] = float(min_val) if isinstance(min_val, (int, float)) else min_val
                    stats["max"] = float(max_val) if isinstance(max_val, (int, float)) else max_val
                    stats["avg"] = round(float(avg_val), 2) if avg_val is not None else None
            except Exception:
                stats["numeric_stats"] = "Not calculated"

        # Text statistics (Min/Max/Avg length, top frequent values)
        elif sem_type in ("Text", "Email", "Phone", "Address", "Description", "Name", "Status", "Identifier"):
            try:
                # Length query
                len_func = "CHAR_LENGTH" if db_type == "mysql" else "LENGTH"
                len_sql = f"""
                    SELECT 
                        MIN({len_func}({c_quoted})) as min_len,
                        MAX({len_func}({c_quoted})) as max_len,
                        AVG({len_func}({c_quoted})) as avg_len
                    FROM {t_quoted}
                    WHERE {c_quoted} IS NOT NULL
                """
                len_row = conn.execute(text(len_sql)).mappings().first()
                if len_row:
                    stats["min_length"] = len_row["min_len"]
                    stats["max_length"] = len_row["max_len"]
                    stats["avg_length"] = round(float(len_row["avg_len"]), 1) if len_row["avg_len"] is not None else None

                # Top 5 frequent values
                top_sql = f"""
                    SELECT {c_quoted} as val, COUNT(*) as cnt
                    FROM {t_quoted}
                    WHERE {c_quoted} IS NOT NULL
                    GROUP BY {c_quoted}
                    ORDER BY cnt DESC
                    LIMIT 5
                """
                top_rows = conn.execute(text(top_sql)).fetchall()
                stats["top_values"] = [{"value": str(r[0]), "count": int(r[1])} for r in top_rows]
            except Exception:
                stats["text_stats"] = "Not calculated"

        # Date / Timestamp statistics
        elif sem_type in ("Date", "Timestamp"):
            try:
                date_sql = f"""
                    SELECT 
                        MIN({c_quoted}) as min_d,
                        MAX({c_quoted}) as max_d
                    FROM {t_quoted}
                    WHERE {c_quoted} IS NOT NULL
                """
                date_row = conn.execute(text(date_sql)).mappings().first()
                if date_row:
                    min_d = date_row["min_d"]
                    max_d = date_row["max_d"]
                    stats["earliest_date"] = min_d.isoformat() if isinstance(min_d, (datetime, date)) else str(min_d)
                    stats["latest_date"] = max_d.isoformat() if isinstance(max_d, (datetime, date)) else str(max_d)
            except Exception:
                stats["date_stats"] = "Not calculated"

        # Boolean statistics
        elif sem_type == "Boolean":
            try:
                bool_sql = f"""
                    SELECT 
                        SUM(CASE WHEN {c_quoted} = 1 OR {c_quoted} IS TRUE THEN 1 ELSE 0 END) as true_cnt,
                        SUM(CASE WHEN {c_quoted} = 0 OR {c_quoted} IS FALSE THEN 1 ELSE 0 END) as false_cnt
                    FROM {t_quoted}
                    WHERE {c_quoted} IS NOT NULL
                """
                bool_row = conn.execute(text(bool_sql)).mappings().first()
                if bool_row:
                    stats["true_count"] = int(bool_row["true_cnt"] or 0)
                    stats["false_count"] = int(bool_row["false_cnt"] or 0)
            except Exception:
                stats["boolean_stats"] = "Not calculated"

        profile["statistics"] = stats

    return profile
