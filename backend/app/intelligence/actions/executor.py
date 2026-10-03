"""
backend/app/intelligence/actions/executor.py

Phase 8.8: Transactional Action Executor
Safely executes validated and explicitly confirmed mutations within strict
transaction boundaries, verifies state, and audits the result.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.intelligence.actions.models import (
    ActionProposal,
    ActionStatus,
    ActionRisk,
    ActionExecutionResult,
    ActionAuditRecord,
)
from app.intelligence.actions.confirmation import validate_confirmation_token
from app.intelligence.actions.verification import verify_action_execution
from app.intelligence.actions.action_audit import save_action, record_audit


class ActionExecutionConflict(Exception):
    """Raised when an action has already executed (duplicate execution protection)."""
    pass


class ActionExecutionError(Exception):
    """Raised when pre-conditions, tokens, or transaction checks fail."""
    pass


def execute_action(
    proposal: ActionProposal,
    engine: Engine,
    user_id: str,
    confirmation_token: str,
    current_db_identity: str,
    db_type: str = "sqlite",
) -> ActionExecutionResult:
    """
    Executes a confirmed action within an atomic transaction.
    Enforces token validation, transaction boundaries, post-verification, and audit logging.
    """
    now_str = datetime.now(timezone.utc).isoformat()
    tx_id = f"tx_{uuid.uuid4().hex[:8]}"

    # 1. Duplicate execution guard
    if proposal.status in (ActionStatus.EXECUTED.value, ActionStatus.VERIFIED.value):
        raise ActionExecutionConflict(
            f"Action '{proposal.action_id}' has already been executed (state: {proposal.status}). Duplicate execution blocked."
        )

    # 2. State progression guard
    if proposal.status != ActionStatus.CONFIRMED.value:
        raise ActionExecutionError(
            f"Action '{proposal.action_id}' cannot be executed in state '{proposal.status}'. "
            "Action must be explicitly confirmed first."
        )

    # 3. Confirmation token validation
    if not proposal.confirmation or not proposal.confirmation.confirmation_token:
        raise ActionExecutionError("Action has no confirmation record.")

    # Match token
    token_to_verify = confirmation_token or proposal.confirmation.confirmation_token
    is_valid_token, token_err = validate_confirmation_token(
        token_str=token_to_verify,
        proposal=proposal,
        user_id=user_id,
        current_db_identity=current_db_identity,
    )
    if not is_valid_token:
        proposal.status = ActionStatus.REJECTED.value
        save_action(proposal)
        raise ActionExecutionError(f"Confirmation validation failed: {token_err}")

    # 4. High-risk acknowledgement check
    if proposal.risk == ActionRisk.HIGH.value:
        if not proposal.confirmation.high_risk_acknowledged:
            raise ActionExecutionError(
                "Execution blocked: High-risk actions require explicit high-risk acknowledgement checkbox."
            )

    # 5. Database identity consistency
    if proposal.database_identity != current_db_identity:
        raise ActionExecutionError(
            "Active database connection has changed since this action was prepared. Re-plan required."
        )

    # 6. Prepare parameterized execution
    sql = proposal.parameterized_sql or proposal.sql_preview
    if not sql:
        raise ActionExecutionError("Action proposal contains no executable SQL statement.")

    params = proposal.parameters or {}

    proposal.status = ActionStatus.EXECUTING.value
    save_action(proposal)

    actual_affected = 0
    try:
        # Atomic Transaction Boundary
        with engine.begin() as conn:
            stmt = text(sql)
            res = conn.execute(stmt, params)
            raw_affected = res.rowcount
            actual_affected = int(raw_affected) if (raw_affected is not None and raw_affected >= 0) else 1

        # Post-execution verification against live database
        verification = verify_action_execution(
            proposal=proposal,
            engine=engine,
            db_type=db_type,
        )
        proposal.verification = verification

        final_status = ActionStatus.VERIFIED.value if verification.verified else ActionStatus.VERIFICATION_FAILED.value
        proposal.status = final_status

        exec_res = ActionExecutionResult(
            success=verification.verified,
            action_id=proposal.action_id,
            status=final_status,
            actual_rows_affected=actual_affected,
            executed_at=now_str,
            error=None if verification.verified else verification.details,
            transaction_id=tx_id,
        )
        proposal.execution_result = exec_res
        save_action(proposal)

        # Audit entry
        audit_rec = ActionAuditRecord(
            audit_id=f"aud_{uuid.uuid4().hex[:8]}",
            action_id=proposal.action_id,
            user_id=user_id,
            timestamp=now_str,
            action_type=proposal.action_type,
            target_table=proposal.target.table,
            target_columns=[c.column for c in proposal.changes],
            reason=proposal.reason,
            source_signal=proposal.source_signal_id,
            risk=proposal.risk,
            affected_rows=actual_affected,
            confirmation_token=proposal.confirmation.confirmation_token,
            execution_status="SUCCESS",
            verification_status="VERIFIED" if verification.verified else "FAILED",
            error=exec_res.error,
            database_identity=current_db_identity,
        )
        record_audit(audit_rec)

        return exec_res

    except Exception as e:
        # Transaction safely rolled back automatically by context manager
        err_msg = str(e)
        proposal.status = ActionStatus.EXECUTION_FAILED.value
        exec_res = ActionExecutionResult(
            success=False,
            action_id=proposal.action_id,
            status=ActionStatus.EXECUTION_FAILED.value,
            actual_rows_affected=0,
            executed_at=now_str,
            error=err_msg,
            transaction_id=tx_id,
        )
        proposal.execution_result = exec_res
        save_action(proposal)

        # Record failure audit
        audit_rec = ActionAuditRecord(
            audit_id=f"aud_{uuid.uuid4().hex[:8]}",
            action_id=proposal.action_id,
            user_id=user_id,
            timestamp=now_str,
            action_type=proposal.action_type,
            target_table=proposal.target.table,
            target_columns=[c.column for c in proposal.changes],
            reason=proposal.reason,
            source_signal=proposal.source_signal_id,
            risk=proposal.risk,
            affected_rows=0,
            confirmation_token=proposal.confirmation.confirmation_token if proposal.confirmation else None,
            execution_status="FAILED",
            verification_status="UNVERIFIED",
            error=err_msg,
            database_identity=current_db_identity,
        )
        record_audit(audit_rec)

        raise ActionExecutionError(f"Execution failed (transaction rolled back): {err_msg}")
