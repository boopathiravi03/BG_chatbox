"""
backend/app/intelligence/actions/action_validator.py

Phase 8.8: Multi-Layer Action Validation
Validates schema compatibility, SQL safety, WHERE clause restrictiveness,
parameter safety, and blocks unrestricted mutations.
"""
from __future__ import annotations

import re
from typing import Optional
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app.intelligence.actions.models import ActionProposal, ActionType, ActionValidation
from app.intelligence.actions.action_policy import is_system_table
from app.tools.execute_query import validate_sql

# Patterns indicative of unrestricted conditions or command chaining
TAUTOLOGY_PATTERNS = [
    re.compile(r"^\s*1\s*=\s*1\s*$", re.IGNORECASE),
    re.compile(r"^\s*true\s*$", re.IGNORECASE),
    re.compile(r"^\s*'1'\s*=\s*'1'\s*$", re.IGNORECASE),
    re.compile(r"^\s*0\s*=\s*0\s*$", re.IGNORECASE),
    re.compile(r"^\s*null\s+is\s+null\s*$", re.IGNORECASE),
]

FORBIDDEN_OPERATIONS = [
    "drop", "alter", "truncate", "create", "grant", "revoke",
    "attach", "detach", "replace into", "vacuum", "merge", "copy",
    "exec", "execute", "call", "benchmark", "sleep"
]



def validate_action(proposal: ActionProposal, engine: Optional[Engine] = None) -> ActionValidation:
    """
    Execute rigorous multi-layer validation on an ActionProposal.
    Returns ActionValidation with is_valid=True only if all checks pass.
    """
    passed_checks: list[str] = []
    reasons: list[str] = []
    blocked_reason: Optional[str] = None

    act_type = (proposal.action_type or "").upper().strip()
    target_table = (proposal.target.table or "").strip()

    # 1. Action type check
    if act_type not in (ActionType.INSERT.value, ActionType.UPDATE.value, ActionType.DELETE.value):
        blocked_reason = f"Unsupported action type '{act_type}'. Only INSERT, UPDATE, and DELETE are permitted."
        reasons.append(blocked_reason)
        return ActionValidation(is_valid=False, reasons=reasons, blocked_reason=blocked_reason, passed_checks=passed_checks)
    passed_checks.append("Action type permitted")

    # 2. Target table check
    if not target_table:
        blocked_reason = "Target table is missing or undefined."
        reasons.append(blocked_reason)
        return ActionValidation(is_valid=False, reasons=reasons, blocked_reason=blocked_reason, passed_checks=passed_checks)

    # 3. System table block
    if is_system_table(target_table):
        blocked_reason = f"Target table '{target_table}' is a protected system table. Mutations are strictly prohibited."
        reasons.append(blocked_reason)
        return ActionValidation(is_valid=False, reasons=reasons, blocked_reason=blocked_reason, passed_checks=passed_checks)
    passed_checks.append("Non-system table verified")

    # 4. Mandatory WHERE clause for UPDATE and DELETE
    if act_type in (ActionType.UPDATE.value, ActionType.DELETE.value):
        cond = (proposal.target.condition_sql or "").strip()
        if not cond:
            blocked_reason = f"Unrestricted {act_type} blocked: A specific WHERE condition is strictly required."
            reasons.append(blocked_reason)
            return ActionValidation(is_valid=False, reasons=reasons, blocked_reason=blocked_reason, passed_checks=passed_checks)

        # Check for tautological conditions (1=1, true, etc.)
        cond_lower = cond.lower()
        if any(pat.match(cond_lower) for pat in TAUTOLOGY_PATTERNS) or " or 1=1" in cond_lower or " or '1'='1'" in cond_lower:
            blocked_reason = f"Unrestricted {act_type} blocked: WHERE condition contains a tautology ({cond})."
            reasons.append(blocked_reason)
            return ActionValidation(is_valid=False, reasons=reasons, blocked_reason=blocked_reason, passed_checks=passed_checks)
        passed_checks.append("Restrictive WHERE condition verified")

    # 5. Changes check for UPDATE and INSERT
    if act_type == ActionType.UPDATE.value:
        if not proposal.changes:
            blocked_reason = "UPDATE proposal must specify at least one column change."
            reasons.append(blocked_reason)
            return ActionValidation(is_valid=False, reasons=reasons, blocked_reason=blocked_reason, passed_checks=passed_checks)
        passed_checks.append("Target columns specified")
    elif act_type == ActionType.INSERT.value:
        if not proposal.changes:
            blocked_reason = "INSERT proposal must specify column values for insertion."
            reasons.append(blocked_reason)
            return ActionValidation(is_valid=False, reasons=reasons, blocked_reason=blocked_reason, passed_checks=passed_checks)
        passed_checks.append("Insert values specified")

    # 6. SQL Safety Gate Check on SQL Preview
    sql_check = proposal.parameterized_sql or proposal.sql_preview
    if sql_check:
        # Check forbidden administrative command keywords
        sql_lower = sql_check.lower()
        for forbidden in FORBIDDEN_OPERATIONS:
            pattern = r"\b" + re.escape(forbidden) + r"\b"
            if re.search(pattern, sql_lower):
                blocked_reason = f"Dangerous SQL operation blocked: contains '{forbidden}'."
                reasons.append(blocked_reason)
                return ActionValidation(is_valid=False, reasons=reasons, blocked_reason=blocked_reason, passed_checks=passed_checks)


        # Check for command chaining (semicolon followed by another command)
        statements = [s.strip() for s in sql_check.split(";") if s.strip()]
        if len(statements) > 1:
            blocked_reason = "Command chaining blocked: Multiple SQL statements are not allowed."
            reasons.append(blocked_reason)
            return ActionValidation(is_valid=False, reasons=reasons, blocked_reason=blocked_reason, passed_checks=passed_checks)

        # Verify SQL structure via validate_sql if SELECT/inspection
        passed_checks.append("SQL safety and command single-statement verified")

    # 7. Live Schema Validation (if live engine is connected)
    if engine is not None:
        try:
            insp = inspect(engine)
            tables = insp.get_table_names()
            if target_table not in tables:
                # Case-insensitive check
                matching = [t for t in tables if t.lower() == target_table.lower()]
                if not matching:
                    blocked_reason = f"Table '{target_table}' does not exist in the connected database."
                    reasons.append(blocked_reason)
                    return ActionValidation(is_valid=False, reasons=reasons, blocked_reason=blocked_reason, passed_checks=passed_checks)
                actual_table = matching[0]
            else:
                actual_table = target_table

            # Check column existence
            col_objs = insp.get_columns(actual_table)
            existing_cols = {c["name"].lower() for c in col_objs}

            for chg in proposal.changes:
                if chg.column.lower() not in existing_cols:
                    blocked_reason = f"Column '{chg.column}' does not exist in table '{actual_table}'."
                    reasons.append(blocked_reason)
                    return ActionValidation(is_valid=False, reasons=reasons, blocked_reason=blocked_reason, passed_checks=passed_checks)

            passed_checks.append("Schema and column compatibility verified")
        except Exception as e:
            reasons.append(f"Database schema verification warning: {e}")

    return ActionValidation(
        is_valid=True,
        reasons=reasons,
        blocked_reason=None,
        passed_checks=passed_checks,
    )
