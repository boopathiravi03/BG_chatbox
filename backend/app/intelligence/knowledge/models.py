"""
backend/app/intelligence/knowledge/models.py

Phase 9.1: Enterprise Knowledge & Context Intelligence Data Models
Defines strongly typed data structures for business entities, business metrics,
business rules, context definitions, provenance, lineage, and conflict detection.

Strict Epistemic Principles:
- Distinguishes DATABASE FACT, INFERRED CONTEXT, USER-PROVIDED CONTEXT, and AI INTERPRETATION.
- Every knowledge object MUST have explicit provenance and lifecycle status.
- PROPOSED rules and inferred context cannot silently mutate metric calculations.
- Only CONFIRMED rules can affect active metric resolution.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


# ── Enumerations ─────────────────────────────────────────────────────────────

class KnowledgeProvenance(str, Enum):
    """
    Provenance tracking the origin and authority of business knowledge.
    """
    SCHEMA_DERIVED = "SCHEMA_DERIVED"   # Discovered from DB schema (keys, tables, types)
    DATA_OBSERVED = "DATA_OBSERVED"     # Observed in data values (e.g. distinct status values)
    USER_PROVIDED = "USER_PROVIDED"     # Directly entered or confirmed by authenticated user
    SYSTEM_DEFINED = "SYSTEM_DEFINED"   # Default BG AI platform definitions
    AI_INFERRED = "AI_INFERRED"         # LLM or statistical heuristic proposal


class KnowledgeStatus(str, Enum):
    """
    Lifecycle status of knowledge items.
    Only CONFIRMED or ACTIVE items can automatically alter analytics calculations.
    """
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"         # Inferred or suggested, awaiting human review
    CONFIRMED = "CONFIRMED"       # Human-verified and active
    ACTIVE = "ACTIVE"             # Confirmed and currently participating in calculation
    DISABLED = "DISABLED"         # Manually deactivated by user
    CONFLICTED = "CONFLICTED"     # In conflict with another active definition/rule


class EntityImportance(str, Enum):
    PRIMARY = "PRIMARY"           # Core business entities (e.g. Orders, Customers)
    SECONDARY = "SECONDARY"       # Supporting business entities (e.g. Products, Categories)
    SUPPORTING = "SUPPORTING"     # Lookup, log, or junction entities


class RuleScope(str, Enum):
    METRIC = "METRIC"
    ENTITY = "ENTITY"
    TABLE = "TABLE"
    COLUMN = "COLUMN"
    GLOBAL = "GLOBAL"


class RuleType(str, Enum):
    EXCLUSION = "EXCLUSION"       # e.g. status != 'cancelled'
    INCLUSION = "INCLUSION"       # e.g. type IN ('sale', 'subscription')
    MAPPING = "MAPPING"           # e.g. region mapping
    THRESHOLD = "THRESHOLD"       # e.g. total_amount > 0
    TEMPORAL = "TEMPORAL"         # e.g. fiscal year starting April


# ── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class BusinessEntity:
    """
    Represents a recognized business entity mapped to database tables.
    """
    entity_id: str
    name: str                       # e.g. "Order", "Customer"
    plural_name: str                # e.g. "Orders", "Customers"
    table_name: str                 # Database table name
    description: str                # Business description
    importance: str = EntityImportance.SECONDARY.value
    primary_key: Optional[str] = None
    foreign_keys: list[dict[str, str]] = field(default_factory=list)
    provenance: str = KnowledgeProvenance.SCHEMA_DERIVED.value
    status: str = KnowledgeStatus.PROPOSED.value
    confidence: float = 0.7
    user_id: str = "default_user"
    database_identity: str = "default_db"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BusinessEntity:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class BusinessRule:
    """
    Represents an explicit business rule (e.g., 'exclude cancelled orders from revenue').
    """
    rule_id: str
    name: str
    description: str
    scope: str = RuleScope.METRIC.value
    target_table: str = ""
    target_column: Optional[str] = None
    rule_type: str = RuleType.EXCLUSION.value
    expression: str = ""            # SQL-safe filter fragment e.g. "status != 'cancelled'"
    status: str = KnowledgeStatus.PROPOSED.value
    provenance: str = KnowledgeProvenance.USER_PROVIDED.value
    version: int = 1
    affected_metrics: list[str] = field(default_factory=list)
    user_id: str = "default_user"
    database_identity: str = "default_db"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BusinessRule:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class BusinessMetric:
    """
    Structured definition of a business metric with provenance, formula, and rule bindings.
    """
    metric_id: str
    name: str                       # e.g. "Revenue", "Order Count"
    description: str
    table_name: str
    column_name: Optional[str] = None
    aggregation: str = "SUM"        # SUM, AVG, COUNT, MIN, MAX
    filter_expression: Optional[str] = None  # derived from active confirmed rules
    conditions: list[str] = field(default_factory=list)
    rules_applied: list[str] = field(default_factory=list)  # rule_ids
    version: int = 1
    provenance: str = KnowledgeProvenance.SCHEMA_DERIVED.value
    status: str = KnowledgeStatus.PROPOSED.value
    confidence: float = 0.8
    user_id: str = "default_user"
    database_identity: str = "default_db"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BusinessMetric:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ColumnSemantic:
    """
    Semantic metadata for a specific database column.
    """
    semantic_id: str
    table_name: str
    column_name: str
    business_meaning: str
    data_type: str = "string"
    is_primary_key: bool = False
    is_foreign_key: bool = False
    provenance: str = KnowledgeProvenance.SCHEMA_DERIVED.value
    status: str = KnowledgeStatus.PROPOSED.value
    confidence: float = 0.7
    user_id: str = "default_user"
    database_identity: str = "default_db"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ColumnSemantic:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class KnowledgeConflict:
    """
    Represents an unresolved or resolved conflict between two knowledge definitions.
    """
    conflict_id: str
    knowledge_type: str             # "RULE", "METRIC", "ENTITY"
    item_id_a: str
    item_id_b: str
    target_name: str                # e.g. "Revenue" or "orders.status"
    description: str
    statement_a: str
    statement_b: str
    source_a: str
    source_b: str
    status: str = "UNRESOLVED"      # UNRESOLVED, RESOLVED
    resolution_notes: Optional[str] = None
    resolved_by: Optional[str] = None
    user_id: str = "default_user"
    database_identity: str = "default_db"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeConflict:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class KnowledgeVersionRecord:
    """
    Historical audit trail of a business definition or rule.
    """
    version_id: str
    item_id: str
    item_type: str                  # "METRIC", "RULE", "ENTITY"
    version: int
    snapshot: dict[str, Any]
    change_summary: str
    user_id: str
    database_identity: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeVersionRecord:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class KnowledgeLineageNode:
    """
    A single node in the end-to-end knowledge lineage trace.
    """
    step: str
    type: str                       # ENTITY, METRIC, DEFINITION, RULE, TABLE, COLUMN, SQL
    label: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class KnowledgeLineage:
    """
    Full trace from business concept down to executable SQL calculation.
    """
    target_id: str
    target_name: str
    nodes: list[KnowledgeLineageNode] = field(default_factory=list)
    provenance: str = KnowledgeProvenance.SCHEMA_DERIVED.value
    status: str = KnowledgeStatus.PROPOSED.value
    sql_expression: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "target_name": self.target_name,
            "nodes": [n.to_dict() for n in self.nodes],
            "provenance": self.provenance,
            "status": self.status,
            "sql_expression": self.sql_expression,
        }


@dataclass
class KnowledgeExplanation:
    """
    Transparent explanation answering why BG AI understands a concept this way,
    clearly separating facts, inferences, and user-provided rules.
    """
    knowledge_id: str
    title: str
    provenance: str
    status: str
    version: int
    facts: list[str] = field(default_factory=list)
    inferences: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    rules_applied: list[str] = field(default_factory=list)
    source_description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContextParseResult:
    """
    Result of parsing a natural language business context statement.
    Always produces a PROPOSED rule/definition requiring confirmation.
    """
    raw_statement: str
    parsed_successfully: bool
    proposed_rule: Optional[BusinessRule] = None
    referenced_tables: list[str] = field(default_factory=list)
    referenced_columns: list[str] = field(default_factory=list)
    affected_metrics: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    ambiguity_notes: list[str] = field(default_factory=list)
    requires_user_confirmation: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_statement": self.raw_statement,
            "parsed_successfully": self.parsed_successfully,
            "proposed_rule": self.proposed_rule.to_dict() if self.proposed_rule else None,
            "referenced_tables": self.referenced_tables,
            "referenced_columns": self.referenced_columns,
            "affected_metrics": self.affected_metrics,
            "assumptions": self.assumptions,
            "ambiguity_notes": self.ambiguity_notes,
            "requires_user_confirmation": self.requires_user_confirmation,
        }


@dataclass
class KnowledgeSummary:
    """
    Executive summary of the Enterprise Knowledge base for the active database.
    """
    total_entities: int = 0
    total_metrics: int = 0
    total_rules: int = 0
    confirmed_rules_count: int = 0
    proposed_rules_count: int = 0
    conflicts_count: int = 0
    unconfirmed_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
