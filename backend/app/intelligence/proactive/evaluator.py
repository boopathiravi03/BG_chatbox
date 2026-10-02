"""
backend/app/intelligence/proactive/evaluator.py

Phase 8.3: Deterministic Proactive Metric Evaluator
Continuously evaluates business context, discovers measure shifts, computes
chronological deltas, applies threshold rules, and generates reproducible BusinessAlerts.

100% deterministic:
- All math executed in Python / SQL
- No LLM numerical calculations
- No fake/demo metrics or hallucinated tables
- Strictly read-only query execution
- Full user isolation via DatabaseContext
"""
from __future__ import annotations

import logging
from typing import Any, Optional
from sqlalchemy import text

from app.database.database_manager import get_engine, get_current_db_type
from app.database.connection_context import get_request_user_id
from app.intelligence.schema_analyzer import quote_identifier, analyze_schema
from app.intelligence.ai_analyst.trend_analyzer import get_dialect_date_trunc
from app.intelligence.business_intelligence.business_context import discover_business_context
from app.tools.execute_query import validate_sql
from app.intelligence.proactive.models import (
    BusinessAlert,
    MetricSnapshot,
    AlertRule,
    AlertStatus,
    AlertSeverity,
    AlertCategory,
)
from app.intelligence.proactive.rules import (
    get_default_rules,
    calculate_delta,
    calculate_delta_percent,
    classify_change,
    evaluate_null_rate,
)
from app.intelligence.proactive.alert_store import (
    save_alert,
    find_active_alert,
)

logger = logging.getLogger("bgai.proactive")


def evaluate_proactive_metrics(
    engine: Any = None,
    db_type: Optional[str] = None,
    user_id: Optional[str] = None,
    rules: Optional[list[AlertRule]] = None,
    schema_info: Optional[dict[str, Any]] = None,
    deduplicate: bool = True,
    save_to_store: bool = True,
) -> dict[str, Any]:
    """
    Main evaluation pipeline:
    1. Inspects connected database schema and business context.
    2. Computes chronological metrics with sample sizes >= 3.
    3. Evaluates deltas and null-rates against deterministic rules.
    4. Generates BusinessAlerts and MetricSnapshots with full SQL lineage.
    5. Applies storage-level deduplication per user.
    """
    if engine is None:
        engine = get_engine()
        db_type = get_current_db_type()

    if engine is None or db_type == "none":
        return {
            "status": "disconnected",
            "reason": "No database connected.",
            "alerts": [],
            "snapshots": [],
            "alerts_count": 0,
            "snapshots_count": 0,
        }

    if user_id is None:
        user_id = get_request_user_id() or "default"

    active_rules = rules or get_default_rules()

    # Discover business context
    context = discover_business_context(engine, db_type, schema_info)
    if not context.has_sufficient_data:
        return {
            "status": "insufficient_data",
            "reason": context.reason or "Database does not have sufficient records.",
            "alerts": [],
            "snapshots": [],
            "alerts_count": 0,
            "snapshots_count": 0,
        }

    generated_alerts: list[BusinessAlert] = []
    generated_snapshots: list[MetricSnapshot] = []

    with engine.connect() as conn:
        # ── 1. Chronological Time-Series Metric Evaluation ────────────────────
        for entity in context.entity_tables:
            table_name = entity.get("table", "")
            time_cols = entity.get("time_columns", [])
            if not time_cols or entity.get("row_count", 0) < 3:
                continue

            time_col = time_cols[0]
            t_sql = quote_identifier(table_name, db_type)
            time_sql = quote_identifier(time_col, db_type)

            # Find numeric measure columns in this table
            measures_for_table = [
                m.get("column")
                for m in context.measure_columns
                if m.get("table") == table_name
            ]

            # Targets to evaluate: specific measures or row count volume
            eval_targets = []
            if measures_for_table:
                for mc in measures_for_table[:2]:  # Top 2 measures to keep bounded
                    eval_targets.append((mc, f"SUM({quote_identifier(mc, db_type)})", f"Total {mc.replace('_', ' ').title()}"))
            else:
                eval_targets.append(("*", "COUNT(*)", "Record Volume"))

            for measure_col, agg_expr, friendly_metric in eval_targets:
                date_trunc_expr = get_dialect_date_trunc(time_sql, db_type, interval="month")
                series_sql = (
                    f"SELECT {date_trunc_expr} AS period, {agg_expr} AS val "
                    f"FROM {t_sql} "
                    f"WHERE {time_sql} IS NOT NULL "
                    f"GROUP BY period "
                    f"ORDER BY period ASC"
                )

                # Validate read-only safety
                val_res = validate_sql(series_sql)
                if not val_res["allowed"] or val_res.get("operation") != "select":
                    continue

                try:
                    rows = conn.execute(text(series_sql)).fetchall()
                except Exception as ex:
                    logger.debug(f"Time-series query error on {table_name}: {ex}")
                    continue

                valid_periods = [
                    (str(r[0]), float(r[1]))
                    for r in rows
                    if r[0] is not None and r[1] is not None
                ]

                # Minimum sample size enforcement
                if len(valid_periods) < 3:
                    continue

                prev_period, prev_val = valid_periods[-2]
                curr_period, curr_val = valid_periods[-1]

                delta = calculate_delta(curr_val, prev_val)
                delta_pct = calculate_delta_percent(curr_val, prev_val)

                # Record deterministic measurement snapshot
                snapshot = MetricSnapshot(
                    metric=f"{table_name}.{measure_col}.monthly",
                    user_id=user_id,
                    value=curr_val,
                    period=curr_period,
                    period_start=prev_period,
                    period_end=curr_period,
                    source_tables=[table_name],
                    source_columns=[time_col, measure_col] if measure_col != "*" else [time_col],
                    sql=series_sql,
                    calculation_metadata={
                        "sample_size": len(valid_periods),
                        "baseline_period": prev_period,
                        "baseline_value": prev_val,
                        "observed_period": curr_period,
                        "observed_value": curr_val,
                        "delta": delta,
                        "delta_percent": delta_pct,
                    },
                )
                generated_snapshots.append(snapshot)

                # Threshold & Change Classification
                if delta_pct is not None:
                    classification = classify_change(delta_pct)
                    if classification:
                        category, severity, threshold_applied = classification
                        alert = BusinessAlert(
                            title=f"{severity.capitalize()} {category.replace('_', ' ').title()}: {friendly_metric} in {table_name}",
                            category=category,
                            severity=severity,
                            metric=f"{table_name}.{measure_col}.monthly",
                            user_id=user_id,
                            previous_value=prev_val,
                            current_value=curr_val,
                            delta=delta,
                            delta_percent=delta_pct,
                            threshold_applied=threshold_applied,
                            source_tables=[table_name],
                            source_columns=[time_col, measure_col] if measure_col != "*" else [time_col],
                            lineage_steps=[
                                f"Filtered {table_name} where {time_col} IS NOT NULL",
                                f"Grouped chronological periods using {db_type} date truncation",
                                f"Aggregated {agg_expr} for sample size of {len(valid_periods)} periods",
                                f"Compared current period ({curr_period}) against baseline ({prev_period})",
                            ],
                            sql=series_sql,
                            evidence={
                                "periods": [p[0] for p in valid_periods],
                                "values": [p[1] for p in valid_periods],
                                "sample_size": len(valid_periods),
                                "baseline": prev_val,
                                "observed": curr_val,
                                "delta": delta,
                                "delta_percent": delta_pct,
                            },
                            explanation=(
                                f"{friendly_metric} in table '{table_name}' shifted by {delta_pct:+.1f}% "
                                f"(from {prev_val:g} in {prev_period} to {curr_val:g} in {curr_period})."
                            ),
                            recommendation=(
                                f"Review transactions in '{table_name}' during {curr_period} "
                                f"to evaluate operational causes of this {category.lower().replace('_', ' ')}."
                            ),
                            action_suggestion={
                                "agent": "analyst_agent",
                                "task": f"Investigate {delta_pct:+.1f}% shift in {table_name} {friendly_metric}",
                            },
                            status=AlertStatus.NEW,
                        )
                        generated_alerts.append(alert)

        # ── 2. Data Quality Degradation (Null Rate) Evaluation ────────────────
        for entity in context.entity_tables:
            table_name = entity.get("table", "")
            t_sql = quote_identifier(table_name, db_type)
            row_count = entity.get("row_count", 0)
            if row_count < 5:
                continue

            # Check primary keys and critical foreign key columns
            cols_to_check = []
            for col_obj in entity.get("columns", []):
                col_name = col_obj.get("name") if isinstance(col_obj, dict) else str(col_obj)
                if col_name.lower().endswith("_id") or col_name.lower() in {"id", "email", "status"}:
                    cols_to_check.append(col_name)

            for col_name in cols_to_check[:3]:
                c_sql = quote_identifier(col_name, db_type)
                null_sql = f"SELECT COUNT(*) AS total, COUNT({c_sql}) AS filled FROM {t_sql}"
                
                val_res = validate_sql(null_sql)
                if not val_res["allowed"] or val_res.get("operation") != "select":
                    continue

                try:
                    row = conn.execute(text(null_sql)).fetchone()
                    if row and row[0] and row[0] > 0:
                        total_rows = float(row[0])
                        filled_rows = float(row[1])
                        null_rate = (total_rows - filled_rows) / total_rows

                        eval_result = evaluate_null_rate(null_rate)
                        if eval_result:
                            category, severity, threshold_applied = eval_result
                            alert = BusinessAlert(
                                title=f"Data Quality Degradation: High Null Rate in {table_name}.{col_name}",
                                category=category,
                                severity=severity,
                                metric=f"{table_name}.{col_name}.null_rate",
                                user_id=user_id,
                                previous_value=0.0,
                                current_value=round(null_rate, 4),
                                delta=round(null_rate, 4),
                                delta_percent=round(null_rate * 100.0, 2),
                                threshold_applied=threshold_applied,
                                source_tables=[table_name],
                                source_columns=[col_name],
                                lineage_steps=[
                                    f"Scanned table {table_name}",
                                    f"Counted null entries in critical column {col_name}",
                                    f"Computed null density across {int(total_rows)} records",
                                ],
                                sql=null_sql,
                                evidence={
                                    "total_records": int(total_rows),
                                    "null_records": int(total_rows - filled_rows),
                                    "null_rate": round(null_rate, 4),
                                    "null_percentage": round(null_rate * 100.0, 2),
                                },
                                explanation=(
                                    f"Column '{col_name}' in table '{table_name}' has a null rate of "
                                    f"{null_rate * 100:.1f}% ({int(total_rows - filled_rows)} of {int(total_rows)} rows missing values)."
                                ),
                                recommendation=(
                                    f"Inspect upstream ingestion pipelines populating '{table_name}.{col_name}' "
                                    f"to prevent referential or validation failures."
                                ),
                                action_suggestion={
                                    "agent": "data_quality_agent",
                                    "task": f"Audit and resolve null values in {table_name}.{col_name}",
                                },
                                status=AlertStatus.NEW,
                            )
                            generated_alerts.append(alert)
                except Exception as ex:
                    logger.debug(f"Null check error on {table_name}.{col_name}: {ex}")
                    continue

        # ── 3. Cross-Table Orphan Record Evaluation ───────────────────────────
        for rel in context.relationships:
            from_t = rel.get("from_table")
            to_t = rel.get("to_table")
            from_c = rel.get("from_column")
            to_c = rel.get("to_column")
            if not (from_t and to_t and from_c and to_c):
                continue

            from_sql = quote_identifier(from_t, db_type)
            to_sql = quote_identifier(to_t, db_type)
            fc_sql = quote_identifier(from_c, db_type)
            tc_sql = quote_identifier(to_c, db_type)

            orphan_sql = (
                f"SELECT COUNT(*) FROM {from_sql} f "
                f"LEFT JOIN {to_sql} t ON f.{fc_sql} = t.{tc_sql} "
                f"WHERE t.{tc_sql} IS NULL AND f.{fc_sql} IS NOT NULL"
            )

            val_res = validate_sql(orphan_sql)
            if not val_res["allowed"] or val_res.get("operation") != "select":
                continue

            try:
                orphan_count = conn.execute(text(orphan_sql)).scalar()
                if orphan_count and int(orphan_count) > 0:
                    alert = BusinessAlert(
                        title=f"Data Quality Degradation: Orphan Foreign Keys in {from_t} -> {to_t}",
                        category=AlertCategory.DATA_QUALITY_DEGRADATION,
                        severity=AlertSeverity.WARNING if int(orphan_count) < 20 else AlertSeverity.CRITICAL,
                        metric=f"{from_t}.{from_c}.orphan_count",
                        user_id=user_id,
                        previous_value=0.0,
                        current_value=float(orphan_count),
                        delta=float(orphan_count),
                        delta_percent=None,
                        threshold_applied="Orphan records > 0",
                        source_tables=[from_t, to_t],
                        source_columns=[from_c, to_c],
                        lineage_steps=[
                            f"Identified foreign key link: {from_t}.{from_c} -> {to_t}.{to_c}",
                            f"Executed LEFT JOIN to detect dangling parent references",
                            f"Identified {int(orphan_count)} orphan records",
                        ],
                        sql=orphan_sql,
                        evidence={
                            "from_table": from_t,
                            "to_table": to_t,
                            "from_column": from_c,
                            "to_column": to_c,
                            "orphan_count": int(orphan_count),
                        },
                        explanation=(
                            f"Detected {int(orphan_count)} orphan record(s) in '{from_t}' referencing "
                            f"non-existent records in parent table '{to_t}'."
                        ),
                        recommendation=(
                            f"Remediate dangling foreign keys in '{from_t}.{from_c}' to restore relational integrity."
                        ),
                        action_suggestion={
                            "agent": "action_agent",
                            "task": f"Remediate orphan foreign keys in {from_t}.{from_c}",
                        },
                        status=AlertStatus.NEW,
                    )
                    generated_alerts.append(alert)
            except Exception as ex:
                logger.debug(f"Orphan query error on {from_t} -> {to_t}: {ex}")
                continue

    # ── 4. Deduplication & Persistence ────────────────────────────────────────
    final_alerts: list[BusinessAlert] = []
    for alert in generated_alerts:
        if deduplicate:
            existing = find_active_alert(alert.metric, alert.category, user_id=user_id)
            if existing:
                # Update existing alert in-place
                existing.current_value = alert.current_value
                existing.delta = alert.delta
                existing.delta_percent = alert.delta_percent
                existing.evidence = alert.evidence
                existing.sql = alert.sql
                existing.explanation = alert.explanation
                if save_to_store:
                    saved = save_alert(existing, user_id=user_id)
                    final_alerts.append(saved)
                else:
                    final_alerts.append(existing)
                continue

        if save_to_store:
            saved = save_alert(alert, user_id=user_id)
            final_alerts.append(saved)
        else:
            final_alerts.append(alert)

    return {
        "status": "success",
        "alerts": [a.to_dict() for a in final_alerts],
        "snapshots": [s.to_dict() for s in generated_snapshots],
        "alerts_count": len(final_alerts),
        "snapshots_count": len(generated_snapshots),
    }
