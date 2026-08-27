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


@dataclass
class TableProfile:
    name: str
    row_count: int = 0
    columns: list[ColumnProfile] = field(default_factory=list)
    foreign_keys: list[dict[str, str]] = field(default_factory=list)
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

    def clear(self) -> None:
        self.database_type = ""
        self.tables.clear()
        self.total_tables = 0
        self.total_columns = 0
        self.total_rows = 0
        self.relationships.clear()
        self.analyzed = False
        self.summary = ""

    def to_context(self) -> str:
        lines = [
            f"Database type: {self.database_type or 'unknown'}",
            f"Tables: {self.total_tables}",
            f"Columns: {self.total_columns}",
            f"Total rows: {self.total_rows}",
            "",
            "Tables and columns:",
        ]

        for table_name, table in self.tables.items():
            lines.append(f"- {table_name} ({table.row_count} rows)")
            for column in table.columns:
                flags = []
                if column.primary_key:
                    flags.append("PK")
                if not column.nullable:
                    flags.append("NOT NULL")
                flag_text = f" [{', '.join(flags)}]" if flags else ""
                lines.append(f"  - {column.name}: {column.type}{flag_text}")

        if self.relationships:
            lines.append("")
            lines.append("Relationships:")
            for rel in self.relationships:
                lines.append(f"- {rel}")

        return "\n".join(lines)
