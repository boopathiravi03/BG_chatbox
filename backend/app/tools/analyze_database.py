from __future__ import annotations

from typing import Any
from sqlalchemy import inspect, text
from app.agent.database_profile import DatabaseProfile, TableProfile, ColumnProfile
from app.database.database_manager import get_engine, get_current_db_type


def analyze_database() -> DatabaseProfile:
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
                columns = inspector.get_columns(table_name)
                foreign_keys = inspector.get_foreign_keys(table_name)
                indexes = inspector.get_indexes(table_name)

                try:
                    row_count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar() or 0
                except Exception:
                    row_count = 0

                try:
                    sample_rows = conn.execute(text(f"SELECT * FROM {table_name} LIMIT 5")).mappings().fetchall()
                    sample_rows = [dict(row) for row in sample_rows]
                except Exception:
                    sample_rows = []

                column_profiles = []
                for column in columns:
                    column_profiles.append(
                        ColumnProfile(
                            name=column.get("name", ""),
                            type=str(column.get("type", "")),
                            nullable=column.get("nullable", True),
                            default=column.get("default"),
                            primary_key=column.get("primary_key", False),
                        )
                    )

                profile.total_columns += len(column_profiles)
                profile.total_rows += row_count

                profile.tables[table_name] = TableProfile(
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
                )

        profile.relationships = _build_relationships(profile)
        profile.analyzed = True
        profile.summary = (
            f"Database contains {profile.total_tables} tables, "
            f"{profile.total_columns} columns, and approximately "
            f"{profile.total_rows} total rows."
        )
    except Exception as e:
        profile.summary = f"Database analysis failed: {str(e)}"
        profile.analyzed = False

    return profile


def _build_relationships(profile: DatabaseProfile) -> list[str]:
    relationships: list[str] = []

    for table_name, table in profile.tables.items():
        for fk in table.foreign_keys:
            constrained = ", ".join(fk.get("constrained_columns", []))
            referred_table = fk.get("referred_table", "")
            referred_columns = ", ".join(fk.get("referred_columns", []))
            if referred_table and constrained:
                relationships.append(
                    f"{table_name}.{constrained} -> {referred_table}.{referred_columns}"
                )

    return relationships
