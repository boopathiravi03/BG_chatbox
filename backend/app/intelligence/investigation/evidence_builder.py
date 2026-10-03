"""
backend/app/intelligence/investigation/evidence_builder.py

Phase 8.7: Real Database Evidence Builder
Gathers verifiable database measurements across chronological periods and dimensional relationships.

Guarantees:
- Real connected database data only
- Strictly read-only queries validated via validate_sql
- Comprehensive SQL lineage and calculation descriptions
- Graceful handling of single-table, unjoined, or low-record schemas
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
from app.intelligence.investigation.models import EvidenceItem, ObservedChange

logger = logging.getLogger("bgai.investigation.evidence")


def build_investigation_evidence(
    engine: Any,
    db_type: str,
    target_table: Optional[str] = None,
    target_metric: Optional[str] = None,
    schema_info: Optional[dict[str, Any]] = None,
) -> tuple[Optional[ObservedChange], list[EvidenceItem], dict[str, Any]]:
    """
    Builds quantitative, verifiable evidence items from the connected database.

    Returns:
        (observed_change, evidence_items, metadata)
    """
    evidence_items: list[EvidenceItem] = []
    metadata: dict[str, Any] = {
        "tables_inspected": [],
        "has_temporal_data": False,
        "has_measure_data": False,
        "insufficient_data_reasons": [],
    }

    if engine is None or db_type == "none":
        return None, evidence_items, metadata

    # 1. Discover business context and schema
    context = discover_business_context(engine, db_type, schema_info)
    if not context.has_sufficient_data:
        metadata["insufficient_data_reasons"].append(context.reason or "Database records insufficient.")
        return None, evidence_items, metadata

    # Determine primary table to investigate
    primary_entity = None
    if target_table:
        for ent in context.entity_tables:
            if ent.get("table", "").lower() == target_table.lower():
                primary_entity = ent
                break

    if not primary_entity and context.entity_tables:
        primary_entity = context.entity_tables[0]

    if not primary_entity:
        metadata["insufficient_data_reasons"].append("No valid business entity table discovered.")
        return None, evidence_items, metadata

    table_name = primary_entity.get("table", "")
    metadata["tables_inspected"].append(table_name)
    time_cols = primary_entity.get("time_columns", [])
    measures = [m.get("column", "") for m in getattr(context, "measure_columns", []) if m.get("table", "").lower() == table_name.lower()]

    time_col = time_cols[0] if time_cols else None
    t_sql = quote_identifier(table_name, db_type)

    observed_change: Optional[ObservedChange] = None

    try:
        with engine.connect() as conn:
            # ── A. Chronological Trend & Volume Evidence (if time_col exists) ─────────
            if time_col and primary_entity.get("row_count", 0) >= 2:
                metadata["has_temporal_data"] = True
                m_sql = quote_identifier(time_col, db_type)
                date_trunc_expr = get_dialect_date_trunc(m_sql, db_type, "month")

                # Query chronological counts
                vol_query = f"""
                    SELECT {date_trunc_expr} AS period, COUNT(*) AS cnt
                    FROM {t_sql}
                    WHERE {m_sql} IS NOT NULL
                    GROUP BY period
                    ORDER BY period ASC
                    LIMIT 24
                """
                val_res = validate_sql(vol_query)
                if val_res.get("allowed"):
                    rows = conn.execute(text(vol_query)).fetchall()
                    if len(rows) >= 2:
                        prev_row = rows[-2]
                        curr_row = rows[-1]
                        prev_period, prev_cnt = str(prev_row[0]), int(prev_row[1])
                        curr_period, curr_cnt = str(curr_row[0]), int(curr_row[1])

                        cnt_delta = curr_cnt - prev_cnt
                        cnt_pct = round((cnt_delta / prev_cnt) * 100, 2) if prev_cnt > 0 else 0.0

                        vol_ev = EvidenceItem(
                            evidence_id=f"ev_vol_{uuid.uuid4().hex[:6]}",
                            metric="Record Volume",
                            current_value=curr_cnt,
                            previous_value=prev_cnt,
                            delta=cnt_delta,
                            delta_percent=cnt_pct,
                            time_range=f"{prev_period} vs {curr_period}",
                            source_table=table_name,
                            source_columns=[time_col],
                            record_count=curr_cnt + prev_cnt,
                            sql_lineage=vol_query.strip(),
                            calculation_description=f"COUNT(*) comparison across chronological periods ({prev_period} to {curr_period})",
                        )
                        evidence_items.append(vol_ev)

                        # Set default observed change if none exists yet
                        if not observed_change:
                            direction = "increased" if cnt_delta > 0 else "decreased" if cnt_delta < 0 else "unchanged"
                            observed_change = ObservedChange(
                                metric=f"{table_name} volume",
                                current_value=curr_cnt,
                                previous_value=prev_cnt,
                                delta=cnt_delta,
                                delta_percent=cnt_pct,
                                time_period=f"{prev_period} -> {curr_period}",
                                formatted_change=f"{table_name} volume {direction} by {abs(cnt_pct)}% ({prev_cnt} -> {curr_cnt})",
                            )

                # ── B. Direct Numerical Measures (e.g. quantity, amount) ───────────
                for measure_col in measures[:2]:
                    metadata["has_measure_data"] = True
                    col_sql = quote_identifier(measure_col, db_type)
                    meas_query = f"""
                        SELECT {date_trunc_expr} AS period,
                               SUM({col_sql}) AS total_val,
                               AVG({col_sql}) AS avg_val
                        FROM {t_sql}
                        WHERE {m_sql} IS NOT NULL AND {col_sql} IS NOT NULL
                        GROUP BY period
                        ORDER BY period ASC
                        LIMIT 24
                    """
                    if validate_sql(meas_query).get("allowed"):
                        m_rows = conn.execute(text(meas_query)).fetchall()
                        if len(m_rows) >= 2:
                            p_row, c_row = m_rows[-2], m_rows[-1]
                            p_period, p_sum, p_avg = str(p_row[0]), float(p_row[1] or 0), float(p_row[2] or 0)
                            c_period, c_sum, c_avg = str(c_row[0]), float(c_row[1] or 0), float(c_row[2] or 0)

                            sum_delta = round(c_sum - p_sum, 2)
                            sum_pct = round((sum_delta / p_sum) * 100, 2) if p_sum > 0 else 0.0
                            avg_delta = round(c_avg - p_avg, 2)
                            avg_pct = round((avg_delta / p_avg) * 100, 2) if p_avg > 0 else 0.0

                            evidence_items.append(EvidenceItem(
                                evidence_id=f"ev_sum_{uuid.uuid4().hex[:6]}",
                                metric=f"Total {measure_col}",
                                current_value=c_sum,
                                previous_value=p_sum,
                                delta=sum_delta,
                                delta_percent=sum_pct,
                                time_range=f"{p_period} vs {c_period}",
                                source_table=table_name,
                                source_columns=[time_col, measure_col],
                                sql_lineage=meas_query.strip(),
                                calculation_description=f"SUM({measure_col}) grouped by {time_col} ({p_period} to {c_period})",
                            ))

                            evidence_items.append(EvidenceItem(
                                evidence_id=f"ev_avg_{uuid.uuid4().hex[:6]}",
                                metric=f"Average {measure_col}",
                                current_value=c_avg,
                                previous_value=p_avg,
                                delta=avg_delta,
                                delta_percent=avg_pct,
                                time_range=f"{p_period} vs {c_period}",
                                source_table=table_name,
                                source_columns=[time_col, measure_col],
                                sql_lineage=meas_query.strip(),
                                calculation_description=f"AVG({measure_col}) grouped by {time_col} ({p_period} to {c_period})",
                            ))

                            # Upgrade observed change if this is a primary monetary / quantity measure
                            if target_metric and target_metric.lower() in measure_col.lower() or not observed_change:
                                direction = "increased" if sum_delta > 0 else "decreased" if sum_delta < 0 else "unchanged"
                                observed_change = ObservedChange(
                                    metric=f"Total {measure_col}",
                                    current_value=c_sum,
                                    previous_value=p_sum,
                                    delta=sum_delta,
                                    delta_percent=sum_pct,
                                    time_period=f"{p_period} -> {c_period}",
                                    formatted_change=f"Total {measure_col} {direction} by {abs(sum_pct)}% ({p_sum} -> {c_sum})",
                                )

                # ── C. Multi-Table Cross-Join Metrics (e.g. orders * products) ─────
                # Check for relationships where joined table has price/amount
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

                        if t1.lower() == table_name.lower():
                            join_table, join_key_source, join_key_target = t2, c1, c2
                        elif t2.lower() == table_name.lower():
                            join_table, join_key_source, join_key_target = t1, c2, c1
                        else:
                            continue

                        # Find numeric column in join_table (like price, rate, unit_cost)
                        join_table_meta = next((e for e in context.entity_tables if e.get("table", "").lower() == join_table.lower()), None)
                        if not join_table_meta:
                            continue

                        join_measures = [m.get("column", "") for m in getattr(context, "measure_columns", []) if m.get("table", "").lower() == join_table.lower()]
                        if not join_measures or not measures:
                            continue

                        jt_sql = quote_identifier(join_table, db_type)
                        t1_col_sql = f"{t_sql}.{quote_identifier(measures[0], db_type)}"
                        t2_col_sql = f"{jt_sql}.{quote_identifier(join_measures[0], db_type)}"
                        join_on_sql = f"{t_sql}.{quote_identifier(join_key_source, db_type)} = {jt_sql}.{quote_identifier(join_key_target, db_type)}"

                        cross_query = f"""
                            SELECT {date_trunc_expr} AS period,
                                   SUM({t1_col_sql} * {t2_col_sql}) AS cross_total
                            FROM {t_sql}
                            INNER JOIN {jt_sql} ON {join_on_sql}
                            WHERE {t_sql}.{m_sql} IS NOT NULL
                            GROUP BY period
                            ORDER BY period ASC
                            LIMIT 24
                        """
                        if validate_sql(cross_query).get("allowed"):
                            try:
                                cr_rows = conn.execute(text(cross_query)).fetchall()
                                if len(cr_rows) >= 2:
                                    metadata["tables_inspected"].append(join_table)
                                    p_row, c_row = cr_rows[-2], cr_rows[-1]
                                    p_period, p_val = str(p_row[0]), float(p_row[1] or 0)
                                    c_period, c_val = str(c_row[0]), float(c_row[1] or 0)

                                    cr_delta = round(c_val - p_val, 2)
                                    cr_pct = round((cr_delta / p_val) * 100, 2) if p_val > 0 else 0.0

                                    metric_label = f"Computed Revenue ({table_name}.{measures[0]} * {join_table}.{join_measures[0]})"
                                    evidence_items.append(EvidenceItem(
                                        evidence_id=f"ev_rev_{uuid.uuid4().hex[:6]}",
                                        metric=metric_label,
                                        current_value=c_val,
                                        previous_value=p_val,
                                        delta=cr_delta,
                                        delta_percent=cr_pct,
                                        time_range=f"{p_period} vs {c_period}",
                                        source_table=f"{table_name} JOIN {join_table}",
                                        source_columns=[measures[0], join_measures[0]],
                                        sql_lineage=cross_query.strip(),
                                        calculation_description=f"SUM({table_name}.{measures[0]} * {join_table}.{join_measures[0]}) across chronological periods",
                                    ))

                                    # Prioritize computed revenue as headline observed change if significant change
                                    direction = "increased" if cr_delta > 0 else "decreased" if cr_delta < 0 else "unchanged"
                                    observed_change = ObservedChange(
                                        metric="Revenue",
                                        current_value=c_val,
                                        previous_value=p_val,
                                        delta=cr_delta,
                                        delta_percent=cr_pct,
                                        time_period=f"{p_period} -> {c_period}",
                                        formatted_change=f"Revenue {direction} by {abs(cr_pct)}% ({p_val} -> {c_val})",
                                    )
                                    break
                            except Exception as e:
                                logger.debug(f"Cross join calculation skipped: {e}")

            # ── D. Fallback if no time column: Overall Distribution / Summary ──
            if not evidence_items and primary_entity.get("row_count", 0) > 0:
                count_query = f"SELECT COUNT(*) FROM {t_sql}"
                if validate_sql(count_query).get("allowed"):
                    tot_count = conn.execute(text(count_query)).scalar() or 0
                    evidence_items.append(EvidenceItem(
                        evidence_id=f"ev_tot_{uuid.uuid4().hex[:6]}",
                        metric=f"{table_name} Total Records",
                        current_value=tot_count,
                        previous_value=None,
                        source_table=table_name,
                        record_count=tot_count,
                        sql_lineage=count_query,
                        calculation_description=f"Total record count in table {table_name}",
                    ))
                    if not observed_change:
                        observed_change = ObservedChange(
                            metric=f"{table_name} state",
                            current_value=tot_count,
                            previous_value=None,
                            formatted_change=f"Table {table_name} contains {tot_count} active records",
                        )

    except Exception as e:
        logger.warning(f"Error during evidence gathering: {e}")
        metadata["insufficient_data_reasons"].append(f"Query execution error: {str(e)}")

    return observed_change, evidence_items, metadata
