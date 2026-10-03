"""
backend/app/intelligence/investigation/contributor_analysis.py

Phase 8.7: Dimensional Contributor & Associated Factor Analyzer
Evaluates categorical dimensions to surface measurable shifts associated with an observed change.

Epistemic Hygiene:
- Never asserts causation without proof.
- Uses terminology: "observed contributor", "contributing signal", "associated change".
- Computes deterministic deltas and contribution shares from real schema dimensions.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional
from sqlalchemy import text

from app.tools.execute_query import validate_sql
from app.intelligence.schema_analyzer import quote_identifier, analyze_schema
from app.intelligence.ai_analyst.trend_analyzer import get_dialect_date_trunc
from app.intelligence.business_intelligence.business_context import discover_business_context
from app.intelligence.investigation.models import ContributingFactor, EvidenceItem, ObservedChange

logger = logging.getLogger("bgai.investigation.contributors")


def analyze_contributing_factors(
    engine: Any,
    db_type: str,
    target_table: str,
    observed_change: Optional[ObservedChange],
    evidence_items: list[EvidenceItem],
    schema_info: Optional[dict[str, Any]] = None,
) -> tuple[list[ContributingFactor], list[str]]:
    """
    Analyzes categorical dimensions in the primary table and joined entity tables.

    Returns:
        (contributing_factors, dimensions_analyzed)
    """
    contributing_factors: list[ContributingFactor] = []
    dimensions_analyzed: list[str] = []

    if engine is None or db_type == "none" or not target_table:
        return contributing_factors, dimensions_analyzed

    context = discover_business_context(engine, db_type, schema_info)
    t_sql = quote_identifier(target_table, db_type)

    primary_entity = next((e for e in context.entity_tables if e.get("table", "").lower() == target_table.lower()), None)
    if not primary_entity:
        return contributing_factors, dimensions_analyzed

    time_cols = primary_entity.get("time_columns", [])
    primary_dims = primary_entity.get("dimension_columns", []) or [
        d.get("column", "") for d in getattr(context, "dimension_columns", []) if d.get("table", "").lower() == target_table.lower()
    ]
    time_col = time_cols[0] if time_cols else None

    # Discover candidate dimensions across primary and joined tables
    candidate_dimensions: list[dict[str, Any]] = []

    # 1. Primary table dimensions (status, category, type, etc.)
    for dim_col in primary_dims:
        if dim_col:
            candidate_dimensions.append({
                "source_table": target_table,
                "column": dim_col,
                "is_joined": False,
            })

    # 2. Joined tables dimensions (e.g. products.category, customers.city)
    if hasattr(context, "relationships") and context.relationships:
        for rel in context.relationships:
            t1 = rel.get("from_table", "")
            t2 = rel.get("to_table", "")
            c1 = rel.get("from_column", "")
            c2 = rel.get("to_column", "")
            if isinstance(c1, list):
                c1 = c1[0] if c1 else ""
            if isinstance(c2, list):
                c2 = c2[0] if c2 else ""
            if not c1 or not c2:
                continue

            if t1.lower() == target_table.lower():
                jt, j_src, j_tgt = t2, c1, c2
            elif t2.lower() == target_table.lower():
                jt, j_src, j_tgt = t1, c2, c1
            else:
                continue

            j_meta = next((e for e in context.entity_tables if e.get("table", "").lower() == jt.lower()), None)
            if j_meta:
                j_dims = j_meta.get("dimension_columns", []) or [
                    d.get("column", "") for d in getattr(context, "dimension_columns", []) if d.get("table", "").lower() == jt.lower()
                ]
                for j_dim in j_dims:
                    if j_dim:
                        candidate_dimensions.append({
                            "source_table": jt,
                            "column": j_dim,
                            "is_joined": True,
                            "join_table": jt,
                            "join_key_source": j_src,
                            "join_key_target": j_tgt,
                        })

    if not candidate_dimensions:
        return contributing_factors, dimensions_analyzed

    try:
        with engine.connect() as conn:
            for dim_info in candidate_dimensions[:4]:  # Bounded to top 4 candidate dimensions
                dim_col = dim_info["column"]
                src_tbl = dim_info["source_table"]
                dim_label = f"{src_tbl}.{dim_col}" if dim_info["is_joined"] else dim_col
                dimensions_analyzed.append(dim_label)

                # Find associated evidence IDs
                related_ev_ids = [
                    e.evidence_id for e in evidence_items
                    if src_tbl.lower() in e.source_table.lower() or dim_col.lower() in [c.lower() for c in e.source_columns]
                ]

                # ── Case A: Chronological comparison (if time_col exists) ─────────
                if time_col and primary_entity.get("row_count", 0) >= 2:
                    m_sql = quote_identifier(time_col, db_type)
                    date_trunc_expr = get_dialect_date_trunc(m_sql, db_type, "month")

                    if not dim_info["is_joined"]:
                        d_col_sql = quote_identifier(dim_col, db_type)
                        breakdown_query = f"""
                            SELECT {date_trunc_expr} AS period,
                                   {d_col_sql} AS dim_val,
                                   COUNT(*) AS cnt
                            FROM {t_sql}
                            WHERE {m_sql} IS NOT NULL AND {d_col_sql} IS NOT NULL
                            GROUP BY period, dim_val
                            ORDER BY period ASC, cnt DESC
                            LIMIT 60
                        """
                    else:
                        jt_sql = quote_identifier(dim_info["join_table"], db_type)
                        d_col_sql = f"{jt_sql}.{quote_identifier(dim_col, db_type)}"
                        join_on_sql = f"{t_sql}.{quote_identifier(dim_info['join_key_source'], db_type)} = {jt_sql}.{quote_identifier(dim_info['join_key_target'], db_type)}"
                        breakdown_query = f"""
                            SELECT {date_trunc_expr} AS period,
                                   {d_col_sql} AS dim_val,
                                   COUNT(*) AS cnt
                            FROM {t_sql}
                            INNER JOIN {jt_sql} ON {join_on_sql}
                            WHERE {t_sql}.{m_sql} IS NOT NULL AND {d_col_sql} IS NOT NULL
                            GROUP BY period, dim_val
                            ORDER BY period ASC, cnt DESC
                            LIMIT 60
                        """

                    if validate_sql(breakdown_query).get("allowed"):
                        rows = conn.execute(text(breakdown_query)).fetchall()
                        if rows:
                            # Group counts by period and dimension value
                            periods = sorted(list({str(r[0]) for r in rows}))
                            if len(periods) >= 2:
                                p_prev, p_curr = periods[-2], periods[-1]
                                prev_map = {str(r[1]): int(r[2]) for r in rows if str(r[0]) == p_prev}
                                curr_map = {str(r[1]): int(r[2]) for r in rows if str(r[0]) == p_curr}

                                all_vals = set(prev_map.keys()) | set(curr_map.keys())
                                for val in sorted(all_vals):
                                    v_prev = prev_map.get(val, 0)
                                    v_curr = curr_map.get(val, 0)
                                    v_delta = v_curr - v_prev
                                    v_pct = round((v_delta / v_prev) * 100, 2) if v_prev > 0 else 0.0

                                    # Significant shift check (either > 10% change or new emergence)
                                    if abs(v_pct) >= 10.0 or (v_prev > 0 and v_curr == 0) or (v_prev == 0 and v_curr > 0):
                                        impact = "negative" if v_delta < 0 else "positive" if v_delta > 0 else "neutral"
                                        shift_desc = f"{dim_label} '{val}' changed from {v_prev} to {v_curr} ({v_pct:+.1f}%)"

                                        contributing_factors.append(ContributingFactor(
                                            factor_id=f"cf_{uuid.uuid4().hex[:6]}",
                                            dimension=dim_label,
                                            dimension_value=str(val),
                                            impact_type=impact,
                                            contribution_percent=v_pct,
                                            observed_change=shift_desc,
                                            evidence_ids=related_ev_ids,
                                        ))

                # ── Case B: Static distribution breakdown ─────────────────────────
                if not contributing_factors and not dim_info["is_joined"]:
                    d_col_sql = quote_identifier(dim_col, db_type)
                    dist_query = f"""
                        SELECT {d_col_sql} AS dim_val, COUNT(*) AS cnt
                        FROM {t_sql}
                        WHERE {d_col_sql} IS NOT NULL
                        GROUP BY dim_val
                        ORDER BY cnt DESC
                        LIMIT 10
                    """
                    if validate_sql(dist_query).get("allowed"):
                        dist_rows = conn.execute(text(dist_query)).fetchall()
                        tot = sum(int(r[1]) for r in dist_rows)
                        if tot > 0:
                            for r in dist_rows[:3]:
                                val, cnt = str(r[0]), int(r[1])
                                share = round((cnt / tot) * 100, 1)
                                contributing_factors.append(ContributingFactor(
                                    factor_id=f"cf_stat_{uuid.uuid4().hex[:6]}",
                                    dimension=dim_label,
                                    dimension_value=val,
                                    impact_type="neutral",
                                    contribution_percent=share,
                                    observed_change=f"{dim_label} '{val}' accounts for {cnt} records ({share}% of total volume)",
                                    evidence_ids=related_ev_ids,
                                ))

    except Exception as e:
        logger.warning(f"Error during contributor analysis: {e}")

    # Rank factors by absolute contribution percent descending
    contributing_factors.sort(key=lambda x: abs(x.contribution_percent or 0.0), reverse=True)

    return contributing_factors, dimensions_analyzed
