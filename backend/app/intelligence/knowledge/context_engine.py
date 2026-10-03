"""
backend/app/intelligence/knowledge/context_engine.py

Phase 9.1: Natural Language Business Context Parser & Ingestion Engine
Parses user-provided natural language statements into structured BusinessRules.
Follows strict safety:
- Deterministic regex & keyword extraction first.
- Always generates PROPOSED rules that require explicit human confirmation.
- Transparently records referenced tables, columns, and semantic assumptions.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Optional

from app.intelligence.schema_analyzer import analyze_schema
from app.intelligence.knowledge.models import (
    BusinessRule,
    ContextParseResult,
    KnowledgeProvenance,
    KnowledgeStatus,
    RuleScope,
    RuleType,
)
from app.intelligence.knowledge.knowledge_store import save_rule
from app.intelligence.knowledge.business_rules import detect_rule_conflicts

logger = logging.getLogger("bgai.knowledge.context_engine")


def parse_and_propose_context(
    statement: str,
    user_id: str,
    database_identity: str,
    engine: Any = None,
    db_type: str = "none",
) -> ContextParseResult:
    """
    Parses a user-supplied business context statement, extracts intent and schema targets,
    and returns a structured PROPOSED BusinessRule with explicit assumptions.
    Never activates automatically without human confirmation.
    """
    cleaned_statement = statement.strip()
    if not cleaned_statement:
        return ContextParseResult(
            raw_statement=statement,
            parsed_successfully=False,
            ambiguity_notes=["Empty statement provided."],
        )

    # Schema introspection for table/column matching
    schema_info = {}
    if engine and db_type != "none":
        try:
            schema_info = analyze_schema(engine, db_type)
        except Exception as e:
            logger.warning("Schema analysis in context engine failed: %s", str(e))

    tables = schema_info.get("tables", {})
    lower_stmt = cleaned_statement.lower()

    # 1. Detect target table
    target_table = ""
    for tbl in tables.keys():
        clean_tbl = re.sub(r"^(tbl_|dim_|fact_|t_)", "", tbl.lower())
        if clean_tbl in lower_stmt or tbl.lower() in lower_stmt:
            target_table = tbl
            break

    # Default fallback heuristic if orders / sales / customers mentioned
    if not target_table:
        if "order" in lower_stmt or "revenue" in lower_stmt or "sale" in lower_stmt:
            for tbl in tables.keys():
                if "order" in tbl.lower() or "sale" in tbl.lower():
                    target_table = tbl
                    break
        elif "customer" in lower_stmt or "user" in lower_stmt or "churn" in lower_stmt:
            for tbl in tables.keys():
                if "customer" in tbl.lower() or "user" in tbl.lower():
                    target_table = tbl
                    break

    # If still no table matched from schema, use first table or default
    if not target_table and tables:
        target_table = list(tables.keys())[0]
    elif not target_table:
        target_table = "orders"

    # 2. Detect target column
    target_column = ""
    tbl_cols = [c.get("name") if isinstance(c, dict) else str(c) for c in tables.get(target_table, {}).get("columns", [])]
    
    # Priority checks for common column roles
    if "status" in tbl_cols:
        target_column = "status"
    elif "state" in tbl_cols:
        target_column = "state"
    else:
        for c in tbl_cols:
            if c.lower() in lower_stmt:
                target_column = c
                break

    # 3. Detect Rule Type and Expression
    rule_type = RuleType.EXCLUSION.value
    expression = ""
    affected_metrics = ["Revenue", "Total Amount"] if "revenue" in lower_stmt or "sale" in lower_stmt else ["Total Count"]
    assumptions = []

    # Pattern A: Exclusion (e.g. "Cancelled orders should not count toward revenue", "Exclude cancelled from revenue")
    excl_match = re.search(
        r"([a-zA-Z0-9_\'\"]+)\s+(?:orders|records|items|transactions)?\s*(?:should not count|do not count|don't count|are excluded)",
        lower_stmt
    )
    if not excl_match:
        excl_match = re.search(
            r"(?:exclude|omit|remove|ignore|do not count|don't count|should not count)\s+([a-zA-Z0-9_\'\"]+)",
            lower_stmt
        )

    if excl_match:
        val = excl_match.group(1).strip().strip("'\"")
        # Clean common words
        val = re.sub(r"\b(orders|records|items|sales|toward|from|for)\b", "", val).strip()
        if not val and "cancel" in lower_stmt:
            val = "cancelled"

        rule_type = RuleType.EXCLUSION.value
        col_to_use = target_column or "status"
        expression = f"{col_to_use} != '{val}'"
        assumptions.append(f"Mapped exclusion of '{val}' to condition '{expression}' on table '{target_table}'.")

    # Pattern B: Inclusion (e.g. "Only count completed transactions as valid sales")
    elif "only" in lower_stmt and ("count" in lower_stmt or "include" in lower_stmt or "valid" in lower_stmt):
        inc_match = re.search(r"only\s+(?:count|include)?\s*([a-zA-Z0-9_\'\"]+)", lower_stmt)
        val = inc_match.group(1).strip().strip("'\"") if inc_match else "completed"
        val = re.sub(r"\b(orders|records|items|sales|transactions)\b", "", val).strip() or "completed"
        rule_type = RuleType.INCLUSION.value
        col_to_use = target_column or "status"
        expression = f"{col_to_use} = '{val}'"
        assumptions.append(f"Mapped inclusion of '{val}' to condition '{expression}' on table '{target_table}'.")

    # Pattern C: Churn definition
    elif "churn" in lower_stmt:
        days_match = re.search(r"([0-9]+)\s*days?", lower_stmt)
        days = days_match.group(1) if days_match else "90"
        rule_type = RuleType.THRESHOLD.value
        expression = f"days_since_last_order > {days}"
        assumptions.append(f"Interpreted churn threshold as inactivity greater than {days} days.")
        affected_metrics = ["Customer Churn Rate", "Active Customers"]

    # Pattern D: Fiscal year definition
    elif "fiscal year" in lower_stmt:
        month_match = re.search(r"starts? in\s+([a-zA-Z]+)", lower_stmt)
        month = month_match.group(1).capitalize() if month_match else "April"
        rule_type = RuleType.TEMPORAL.value
        expression = f"fiscal_year_start_month = '{month}'"
        assumptions.append(f"Set organizational fiscal calendar start to {month}.")
        affected_metrics = ["Annual Revenue", "YTD Growth"]

    # Fallback generic custom rule
    else:
        rule_type = RuleType.EXCLUSION.value
        expression = f"{target_column or 'status'} IS NOT NULL"
        assumptions.append(f"General data quality filter derived for table '{target_table}'.")

    # Construct the proposed BusinessRule
    rule_id = f"rule_{uuid.uuid4().hex[:12]}"
    proposed_rule = BusinessRule(
        rule_id=rule_id,
        name=f"Rule: {cleaned_statement[:40]}...",
        description=cleaned_statement,
        scope=RuleScope.METRIC.value,
        target_table=target_table,
        target_column=target_column or None,
        rule_type=rule_type,
        expression=expression,
        status=KnowledgeStatus.PROPOSED.value,
        provenance=KnowledgeProvenance.USER_PROVIDED.value,
        version=1,
        affected_metrics=affected_metrics,
        user_id=user_id,
        database_identity=database_identity,
    )

    # Persist the rule as PROPOSED (so it is visible in the UI and can be confirmed or cancelled)
    save_rule(proposed_rule)

    # Check for conflicts against existing rules
    conflicts = detect_rule_conflicts(proposed_rule, user_id=user_id, database_identity=database_identity)
    if conflicts:
        proposed_rule.status = KnowledgeStatus.CONFLICTED.value
        save_rule(proposed_rule)
        assumptions.append(f"WARNING: Detected {len(conflicts)} conflict(s) with existing rules.")

    return ContextParseResult(
        raw_statement=cleaned_statement,
        parsed_successfully=True,
        proposed_rule=proposed_rule,
        referenced_tables=[target_table] if target_table else [],
        referenced_columns=[target_column] if target_column else [],
        affected_metrics=affected_metrics,
        assumptions=assumptions,
        requires_user_confirmation=True,
    )
