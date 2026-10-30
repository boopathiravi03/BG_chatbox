"""backend/app/intelligence/investigation/business_investigator.py

Core engine for Sprint 3: Evidence-Based AI Business Investigator.
Grounded in real database schemas, SQL guardrails, and deterministic calculations.

Workflow:
1. Resolves authorized engine and connection context with strict tenant isolation.
2. Grounded intent discovery: parses business questions or monitoring signals.
3. Checks schemas, available metrics, date dimensions, and foreign key relationships.
4. Generates bounded, read-only analytical queries through SQL command policy.
5. Computes metric deltas, period-over-period comparisons, and ranked dimensional contributors.
6. Builds reproducible evidence provenance and declarative chart configurations.
7. Distinguishes observed facts from unconfirmed hypotheses (never implies causation).
8. Persists structured investigation reports to investigation_store.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from app.database.connection_context import (
    get_request_engine,
    get_request_db_type,
    get_request_user_id,
    set_user_context_for_request,
)
from app.database.database_context import get_database_profile
from app.tools.execute_query import validate_sql
from app.intelligence.schema_analyzer import quote_identifier
from app.intelligence.ai_analyst.trend_analyzer import get_dialect_date_trunc
from app.intelligence.business_intelligence.business_context import discover_business_context
from app.intelligence.investigation.models import (
    InvestigationResult,
    ObservedChange,
    EvidenceItem,
    ContributingFactor,
    Hypothesis,
    InvestigationRecommendation,
    ConfidenceAssessment,
    ConfidenceLevel,
    InvestigationLineage,
)
from app.intelligence.investigation.investigation_store import save_investigation_report

logger = logging.getLogger("bgai.investigation.engine")

_SENSITIVE_COLUMN_KEYWORDS = {
    "password", "secret", "token", "api_key", "apikey", "access_token",
    "private_key", "credential", "auth", "hash", "ssn", "credit_card",
    "card_number", "cvv", "pin", "salt", "passphrase"
}


def is_sensitive_column(col_name: str) -> bool:
    """Detects confidential, security, and credential-bearing columns to prevent leakage."""
    if not col_name:
        return False
    c_lower = col_name.lower()
    return any(k in c_lower for k in _SENSITIVE_COLUMN_KEYWORDS)


def redact_sensitive_value(val: Any) -> str:
    """Masks secret tokens, hashes, and credential strings in outputs."""
    s = str(val or "")
    if any(s.startswith(prefix) for prefix in ["sk_live_", "sk_test_", "Bearer ", "ghp_", "glpat-"]):
        return "[REDACTED_SECRET]"
    if len(s) >= 32 and (s.startswith("$2b$") or s.startswith("$2a$") or re.match(r"^[a-fA-F0-9]{32,64}$", s)):
        return "[REDACTED_SECRET]"
    return s


def parse_business_question_intent(
    question: str,
    available_tables: List[str],
    available_columns: Dict[str, List[str]],
) -> Dict[str, Any]:
    """
    Parses a user's natural language question into grounded investigation parameters.
    Extracts focus type, target metric, requested dimensions, and target entity table.
    """
    q_lower = (question or "").lower()
    intent = {
        "focus_type": "trend_analysis",  # trend_analysis, contributor_breakdown, segment_change, volume_vs_value, inactive_entities, anomaly_check
        "metric_hint": None,
        "dimension_hint": None,
        "table_hint": None,
        "comparison_period": "month",
        "missing_requested_dimensions": [],
    }

    # 1. Focus Type Identification
    if any(k in q_lower for k in ["which product", "what product", "top product", "contributed most", "which category"]):
        intent["focus_type"] = "contributor_breakdown"
        intent["dimension_hint"] = "product"
    elif any(k in q_lower for k in ["region", "country", "city", "state", "territory", "geography"]):
        intent["focus_type"] = "segment_change"
        intent["dimension_hint"] = "region"
    elif any(k in q_lower for k in ["customer group", "segment", "tier", "cohort"]):
        intent["focus_type"] = "segment_change"
        intent["dimension_hint"] = "segment"
    elif any(k in q_lower for k in ["volume", "order volume", "quantity alongside", "alongside revenue", "count alongside"]):
        intent["focus_type"] = "volume_vs_value"
    elif any(k in q_lower for k in ["inactive", "churn", "lost customer", "dormant", "stopped buying"]):
        intent["focus_type"] = "inactive_entities"
    elif any(k in q_lower for k in ["unusual", "historical", "anomaly", "abnormal", "expected"]):
        intent["focus_type"] = "anomaly_check"
    elif any(k in q_lower for k in ["why", "decrease", "drop", "decline", "fall", "surge", "increase", "grow"]):
        intent["focus_type"] = "trend_analysis"

    # 2. Metric Hint Identification
    if any(k in q_lower for k in ["revenue", "sales", "income", "amount", "total", "spend", "dollar"]):
        intent["metric_hint"] = "revenue"
    elif any(k in q_lower for k in ["volume", "orders count", "order count", "number of orders", "transaction count", "number of transactions", "count of"]):
        intent["metric_hint"] = "count"
    elif any(k in q_lower for k in ["price", "average price", "avg price"]):
        intent["metric_hint"] = "price"

    # 3. Table Matching
    matched_tables = []
    for tbl in available_tables:
        if tbl.lower() in q_lower or (len(tbl) > 3 and tbl.lower()[:-1] in q_lower):
            matched_tables.append(tbl)
    intent["table_hint"] = matched_tables[0] if matched_tables else None
    intent["matched_tables"] = matched_tables

    # 4. Period Hint
    if "quarter" in q_lower:
        intent["comparison_period"] = "quarter"
    elif "year" in q_lower or "annual" in q_lower:
        intent["comparison_period"] = "year"
    elif "week" in q_lower:
        intent["comparison_period"] = "week"
    elif "day" in q_lower or "daily" in q_lower:
        intent["comparison_period"] = "day"
    else:
        intent["comparison_period"] = "month"

    return intent


def run_business_investigation(
    user_id: str,
    connection_id: Optional[str] = None,
    question: Optional[str] = None,
    signal_id: Optional[str] = None,
    target_metric: Optional[str] = None,
    target_table: Optional[str] = None,
    time_period: Optional[str] = None,
    context_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Executes a comprehensive, evidence-based business investigation.
    """
    investigation_id = f"inv_{uuid.uuid4().hex[:10]}"
    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.isoformat()
    conn_id = connection_id or "default"

    # 1. Activate and verify connection context
    user_ctx = set_user_context_for_request(user_id, connection_id=conn_id)
    engine = get_request_engine()
    db_type = get_request_db_type()

    if getattr(user_ctx, "connection_lookup_failed", False) or engine is None or db_type == "none":
        return {
            "status": "disconnected",
            "investigation_id": investigation_id,
            "user_id": user_id,
            "connection_id": conn_id,
            "question": question or "Business Investigation",
            "title": "Database Disconnected",
            "summary": f"Cannot execute investigation: connection '{conn_id}' is disconnected or not authorized.",
            "report": None,
            "created_at": now_iso,
        }

    # 2. Discover Schema & Business Context
    b_context = discover_business_context(engine, db_type)
    profile = get_database_profile()
    available_tables = [e.get("table", "") for e in b_context.entity_tables] if b_context.entity_tables else []
    
    # Map column dictionary
    table_columns: Dict[str, List[str]] = {}
    for ent in (b_context.entity_tables or []):
        t_name = ent.get("table", "")
        cols = ent.get("dimension_columns", []) + ent.get("time_columns", [])
        table_columns[t_name] = cols

    # 3. Resolve Intent
    intent = parse_business_question_intent(question or "", available_tables, table_columns)
    
    # Determine primary table
    primary_tbl = target_table or intent.get("table_hint")

    # If the candidate table has no temporal time columns, prefer a candidate table that has time columns
    if primary_tbl:
        ent = next((e for e in (b_context.entity_tables or []) if e.get("table", "").lower() == primary_tbl.lower()), None)
        if ent and not ent.get("time_columns"):
            candidates = (intent.get("matched_tables") or []) + available_tables
            for alt in candidates:
                alt_ent = next((e for e in (b_context.entity_tables or []) if e.get("table", "").lower() == alt.lower()), None)
                if alt_ent and alt_ent.get("time_columns"):
                    primary_tbl = alt
                    break

    if not primary_tbl:
        # Prefer tables with temporal and measure columns (e.g. orders, sales, transactions)
        for ent in (b_context.entity_tables or []):
            if ent.get("time_columns") and ent.get("row_count", 0) > 0:
                primary_tbl = ent.get("table")
                break
        if not primary_tbl:
            for ent in (b_context.entity_tables or []):
                if ent.get("time_columns"):
                    primary_tbl = ent.get("table")
                    break
    if not primary_tbl and available_tables:
        primary_tbl = available_tables[0]

    if not primary_tbl:
        return {
            "status": "insufficient_evidence",
            "investigation_id": investigation_id,
            "user_id": user_id,
            "connection_id": conn_id,
            "question": question or "Business Investigation",
            "title": "No Tables Available",
            "summary": "Database has no accessible business tables to investigate.",
            "report": None,
            "created_at": now_iso,
        }

    primary_ent = next((e for e in (b_context.entity_tables or []) if e.get("table", "").lower() == primary_tbl.lower()), None)
    time_cols = primary_ent.get("time_columns", []) if primary_ent else []
    time_col = time_cols[0] if time_cols else None

    # Determine metric column based on business intent and exclude auxiliary/rate columns
    metric_col = target_metric
    cand_measures = [m.get("column", "") for m in getattr(b_context, "measure_columns", []) if m.get("table", "").lower() == primary_tbl.lower()]
    
    REVENUE_HIGH_PRIORITY = ["revenue", "total_revenue", "net_revenue", "gross_revenue", "total_amount", "sales_amount", "order_total", "subtotal", "total", "amount"]
    METRIC_EXCLUSIONS = ["tax", "tax_amount", "discount", "discount_amount", "shipping", "shipping_amount", "fee", "unit_price", "price", "rate", "cost", "cogs"]

    if not metric_col:
        if intent.get("metric_hint") == "revenue":
            for prio in REVENUE_HIGH_PRIORITY:
                for m in cand_measures:
                    m_low = m.lower()
                    if m_low == prio or m_low.endswith(f"_{prio}"):
                        if not any(ex in m_low for ex in METRIC_EXCLUSIONS if ex != "amount" and ex != "total"):
                            metric_col = m
                            break
                if metric_col:
                    break
            if not metric_col:
                for m in cand_measures:
                    if not any(ex in m.lower() for ex in METRIC_EXCLUSIONS):
                        metric_col = m
                        break
        elif intent.get("metric_hint") == "price":
            for m in cand_measures:
                if any(k in m.lower() for k in ["price", "unit_price", "rate", "avg_price"]):
                    metric_col = m
                    break
        elif intent.get("metric_hint") == "count":
            metric_col = None

        if not metric_col and cand_measures and intent.get("metric_hint") != "count":
            for m in cand_measures:
                if not m.lower().endswith("_id") and not m.lower().startswith("id_") and not any(ex in m.lower() for ex in METRIC_EXCLUSIONS):
                    metric_col = m
                    break
            if not metric_col:
                metric_col = cand_measures[0]

    # Handle missing schema requirements gracefully
    missing_reasons: List[str] = []
    if not time_col:
        missing_reasons.append(f"Table '{primary_tbl}' lacks a chronological timestamp/date column required for period comparisons.")
    if intent.get("focus_type") == "segment_change" and intent.get("dimension_hint") == "region":
        # Check if region/city/state dimension exists in primary or joined tables
        has_region = any(any("region" in c.lower() or "city" in c.lower() or "country" in c.lower() for c in cols) for cols in table_columns.values())
        if not has_region:
            missing_reasons.append("Connected schema does not contain regional or geographic dimensions (e.g. 'region', 'city', 'country').")
    elif intent.get("focus_type") == "segment_change" and intent.get("dimension_hint") == "segment":
        has_segment = any(any("segment" in c.lower() or "tier" in c.lower() or "group" in c.lower() for c in cols) for cols in table_columns.values())
        if not has_segment:
            missing_reasons.append("Connected schema does not contain customer segment dimensions (e.g. 'segment', 'tier', 'group').")

    # 4. Gather Quantitative Evidence & Computations
    evidence_items: List[EvidenceItem] = []
    observed_change: Optional[ObservedChange] = None
    contributing_factors: List[ContributingFactor] = []
    hypotheses: List[Hypothesis] = []
    charts: List[Dict[str, Any]] = []
    lineage_steps: List[str] = []
    comp_periods: List[str] = []
    analyzed_columns: List[str] = []

    t_sql = quote_identifier(primary_tbl, db_type)

    if time_col:
        m_sql = quote_identifier(time_col, db_type)
        if intent.get("metric_hint") == "price" and metric_col:
            val_expr = f"AVG({quote_identifier(metric_col, db_type)})"
            metric_name = f"avg_{metric_col}"
        elif metric_col:
            val_expr = f"SUM({quote_identifier(metric_col, db_type)})"
            metric_name = metric_col
        else:
            val_expr = "COUNT(*)"
            metric_name = "order_count" if "order" in primary_tbl.lower() else "record_count"

        date_trunc_expr = get_dialect_date_trunc(m_sql, db_type, intent["comparison_period"])

        trend_query = f"""
            SELECT {date_trunc_expr} AS period, {val_expr} AS metric_val
            FROM {t_sql}
            WHERE {m_sql} IS NOT NULL
            GROUP BY period
            ORDER BY period DESC
            LIMIT 12
        """
        lineage_steps.append(f"Trend query on {primary_tbl}.{metric_name} grouped by {intent['comparison_period']}")

        try:
            val_trend = validate_sql(trend_query, connection_id=conn_id, user_id=user_id)
            if not val_trend.get("allowed") or val_trend.get("category") != "READ":
                missing_reasons.append(f"Trend query blocked by SQL policy: {val_trend.get('reason') or 'Disallowed command'}")
            else:
                with engine.connect() as conn:
                    rows = conn.execute(text(trend_query)).fetchall()

                    if len(rows) >= 2:
                        # Current vs Previous
                        curr_period, curr_val = rows[0][0], float(rows[0][1] or 0)
                        prev_period, prev_val = rows[1][0], float(rows[1][1] or 0)
                        delta = round(curr_val - prev_val, 2)
                        
                        # Mathematically rigorous percentage change supporting negative and zero baselines
                        if prev_val != 0:
                            delta_pct = round(((curr_val - prev_val) / abs(prev_val)) * 100, 1)
                            formatted_rate = f"{'+' if delta_pct >= 0 else ''}{delta_pct}%"
                        elif curr_val != 0:
                            # Mathematical convention: percentage change from zero is undefined / N/A
                            delta_pct = None
                            formatted_rate = f"N/A (Baseline was zero: 0.00 -> {curr_val:,.2f})"
                        else:
                            delta_pct = 0.0
                            formatted_rate = "0.0% (Zero-baseline: unchanged at 0.00)"

                        comp_periods = [str(prev_period), str(curr_period)]
                        analyzed_columns.extend([time_col, metric_name])

                        observed_change = ObservedChange(
                            metric=metric_name,
                            current_value=curr_val,
                            previous_value=prev_val,
                            delta=delta,
                            delta_percent=delta_pct,
                            time_period=f"{prev_period} vs {curr_period}",
                            formatted_change=f"{'+' if delta >= 0 else ''}{delta} ({formatted_rate})",
                        )

                        evidence_items.append(
                            EvidenceItem(
                                evidence_id=f"ev_{uuid.uuid4().hex[:6]}",
                                metric=metric_name,
                                current_value=curr_val,
                                previous_value=prev_val,
                                delta=delta,
                                delta_percent=delta_pct,
                                time_range=f"{prev_period} to {curr_period}",
                                source_table=primary_tbl,
                                source_columns=[time_col, metric_name],
                                sql_lineage=trend_query.strip(),
                                calculation_description=f"Period-over-period aggregate {val_expr} between {prev_period} and {curr_period}.",
                            )
                        )

                        # Build trend chart
                        chart_data = [{"period": str(r[0]), "value": round(float(r[1] or 0), 2)} for r in reversed(rows)]
                        charts.append({
                            "chart_type": "line",
                            "title": f"{metric_name.replace('_', ' ').title()} Progression by {intent['comparison_period'].title()}",
                            "x_key": "period",
                            "y_keys": ["value"],
                            "data": chart_data,
                        })

                        # ── Dimensional Contributor Analysis ──────────────────────
                        dim_cols = [c for c in (primary_ent.get("dimension_columns", []) if primary_ent else []) if not is_sensitive_column(c)]
                        dim_to_inspect = None
                        join_sql = ""
                        dim_table = primary_tbl

                        if intent.get("dimension_hint") == "product":
                            for c in dim_cols:
                                if any(k in c.lower() for k in ["product", "category", "item"]):
                                    dim_to_inspect = c
                                    break
                        elif intent.get("dimension_hint") in ("region", "segment"):
                            for c in dim_cols:
                                if any(k in c.lower() for k in ["segment", "region", "country", "city", "tier", "group"]):
                                    dim_to_inspect = c
                                    break
                        if not dim_to_inspect and dim_cols:
                            dim_to_inspect = dim_cols[0]

                        # If joined tables exist (e.g. orders JOIN customers)
                        # Join safety: avoid duplicate-producing One-to-Many joins
                        if (not dim_to_inspect or (intent.get("dimension_hint") and intent["dimension_hint"] not in dim_to_inspect.lower())) and hasattr(b_context, "relationships") and b_context.relationships:
                            for rel in b_context.relationships:
                                f_tbl, t_tbl = rel.get("from_table", ""), rel.get("to_table", "")
                                f_col, t_col = rel.get("from_column", ""), rel.get("to_column", "")
                                f_col_str = f_col[0] if isinstance(f_col, list) else f_col
                                t_col_str = t_col[0] if isinstance(t_col, list) else t_col

                                # Many-to-One join: primary_tbl is the child referencing parent PK
                                # Ensures each row of primary_tbl is NOT duplicated
                                if f_tbl.lower() == primary_tbl.lower():
                                    joined_tbl = t_tbl
                                    j_on = f"{quote_identifier(f_tbl, db_type)}.{quote_identifier(f_col_str, db_type)} = {quote_identifier(t_tbl, db_type)}.{quote_identifier(t_col_str, db_type)}"
                                else:
                                    continue

                                j_ent = next((e for e in (b_context.entity_tables or []) if e.get("table", "").lower() == joined_tbl.lower()), None)
                                if j_ent:
                                    for jc in (j_ent.get("dimension_columns") or []):
                                        if is_sensitive_column(jc):
                                            continue
                                        if (intent.get("dimension_hint") and intent["dimension_hint"] in jc.lower()) or not dim_to_inspect:
                                            dim_to_inspect = jc
                                            dim_table = joined_tbl
                                            join_sql = f"JOIN {quote_identifier(joined_tbl, db_type)} ON {j_on}"
                                            break
                                if join_sql:
                                    break

                        if dim_to_inspect:
                            d_col_sql = f"{quote_identifier(dim_table, db_type)}.{quote_identifier(dim_to_inspect, db_type)}"
                            val_col_expr = f"COALESCE({quote_identifier(primary_tbl, db_type)}.{quote_identifier(metric_col, db_type)}, 0)" if metric_col else "1"

                            # Parameterized period-specific comparative decomposition query
                            dim_query = f"""
                                SELECT 
                                    {d_col_sql} AS dim_val,
                                    SUM(CASE WHEN {date_trunc_expr} = :prev_p THEN {val_col_expr} ELSE 0 END) AS prev_metric,
                                    SUM(CASE WHEN {date_trunc_expr} = :curr_p THEN {val_col_expr} ELSE 0 END) AS curr_metric
                                FROM {t_sql}
                                {join_sql}
                                WHERE {quote_identifier(primary_tbl, db_type)}.{m_sql} IS NOT NULL 
                                  AND {d_col_sql} IS NOT NULL
                                  AND {date_trunc_expr} IN (:prev_p, :curr_p)
                                GROUP BY {d_col_sql}
                                LIMIT 50
                            """

                            val_dim = validate_sql(dim_query, connection_id=conn_id, user_id=user_id)
                            if val_dim.get("allowed") and val_dim.get("category") == "READ":
                                lineage_steps.append(f"Period-comparative contributor query on {dim_table}.{dim_to_inspect} for {prev_period} and {curr_period}")
                                dim_rows = conn.execute(
                                    text(dim_query),
                                    {"prev_p": str(prev_period), "curr_p": str(curr_period)}
                                ).fetchall()

                                # Sum gross movements across dimensions to attribute internal reallocations if net delta is zero
                                sum_abs_deltas = sum(abs(round(float(dr[2] or 0) - float(dr[1] or 0), 2)) for dr in dim_rows)

                                breakdown_items = []
                                for r in dim_rows:
                                    d_val = redact_sensitive_value(r[0])
                                    prev_m = float(r[1] or 0)
                                    curr_m = float(r[2] or 0)
                                    dim_delta = round(curr_m - prev_m, 2)

                                    if prev_m != 0:
                                        dim_pct_change = round(((curr_m - prev_m) / abs(prev_m)) * 100, 1)
                                        dim_pct_display = f"{'+' if dim_pct_change >= 0 else ''}{dim_pct_change}%"
                                    elif curr_m != 0:
                                        dim_pct_change = None
                                        dim_pct_display = "N/A (Baseline was zero)"
                                    else:
                                        dim_pct_change = 0.0
                                        dim_pct_display = "0.0%"

                                    if abs(delta) > 0.001:
                                        c_pct = round((dim_delta / delta) * 100, 1)
                                    elif sum_abs_deltas > 0:
                                        c_pct = round((abs(dim_delta) / sum_abs_deltas) * 100, 1)
                                    else:
                                        c_pct = round((curr_m / curr_val) * 100, 1) if curr_val > 0 else 0.0

                                    breakdown_items.append({
                                        "dim_val": d_val,
                                        "prev_metric": prev_m,
                                        "curr_metric": curr_m,
                                        "dim_delta": dim_delta,
                                        "dim_pct_change": dim_pct_change,
                                        "dim_pct_display": dim_pct_display,
                                        "contribution_pct": c_pct,
                                    })

                                # Rank by causal movement:
                                # When delta < 0 (drop), most negative dim_delta first (main drivers of decline)
                                # When delta > 0 (growth), most positive dim_delta first (main drivers of growth)
                                # When delta == 0, largest absolute dim_delta first
                                if delta < 0:
                                    breakdown_items.sort(key=lambda x: x["dim_delta"])
                                elif delta > 0:
                                    breakdown_items.sort(key=lambda x: x["dim_delta"], reverse=True)
                                else:
                                    breakdown_items.sort(key=lambda x: abs(x["dim_delta"]), reverse=True)

                                contributor_chart_data = []
                                for item in breakdown_items[:8]:
                                    d_val = item["dim_val"]
                                    c_pct = item["contribution_pct"]
                                    d_delta = item["dim_delta"]
                                    d_curr = item["curr_metric"]
                                    d_prev = item["prev_metric"]

                                    if delta < 0:
                                        impact = "negative" if d_delta < 0 else "mitigating"
                                    elif delta > 0:
                                        impact = "positive" if d_delta > 0 else "drag"
                                    else:
                                        impact = "offsetting_positive" if d_delta > 0 else ("offsetting_negative" if d_delta < 0 else "neutral")

                                    chg_sign = "+" if d_delta >= 0 else ""
                                    dim_pct_str = item.get("dim_pct_display") or (
                                        f"{'+' if item['dim_pct_change'] >= 0 else ''}{item['dim_pct_change']}%"
                                        if item.get("dim_pct_change") is not None else "N/A (Baseline was zero)"
                                    )
                                    if abs(delta) > 0.001:
                                        obs_desc = f"{chg_sign}{d_delta:,.2f} ({dim_pct_str}) in period. Current: {d_curr:,.2f}, Previous: {d_prev:,.2f}"
                                    else:
                                        obs_desc = f"{chg_sign}{d_delta:,.2f} ({dim_pct_str}). Offsetting shift ({c_pct}% reallocation share). Net total change was 0.00."

                                    factor = ContributingFactor(
                                        factor_id=f"fac_{uuid.uuid4().hex[:6]}",
                                        dimension=f"{dim_table}.{dim_to_inspect}",
                                        dimension_value=d_val,
                                        impact_type=impact,
                                        contribution_percent=c_pct,
                                        observed_change=obs_desc,
                                        evidence_ids=[evidence_items[0].evidence_id],
                                    )
                                    contributing_factors.append(factor)
                                    contributor_chart_data.append({
                                        "dimension": d_val,
                                        "amount": round(d_curr, 2),
                                        "previous": round(d_prev, 2),
                                        "current": round(d_curr, 2),
                                        "delta": round(d_delta, 2),
                                        "share_percent": c_pct,
                                    })

                                if contributor_chart_data:
                                    charts.append({
                                        "chart_type": "bar",
                                        "title": f"Movement by {dim_to_inspect.replace('_', ' ').title()} ({prev_period} vs {curr_period})",
                                        "x_key": "dimension",
                                        "y_keys": ["amount"],
                                        "data": contributor_chart_data,
                                    })
                            else:
                                missing_reasons.append("Dimensional breakdown query blocked by SQL command policy.")
                    else:
                        missing_reasons.append("Insufficient chronological periods: Database contains fewer than 2 distinct historical periods.")
        except Exception as q_err:
            logger.warning(f"Failed to execute analytical investigation query: {q_err}")
            missing_reasons.append(f"Query execution error: {str(q_err)}")

    # 5. Formulate Hypotheses & Confidence
    confidence_level = ConfidenceLevel.HIGH if (observed_change and contributing_factors and not missing_reasons) else (
        ConfidenceLevel.MODERATE if observed_change else ConfidenceLevel.LIMITED
    )

    if observed_change and contributing_factors:
        top_factor = contributing_factors[0]
        hypotheses.append(
            Hypothesis(
                hypothesis_id=f"hyp_{uuid.uuid4().hex[:6]}",
                statement=f"The observed {observed_change.formatted_change} in {observed_change.metric} is strongly concentrated in '{top_factor.dimension_value}' ({top_factor.dimension}), representing {top_factor.contribution_percent}% of the total.",
                supporting_evidence_ids=[e.evidence_id for e in evidence_items],
                confidence_level=confidence_level,
                status="unconfirmed",
                causality_caveat="Observed statistical concentration. Correlation does not establish causation; underlying operational root cause remains unconfirmed.",
            )
        )
    elif missing_reasons:
        hypotheses.append(
            Hypothesis(
                hypothesis_id=f"hyp_{uuid.uuid4().hex[:6]}",
                statement=f"Investigation could not isolate definitive contributors due to schema or data limitations.",
                supporting_evidence_ids=[],
                confidence_level=ConfidenceLevel.LIMITED,
                status="unconfirmed",
                causality_caveat="Insufficient chronological or dimensional depth in connected database. Correlation does not establish causation.",
            )
        )

    # 6. Recommended Next Actions
    recommendations: List[InvestigationRecommendation] = []
    if contributing_factors:
        recommendations.append(
            InvestigationRecommendation(
                recommendation_id=f"rec_{uuid.uuid4().hex[:6]}",
                action_title=f"Investigate pricing and discount shifts in '{contributing_factors[0].dimension_value}'",
                reason=f"Largest concentration of {observed_change.metric if observed_change else 'metric'} volume.",
                target_data=contributing_factors[0].dimension,
                expected_information_gained="Determines if price reductions or returns impacted the shift.",
                priority="high",
            )
        )
    if "orders" in available_tables and "customers" in available_tables:
        recommendations.append(
            InvestigationRecommendation(
                recommendation_id=f"rec_{uuid.uuid4().hex[:6]}",
                action_title="Analyze customer cohort order frequency",
                reason="Cross-referencing order frequency identifies dormant or churning accounts.",
                target_data="customers -> orders",
                expected_information_gained="Distinguishes account churn from average order value decline.",
                priority="medium",
            )
        )
    if missing_reasons:
        for mr in missing_reasons:
            recommendations.append(
                InvestigationRecommendation(
                    recommendation_id=f"rec_{uuid.uuid4().hex[:6]}",
                    action_title="Review schema and temporal tracking",
                    reason=mr,
                    target_data=primary_tbl,
                    expected_information_gained="Enables longitudinal cohort tracking and trend analysis.",
                    priority="low",
                )
            )

    # 7. Synthesize Executive Summary
    resolved_title = question or f"Investigation of {primary_tbl} metrics"
    if observed_change:
        exec_summary = f"Analysis of table '{primary_tbl}' reveals an observed change in {observed_change.metric} of {observed_change.formatted_change} across {observed_change.time_period}."
        if contributing_factors:
            exec_summary += f" The largest associated concentration was in '{contributing_factors[0].dimension_value}' ({contributing_factors[0].contribution_percent}% share)."
    else:
        exec_summary = f"Investigation initiated on '{primary_tbl}'. However, quantitative period comparison could not be completed due to insufficient historical records or schema depth."
        if missing_reasons:
            exec_summary += f" Caveat: {'; '.join(missing_reasons)}"

    status_str = "success" if (observed_change and not missing_reasons) else (
        "insufficient_evidence" if missing_reasons else "success"
    )

    report_payload = {
        "investigation_id": investigation_id,
        "question": question or "Business Investigation",
        "title": resolved_title,
        "status": status_str,
        "primary_table": primary_tbl,
        "observed_change": observed_change.to_dict() if observed_change else None,
        "evidence": [e.to_dict() for e in evidence_items],
        "contributing_factors": [c.to_dict() for c in contributing_factors],
        "hypotheses": [h.to_dict() for h in hypotheses],
        "recommendations": [r.to_dict() for r in recommendations],
        "charts": charts,
        "missing_reasons": missing_reasons,
        "provenance": {
            "connection_id": conn_id,
            "database_type": db_type,
            "tables_inspected": list(dict.fromkeys([primary_tbl] + available_tables[:3])),
            "lineage_steps": lineage_steps,
            "comparison_periods": comp_periods,
            "analyzed_columns": analyzed_columns,
        },
        "created_at": now_iso,
    }

    # 8. Persist to investigation store
    save_investigation_report(
        report_id=investigation_id,
        user_id=user_id,
        connection_id=conn_id,
        question=question or "Business Investigation",
        title=resolved_title,
        status=status_str,
        summary=exec_summary,
        report_data=report_payload,
    )

    return {
        "status": status_str,
        "investigation_id": investigation_id,
        "user_id": user_id,
        "connection_id": conn_id,
        "question": question or "Business Investigation",
        "title": resolved_title,
        "summary": exec_summary,
        "report": report_payload,
        "created_at": now_iso,
    }
