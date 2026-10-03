"""
backend/app/intelligence/knowledge/business_rules.py

Phase 9.1: Business Rule Engine & SQL Safety Gate
Validates business rules for SQL safety, table/column schema conformance,
detects semantic conflicts, and resolves active rule expressions for metric calculations.

Strict Safety Principle:
- ONLY CONFIRMED or ACTIVE rules can affect query filters or metric resolutions.
- PROPOSED, DRAFT, DISABLED, or CONFLICTED rules are strictly excluded from calculation.
- Rejects all DDL, DML, command chaining, and dangerous keywords.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Optional

from app.tools.execute_query import validate_sql
from app.intelligence.knowledge.models import (
    BusinessRule,
    KnowledgeConflict,
    KnowledgeStatus,
    RuleScope,
    RuleType,
)
from app.intelligence.knowledge.knowledge_store import (
    list_rules,
    save_conflict,
)

logger = logging.getLogger("bgai.knowledge.business_rules")

DANGEROUS_PATTERNS = [
    r";",                               # Command chaining
    r"--",                              # Comment injection
    r"/\*",                             # Block comment
    r"\b(drop|alter|truncate|create|attach|detach)\b",  # DDL
    r"\b(insert|update|delete|merge|upsert)\b",          # DML
    r"\b(grant|revoke|call|exec|execute)\b",             # Admin/RPC
    r"\b(union\s+select|select\s+.*from)\b",             # Subqueries/Union
]


def validate_rule_safety(
    expression: str,
    target_table: str,
    target_column: Optional[str] = None,
    schema_info: Optional[dict[str, Any]] = None,
) -> tuple[bool, str]:
    """
    Validates that a business rule expression is safe and adheres to active schema.
    Returns (is_valid, error_message).
    """
    expr_clean = expression.strip()
    if not expr_clean:
        return False, "Rule expression cannot be empty."

    # Check for dangerous patterns
    for pat in DANGEROUS_PATTERNS:
        if re.search(pat, expr_clean, re.IGNORECASE):
            return False, f"Rule expression contains disallowed SQL pattern: '{pat}'."

    # Schema conformance checks if schema_info is supplied
    if schema_info:
        tables = schema_info.get("tables", {})
        if target_table and target_table not in tables:
            return False, f"Target table '{target_table}' does not exist in active database schema."

        if target_table and target_column:
            cols = [c.get("name") if isinstance(c, dict) else str(c) for c in tables.get(target_table, {}).get("columns", [])]
            if cols and target_column not in cols:
                return False, f"Target column '{target_column}' does not exist in table '{target_table}'."

    return True, ""


def detect_rule_conflicts(
    new_rule: BusinessRule,
    user_id: str,
    database_identity: str,
) -> list[KnowledgeConflict]:
    """
    Scans existing rules to detect semantic contradictions.
    Example: 'status != cancelled' vs 'status == cancelled' or opposite scope actions.
    """
    existing_rules = list_rules(user_id=user_id, database_identity=database_identity)
    conflicts: list[KnowledgeConflict] = []

    for er in existing_rules:
        if er.rule_id == new_rule.rule_id:
            continue

        # Check same table and column targeting
        if er.target_table == new_rule.target_table and er.target_column == new_rule.target_column:
            expr1 = er.expression.replace(" ", "").lower()
            expr2 = new_rule.expression.replace(" ", "").lower()

            # Opposing operators check (!= vs = or ==)
            has_opposite_ops = (
                ("!=" in expr1 and ("=" in expr2 or "==" in expr2) and "!=" not in expr2) or
                ("!=" in expr2 and ("=" in expr1 or "==" in expr1) and "!=" not in expr1)
            )

            # Direct negation check
            is_contradiction = has_opposite_ops or (
                er.rule_type == RuleType.EXCLUSION.value and new_rule.rule_type == RuleType.INCLUSION.value
            )

            if is_contradiction:
                conflict = KnowledgeConflict(
                    conflict_id=f"conf_{uuid.uuid4().hex[:12]}",
                    knowledge_type="RULE",
                    item_id_a=er.rule_id,
                    item_id_b=new_rule.rule_id,
                    target_name=f"{new_rule.target_table}.{new_rule.target_column or '*'}",
                    description=f"Direct logical conflict detected between rule '{er.name}' and rule '{new_rule.name}'.",
                    statement_a=er.expression,
                    statement_b=new_rule.expression,
                    source_a=er.provenance,
                    source_b=new_rule.provenance,
                    status="UNRESOLVED",
                    user_id=user_id,
                    database_identity=database_identity,
                )
                save_conflict(conflict)
                conflicts.append(conflict)

    return conflicts


def get_active_filters_for_table(
    table_name: str,
    user_id: str,
    database_identity: str,
) -> list[str]:
    """
    Retrieves all safe SQL filter expressions for a table from CONFIRMED or ACTIVE rules ONLY.
    PROPOSED, DISABLED, or CONFLICTED rules are never returned.
    """
    rules = list_rules(
        user_id=user_id,
        database_identity=database_identity,
        target_table=table_name,
    )

    active_expressions: list[str] = []
    for r in rules:
        if r.status in {KnowledgeStatus.CONFIRMED.value, KnowledgeStatus.ACTIVE.value}:
            if r.expression:
                active_expressions.append(r.expression)

    return active_expressions
