"""
backend/app/intelligence/actions/action_policy.py

Phase 8.8: Action Risk Policy & Sensitivity Rules
Provides deterministic classification of action risks and identifies
business-critical database entities without arbitrary percentages.
"""
from __future__ import annotations

import re
from typing import Optional, Sequence

from app.intelligence.actions.models import ActionRisk, ActionType

# Business-critical terms that indicate financial, authorization, or operational risk
BUSINESS_CRITICAL_COLUMNS = frozenset({
    "price", "unit_price", "amount", "balance", "salary", "wage",
    "status", "inventory", "stock", "credit", "payment", "role",
    "permission", "cost", "total", "revenue", "discount", "is_admin",
    "tax", "rate", "fee"
})

# System tables that must NEVER be mutated
SYSTEM_TABLE_PATTERNS = [
    re.compile(r"^sqlite_", re.IGNORECASE),
    re.compile(r"^pg_", re.IGNORECASE),
    re.compile(r"^information_schema", re.IGNORECASE),
    re.compile(r"^mysql", re.IGNORECASE),
    re.compile(r"^performance_schema", re.IGNORECASE),
    re.compile(r"^sys", re.IGNORECASE),
]


def is_system_table(table_name: str) -> bool:
    """Return True if the table is an internal system catalog."""
    tbl = table_name.strip()
    return any(p.match(tbl) for p in SYSTEM_TABLE_PATTERNS)


def is_business_critical_column(column_name: str) -> bool:
    """
    Return True if the column matches known sensitive/business-critical tokens.
    Uses tokenization so 'order_status' or 'product_price' matches.
    """
    col_clean = column_name.strip().lower()
    if col_clean in BUSINESS_CRITICAL_COLUMNS:
        return True
    tokens = re.split(r"[_\-\s]+", col_clean)
    return any(t in BUSINESS_CRITICAL_COLUMNS for t in tokens)


def classify_action_risk(
    action_type: str,
    table_name: str,
    target_columns: Sequence[str],
    estimated_rows: int = 1,
    condition_sql: Optional[str] = None,
    is_blocked: bool = False,
    has_foreign_dependents: bool = False,
) -> ActionRisk:
    """
    Deterministically classify action risk into LOW, MEDIUM, HIGH, or BLOCKED.
    """
    if is_blocked:
        return ActionRisk.BLOCKED

    # System tables are always blocked
    if is_system_table(table_name):
        return ActionRisk.BLOCKED

    act_type = action_type.upper().strip()

    # DDL or unsupported commands
    if act_type not in (ActionType.INSERT.value, ActionType.UPDATE.value, ActionType.DELETE.value):
        return ActionRisk.BLOCKED

    # Unrestricted mutations are BLOCKED
    if act_type in (ActionType.UPDATE.value, ActionType.DELETE.value):
        if not condition_sql or not condition_sql.strip():
            return ActionRisk.BLOCKED
        # Check for trivial tautologies like 1=1 or true
        cleaned_cond = condition_sql.strip().lower()
        if cleaned_cond in ("1=1", "1 = 1", "true", "1", "'1'='1'"):
            return ActionRisk.BLOCKED

    # DELETE is always HIGH risk
    if act_type == ActionType.DELETE.value:
        return ActionRisk.HIGH

    # Multiple affected records > 5 is HIGH risk
    if estimated_rows > 5:
        return ActionRisk.HIGH

    # Check for business-critical columns
    if any(is_business_critical_column(c) for c in target_columns):
        return ActionRisk.HIGH

    # If deleting or updating a record that has active foreign key dependents
    if has_foreign_dependents:
        return ActionRisk.HIGH

    # Multi-row update (2 to 5 rows)
    if estimated_rows > 1:
        return ActionRisk.MEDIUM

    # Single-row non-critical update or insert
    return ActionRisk.LOW
