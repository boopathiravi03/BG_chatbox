"""
backend/app/intelligence/business_intelligence/insight_engine.py

Phase 8.1: Automated Business Intelligence Engine
Generates deterministic, verified, evidence-backed business insights across 9 categories:
- TREND
- GROWTH
- DECLINE
- TOP_CONTRIBUTOR
- CONCENTRATION
- QUALITY
- ANOMALY
- FORECAST
- PERFORMANCE
- DATA_COMPLETENESS

Never calculates math using an LLM. Bounded, safe read-only SQL queries.
"""
from __future__ import annotations

import logging
from typing import Any, Optional
from sqlalchemy import text
from app.intelligence.schema_analyzer import quote_identifier, analyze_schema
from app.intelligence.ai_analyst.trend_analyzer import get_dialect_date_trunc
from app.intelligence.business_intelligence.models import (
    BusinessInsight,
    BusinessContext,
    DiscoveredMetric,
    BusinessIntelligenceReport,
    InsightCategory,
    InsightSeverity,
)
from app.intelligence.business_intelligence.business_context import discover_business_context
from app.intelligence.business_intelligence.metric_discovery import discover_business_metrics
from app.intelligence.business_intelligence.insight_ranker import rank_insights
from app.intelligence.business_intelligence.insight_explainer import (
    generate_deterministic_explanation,
    polish_explanation_with_groq_if_available,
)

logger = logging.getLogger("bgai.bi")


def generate_business_intelligence_report(
    engine: Any = None,
    db_type: Optional[str] = None,
    user_id: Optional[str] = None,
    enable_groq_polishing: bool = False,
    force_refresh: bool = False,
) -> BusinessIntelligenceReport:
    """
    Main entry point: executes deterministic discovery, insight generation, and ranking.
    Returns a complete BusinessIntelligenceReport with verified numbers and evidence.
    """
    from app.database.database_manager import get_engine, get_current_db_type
    from app.security.user_cache import cache_get, cache_set, CACHE_INSIGHTS_REPORT

    if engine is None:
        engine = get_engine()
    if db_type is None:
        db_type = get_current_db_type()

    if engine is None or db_type == "none":
        return BusinessIntelligenceReport(
            status="no_database",
            message="Connect a database to generate insights.",
            business_context=BusinessContext(has_sufficient_data=False, reason="No database connected."),
        )

    if not force_refresh and user_id:
        cached = cache_get(user_id, CACHE_INSIGHTS_REPORT)
        if cached is not None:
            return cached

    # 1. Discover Business Context
    context = discover_business_context(engine, db_type)
    if not context.has_sufficient_data:
        return BusinessIntelligenceReport(
            status="insufficient_data",
            message=context.reason or "Insufficient business data for automatic insight generation.",
            business_context=context,
        )

    # 2. Discover Metrics
    metrics = discover_business_metrics(engine, db_type, context)

    insights: list[BusinessInsight] = []

    # 3. Generate Insight Types
    try:
        # A, B, C: Trend, Growth & Decline Insights
        temporal_insights = _generate_temporal_insights(engine, db_type, context)
        insights.extend(temporal_insights)
    except Exception as e:
        logger.debug("Temporal insights error: %s", str(e))

    try:
        # C, D: Top Contributor & Concentration Insights
        breakdown_insights = _generate_breakdown_insights(engine, db_type, context)
        insights.extend(breakdown_insights)
    except Exception as e:
        logger.debug("Breakdown insights error: %s", str(e))

    try:
        # E, I: Data Quality & Completeness Insights
        quality_insights = _generate_quality_insights(engine, db_type, context)
        insights.extend(quality_insights)
    except Exception as e:
        logger.debug("Quality insights error: %s", str(e))

    try:
        # F: Statistical Anomaly Insights
        anomaly_insights = _generate_anomaly_insights(engine, db_type)
        insights.extend(anomaly_insights)
    except Exception as e:
        logger.debug("Anomaly insights error: %s", str(e))

    try:
        # G: Forecast Insights
        forecast_insights = _generate_forecast_insights(engine, db_type, context)
        insights.extend(forecast_insights)
    except Exception as e:
        logger.debug("Forecast insights error: %s", str(e))

    try:
        # H: Performance Insights
        performance_insights = _generate_performance_insights(engine, db_type)
        insights.extend(performance_insights)
    except Exception as e:
        logger.debug("Performance insights error: %s", str(e))

    # 4. Deterministic Ranking
    ranked_insights = rank_insights(insights)

    # 5. Optional Groq Polish (never modifies numbers, only runs if explicitly requested)
    if enable_groq_polishing:
        for ins in ranked_insights[:3]:  # Polish top 3 only to conserve rate limits
            polish_explanation_with_groq_if_available(ins)

    # 6. Summarize counts
    summary = {
        "total": len(ranked_insights),
        "critical": sum(1 for i in ranked_insights if i.severity == InsightSeverity.CRITICAL),
        "warning": sum(1 for i in ranked_insights if i.severity == InsightSeverity.WARNING),
        "info": sum(1 for i in ranked_insights if i.severity == InsightSeverity.INFO),
    }

    report = BusinessIntelligenceReport(
        insights=ranked_insights,
        summary=summary,
        business_context=context,
        metrics=metrics,
        status="success",
        message="Business intelligence generated successfully.",
    )

    if user_id:
        cache_set(user_id, CACHE_INSIGHTS_REPORT, report)

    return report


def _generate_temporal_insights(engine: Any, db_type: str, context: BusinessContext) -> list[BusinessInsight]:
    """Computes TREND, GROWTH, and DECLINE insights by analyzing time-series slices."""
    insights: list[BusinessInsight] = []
    seen_pairs = set()

    with engine.connect() as conn:
        for entity in context.entity_tables:
            table_name = entity.get("table", "")
            time_cols = entity.get("time_columns", [])
            if not time_cols:
                continue
            date_col = time_cols[0]

            # Find measure columns in this table
            measures = [m["column"] for m in context.measure_columns if m["table"] == table_name]
            
            # Analyze each measure or record volume
            targets = measures[:2] if measures else [None]

            for measure_col in targets:
                pair_key = (table_name, date_col, measure_col)
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                t_sql = quote_identifier(table_name, db_type)
                d_sql = quote_identifier(date_col, db_type)
                date_expr = get_dialect_date_trunc(d_sql, db_type, "month")

                if measure_col:
                    m_sql = quote_identifier(measure_col, db_type)
                    val_expr = f"SUM({m_sql})"
                    metric_label = f"{table_name.title()} {measure_col.replace('_', ' ').title()}"
                    where_clause = f"WHERE {d_sql} IS NOT NULL AND {m_sql} IS NOT NULL"
                else:
                    val_expr = "COUNT(*)"
                    metric_label = f"{table_name.title()} Volume"
                    where_clause = f"WHERE {d_sql} IS NOT NULL"

                sql = f"""
                    SELECT {date_expr} AS period, {val_expr} AS val, COUNT(*) AS rec_cnt
                    FROM {t_sql}
                    {where_clause}
                    GROUP BY period
                    ORDER BY period ASC
                    LIMIT 24
                """

                try:
                    cursor = conn.execute(text(sql))
                    rows = cursor.fetchall()
                except Exception:
                    continue

                if len(rows) < 2:
                    continue

                # Compare last period with previous period
                prev_period, prev_val, _ = rows[-2]
                curr_period, curr_val, curr_cnt = rows[-1]

                prev_f = float(prev_val or 0.0)
                curr_f = float(curr_val or 0.0)

                delta = round(curr_f - prev_f, 2)
                if prev_f != 0:
                    pct_change = round((delta / prev_f) * 100.0, 2)
                else:
                    pct_change = 100.0 if curr_f > 0 else 0.0

                evidence = {
                    "current_period": str(curr_period),
                    "current_value": curr_f,
                    "previous_period": str(prev_period),
                    "previous_value": prev_f,
                    "change_value": delta,
                    "change_percent": pct_change,
                    "record_count": curr_cnt,
                    "periods_observed": len(rows),
                    "source": f"{table_name}.{date_col}",
                    "sql": " ".join(sql.split()),
                }

                # Growth or Decline
                if pct_change < 0:
                    cat = InsightCategory.DECLINE
                    sev = (
                        InsightSeverity.CRITICAL if pct_change <= -25.0
                        else InsightSeverity.WARNING if pct_change <= -5.0
                        else InsightSeverity.INFO
                    )
                else:
                    cat = InsightCategory.GROWTH
                    sev = InsightSeverity.INFO

                title, summary, rec = generate_deterministic_explanation(
                    category=cat,
                    metric_name=metric_label,
                    current_val=curr_f,
                    prev_val=prev_f,
                    change_pct=pct_change,
                )

                insights.append(
                    BusinessInsight(
                        title=title,
                        summary=summary,
                        category=cat,
                        severity=sev,
                        metric=metric_label,
                        current_value=curr_f,
                        previous_value=prev_f,
                        change_value=delta,
                        change_percent=pct_change,
                        source_tables=[table_name],
                        source_columns=[date_col] + ([measure_col] if measure_col else []),
                        sql=evidence["sql"],
                        evidence=evidence,
                        investigation_type="ai_analyst",
                        recommended_next_step=rec,
                    )
                )

                # Add overall Trend insight if >= 3 periods
                if len(rows) >= 3:
                    trend_title, trend_summary, trend_rec = generate_deterministic_explanation(
                        category=InsightCategory.TREND,
                        metric_name=metric_label,
                        current_val=curr_f,
                        prev_val=float(rows[0][1] or 0.0),
                        change_pct=pct_change,
                    )
                    insights.append(
                        BusinessInsight(
                            title=trend_title,
                            summary=trend_summary,
                            category=InsightCategory.TREND,
                            severity=InsightSeverity.INFO,
                            metric=metric_label,
                            current_value=curr_f,
                            previous_value=float(rows[0][1] or 0.0),
                            change_value=delta,
                            change_percent=pct_change,
                            source_tables=[table_name],
                            source_columns=[date_col] + ([measure_col] if measure_col else []),
                            sql=evidence["sql"],
                            evidence={**evidence, "baseline_period": str(rows[0][0])},
                            investigation_type="ai_analyst",
                            recommended_next_step=trend_rec,
                        )
                    )

    return insights


def _generate_breakdown_insights(engine: Any, db_type: str, context: BusinessContext) -> list[BusinessInsight]:
    """Computes TOP_CONTRIBUTOR and CONCENTRATION insights."""
    insights: list[BusinessInsight] = []

    with engine.connect() as conn:
        for entity in context.entity_tables:
            table_name = entity.get("table", "")
            dims = entity.get("dimension_columns", [])
            measures = [m["column"] for m in context.measure_columns if m["table"] == table_name]

            if not dims:
                continue

            for dim_col in dims[:4]:
                c_low = dim_col.lower()
                if c_low in ("name", "first_name", "last_name", "email", "phone"):
                    continue

                measure_col = measures[0] if measures else None

                t_sql = quote_identifier(table_name, db_type)
                d_sql = quote_identifier(dim_col, db_type)

                if measure_col:
                    m_sql = quote_identifier(measure_col, db_type)
                    val_expr = f"SUM({m_sql})"
                    metric_name = f"{table_name.title()} {measure_col.replace('_', ' ').title()}"
                    where_clause = f"WHERE {d_sql} IS NOT NULL AND {m_sql} IS NOT NULL"
                else:
                    val_expr = "COUNT(*)"
                    metric_name = f"{table_name.title()} Volume"
                    where_clause = f"WHERE {d_sql} IS NOT NULL"

                sql = f"""
                    SELECT {d_sql} AS dimension, {val_expr} AS total_val, COUNT(*) AS rec_cnt
                    FROM {t_sql}
                    {where_clause}
                    GROUP BY {d_sql}
                    ORDER BY total_val DESC
                    LIMIT 10
                """

                try:
                    cursor = conn.execute(text(sql))
                    rows = cursor.fetchall()
                except Exception:
                    continue

                if not rows or len(rows) < 2:
                    continue

                grand_total = sum(float(r[1] or 0) for r in rows)
                if grand_total <= 0:
                    continue

                # Top Contributor
                top_dim, top_val, _ = rows[0]
                top_f = float(top_val or 0)
                top_share = round((top_f / grand_total) * 100.0, 2)

                if top_share >= 25.0:
                    title, summary, rec = generate_deterministic_explanation(
                        category=InsightCategory.TOP_CONTRIBUTOR,
                        metric_name=metric_name,
                        current_val=top_f,
                        prev_val=grand_total,
                        change_pct=None,
                        dimension_value=str(top_dim),
                        share_pct=top_share,
                    )

                    insights.append(
                        BusinessInsight(
                            title=title,
                            summary=summary,
                            category=InsightCategory.TOP_CONTRIBUTOR,
                            severity=InsightSeverity.INFO,
                            metric=metric_name,
                            current_value=top_f,
                            previous_value=grand_total,
                            change_percent=top_share,
                            source_tables=[table_name],
                            source_columns=[dim_col] + ([measure_col] if measure_col else []),
                            sql=" ".join(sql.split()),
                            evidence={
                                "top_dimension": str(top_dim),
                                "top_value": top_f,
                                "grand_total": grand_total,
                                "share_percent": top_share,
                                "sample_size": len(rows),
                                "sql": " ".join(sql.split()),
                            },
                            investigation_type="ai_analyst",
                            recommended_next_step=rec,
                        )
                    )

                # Concentration (Top items concentration)
                top_k = min(3, len(rows))
                top_k_val = sum(float(r[1] or 0) for r in rows[:top_k])
                top_k_share = round((top_k_val / grand_total) * 100.0, 2)

                if top_k_share >= 50.0:
                    sev = InsightSeverity.WARNING if top_k_share >= 65.0 else InsightSeverity.INFO
                    title, summary, rec = generate_deterministic_explanation(
                        category=InsightCategory.CONCENTRATION,
                        metric_name=metric_name,
                        current_val=top_k_val,
                        prev_val=grand_total,
                        change_pct=None,
                        share_pct=top_k_share,
                        details={"top_count": top_k, "dimension_label": dim_col.replace("_", " ")},
                    )

                    insights.append(
                        BusinessInsight(
                            title=title,
                            summary=summary,
                            category=InsightCategory.CONCENTRATION,
                            severity=sev,
                            metric=metric_name,
                            current_value=top_k_val,
                            previous_value=grand_total,
                            change_percent=top_k_share,
                            source_tables=[table_name],
                            source_columns=[dim_col] + ([measure_col] if measure_col else []),
                            sql=" ".join(sql.split()),
                            evidence={
                                "top_count": top_k,
                                "top_total": top_k_val,
                                "grand_total": grand_total,
                                "share_percent": top_k_share,
                                "dimension": dim_col,
                                "sql": " ".join(sql.split()),
                            },
                            investigation_type="ai_analyst",
                            recommended_next_step=rec,
                        )
                    )

    return insights


def _generate_quality_insights(engine: Any, db_type: str, context: BusinessContext) -> list[BusinessInsight]:
    """Generates QUALITY and DATA_COMPLETENESS insights."""
    insights: list[BusinessInsight] = []
    null_heavy_tables = set()

    with engine.connect() as conn:
        for entity in context.entity_tables:
            table_name = entity.get("table", "")
            row_count = entity.get("row_count", 0)
            if row_count < 10:
                continue

            t_sql = quote_identifier(table_name, db_type)
            cols = entity.get("dimension_columns", []) + [m["column"] for m in context.measure_columns if m["table"] == table_name]

            for col_name in cols[:3]:
                c_sql = quote_identifier(col_name, db_type)
                sql = f"SELECT COUNT(*) FROM {t_sql} WHERE {c_sql} IS NULL"
                try:
                    null_count = conn.execute(text(sql)).scalar() or 0
                    null_pct = round((null_count / row_count) * 100.0, 2)
                    if null_pct >= 15.0:
                        null_heavy_tables.add(table_name)
                        sev = InsightSeverity.WARNING if null_pct >= 30.0 else InsightSeverity.INFO
                        title, summary, rec = generate_deterministic_explanation(
                            category=InsightCategory.QUALITY,
                            metric_name=f"{table_name}.{col_name}",
                            current_val=null_count,
                            prev_val=row_count,
                            change_pct=null_pct,
                            details={"table": table_name, "column": col_name, "null_percent": null_pct},
                        )

                        insights.append(
                            BusinessInsight(
                                title=title,
                                summary=summary,
                                category=InsightCategory.QUALITY,
                                severity=sev,
                                metric=f"Missing {col_name}",
                                current_value=null_count,
                                previous_value=row_count,
                                change_percent=null_pct,
                                source_tables=[table_name],
                                source_columns=[col_name],
                                sql=sql,
                                evidence={
                                    "table": table_name,
                                    "column": col_name,
                                    "null_records": null_count,
                                    "total_records": row_count,
                                    "null_percent": null_pct,
                                    "sql": sql,
                                },
                                investigation_type="data_explorer",
                                recommended_next_step=rec,
                            )
                        )
                except Exception:
                    pass

    # DATA_COMPLETENESS across tables
    if null_heavy_tables:
        tot_tables = max(1, len(context.entity_tables))
        aff_tables = len(null_heavy_tables)
        ratio = round((aff_tables / tot_tables) * 100.0, 1)
        sev = InsightSeverity.WARNING if ratio >= 30.0 else InsightSeverity.INFO

        title, summary, rec = generate_deterministic_explanation(
            category=InsightCategory.DATA_COMPLETENESS,
            metric_name="Table Completeness",
            current_val=aff_tables,
            prev_val=tot_tables,
            change_pct=ratio,
            details={"affected_tables": aff_tables, "total_tables": tot_tables},
        )

        insights.append(
            BusinessInsight(
                title=title,
                summary=summary,
                category=InsightCategory.DATA_COMPLETENESS,
                severity=sev,
                metric="Data Completeness",
                current_value=aff_tables,
                previous_value=tot_tables,
                change_percent=ratio,
                source_tables=list(null_heavy_tables),
                evidence={
                    "affected_tables": aff_tables,
                    "total_tables": tot_tables,
                    "null_heavy_ratio": ratio,
                    "tables": list(null_heavy_tables),
                },
                investigation_type="data_health",
                recommended_next_step=rec,
            )
        )

    return insights


def _generate_anomaly_insights(engine: Any, db_type: str) -> list[BusinessInsight]:
    """Reuses Phase 4 anomaly detection to produce verified ANOMALY insights."""
    insights: list[BusinessInsight] = []
    try:
        from app.intelligence.anomaly.detector import detect_anomalies
        anomaly_report = detect_anomalies(engine=engine, db_type=db_type)
        if anomaly_report and anomaly_report.findings:
            for finding in anomaly_report.findings[:3]:
                sev = (
                    InsightSeverity.CRITICAL if finding.severity == "CRITICAL"
                    else InsightSeverity.WARNING if finding.severity == "WARNING"
                    else InsightSeverity.INFO
                )
                title, summary, rec = generate_deterministic_explanation(
                    category=InsightCategory.ANOMALY,
                    metric_name=finding.column or finding.table,
                    current_val=finding.severity_score,
                    prev_val=None,
                    change_pct=None,
                    details={
                        "table": finding.table,
                        "column": finding.column,
                        "anomaly_type": finding.anomaly_type,
                        "finding": finding.finding,
                    },
                )

                insights.append(
                    BusinessInsight(
                        title=title,
                        summary=summary,
                        category=InsightCategory.ANOMALY,
                        severity=sev,
                        metric=f"Anomaly: {finding.table}.{finding.column or 'general'}",
                        current_value=finding.severity_score,
                        source_tables=[finding.table],
                        source_columns=[finding.column] if finding.column else [],
                        evidence={
                            "anomaly_type": finding.anomaly_type,
                            "severity_score": finding.severity_score,
                            "evidence": finding.evidence,
                            "sample_size": finding.evidence.get("sample_size", 0) if isinstance(finding.evidence, dict) else 0,
                        },
                        investigation_type="anomaly_center",
                        recommended_next_step=rec,
                    )
                )
    except Exception as e:
        logger.debug("Failed anomaly integration: %s", str(e))

    return insights


def _generate_forecast_insights(engine: Any, db_type: str, context: BusinessContext) -> list[BusinessInsight]:
    """Reuses Phase 4 forecasting capabilities to generate FORECAST insights."""
    insights: list[BusinessInsight] = []
    try:
        from app.intelligence.forecasting.forecaster import fit_and_predict_exponential_smoothing

        for entity in context.entity_tables:
            table_name = entity.get("table", "")
            time_cols = entity.get("time_columns", [])
            measures = [m["column"] for m in context.measure_columns if m["table"] == table_name]

            if not time_cols or not measures:
                continue

            date_col = time_cols[0]
            measure_col = measures[0]

            t_sql = quote_identifier(table_name, db_type)
            d_sql = quote_identifier(date_col, db_type)
            m_sql = quote_identifier(measure_col, db_type)
            date_expr = get_dialect_date_trunc(d_sql, db_type, "month")

            sql = f"""
                SELECT {date_expr} AS period, SUM({m_sql}) AS val
                FROM {t_sql}
                WHERE {d_sql} IS NOT NULL AND {m_sql} IS NOT NULL
                GROUP BY period
                ORDER BY period ASC
                LIMIT 24
            """

            with engine.connect() as conn:
                rows = conn.execute(text(sql)).fetchall()

            if len(rows) >= 5:
                series = [float(r[1] or 0.0) for r in rows]
                _, out_of_sample, _ = fit_and_predict_exponential_smoothing(series, horizon=1)
                if out_of_sample:
                    proj_val = round(out_of_sample[0], 2)
                    metric_label = f"{table_name.title()} {measure_col.replace('_', ' ').title()}"

                    title, summary, rec = generate_deterministic_explanation(
                        category=InsightCategory.FORECAST,
                        metric_name=metric_label,
                        current_val=proj_val,
                        prev_val=series[-1],
                        change_pct=None,
                        details={"horizon": "upcoming period"},
                    )

                    insights.append(
                        BusinessInsight(
                            title=title,
                            summary=summary,
                            category=InsightCategory.FORECAST,
                            severity=InsightSeverity.INFO,
                            metric=metric_label,
                            current_value=proj_val,
                            previous_value=series[-1],
                            source_tables=[table_name],
                            source_columns=[date_col, measure_col],
                            sql=" ".join(sql.split()),
                            evidence={
                                "forecast_value": proj_val,
                                "latest_actual": series[-1],
                                "method": "Holt's Exponential Smoothing",
                                "historical_observations": len(series),
                                "sql": " ".join(sql.split()),
                            },
                            investigation_type="forecasting",
                            recommended_next_step=rec,
                        )
                    )
                    break  # 1 high-quality forecast insight is sufficient
    except Exception as e:
        logger.debug("Failed forecast integration: %s", str(e))

    return insights


def _generate_performance_insights(engine: Any, db_type: str) -> list[BusinessInsight]:
    """Reuses Phase 1 performance analysis to produce PERFORMANCE insights."""
    insights: list[BusinessInsight] = []
    try:
        from app.intelligence.performance_analyzer import analyze_performance
        schema = analyze_schema(engine, db_type)
        findings = analyze_performance(schema)
        for f in findings[:2]:
            table_name = getattr(f, "table", "") or "General"
            reason = getattr(f, "recommendation", "") or getattr(f, "finding", "Index recommendation")

            title, summary, rec = generate_deterministic_explanation(
                category=InsightCategory.PERFORMANCE,
                metric_name=table_name,
                current_val=None,
                prev_val=None,
                change_pct=None,
                details={"table": table_name, "reason": reason},
            )

            insights.append(
                BusinessInsight(
                    title=title,
                    summary=summary,
                    category=InsightCategory.PERFORMANCE,
                    severity=InsightSeverity.WARNING,
                    metric="Indexing & Execution",
                    source_tables=[table_name] if table_name != "General" else [],
                    evidence={"recommendation": reason},
                    investigation_type="data_health",
                    recommended_next_step=rec,
                )
            )
    except Exception as e:
        logger.debug("Failed performance integration: %s", str(e))

    return insights
