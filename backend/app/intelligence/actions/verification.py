"""
backend/app/intelligence/actions/verification.py

Phase 8.8: Post-Execution Verification
Validates that mutations actually took effect in the live database
and match the expected state.
"""
from __future__ import annotations

from typing import Any, Optional
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.intelligence.actions.models import (
    ActionProposal,
    ActionType,
    ActionVerification,
)
from app.intelligence.schema_analyzer import quote_identifier


def verify_action_execution(
    proposal: ActionProposal,
    engine: Engine,
    db_type: str = "sqlite",
) -> ActionVerification:
    """
    Executes post-mutation verification queries to confirm database state matches
    the approved proposal.
    """
    act_type = (proposal.action_type or "").upper().strip()
    table_name = proposal.target.table
    table_q = quote_identifier(table_name, db_type)
    cond = (proposal.target.condition_sql or "").strip()
    params = proposal.target.condition_params or {}

    try:
        if act_type == ActionType.DELETE.value:
            # For DELETE, the affected rows should now be 0
            v_sql = f"SELECT COUNT(*) FROM {table_q} WHERE {cond}"
            with engine.connect() as conn:
                res = conn.execute(text(v_sql), params)
                remaining_count = int(res.scalar() or 0)

            verified = (remaining_count == 0)
            details = (
                "Verified: Target record(s) no longer exist in database."
                if verified
                else f"Verification warning: {remaining_count} records still match the delete condition."
            )
            return ActionVerification(
                verified=verified,
                verification_sql=v_sql,
                expected_value=0,
                actual_value=remaining_count,
                details=details,
            )

        elif act_type == ActionType.UPDATE.value:
            if not proposal.changes:
                return ActionVerification(
                    verified=True,
                    verification_sql="-- No columns changed",
                    details="No column changes to verify.",
                )

            # Check the first modified column
            target_col = proposal.changes[0].column
            target_col_q = quote_identifier(target_col, db_type)
            expected_val = proposal.changes[0].proposed_value

            v_sql = f"SELECT {target_col_q} FROM {table_q} WHERE {cond} LIMIT 1"
            with engine.connect() as conn:
                res = conn.execute(text(v_sql), params)
                row = res.fetchone()

            if row is None:
                return ActionVerification(
                    verified=False,
                    verification_sql=v_sql,
                    expected_value=expected_val,
                    actual_value=None,
                    details=f"Verification failed: Record matching condition '{cond}' could not be found.",
                )

            observed_val = row[0]

            # Compare values with type tolerance (e.g. float vs int vs str)
            verified = False
            if str(observed_val).strip() == str(expected_val).strip():
                verified = True
            elif isinstance(expected_val, (int, float)) and isinstance(observed_val, (int, float)):
                verified = abs(float(expected_val) - float(observed_val)) < 1e-5

            details = (
                f"Verified: {target_col} successfully updated to '{expected_val}'."
                if verified
                else f"Verification failed: Expected {target_col} to be '{expected_val}', but observed '{observed_val}'."
            )

            return ActionVerification(
                verified=verified,
                verification_sql=v_sql,
                expected_value=expected_val,
                actual_value=observed_val,
                details=details,
            )

        elif act_type == ActionType.INSERT.value:
            # For INSERT, verify that a record matching the inserted values exists
            check_clauses = []
            check_params: dict[str, Any] = {}
            for idx, chg in enumerate(proposal.changes):
                param_key = f"v_p_{idx}"
                check_clauses.append(f"{quote_identifier(chg.column, db_type)} = :{param_key}")
                check_params[param_key] = chg.proposed_value

            where_str = " AND ".join(check_clauses)
            v_sql = f"SELECT COUNT(*) FROM {table_q} WHERE {where_str}"
            with engine.connect() as conn:
                res = conn.execute(text(v_sql), check_params)
                match_count = int(res.scalar() or 0)

            verified = (match_count > 0)
            details = (
                "Verified: Newly inserted record confirmed in database."
                if verified
                else "Verification failed: Inserted record not found in database."
            )

            return ActionVerification(
                verified=verified,
                verification_sql=v_sql,
                expected_value=1,
                actual_value=match_count,
                details=details,
            )

    except Exception as e:
        return ActionVerification(
            verified=False,
            verification_sql=f"-- Verification error: {e}",
            expected_value=None,
            actual_value=None,
            details=f"Verification query failed with error: {e}",
        )

    return ActionVerification(
        verified=True,
        verification_sql="-- Verified",
        details="Action completed without verification errors.",
    )
