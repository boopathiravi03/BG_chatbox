"""
backend/app/intelligence/actions/impact_preview.py

Phase 8.8: Read-Only Impact Preview & Dry-Run Calculation
Simulates mutation impact, fetches sample current records, predicts proposed state,
checks referencing foreign keys, and assesses risk without altering user data.
"""
from __future__ import annotations

import copy
from typing import Any, Optional
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.intelligence.actions.models import (
    ActionProposal,
    ActionImpact,
    ActionType,
    ActionRisk,
)
from app.intelligence.actions.action_policy import classify_action_risk
from app.intelligence.schema_analyzer import quote_identifier

MAX_PERMITTED_AFFECTED_ROWS = 500


def calculate_impact_preview(
    proposal: ActionProposal,
    engine: Optional[Engine] = None,
    db_type: str = "sqlite",
) -> tuple[ActionImpact, ActionRisk]:
    """
    Dry-run simulation of an action proposal.
    Executes strictly READ-ONLY SELECT queries to preview affected records,
    related foreign keys, and determine whether impact is excessive.
    """
    warnings: list[str] = []
    current_samples: list[dict[str, Any]] = []
    proposed_samples: list[dict[str, Any]] = []
    related_counts: dict[str, int] = {}
    actual_count = 0
    is_excessive = False

    act_type = (proposal.action_type or "").upper().strip()
    table_name = proposal.target.table
    table_q = quote_identifier(table_name, db_type)
    condition = (proposal.target.condition_sql or "").strip()
    params = proposal.target.condition_params or {}

    if engine is None:
        # Offline estimation
        est = proposal.impact.estimated_rows if proposal.impact else 1
        return ActionImpact(
            estimated_rows=est,
            actual_preview_rows=est,
            warnings=["Offline preview: Database engine not currently attached."],
        ), ActionRisk.MEDIUM

    try:
        insp = inspect(engine)
        pks = insp.get_pk_constraint(table_name).get("constrained_columns", [])
        if not proposal.target.primary_keys and pks:
            proposal.target.primary_keys = pks

        if act_type in (ActionType.UPDATE.value, ActionType.DELETE.value):
            where_clause = f"WHERE {condition}" if condition else ""

            # 1. Count exact affected rows
            count_sql = f"SELECT COUNT(*) FROM {table_q} {where_clause}"
            with engine.connect() as conn:
                res = conn.execute(text(count_sql), params)
                actual_count = int(res.scalar() or 0)

            # 2. Check if excessive
            if actual_count > MAX_PERMITTED_AFFECTED_ROWS:
                is_excessive = True
                warnings.append(
                    f"Excessive impact: {actual_count} records match this condition. "
                    f"Actions affecting more than {MAX_PERMITTED_AFFECTED_ROWS} records are blocked for safety."
                )

            # 3. Fetch current sample records (max 10)
            sample_sql = f"SELECT * FROM {table_q} {where_clause} LIMIT 10"
            with engine.connect() as conn:
                sample_res = conn.execute(text(sample_sql), params)
                keys = list(sample_res.keys())
                for row in sample_res.fetchall():
                    rec = dict(zip(keys, row))
                    # Serialize values cleanly
                    clean_rec = {k: str(v) if not isinstance(v, (int, float, bool, type(None))) else v for k, v in rec.items()}
                    current_samples.append(clean_rec)

            # 4. Generate proposed sample records
            if act_type == ActionType.UPDATE.value:
                for rec in current_samples:
                    proposed_rec = copy.deepcopy(rec)
                    for chg in proposal.changes:
                        proposed_rec[chg.column] = chg.proposed_value
                    proposed_samples.append(proposed_rec)
            elif act_type == ActionType.DELETE.value:
                # Proposed is empty/deleted
                proposed_samples = []

            # 5. Check foreign key dependencies if deleting or updating PK
            if pks and current_samples:
                pk_col = pks[0]
                pk_vals = [s.get(pk_col) for s in current_samples if s.get(pk_col) is not None]
                if pk_vals:
                    # Scan other tables for FK references to this table
                    all_tables = insp.get_table_names()
                    for other_t in all_tables:
                        if other_t.lower() == table_name.lower():
                            continue
                        fks = insp.get_foreign_keys(other_t)
                        for fk in fks:
                            referred_t = fk.get("referred_table")
                            if referred_t and referred_t.lower() == table_name.lower():
                                constrained_cols = fk.get("constrained_columns", [])
                                if constrained_cols:
                                    child_fk_col = constrained_cols[0]
                                    child_t_q = quote_identifier(other_t, db_type)
                                    child_fk_q = quote_identifier(child_fk_col, db_type)
                                    # Count referencing rows
                                    try:
                                        with engine.connect() as conn:
                                            # Parameterize the first pk sample or in-clause
                                            val = pk_vals[0]
                                            ref_sql = f"SELECT COUNT(*) FROM {child_t_q} WHERE {child_fk_q} = :pv"
                                            ref_cnt = conn.execute(text(ref_sql), {"pv": val}).scalar()
                                            if ref_cnt and ref_cnt > 0:
                                                related_counts[other_t] = int(ref_cnt)
                                                warnings.append(
                                                    f"Table '{other_t}' has {ref_cnt} dependent record(s) referencing this target."
                                                )
                                    except Exception:
                                        pass

        elif act_type == ActionType.INSERT.value:
            actual_count = 1
            new_rec = {chg.column: chg.proposed_value for chg in proposal.changes}
            clean_rec = {k: str(v) if not isinstance(v, (int, float, bool, type(None))) else v for k, v in new_rec.items()}
            proposed_samples.append(clean_rec)

    except Exception as e:
        warnings.append(f"Preview calculation encountered an error: {e}")

    impact = ActionImpact(
        estimated_rows=proposal.impact.estimated_rows if proposal.impact else actual_count,
        actual_preview_rows=actual_count,
        current_sample_records=current_samples,
        proposed_sample_records=proposed_samples,
        related_records_count=related_counts,
        warnings=warnings,
        is_excessive=is_excessive,
    )

    # Classify risk
    target_cols = [c.column for c in proposal.changes]
    risk = classify_action_risk(
        action_type=act_type,
        table_name=table_name,
        target_columns=target_cols,
        estimated_rows=actual_count,
        condition_sql=condition,
        is_blocked=is_excessive,
        has_foreign_dependents=len(related_counts) > 0,
    )

    return impact, risk
