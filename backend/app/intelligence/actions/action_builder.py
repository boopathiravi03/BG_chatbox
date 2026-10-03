"""
backend/app/intelligence/actions/action_builder.py

Phase 8.8: Action Proposal Builder
Constructs parameterized action proposals from recommendations, decision plans,
or explicit business requests with multi-layer validation and impact previews.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Sequence
from sqlalchemy.engine import Engine

from app.intelligence.actions.models import (
    ActionProposal,
    ActionTarget,
    ActionChange,
    ActionType,
    ActionStatus,
    ActionRisk,
)
from app.intelligence.actions.action_validator import validate_action
from app.intelligence.actions.impact_preview import calculate_impact_preview
from app.intelligence.schema_analyzer import quote_identifier


def build_action_proposal(
    user_id: str,
    action_type: str,
    target_table: str,
    changes: Sequence[dict[str, Any] | ActionChange],
    condition_sql: Optional[str] = None,
    condition_params: Optional[dict[str, Any]] = None,
    reason: str = "",
    source_signal_id: Optional[str] = None,
    engine: Optional[Engine] = None,
    db_type: str = "sqlite",
    database_identity: str = "none",
) -> ActionProposal:
    """
    Constructs and validates a new ActionProposal.
    Enforces unambiguous targeting, prepares parameterized SQL, and evaluates dry-run impact.
    """
    act_id = f"act_{uuid.uuid4().hex[:8]}"
    now_str = datetime.now(timezone.utc).isoformat()
    clean_act_type = action_type.upper().strip()

    # Normalize changes
    action_changes: list[ActionChange] = []
    for c in changes:
        if isinstance(c, ActionChange):
            action_changes.append(c)
        elif isinstance(c, dict):
            action_changes.append(
                ActionChange(
                    column=c.get("column", ""),
                    current_value=c.get("current_value"),
                    proposed_value=c.get("proposed_value"),
                    value_type=c.get("value_type"),
                )
            )

    target_cols = [c.column for c in action_changes]
    target = ActionTarget(
        table=target_table.strip(),
        columns=target_cols,
        condition_sql=condition_sql.strip() if condition_sql else None,
        condition_params=dict(condition_params or {}),
    )

    # Build Parameterized SQL and Preview
    table_q = quote_identifier(target_table, db_type)
    sql_preview = ""
    param_sql = ""
    parameters: dict[str, Any] = dict(condition_params or {})

    if clean_act_type == ActionType.UPDATE.value:
        set_clauses = []
        preview_clauses = []
        for idx, chg in enumerate(action_changes):
            param_name = f"val_{idx}"
            col_q = quote_identifier(chg.column, db_type)
            set_clauses.append(f"{col_q} = :{param_name}")
            parameters[param_name] = chg.proposed_value

            # Format preview with human-readable literals
            pv = chg.proposed_value
            lit_val = f"'{pv}'" if isinstance(pv, str) else str(pv)
            preview_clauses.append(f"{col_q} = {lit_val}")

        where_clause = f"WHERE {condition_sql}" if condition_sql else ""
        param_sql = f"UPDATE {table_q} SET {', '.join(set_clauses)} {where_clause}".strip()
        sql_preview = f"UPDATE {table_q} SET {', '.join(preview_clauses)} {where_clause}".strip()

    elif clean_act_type == ActionType.INSERT.value:
        col_names = []
        param_placeholders = []
        preview_vals = []
        for idx, chg in enumerate(action_changes):
            param_name = f"val_{idx}"
            col_q = quote_identifier(chg.column, db_type)
            col_names.append(col_q)
            param_placeholders.append(f":{param_name}")
            parameters[param_name] = chg.proposed_value

            pv = chg.proposed_value
            lit_val = f"'{pv}'" if isinstance(pv, str) else str(pv)
            preview_vals.append(lit_val)

        param_sql = f"INSERT INTO {table_q} ({', '.join(col_names)}) VALUES ({', '.join(param_placeholders)})"
        sql_preview = f"INSERT INTO {table_q} ({', '.join(col_names)}) VALUES ({', '.join(preview_vals)})"

    elif clean_act_type == ActionType.DELETE.value:
        where_clause = f"WHERE {condition_sql}" if condition_sql else ""
        param_sql = f"DELETE FROM {table_q} {where_clause}".strip()
        sql_preview = param_sql

    proposal = ActionProposal(
        action_id=act_id,
        user_id=user_id,
        action_type=clean_act_type,
        status=ActionStatus.PROPOSED.value,
        target=target,
        changes=action_changes,
        reason=reason or f"Controlled {clean_act_type} action on {target_table}",
        source_signal_id=source_signal_id,
        risk=ActionRisk.LOW.value,
        sql_preview=sql_preview,
        parameterized_sql=param_sql,
        parameters=parameters,
        created_at=now_str,
        updated_at=now_str,
        database_identity=database_identity,
    )

    # 1. Validation Layer
    validation = validate_action(proposal, engine=engine)
    proposal.validation = validation

    if not validation.is_valid:
        proposal.status = ActionStatus.BLOCKED.value
        proposal.risk = ActionRisk.BLOCKED.value
        return proposal

    # 2. Impact Preview Layer
    impact, risk = calculate_impact_preview(proposal, engine=engine, db_type=db_type)
    proposal.impact = impact
    proposal.risk = risk.value

    # Update status based on risk and excessive impact
    if risk == ActionRisk.BLOCKED or impact.is_excessive:
        proposal.status = ActionStatus.BLOCKED.value
    else:
        proposal.status = ActionStatus.READY_FOR_CONFIRMATION.value

    return proposal
