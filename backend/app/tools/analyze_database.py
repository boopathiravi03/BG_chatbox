from __future__ import annotations

import re
from typing import Any, Optional

from sqlalchemy import inspect, text

from app.agent.database_profile import (
    DatabaseProfile,
    TableProfile,
    ColumnProfile,
    DataHealthFinding,
)

from app.database.database_manager import (
    get_engine,
    get_current_db_type,
)

# Column keywords whose sample values should never be extracted or exposed
SENSITIVE_KEYWORDS = {
    "password", "passwd", "secret", "token", "ssn", "social_security",
    "credit_card", "card_num", "cvv", "pin", "api_key", "auth_token",
    "private_key", "hash", "salt", "seed",
}


def _is_sensitive_column(column_name: str) -> bool:
    tokens = set(re.split(r"[^a-zA-Z0-9]+", column_name.lower()))
    return bool(tokens.intersection(SENSITIVE_KEYWORDS)) or any(
        k in column_name.lower() for k in ["password", "secret", "token", "ssn", "credit_card", "private_key"]
    )



def analyze_database(
    user_id: Optional[str] = None,
    connection_id: Optional[str] = None,
) -> DatabaseProfile:
    """
    Analyze the connected database automatically.
    Discovers tables, columns, keys, indexes, business entities, metrics, dimensions,
    and detects data-quality issues while protecting sensitive credentials.
    Supports both relational engines and non-relational connectors.
    """
    profile = DatabaseProfile()
    profile.user_id = user_id
    profile.connection_id = connection_id

    # 1. Resolve active connector or engine
    connector = None
    target_engine = None
    db_type = "none"

    try:
        from app.database.connection_context import get_request_engine, get_request_db_type, get_request_user_id
        from app.connectors.registry import get_connection_registry

        eff_uid = user_id or get_request_user_id()
        if eff_uid:
            reg = get_connection_registry()
            connector = reg.get_connector(eff_uid, connection_id) if connection_id else reg.get_active_connector(eff_uid)

        target_engine = get_request_engine() or get_engine()
        db_type = get_request_db_type() if get_request_db_type() != "none" else get_current_db_type()
        if connector and hasattr(connector, "connector_type"):
            db_type = connector.connector_type
    except Exception:
        target_engine = get_engine()
        db_type = get_current_db_type()

    profile.database_type = db_type

    # 2. Check if this is a non-relational connector (Document / Vector / Key-Value)
    if connector and getattr(connector, "category", None) and connector.category.value in ("document", "vector"):
        return _analyze_non_relational(connector, profile)

    if target_engine is None:
        profile.summary = "No active database connection available."
        profile.analyzed = False
        return profile

    try:
        inspector = inspect(target_engine)
        table_names = inspector.get_table_names()
        profile.total_tables = len(table_names)

        with target_engine.connect() as conn:
            for table_name in table_names:
                columns = inspector.get_columns(table_name)
                foreign_keys = inspector.get_foreign_keys(table_name)
                indexes = inspector.get_indexes(table_name)

                row_count = _get_row_count(conn, table_name)
                sample_rows = _get_sample_rows(conn, table_name)

                column_profiles: list[ColumnProfile] = []
                metric_cols: list[str] = []
                dim_cols: list[str] = []
                date_cols: list[str] = []
                primary_keys: list[str] = []

                for column in columns:
                    column_name = column.get("name", "")
                    column_type = str(column.get("type", ""))
                    nullable = column.get("nullable", True)
                    default = column.get("default")
                    primary_key = column.get("primary_key", False)
                    if primary_key:
                        primary_keys.append(column_name)

                    role = _detect_column_role(column_name, column_type, primary_key)

                    # Classify column semantic roles
                    if role == "numeric_measure":
                        metric_cols.append(column_name)
                    elif role in ("date", "datetime"):
                        date_cols.append(column_name)
                    elif role in ("category", "identifier", "email", "name"):
                        dim_cols.append(column_name)

                    is_sensitive = _is_sensitive_column(column_name)
                    stats = _get_column_statistics(
                        conn, table_name, column_name, column_type, row_count, is_sensitive=is_sensitive
                    )

                    column_profiles.append(
                        ColumnProfile(
                            name=column_name,
                            type=column_type,
                            nullable=nullable,
                            default=default,
                            primary_key=primary_key,
                            role=role,
                            null_count=stats["null_count"],
                            unique_count=stats["unique_count"],
                            total_values=stats["total_values"],
                            sample_values=stats["sample_values"],
                            min_value=stats["min_value"],
                            max_value=stats["max_value"],
                            average_value=stats["average_value"],
                        )
                    )

                profile.total_columns += len(column_profiles)
                profile.total_rows += row_count

                # Entity classification
                entity_type = _classify_entity_type(table_name)
                profile.business_entities.setdefault(entity_type, []).append(table_name)

                # Duplicate detection on primary/candidate keys
                duplicate_count = 0
                if primary_keys and row_count > 0:
                    duplicate_count = _detect_key_duplicates(conn, table_name, primary_keys[0])

                t_profile = TableProfile(
                    name=table_name,
                    row_count=row_count,
                    columns=column_profiles,
                    foreign_keys=[
                        {
                            "constrained_columns": fk.get("constrained_columns", []),
                            "referred_table": fk.get("referred_table", ""),
                            "referred_columns": fk.get("referred_columns", []),
                        }
                        for fk in foreign_keys
                    ],
                    indexes=[idx.get("name", "") for idx in indexes if idx.get("name")],
                    sample_rows=sample_rows,
                    entity_type=entity_type,
                    business_purpose=_infer_business_purpose(table_name, entity_type, row_count),
                    metric_columns=metric_cols,
                    dimension_columns=dim_cols,
                    date_columns=date_cols,
                    duplicate_count=duplicate_count,
                )

                profile.tables[table_name] = t_profile

        # Build relationships and insights
        profile.relationships = _build_relationships(profile)
        profile.insights = _build_database_insights(profile)

        # Build data health findings & compute score
        profile.data_health_findings = _audit_data_health(profile)
        profile.health_score = _calculate_health_score(profile.data_health_findings, profile.total_tables)

        profile.analyzed = True
        profile.summary = (
            f"Database contains {profile.total_tables} tables, {profile.total_columns} columns, "
            f"and approximately {profile.total_rows} total rows. Overall Data Health Score: {profile.health_score}/100."
        )

    except Exception as e:
        profile.summary = f"Database analysis encountered an issue: {str(e)}"
        profile.analyzed = False

    return profile


def _analyze_non_relational(connector: Any, profile: DatabaseProfile) -> DatabaseProfile:
    """Safely profiles document or non-relational database connectors without SQLAlchemy inspect()."""
    try:
        schema = connector.get_schema() or {}
        stats = connector.get_stats() or {}

        tables_data = schema.get("collections", schema)
        if isinstance(tables_data, dict):
            for coll_name, coll_meta in tables_data.items():
                col_profiles = []
                metric_cols = []
                dim_cols = []
                date_cols = []

                fields = coll_meta.get("fields", coll_meta) if isinstance(coll_meta, dict) else {}
                if isinstance(fields, dict):
                    for f_name, f_type in fields.items():
                        f_type_str = str(f_type.get("type", f_type) if isinstance(f_type, dict) else f_type)
                        role = _detect_column_role(f_name, f_type_str, f_name in ("_id", "id"))
                        if role == "numeric_measure":
                            metric_cols.append(f_name)
                        elif role in ("date", "datetime"):
                            date_cols.append(f_name)
                        else:
                            dim_cols.append(f_name)

                        col_profiles.append(
                            ColumnProfile(
                                name=f_name,
                                type=f_type_str,
                                primary_key=(f_name in ("_id", "id")),
                                role=role,
                            )
                        )

                doc_count = coll_meta.get("count", coll_meta.get("documents", 0)) if isinstance(coll_meta, dict) else 0
                entity_type = _classify_entity_type(coll_name)
                profile.business_entities.setdefault(entity_type, []).append(coll_name)

                profile.tables[coll_name] = TableProfile(
                    name=coll_name,
                    row_count=doc_count,
                    columns=col_profiles,
                    entity_type=entity_type,
                    business_purpose=f"{entity_type.title()} collection containing {doc_count} documents.",
                    metric_columns=metric_cols,
                    dimension_columns=dim_cols,
                    date_columns=date_cols,
                )
                profile.total_columns += len(col_profiles)
                profile.total_rows += doc_count

        profile.total_tables = len(profile.tables)
        profile.health_score = 95
        profile.analyzed = True
        profile.summary = f"{profile.database_type.upper()} store with {profile.total_tables} collections/namespaces and {profile.total_rows} items."
    except Exception as e:
        profile.summary = f"Non-relational analysis fallback: {str(e)}"
        profile.analyzed = False

    return profile


def _classify_entity_type(table_name: str) -> str:
    """Maps table names to high-level business entity types."""
    tokens = set(re.split(r"[^a-zA-Z0-9]+", table_name.lower()))
    entity_mappings = {
        "CUSTOMER": {"customer", "customers", "client", "clients", "user", "users", "account", "accounts", "buyer", "buyers", "member", "members", "patient", "patients", "subscriber", "subscribers"},
        "PRODUCT": {"product", "products", "item", "items", "good", "goods", "inventory", "service", "services", "course", "courses", "catalog", "merchandise"},
        "ORDER": {"order", "orders", "transaction", "transactions", "sale", "sales", "invoice", "invoices", "purchase", "purchases", "payment", "payments", "booking", "bookings", "receipt", "receipts"},
        "DIMENSION": {"category", "categories", "type", "types", "status", "statuses", "country", "countries", "region", "regions", "city", "cities", "department", "departments", "lookup", "lookups", "tag", "tags"},
        "LOG": {"log", "logs", "event", "events", "audit", "audits", "history", "session", "sessions", "trace", "traces"},
    }
    for entity_type, keywords in entity_mappings.items():
        if tokens.intersection(keywords) or any(k in table_name.lower() for k in keywords):
            return entity_type
    return "GENERAL"


def _infer_business_purpose(table_name: str, entity_type: str, row_count: int) -> str:
    if entity_type == "CUSTOMER":
        return f"Customer/account records repository ({row_count} records)."
    elif entity_type == "PRODUCT":
        return f"Product catalog and merchandise master ({row_count} items)."
    elif entity_type == "ORDER":
        return f"Transactional order and sales records ({row_count} transactions)."
    elif entity_type == "DIMENSION":
        return f"Lookup dimension / categorization table ({row_count} entries)."
    elif entity_type == "LOG":
        return f"Operational logs and telemetry history ({row_count} entries)."
    return f"Operational data table '{table_name}' ({row_count} rows)."


def _get_row_count(conn, table_name: str) -> int:
    try:
        result = conn.execute(text(f"SELECT COUNT(*) FROM {_quote_identifier(table_name)}"))
        return int(result.scalar() or 0)
    except Exception:
        return 0


def _get_sample_rows(conn, table_name: str) -> list[dict[str, Any]]:
    try:
        result = conn.execute(text(f"SELECT * FROM {_quote_identifier(table_name)} LIMIT 5"))
        raw_rows = [dict(row) for row in result.mappings().fetchall()]
        # Redact sensitive values from sample rows
        sanitized = []
        for r in raw_rows:
            cleaned = {}
            for k, v in r.items():
                if _is_sensitive_column(k):
                    cleaned[k] = "[REDACTED]"
                else:
                    cleaned[k] = v
            sanitized.append(cleaned)
        return sanitized
    except Exception:
        return []


def _detect_key_duplicates(conn, table_name: str, key_column: str) -> int:
    try:
        table_sql = _quote_identifier(table_name)
        col_sql = _quote_identifier(key_column)
        sql = f"SELECT COUNT(*) - COUNT(DISTINCT {col_sql}) FROM {table_sql} WHERE {col_sql} IS NOT NULL"
        res = conn.execute(text(sql)).scalar()
        return max(0, int(res or 0))
    except Exception:
        return 0


def _get_column_statistics(
    conn,
    table_name: str,
    column_name: str,
    column_type: str,
    row_count: int,
    is_sensitive: bool = False,
) -> dict[str, Any]:
    stats = {
        "null_count": 0,
        "unique_count": 0,
        "total_values": row_count,
        "sample_values": ["[REDACTED]"] if is_sensitive else [],
        "min_value": None,
        "max_value": None,
        "average_value": None,
    }

    if row_count == 0:
        return stats

    table_sql = _quote_identifier(table_name)
    column_sql = _quote_identifier(column_name)

    # 1. Null count
    try:
        result = conn.execute(
            text(f"SELECT COUNT(*) - COUNT({column_sql}) FROM {table_sql}")
        )
        stats["null_count"] = int(result.scalar() or 0)
    except Exception:
        pass

    # 2. Unique count (bound to small/medium tables to preserve performance)
    if row_count <= 100000:
        try:
            result = conn.execute(
                text(f"SELECT COUNT(DISTINCT {column_sql}) FROM {table_sql}")
            )
            stats["unique_count"] = int(result.scalar() or 0)
        except Exception:
            pass

    # 3. Sample values (strictly skipped for sensitive fields)
    if not is_sensitive:
        try:
            result = conn.execute(
                text(f"SELECT {column_sql} FROM {table_sql} WHERE {column_sql} IS NOT NULL LIMIT 5")
            )
            values = []
            for row in result.fetchall():
                if row and row[0] not in values:
                    values.append(row[0])
            stats["sample_values"] = values
        except Exception:
            pass

    # 4. Numeric min/max/avg
    if _is_numeric_type(column_type):
        try:
            result = conn.execute(
                text(f"SELECT MIN({column_sql}), MAX({column_sql}), AVG({column_sql}) FROM {table_sql}")
            )
            row = result.fetchone()
            if row:
                stats["min_value"] = row[0]
                stats["max_value"] = row[1]
                stats["average_value"] = round(row[2], 2) if row[2] is not None else None
        except Exception:
            pass

    return stats


def _detect_column_role(column_name: str, column_type: str, primary_key: bool) -> str:
    name = column_name.lower().strip()
    normalized = re.sub(r"[^a-z0-9]+", "_", name).strip("_")

    if primary_key:
        return "identifier"
    if any(t in normalized for t in ["email", "e_mail"]):
        return "email"
    if any(t in normalized for t in ["phone", "mobile", "contact"]):
        return "phone"
    if any(t in normalized for t in ["first_name", "last_name", "full_name"]) or normalized == "name":
        return "name"
    if any(t in normalized for t in ["date", "dob", "birth", "created_at", "updated_at", "order_date"]):
        return "date"
    if any(t in normalized for t in ["timestamp", "datetime", "created_time"]):
        return "datetime"
    if any(t in normalized for t in ["price", "amount", "cost", "salary", "revenue", "income", "total", "balance", "discount", "fee", "tax", "quantity", "qty"]):
        return "numeric_measure"
    if any(t in normalized for t in ["status", "state", "type", "category", "gender", "role", "country", "city"]):
        return "category"
    if any(t in normalized for t in ["description", "comment", "remarks", "address", "note"]):
        return "text"
    if _is_numeric_type(column_type):
        return "numeric"
    if _is_date_type(column_type):
        return "date"
    return "text"


def _is_numeric_type(column_type: str) -> bool:
    val = column_type.lower()
    return any(item in val for item in ["int", "integer", "bigint", "smallint", "decimal", "numeric", "float", "double", "real", "number"])


def _is_date_type(column_type: str) -> bool:
    val = column_type.lower()
    return any(item in val for item in ["date", "datetime", "timestamp", "time"])


def _quote_identifier(identifier: str) -> str:
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'


def _build_relationships(profile: DatabaseProfile) -> list[str]:
    relationships: list[str] = []
    for table_name, table in profile.tables.items():
        for fk in table.foreign_keys:
            constrained = ", ".join(fk.get("constrained_columns", []))
            ref_table = fk.get("referred_table", "")
            ref_cols = ", ".join(fk.get("referred_columns", []))
            if ref_table and constrained:
                relationships.append(f"{table_name}.{constrained} -> {ref_table}.{ref_cols}")
    return relationships


def _audit_data_health(profile: DatabaseProfile) -> list[DataHealthFinding]:
    """Generates structured, actionable data health findings across tables and columns."""
    findings: list[DataHealthFinding] = []

    for table_name, table in profile.tables.items():
        # 1. Missing primary key check
        has_pk = any(col.primary_key for col in table.columns)
        if not has_pk and table.row_count > 0:
            findings.append(
                DataHealthFinding(
                    id=f"pk_{table_name}",
                    table=table_name,
                    severity="high",
                    type="Missing Primary Key",
                    description=f"Table '{table_name}' has no defined primary key identifier.",
                    suggested_action=f"Define a primary key (e.g. 'id') on '{table_name}' to enable indexing and transactional consistency.",
                )
            )

        # 2. Empty table check
        if table.row_count == 0:
            findings.append(
                DataHealthFinding(
                    id=f"empty_{table_name}",
                    table=table_name,
                    severity="low",
                    type="Empty Table",
                    description=f"Table '{table_name}' contains 0 records.",
                    suggested_action=f"Populate initial data into '{table_name}' or remove it if obsolete.",
                )
            )

        # 3. Duplicate key detection
        if table.duplicate_count > 0:
            findings.append(
                DataHealthFinding(
                    id=f"dup_{table_name}",
                    table=table_name,
                    severity="high",
                    type="Duplicate Records",
                    description=f"Table '{table_name}' contains {table.duplicate_count} duplicate key records.",
                    suggested_action=f"Apply a unique constraint or deduplicate rows in '{table_name}'.",
                    metric_value=table.duplicate_count,
                )
            )

        # 4. Column-level quality checks (null ratios, zero variance)
        for col in table.columns:
            if col.total_values <= 0:
                continue

            null_pct = (col.null_count / col.total_values) * 100
            if null_pct >= 50:
                severity = "high" if null_pct >= 80 else "medium"
                findings.append(
                    DataHealthFinding(
                        id=f"null_{table_name}_{col.name}",
                        table=table_name,
                        column=col.name,
                        severity=severity,
                        type="High Null Ratio",
                        description=f"Column '{table_name}.{col.name}' has {null_pct:.1f}% null values.",
                        suggested_action=f"Investigate whether null values in '{col.name}' represent missing data or optional attributes.",
                        metric_value=round(null_pct, 1),
                    )
                )

            if col.unique_count == 1 and table.row_count > 1:
                findings.append(
                    DataHealthFinding(
                        id=f"const_{table_name}_{col.name}",
                        table=table_name,
                        column=col.name,
                        severity="low",
                        type="Single Constant Value",
                        description=f"Column '{table_name}.{col.name}' has only 1 distinct value across all rows.",
                        suggested_action=f"Evaluate whether '{col.name}' is redundant or should have a default setting.",
                        metric_value=1,
                    )
                )

    return findings


def _calculate_health_score(findings: list[DataHealthFinding], total_tables: int) -> int:
    """Calculates a deterministic data quality health score from 10 to 100."""
    if total_tables == 0:
        return 100

    score = 100
    for finding in findings:
        if finding.severity == "high":
            score -= 12
        elif finding.severity == "medium":
            score -= 6
        elif finding.severity == "low":
            score -= 2

    return max(10, min(100, score))


def _build_database_insights(profile: DatabaseProfile) -> list[str]:
    insights: list[str] = []

    for table_name, table in profile.tables.items():
        if table.row_count == 0:
            insights.append(f"Table '{table_name}' is empty.")
        if table.duplicate_count > 0:
            insights.append(f"Table '{table_name}' has {table.duplicate_count} duplicate key values.")

        for column in table.columns:
            if column.total_values <= 0:
                continue
            null_pct = (column.null_count / column.total_values) * 100
            if null_pct >= 50:
                insights.append(f"Column '{table_name}.{column.name}' has {null_pct:.0f}% null values.")

    if profile.relationships:
        insights.append(f"Detected {len(profile.relationships)} relational connection(s) between business entities.")

    return insights
