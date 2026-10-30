from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class DataHealthFinding:
    id: str
    table: str
    column: Optional[str] = None
    severity: str = "medium"  # "high", "medium", "low"
    type: str = "General"     # e.g., "Missing Primary Key", "High Null Ratio", "Duplicate Records", "Empty Table", "Single Value Column"
    description: str = ""
    suggested_action: str = ""
    metric_value: Optional[Any] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "table": self.table,
            "column": self.column,
            "severity": self.severity,
            "type": self.type,
            "description": self.description,
            "suggested_action": self.suggested_action,
            "metric_value": self.metric_value,
        }


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

    # Sprint 1 Semantic & Business Metadata
    entity_type: str = "GENERAL"  # "CUSTOMER", "ORDER", "TRANSACTION", "PRODUCT", "DIMENSION", "LOOKUP", "GENERAL"
    business_purpose: str = ""
    metric_columns: list[str] = field(default_factory=list)
    dimension_columns: list[str] = field(default_factory=list)
    date_columns: list[str] = field(default_factory=list)
    duplicate_count: int = 0
    health_issues: list[str] = field(default_factory=list)


@dataclass
class DatabaseProfile:
    database_type: str = ""
    connection_id: Optional[str] = None
    user_id: Optional[str] = None

    tables: dict[str, TableProfile] = field(default_factory=dict)

    total_tables: int = 0
    total_columns: int = 0
    total_rows: int = 0

    relationships: list[str] = field(default_factory=list)

    analyzed: bool = False
    summary: str = ""

    # AI-generated/general database insights
    insights: list[str] = field(default_factory=list)

    # Sprint 1 Data Health & Business Intelligence
    health_score: int = 100
    data_health_findings: list[DataHealthFinding] = field(default_factory=list)
    business_entities: dict[str, list[str]] = field(default_factory=dict)
    semantic_summary: str = ""

    def clear(self) -> None:
        self.database_type = ""
        self.connection_id = None
        self.user_id = None
        self.tables.clear()

        self.total_tables = 0
        self.total_columns = 0
        self.total_rows = 0

        self.relationships.clear()
        self.insights.clear()
        self.health_score = 100
        self.data_health_findings.clear()
        self.business_entities.clear()
        self.semantic_summary = ""

        self.analyzed = False
        self.summary = ""

    def to_context(self) -> str:
        """
        Convert the live database profile into compact, semantic context
        that can be supplied to the AI analyst.
        """
        lines = [
            f"Database type: {self.database_type or 'unknown'}",
            f"Overall Data Health Score: {self.health_score}/100",
            f"Tables: {self.total_tables}",
            f"Columns: {self.total_columns}",
            f"Total rows: {self.total_rows}",
        ]

        if self.business_entities:
            lines.append("")
            lines.append("BUSINESS ENTITY CLASSIFICATIONS:")
            for entity_type, table_names in self.business_entities.items():
                lines.append(f"- {entity_type}: {', '.join(table_names)}")

        lines.append("")
        lines.append("LIVE DATABASE STRUCTURE:")

        for table_name, table in self.tables.items():
            entity_tag = f" [{table.entity_type}]" if table.entity_type != "GENERAL" else ""
            lines.append(
                f"- Table: {table_name}{entity_tag} ({table.row_count} rows)"
            )
            if table.business_purpose:
                lines.append(f"  purpose: {table.business_purpose}")
            if table.metric_columns:
                lines.append(f"  metrics: {', '.join(table.metric_columns)}")
            if table.date_columns:
                lines.append(f"  dates: {', '.join(table.date_columns)}")

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
                    # Sanitize sample values in context
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
                        f"    nulls: {null_percent:.1f}%, unique: {unique_percent:.1f}%"
                    )

                if (
                    column.min_value is not None
                    or column.max_value is not None
                ):
                    lines.append(
                        f"    range: {column.min_value} -> {column.max_value}"
                    )

                if column.average_value is not None:
                    lines.append(
                        f"    average: {column.average_value}"
                    )

            if table.foreign_keys:
                lines.append("  Foreign keys:")
                for fk in table.foreign_keys:
                    lines.append(f"    - {fk}")

        if self.relationships:
            lines.append("")
            lines.append("RELATIONSHIPS:")
            for relationship in self.relationships:
                lines.append(f"- {relationship}")

        if self.data_health_findings:
            lines.append("")
            lines.append(f"DATA HEALTH FINDINGS (Health Score: {self.health_score}/100):")
            for finding in self.data_health_findings[:10]:
                col_txt = f".{finding.column}" if finding.column else ""
                lines.append(
                    f"- [{finding.severity.upper()}] {finding.table}{col_txt}: {finding.description} (Action: {finding.suggested_action})"
                )

        if self.insights:
            lines.append("")
            lines.append("DATABASE INSIGHTS:")
            for insight in self.insights:
                lines.append(f"- {insight}")

        return "\n".join(lines)
