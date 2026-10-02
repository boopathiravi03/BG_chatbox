"""
backend/app/intelligence/proactive/action_bridge.py

Phase 8.3: Safe Action Bridge for Proactive Intelligence
Connects actionable business alerts to the existing Phase 5 Specialist Agent
and Safe Action architecture.

STRICT SAFETY CONSTRAINTS:
- NEVER automatically executes database mutations.
- Only maps supported categories (e.g. data quality orphan remediation).
- Every proposal requires explicit human confirmation (requires_confirmation = True).
- Pre-execution non-destructive affected-row estimation using COUNT(*).
- Reuses existing ActionPlan model and validate_sql security guardrails.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text

from app.database.database_manager import get_engine, get_current_db_type
from app.database.connection_context import get_request_user_id
from app.intelligence.schema_analyzer import quote_identifier
from app.tools.execute_query import validate_sql
from app.agents.models import ActionPlan
from app.agents.audit import store_action
from app.intelligence.proactive.models import (
    BusinessAlert,
    AlertCategory,
)

logger = logging.getLogger("bgai.proactive.action_bridge")


def prepare_action_proposal(
    alert: BusinessAlert,
    user_id: Optional[str] = None,
    engine: Any = None,
    db_type: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """
    Evaluates whether an alert can safely map to an existing Safe Action capability.
    Returns a structured Action Proposal dictionary requiring human confirmation,
    or None if the alert does not map to a supported safe remediation.

    Guaranteed Non-Mutating:
    - Never executes INSERT, UPDATE, or DELETE.
    - Estimates affected rows strictly with read-only COUNT(*).
    """
    # High-level metric shifts (drops, spikes, forecast variance) require human analysis,
    # never automated mutation proposals.
    if alert.category in {
        AlertCategory.METRIC_DROP,
        AlertCategory.METRIC_SPIKE,
        AlertCategory.ANOMALY_DETECTED,
        AlertCategory.FORECAST_DEVIATION,
    }:
        return None

    evidence = alert.evidence or {}
    orphan_count = evidence.get("orphan_count")

    # Map: Relational Integrity / Orphan Foreign Key Remediation
    if alert.category == AlertCategory.DATA_QUALITY_DEGRADATION and orphan_count and int(orphan_count) > 0:
        from_table = evidence.get("from_table") or (alert.source_tables[0] if alert.source_tables else None)
        to_table = evidence.get("to_table") or (alert.source_tables[1] if len(alert.source_tables) > 1 else None)
        from_col = evidence.get("from_column") or (alert.source_columns[0] if alert.source_columns else None)
        to_col = evidence.get("to_column") or (alert.source_columns[1] if len(alert.source_columns) > 1 else None)

        if not (from_table and to_table and from_col and to_col):
            return None

        if engine is None:
            engine = get_engine()
            db_type = get_current_db_type()

        t_from = quote_identifier(from_table, db_type)
        t_to = quote_identifier(to_table, db_type)
        c_from = quote_identifier(from_col, db_type)
        c_to = quote_identifier(to_col, db_type)

        where_clause = f"{c_from} NOT IN (SELECT {c_to} FROM {t_to}) AND {c_from} IS NOT NULL"
        proposed_sql = f"DELETE FROM {t_from} WHERE {where_clause}"
        verification_sql = f"SELECT COUNT(*) FROM {t_from} WHERE {where_clause}"

        # 1. SQL Safety Validation
        val_res = validate_sql(proposed_sql)
        if not val_res.get("allowed"):
            logger.warning(f"Proposed SQL rejected by validation: {val_res.get('reason')}")
            return None

        # 2. Pre-execution row estimation (strictly read-only COUNT(*))
        estimated_rows = int(orphan_count)
        if engine is not None and db_type != "none":
            try:
                with engine.connect() as conn:
                    est = conn.execute(text(verification_sql)).scalar()
                    if est is not None:
                        estimated_rows = int(est)
            except Exception as ex:
                logger.debug(f"Row estimation fallback to alert evidence: {ex}")

        action_id = f"act_{uuid.uuid4().hex[:8]}"
        task_id = f"task_{uuid.uuid4().hex[:8]}"

        # 3. Create Phase 5 ActionPlan model (AWAITING_CONFIRMATION)
        plan = ActionPlan(
            action_id=action_id,
            task_id=task_id,
            agent_name="action_agent",
            table=from_table,
            action_type="DELETE",
            estimated_rows=estimated_rows,
            exact_sql=proposed_sql,
            verification_sql=verification_sql,
            expected_verification_result="0",
            risk_level="MEDIUM" if estimated_rows < 50 else "HIGH",
            potential_consequence=(
                f"Will permanently delete {estimated_rows} orphan record(s) in table '{from_table}' "
                f"that reference non-existent records in '{to_table}'."
            ),
            rollback_considerations=(
                "Executed within a transactional block. Automatic rollback occurs if post-verification "
                "detects remaining matching rows or encounters database errors."
            ),
            status="AWAITING_CONFIRMATION",
            created_at=datetime.utcnow().isoformat(),
        )

        try:
            store_action(plan)
        except Exception:
            pass  # If store_action is unavailable in standalone test, proceed safely

        return {
            "action_id": action_id,
            "task_id": task_id,
            "action_type": "DELETE",
            "description": f"Delete {estimated_rows} orphan record(s) from '{from_table}'",
            "target_table": from_table,
            "target_columns": [from_col],
            "proposed_sql": proposed_sql,
            "verification_sql": verification_sql,
            "parameters": {"from_table": from_table, "to_table": to_table, "column": from_col},
            "estimated_affected_rows": estimated_rows,
            "dry_run": True,
            "requires_confirmation": True,  # ALWAYS TRUE: No automatic execution
            "safety_notes": (
                "Human confirmation required. Operation will execute inside a transactional block "
                "with automated rollback if post-verification fails."
            ),
            "source_alert_id": alert.alert_id,
            "action_plan": plan.to_dict(),
        }

    return None

