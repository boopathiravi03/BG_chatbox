from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ColumnProfile:
    name: str
    type: str = ""
    nullable: bool = True
    default: Any = None
    primary_key: bool = False

    # AI semantic information
    role: str = "unknown"

    # Data quality
    null_count: int = 0
    unique_count: int = 0
    total_values: int = 0

    # Preview/statistical information
    sample_values: list[Any] = field(default_factory=list)
    min_value: Any = None
    max_value: Any = None
    average_value: Any = None


@dataclass
class TableProfile:
    name: str
    row_count: int = 0
    columns: list[ColumnProfile] = field(default_factory=list)
    foreign_keys: list[dict[str, Any]] = field(default_factory=list)
    indexes: list[str] = field(default_factory=list)
    sample_rows: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DatabaseProfile:
    database_type: str = ""

    tables: dict[str, TableProfile] = field(default_factory=dict)

    total_tables: int = 0
    total_columns: int = 0
    total_rows: int = 0

    relationships: list[str] = field(default_factory=list)

    analyzed: bool = False
    summary: str = ""

    # AI-generated/general database insights
    insights: list[str] = field(default_factory=list)

    def clear(self) -> None:
        self.database_type = ""
        self.tables.clear()

        self.total_tables = 0
        self.total_columns = 0
        self.total_rows = 0

        self.relationships.clear()
        self.insights.clear()

        self.analyzed = False
        self.summary = ""

    def to_context(self) -> str:
        """
        Convert the live database profile into compact context
        that can be supplied to the AI.
        """

        lines = [
            f"Database type: {self.database_type or 'unknown'}",
            f"Tables: {self.total_tables}",
            f"Columns: {self.total_columns}",
            f"Total rows: {self.total_rows}",
            "",
            "LIVE DATABASE STRUCTURE:",
        ]

        for table_name, table in self.tables.items():
            lines.append(
                f"- Table: {table_name} ({table.row_count} rows)"
            )

            for column in table.columns:
                flags = []

                if column.primary_key:
                    flags.append("PK")

                if not column.nullable:
                    flags.append("NOT NULL")

                flag_text = (
                    f" [{', '.join(flags)}]"
                    if flags
                    else ""
                )

                role_text = (
                    f", role={column.role}"
                    if column.role and column.role != "unknown"
                    else ""
                )

                lines.append(
                    f"  - {column.name}: "
                    f"{column.type}"
                    f"{flag_text}"
                    f"{role_text}"
                )

                if column.sample_values:
                    values = ", ".join(
                        repr(value)
                        for value in column.sample_values[:5]
                    )

                    lines.append(
                        f"    sample values: {values}"
                    )

                if column.total_values > 0:
                    null_percent = (
                        column.null_count
                        / column.total_values
                        * 100
                    )

                    unique_percent = (
                        column.unique_count
                        / column.total_values
                        * 100
                    )

                    lines.append(
                        f"    nulls: {null_percent:.1f}%, "
                        f"unique: {unique_percent:.1f}%"
                    )

                if (
                    column.min_value is not None
                    or column.max_value is not None
                ):
                    lines.append(
                        f"    range: "
                        f"{column.min_value} -> "
                        f"{column.max_value}"
                    )

                if column.average_value is not None:
                    lines.append(
                        f"    average: "
                        f"{column.average_value}"
                    )

            if table.foreign_keys:
                lines.append("  Foreign keys:")

                for fk in table.foreign_keys:
                    lines.append(
                        f"    - {fk}"
                    )

        if self.relationships:
            lines.append("")
            lines.append("RELATIONSHIPS:")

            for relationship in self.relationships:
                lines.append(
                    f"- {relationship}"
                )

        if self.insights:
            lines.append("")
            lines.append("DATABASE INSIGHTS:")

            for insight in self.insights:
                lines.append(
                    f"- {insight}"
                )

        return "\n".join(lines)
