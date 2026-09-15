from __future__ import annotations

import re
from typing import Any

from sqlalchemy import inspect, text

from app.agent.database_profile import (
    DatabaseProfile,
    TableProfile,
    ColumnProfile,
)

from app.database.database_manager import (
    get_engine,
    get_current_db_type,
)


def analyze_database() -> DatabaseProfile:
    """
    Analyze the currently connected database.

    This function is intentionally database-agnostic.
    It works from the live SQLAlchemy engine and inspector,
    so BG AI can understand completely different schemas.
    """

    profile = DatabaseProfile()

    try:
        engine = get_engine()

        if engine is None:
            return profile

        profile.database_type = get_current_db_type()

        inspector = inspect(engine)

        table_names = inspector.get_table_names()

        profile.total_tables = len(table_names)

        with engine.connect() as conn:

            for table_name in table_names:

                columns = inspector.get_columns(
                    table_name
                )

                foreign_keys = inspector.get_foreign_keys(
                    table_name
                )

                indexes = inspector.get_indexes(
                    table_name
                )

                row_count = _get_row_count(
                    conn,
                    table_name
                )

                sample_rows = _get_sample_rows(
                    conn,
                    table_name
                )

                column_profiles = []

                for column in columns:

                    column_name = column.get(
                        "name",
                        ""
                    )

                    column_type = str(
                        column.get("type", "")
                    )

                    nullable = column.get(
                        "nullable",
                        True
                    )

                    default = column.get(
                        "default"
                    )

                    primary_key = column.get(
                        "primary_key",
                        False
                    )

                    role = _detect_column_role(
                        column_name,
                        column_type,
                        primary_key
                    )

                    stats = _get_column_statistics(
                        conn,
                        table_name,
                        column_name,
                        column_type,
                        row_count
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
                            sample_values=stats[
                                "sample_values"
                            ],
                            min_value=stats[
                                "min_value"
                            ],
                            max_value=stats[
                                "max_value"
                            ],
                            average_value=stats[
                                "average_value"
                            ],
                        )
                    )

                profile.total_columns += len(
                    column_profiles
                )

                profile.total_rows += row_count

                profile.tables[table_name] = TableProfile(
                    name=table_name,
                    row_count=row_count,
                    columns=column_profiles,
                    foreign_keys=[
                        {
                            "constrained_columns":
                                fk.get(
                                    "constrained_columns",
                                    []
                                ),
                            "referred_table":
                                fk.get(
                                    "referred_table",
                                    ""
                                ),
                            "referred_columns":
                                fk.get(
                                    "referred_columns",
                                    []
                                ),
                        }
                        for fk in foreign_keys
                    ],
                    indexes=[
                        idx.get("name", "")
                        for idx in indexes
                        if idx.get("name")
                    ],
                    sample_rows=sample_rows,
                )

        profile.relationships = (
            _build_relationships(profile)
        )

        profile.insights = (
            _build_database_insights(profile)
        )

        profile.analyzed = True

        profile.summary = (
            f"Database contains "
            f"{profile.total_tables} tables, "
            f"{profile.total_columns} columns, "
            f"and approximately "
            f"{profile.total_rows} total rows."
        )

    except Exception as e:

        profile.summary = (
            f"Database analysis failed: {str(e)}"
        )

        profile.analyzed = False

    return profile


def _get_row_count(
    conn,
    table_name: str,
) -> int:

    try:
        result = conn.execute(
            text(
                f"SELECT COUNT(*) "
                f"FROM {_quote_identifier(table_name)}"
            )
        )

        return int(result.scalar() or 0)

    except Exception:
        return 0


def _get_sample_rows(
    conn,
    table_name: str,
) -> list[dict[str, Any]]:

    try:
        result = conn.execute(
            text(
                f"SELECT * "
                f"FROM {_quote_identifier(table_name)} "
                f"LIMIT 5"
            )
        )

        return [
            dict(row)
            for row in result.mappings().fetchall()
        ]

    except Exception:
        return []


def _get_column_statistics(
    conn,
    table_name: str,
    column_name: str,
    column_type: str,
    row_count: int,
) -> dict[str, Any]:

    stats = {
        "null_count": 0,
        "unique_count": 0,
        "total_values": row_count,
        "sample_values": [],
        "min_value": None,
        "max_value": None,
        "average_value": None,
    }

    if row_count == 0:
        return stats

    table_sql = _quote_identifier(table_name)
    column_sql = _quote_identifier(column_name)

    try:
        result = conn.execute(
            text(
                f"SELECT "
                f"COUNT(*) - COUNT({column_sql}) "
                f"FROM {table_sql}"
            )
        )

        stats["null_count"] = int(
            result.scalar() or 0
        )

    except Exception:
        pass

    try:
        result = conn.execute(
            text(
                f"SELECT COUNT(DISTINCT {column_sql}) "
                f"FROM {table_sql}"
            )
        )

        stats["unique_count"] = int(
            result.scalar() or 0
        )

    except Exception:
        pass

    try:
        result = conn.execute(
            text(
                f"SELECT {column_sql} "
                f"FROM {table_sql} "
                f"WHERE {column_sql} IS NOT NULL "
                f"LIMIT 5"
            )
        )

        values = []

        for row in result.fetchall():

            if row:
                value = row[0]

                if value not in values:
                    values.append(value)

        stats["sample_values"] = values

    except Exception:
        pass

    if _is_numeric_type(column_type):

        try:
            result = conn.execute(
                text(
                    f"SELECT "
                    f"MIN({column_sql}), "
                    f"MAX({column_sql}), "
                    f"AVG({column_sql}) "
                    f"FROM {table_sql}"
                )
            )

            row = result.fetchone()

            if row:

                stats["min_value"] = row[0]
                stats["max_value"] = row[1]
                stats["average_value"] = row[2]

        except Exception:
            pass

    return stats


def _detect_column_role(
    column_name: str,
    column_type: str,
    primary_key: bool,
) -> str:

    name = column_name.lower().strip()

    normalized = re.sub(
        r"[^a-z0-9]+",
        "_",
        name,
    ).strip("_")

    if primary_key:
        return "identifier"

    if any(
        token in normalized
        for token in [
            "email",
            "e_mail",
        ]
    ):
        return "email"

    if any(
        token in normalized
        for token in [
            "phone",
            "mobile",
            "contact",
        ]
    ):
        return "phone"

    if any(
        token in normalized
        for token in [
            "name",
            "first_name",
            "last_name",
            "full_name",
        ]
    ):
        return "name"

    if any(
        token in normalized
        for token in [
            "date",
            "dob",
            "birth",
        ]
    ):
        return "date"

    if any(
        token in normalized
        for token in [
            "time",
            "timestamp",
        ]
    ):
        return "datetime"

    if any(
        token in normalized
        for token in [
            "price",
            "amount",
            "cost",
            "salary",
            "revenue",
            "income",
            "total",
            "balance",
        ]
    ):
        return "numeric_measure"

    if any(
        token in normalized
        for token in [
            "status",
            "state",
            "type",
            "category",
            "gender",
            "role",
        ]
    ):
        return "category"

    if any(
        token in normalized
        for token in [
            "description",
            "comment",
            "remarks",
            "address",
            "note",
        ]
    ):
        return "text"

    if _is_numeric_type(column_type):
        return "numeric"

    if _is_date_type(column_type):
        return "date"

    return "text"


def _is_numeric_type(column_type: str) -> bool:

    value = column_type.lower()

    numeric_types = [
        "int",
        "integer",
        "bigint",
        "smallint",
        "decimal",
        "numeric",
        "float",
        "double",
        "real",
        "number",
    ]

    return any(
        item in value
        for item in numeric_types
    )


def _is_date_type(column_type: str) -> bool:

    value = column_type.lower()

    return any(
        item in value
        for item in [
            "date",
            "datetime",
            "timestamp",
            "time",
        ]
    )


def _quote_identifier(
    identifier: str,
) -> str:

    """
    Quote a SQL identifier safely for the common
    SQL dialects used by BG AI.

    SQLAlchemy handles the actual database connection;
    this helper is only used for generated analysis SQL.
    """

    escaped = identifier.replace(
        '"',
        '""'
    )

    return f'"{escaped}"'


def _build_relationships(
    profile: DatabaseProfile,
) -> list[str]:

    relationships: list[str] = []

    for table_name, table in profile.tables.items():

        for fk in table.foreign_keys:

            constrained = ", ".join(
                fk.get(
                    "constrained_columns",
                    []
                )
            )

            referred_table = fk.get(
                "referred_table",
                ""
            )

            referred_columns = ", ".join(
                fk.get(
                    "referred_columns",
                    []
                )
            )

            if (
                referred_table
                and constrained
            ):

                relationships.append(
                    f"{table_name}."
                    f"{constrained} -> "
                    f"{referred_table}."
                    f"{referred_columns}"
                )

    return relationships


def _build_database_insights(
    profile: DatabaseProfile,
) -> list[str]:

    insights: list[str] = []

    for table_name, table in profile.tables.items():

        if table.row_count == 0:

            insights.append(
                f"Table '{table_name}' is empty."
            )

        for column in table.columns:

            if column.total_values <= 0:
                continue

            null_percent = (
                column.null_count
                / column.total_values
                * 100
            )

            if null_percent >= 50:

                insights.append(
                    f"Column '{table_name}."
                    f"{column.name}' has "
                    f"{null_percent:.0f}% "
                    f"null values."
                )

            if (
                column.unique_count == 1
                and table.row_count > 1
            ):

                insights.append(
                    f"Column '{table_name}."
                    f"{column.name}' contains "
                    f"the same value across "
                    f"the table."
                )

    if profile.relationships:

        insights.append(
            f"Detected "
            f"{len(profile.relationships)} "
            f"database relationship(s)."
        )

    return insights
