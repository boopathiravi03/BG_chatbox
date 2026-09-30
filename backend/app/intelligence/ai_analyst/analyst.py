from __future__ import annotations

import re
from typing import Any, Optional

from app.agent.groq_agent import ask_groq
from app.intelligence.scanner import get_cached_report, run_database_intelligence_scan
from app.intelligence.ai_analyst.models import (
    AnalystResult,
    Evidence,
    RecommendedInvestigation,
    QuickAction,
)
from app.intelligence.ai_analyst.metric_engine import discover_metrics_in_schema
from app.intelligence.ai_analyst.trend_analyzer import analyze_trend
from app.intelligence.ai_analyst.comparison_engine import analyze_ranking, analyze_distribution
from app.intelligence.ai_analyst.diagnostic_engine import perform_why_diagnostic
from app.intelligence.ai_analyst.quality_analyzer import analyze_health_findings


def classify_analysis_intent(question: str) -> str:
    """
    Classifies the user's analytical query into an analytical task type:
    - trend
    - diagnostic ("why")
    - ranking (top-n / bottom-n)
    - distribution
    - quality
    - comparison
    - correlation
    - overview
    """
    q = question.lower().strip()

    if re.search(r"\b(anomal|outlier|unusual|abnormal|spike|irregular)\b", q):
        return "anomaly"

    if re.search(r"\b(forecast|predict|future|projection|projected|what may happen|estimate next)\b", q):
        return "forecast"

    if re.search(r"\b(health|unhealthy|quality|orphan|null|missing|integrity|audit)\b", q):
        return "quality"

    if re.search(r"\b(why|reason|cause|driver|contribut|fell|drop|declin)\b", q):
        return "diagnostic"

    if re.search(r"\b(trend|over time|timeline|monthly|weekly|daily|growth|historical)\b", q):
        return "trend"

    if re.search(r"\b(top|highest|most|lowest|bottom|least|best|worst|rank)\b", q):
        return "ranking"

    if re.search(r"\b(distribut|breakdown|status|percentage|proportion|share|split)\b", q):
        return "distribution"

    if re.search(r"\b(compare|versus|vs|difference|between)\b", q):
        return "comparison"

    if re.search(r"\b(correlat|relat|associated|connect)\b", q):
        return "correlation"

    return "overview"


def find_target_entity(
    question: str,
    metrics_info: list[dict[str, Any]],
    user_table: Optional[str] = None,
    user_metric: Optional[str] = None,
) -> tuple[Optional[dict[str, Any]], Optional[str], Optional[str], Optional[str]]:
    """
    Identifies the best matching table, numeric column, date column, and category column.
    """
    q = question.lower()

    # 1. Match table
    target_table_info = None
    if user_table:
        target_table_info = next((m for m in metrics_info if m["table"].lower() == user_table.lower()), None)

    if not target_table_info:
        for m in metrics_info:
            t_name = m["table"].lower()
            if t_name in q or t_name[:-1] in q:
                target_table_info = m
                break

    if not target_table_info and metrics_info:
        # Default to table with most numeric columns or highest row count
        target_table_info = sorted(metrics_info, key=lambda x: (len(x["numeric_columns"]), x["row_count"]), reverse=True)[0]

    if not target_table_info:
        return None, None, None, None

    # 2. Match numeric metric column
    target_metric_col = user_metric
    if not target_metric_col:
        for num_col in target_table_info["numeric_columns"]:
            c_name = num_col["name"].lower()
            if c_name in q or any(term in q for term in ("sales", "revenue", "amount", "price", "cost", "total")):
                target_metric_col = num_col["name"]
                break

    if not target_metric_col and target_table_info["numeric_columns"]:
        target_metric_col = target_table_info["numeric_columns"][0]["name"]

    # 3. Match date column
    target_date_col = None
    if target_table_info["date_columns"]:
        target_date_col = target_table_info["date_columns"][0]["name"]

    # 4. Match category column
    target_category_col = None
    if target_table_info["category_columns"]:
        target_category_col = target_table_info["category_columns"][0]["name"]

    return target_table_info, target_metric_col, target_date_col, target_category_col


def generate_groq_analyst_explanation(
    question: str,
    key_insight: str,
    evidence_dict: dict[str, Any],
) -> str:
    """
    Uses Groq to generate a concise, professional executive explanation of the verified evidence.
    Falls back gracefully if Groq is unavailable.
    """
    prompt = f"""You are the senior AI Analyst in BG AI, a professional enterprise data workspace.
The user asked: "{question}"

Verified Database Evidence (Derived from SQL execution):
{evidence_dict}

Key Insight:
{key_insight}

Task:
Write a concise, high-impact 2-3 sentence executive explanation of these findings.
Rules:
1. State only the facts directly supported by the evidence above.
2. If discussing trends or drivers, describe them as "associated with" or "concentrated in", NEVER claim causation.
3. Be direct, authoritative, and analytical.
4. Do NOT output markdown code blocks or greetings.
"""
    try:
        explanation = ask_groq(prompt)
        if explanation and len(explanation.strip()) > 10:
            return explanation.strip()
    except Exception:
        pass

    # Deterministic fallback
    current_val = evidence_dict.get("current_value")
    pct_chg = evidence_dict.get("percentage_change")
    direction = evidence_dict.get("direction", "recorded")
    table = evidence_dict.get("source_table", "the database")

    if pct_chg is not None and current_val is not None:
        return f"Analysis of '{table}' indicates values currently stand at {current_val:,.2f}, representing a {direction} trend of {abs(pct_chg)}% across recorded periods."
    return key_insight


def run_ai_analysis(
    question: str,
    table: Optional[str] = None,
    metric: Optional[str] = None,
) -> AnalystResult:
    """
    Executes the full structured AI Analyst pipeline:
    Question -> Intent -> Metrics -> SQL -> Analysis Engine -> Evidence -> Groq Explanation -> Structured Result.
    """
    report = get_cached_report()
    if report is None:
        report = run_database_intelligence_scan(force_refresh=False)

    if not report or report.database_type == "none" or not report.schema_summary:
        return AnalystResult(
            question=question,
            analysis_type="none",
            key_insight="No database connected.",
            evidence=Evidence(
                metric_name="None",
                calculation="None",
                source_table="None",
                confidence_note="Connect a database to analyze your data.",
            ),
            status="error",
            error_message="Connect a database to analyze your data.",
        )

    intent = classify_analysis_intent(question)
    metrics_info = discover_metrics_in_schema(report.schema_summary)

    # 1. Quality & Health Analysis
    if intent == "quality":
        qh_data = analyze_health_findings()
        evidence = Evidence(
            metric_name="Database Health Score",
            calculation="Deductive multi-factor audit (0-100)",
            source_table="All Tables",
            current_value=qh_data["health_score"],
            breakdown=qh_data["findings"],
            confidence_note=f"Audited {qh_data['total_findings']} health factors across {report.total_tables} tables.",
        )

        key_insight = f"Database health score is {qh_data['health_score']}/100. {qh_data['health_verdict']}"
        explanation = generate_groq_analyst_explanation(question, key_insight, evidence.to_dict())

        return AnalystResult(
            question=question,
            analysis_type="quality",
            key_insight=key_insight,
            evidence=evidence,
            recommended_investigations=[
                RecommendedInvestigation(label="Open Data Health Doctor", action="health"),
                RecommendedInvestigation(label="Inspect Schema Topology", action="explorer"),
            ],
            ai_explanation=explanation,
            breakdown=qh_data["findings"],
            status="success",
        )

    # 2. Anomaly Intelligence Analysis
    if intent == "anomaly":
        from app.intelligence.anomaly import detect_anomalies
        anomaly_report = detect_anomalies(force_refresh=False)
        total = anomaly_report.total_anomalies
        crit = anomaly_report.critical_count
        warn = anomaly_report.warning_count
        info_c = anomaly_report.info_count

        evidence = Evidence(
            metric_name="Detected Anomalies",
            calculation="IQR & Multi-factor Statistical Audit",
            source_table=table or "Connected Database",
            current_value=total,
            breakdown=[a.to_dict() for a in anomaly_report.anomalies[:10]],
            confidence_note=f"Verified {total} statistical and structural anomalies ({crit} critical, {warn} warnings, {info_c} informational).",
        )

        if total == 0:
            key_insight = "No statistical or data quality anomalies detected across scanned tables."
        else:
            top_a = anomaly_report.anomalies[0]
            key_insight = f"Detected {total} anomalies ({crit} critical, {warn} warnings). Top finding: {top_a.metric} in '{top_a.table}' ({top_a.deviation_str})."

        explanation = generate_groq_analyst_explanation(question, key_insight, evidence.to_dict())

        return AnalystResult(
            question=question,
            analysis_type="anomaly",
            key_insight=key_insight,
            evidence=evidence,
            recommended_investigations=[
                RecommendedInvestigation(label="Open Anomaly Center", action="anomalies"),
                RecommendedInvestigation(label="Inspect in Data Explorer", action="explorer", target=anomaly_report.anomalies[0].table if total > 0 else None),
            ],
            ai_explanation=explanation,
            breakdown=[a.to_dict() for a in anomaly_report.anomalies[:10]],
            status="success",
        )

    # 3. Time-Series Forecasting Analysis
    if intent == "forecast":
        from app.intelligence.forecasting import detect_forecast_candidates, run_forecast
        candidates, err = detect_forecast_candidates()
        if not candidates or err:
            return AnalystResult(
                question=question,
                analysis_type="forecast",
                key_insight=err or "Forecasting unavailable: no suitable time-series data was detected.",
                evidence=Evidence(
                    metric_name="Forecasting",
                    calculation="Time Series Check",
                    source_table=table or "None",
                    confidence_note="Requires at least one date column and sufficient historical observations.",
                ),
                status="insufficient_data",
                error_message=err or "No suitable time-series candidates found.",
            )

        chosen = None
        if table:
            chosen = next((c for c in candidates if c.table.lower() == table.lower()), None)
        if not chosen:
            chosen = candidates[0]

        fc_result = run_forecast(
            table=chosen.table,
            date_column=chosen.date_column,
            metric_column=chosen.metric_column,
            frequency=chosen.frequency,
            horizon=3,
        )

        if fc_result.status != "success":
            return AnalystResult(
                question=question,
                analysis_type="forecast",
                key_insight=fc_result.error_message or "Insufficient historical data for forecasting.",
                evidence=Evidence(
                    metric_name=chosen.metric_label,
                    calculation=chosen.calculation,
                    source_table=chosen.table,
                ),
                status=fc_result.status,
                error_message=fc_result.error_message,
            )

        last_obs = fc_result.observations[-fc_result.forecast_horizon]
        final_obs = fc_result.observations[-1]
        delta_proj = round(final_obs.value - last_obs.value, 2)
        dir_proj = "up" if delta_proj > 0 else ("down" if delta_proj < 0 else "flat")

        evidence = Evidence(
            metric_name=fc_result.metric_name,
            calculation=f"{fc_result.method} ({fc_result.forecast_horizon} {fc_result.horizon_unit})",
            source_table=fc_result.source_table,
            source_column=fc_result.metric_column,
            date_column=fc_result.date_column,
            current_value=final_obs.value,
            previous_value=last_obs.value,
            absolute_change=delta_proj,
            direction=dir_proj,
            confidence_note=f"Projected with {fc_result.method}. MAE: {fc_result.validation.get('mae', 'N/A')}.",
            breakdown=[o.to_dict() for o in fc_result.observations],
        )

        return AnalystResult(
            question=question,
            analysis_type="forecast",
            key_insight=f"Projected {fc_result.metric_name} moves from {last_obs.value:,.2f} to {final_obs.value:,.2f} over the next {fc_result.forecast_horizon} periods.",
            evidence=evidence,
            chart=fc_result.chart,
            breakdown=[o.to_dict() for o in fc_result.observations],
            recommended_investigations=[
                RecommendedInvestigation(label="Open Forecasting Studio", action="forecasting"),
                RecommendedInvestigation(label="Inspect Query in SQL Lab", action="sqllab", query=fc_result.sql_query),
            ],
            ai_explanation=fc_result.ai_explanation,
            sql_query=fc_result.sql_query,
            status="success",
        )

    # Find target entity and attributes
    target_info, target_metric, target_date, target_category = find_target_entity(
        question=question,
        metrics_info=metrics_info,
        user_table=table,
        user_metric=metric,
    )

    if not target_info:
        return AnalystResult(
            question=question,
            analysis_type=intent,
            key_insight="This database does not contain enough populated tables for this analysis.",
            evidence=Evidence(
                metric_name="Unavailable",
                calculation="None",
                source_table="None",
                confidence_note="Database tables contain no records.",
            ),
            status="insufficient_data",
            error_message="This database does not contain enough populated tables for this analysis.",
        )

    target_table_name = target_info["table"]

    # 2. Time-Series Trend Analysis
    if intent == "trend":
        if not target_date:
            return AnalystResult(
                question=question,
                analysis_type="trend",
                key_insight="Time-series analysis is unavailable because no suitable date/time field was detected.",
                evidence=Evidence(
                    metric_name=target_metric or "Records",
                    calculation="Chronological Aggregation",
                    source_table=target_table_name,
                    confidence_note="No date or timestamp columns found in schema.",
                ),
                recommended_investigations=[
                    RecommendedInvestigation(label=f"Inspect '{target_table_name}' in Data Explorer", action="explorer", target=target_table_name),
                ],
                ai_explanation="A date or timestamp column is required to calculate historical trends over time.",
                status="unavailable",
            )

        trend_res = analyze_trend(
            table_name=target_table_name,
            metric_col=target_metric,
            date_col=target_date,
            agg_func="SUM" if target_metric else "COUNT",
            interval="month",
        )

        if trend_res.get("status") != "success":
            return AnalystResult(
                question=question,
                analysis_type="trend",
                key_insight=trend_res.get("message", "Insufficient chronological data."),
                evidence=Evidence(
                    metric_name=target_metric or "Records",
                    calculation="Time Series",
                    source_table=target_table_name,
                ),
                status=trend_res.get("status", "error"),
                error_message=trend_res.get("message"),
            )

        evidence = Evidence(
            metric_name=target_metric or "Records",
            calculation=trend_res["calculation"],
            source_table=target_table_name,
            source_column=target_metric,
            date_column=target_date,
            current_value=trend_res["current_value"],
            previous_value=trend_res["previous_value"],
            absolute_change=trend_res["absolute_change"],
            percentage_change=trend_res["percentage_change"],
            growth_rate=trend_res["percentage_change"],
            direction=trend_res["direction"],
            sample_count=trend_res["sample_count"],
            time_period=trend_res["current_period"],
            breakdown=trend_res["breakdown"],
        )

        growth_str = f"{'+' if trend_res['percentage_change'] > 0 else ''}{trend_res['percentage_change']}%"
        key_insight = f"{target_metric or 'Activity'} in '{target_table_name}' shifted {growth_str} in recent period ({trend_res['current_period']})."
        explanation = generate_groq_analyst_explanation(question, key_insight, evidence.to_dict())

        return AnalystResult(
            question=question,
            analysis_type="trend",
            key_insight=key_insight,
            evidence=evidence,
            chart=trend_res.get("chart"),
            breakdown=trend_res["breakdown"],
            recommended_investigations=[
                RecommendedInvestigation(label=f"Inspect '{target_table_name}' in Explorer", action="explorer", target=target_table_name),
                RecommendedInvestigation(label="Query in SQL Lab", action="sqllab", query=trend_res.get("sql")),
            ],
            ai_explanation=explanation,
            sql_query=trend_res.get("sql"),
            status="success",
        )

    # 3. Diagnostic / "WHY" Analysis
    if intent in ("diagnostic", "correlation"):
        diag_res = perform_why_diagnostic(
            table_name=target_table_name,
            metric_col=target_metric,
            dimension_cols=[c["name"] for c in target_info["category_columns"]],
            date_col=target_date,
            agg_func="SUM" if target_metric else "COUNT",
        )

        if diag_res.get("status") != "success":
            # Fallback to ranking if diagnostic lacks categories
            intent = "ranking"
        else:
            top_driver = diag_res["contributors"][0] if diag_res["contributors"] else None
            evidence = Evidence(
                metric_name=target_metric or "Count",
                calculation=f"Dimensional breakdown on {diag_res['dimension_column']}",
                source_table=target_table_name,
                source_column=target_metric,
                current_value=diag_res["total_value"],
                breakdown=diag_res["contributors"],
                confidence_note=diag_res["causality_disclaimer"],
            )

            key_insight = diag_res["driver_summary"]
            explanation = generate_groq_analyst_explanation(question, key_insight, evidence.to_dict())

            return AnalystResult(
                question=question,
                analysis_type="diagnostic",
                key_insight=key_insight,
                evidence=evidence,
                chart=diag_res.get("chart"),
                breakdown=diag_res["contributors"],
                recommended_investigations=[
                    RecommendedInvestigation(label=f"Inspect '{target_table_name}' in Explorer", action="explorer", target=target_table_name),
                    RecommendedInvestigation(label="Query in SQL Lab", action="sqllab", query=diag_res.get("sql")),
                ],
                ai_explanation=explanation,
                sql_query=diag_res.get("sql"),
                status="success",
            )

    # 4. Ranking / Top-N Analysis
    if intent in ("ranking", "comparison"):
        dim_col = target_category or (target_info["primary_keys"][0] if target_info["primary_keys"] else None)
        if not dim_col and target_info["category_columns"]:
            dim_col = target_info["category_columns"][0]["name"]

        if not dim_col:
            dim_col = target_info["numeric_columns"][0]["name"] if target_info["numeric_columns"] else "id"

        is_bottom = any(w in question.lower() for w in ("bottom", "lowest", "least", "worst"))

        rank_res = analyze_ranking(
            table_name=target_table_name,
            dimension_col=dim_col,
            metric_col=target_metric,
            agg_func="SUM" if target_metric else "COUNT",
            limit=10,
            ascending=is_bottom,
        )

        if rank_res.get("status") == "success":
            evidence = Evidence(
                metric_name=target_metric or "Count",
                calculation=rank_res["calculation"],
                source_table=target_table_name,
                source_column=target_metric,
                current_value=rank_res["total_value"],
                breakdown=rank_res["breakdown"],
            )

            top_item = rank_res["breakdown"][0] if rank_res["breakdown"] else None
            top_str = f"'{top_item['category']}' leads with {top_item['value']:,.2f} ({top_item['percentage']}%)" if top_item else "Computed rankings."
            key_insight = f"{'Bottom' if is_bottom else 'Top'} ranking for '{target_table_name}' by {dim_col}: {top_str}."
            explanation = generate_groq_analyst_explanation(question, key_insight, evidence.to_dict())

            return AnalystResult(
                question=question,
                analysis_type="ranking",
                key_insight=key_insight,
                evidence=evidence,
                chart=rank_res.get("chart"),
                breakdown=rank_res["breakdown"],
                recommended_investigations=[
                    RecommendedInvestigation(label=f"Inspect '{target_table_name}' in Explorer", action="explorer", target=target_table_name),
                    RecommendedInvestigation(label="Query in SQL Lab", action="sqllab", query=rank_res.get("sql")),
                ],
                ai_explanation=explanation,
                sql_query=rank_res.get("sql"),
                status="success",
            )

    # 5. Distribution Analysis (Default Fallback)
    cat_col = target_category
    if not cat_col and target_info["category_columns"]:
        cat_col = target_info["category_columns"][0]["name"]

    if cat_col:
        dist_res = analyze_distribution(table_name=target_table_name, category_col=cat_col)
        if dist_res.get("status") == "success":
            evidence = Evidence(
                metric_name=f"Distribution of {cat_col}",
                calculation=f"COUNT grouped by {cat_col}",
                source_table=target_table_name,
                source_column=cat_col,
                current_value=dist_res["total_records"],
                breakdown=dist_res["breakdown"],
            )

            top_share = dist_res["breakdown"][0] if dist_res["breakdown"] else None
            share_str = f"'{top_share['category']}' holds {top_share['percentage']}% of records." if top_share else "Calculated distribution."
            key_insight = f"Distribution of '{target_table_name}.{cat_col}': {share_str}"
            explanation = generate_groq_analyst_explanation(question, key_insight, evidence.to_dict())

            return AnalystResult(
                question=question,
                analysis_type="distribution",
                key_insight=key_insight,
                evidence=evidence,
                chart=dist_res.get("chart"),
                breakdown=dist_res["breakdown"],
                recommended_investigations=[
                    RecommendedInvestigation(label=f"Inspect '{target_table_name}' in Explorer", action="explorer", target=target_table_name),
                    RecommendedInvestigation(label="Query in SQL Lab", action="sqllab", query=dist_res.get("sql")),
                ],
                ai_explanation=explanation,
                sql_query=dist_res.get("sql"),
                status="success",
            )

    # Generic Overview Fallback
    evidence = Evidence(
        metric_name="Record Count",
        calculation="COUNT(*)",
        source_table=target_table_name,
        current_value=target_info["row_count"],
    )
    key_insight = f"Table '{target_table_name}' has {target_info['row_count']:,} verified records."

    return AnalystResult(
        question=question,
        analysis_type="overview",
        key_insight=key_insight,
        evidence=evidence,
        recommended_investigations=[
            RecommendedInvestigation(label=f"Inspect '{target_table_name}' in Explorer", action="explorer", target=target_table_name),
        ],
        ai_explanation=f"Entity table '{target_table_name}' is active in the database with verified integrity.",
        status="success",
    )


def generate_quick_actions() -> list[QuickAction]:
    """
    Dynamically generates tailored analysis actions based on currently connected database schema.
    """
    report = get_cached_report()
    if report is None:
        report = run_database_intelligence_scan(force_refresh=False)

    if not report or report.database_type == "none" or not report.schema_summary:
        return []

    metrics_info = discover_metrics_in_schema(report.schema_summary)
    actions = []

    # 1. Health Audit (Always available)
    actions.append(
        QuickAction(
            id="health_audit",
            title="Database Health & Integrity Audit",
            question="Audit my database health findings and data quality issues",
            category="quality",
        )
    )

    # 2. Time-Series Trend Action (if table has date column)
    for m in metrics_info:
        if m["date_columns"] and m["numeric_columns"]:
            num_name = m["numeric_columns"][0]["name"]
            date_name = m["date_columns"][0]["name"]
            actions.append(
                QuickAction(
                    id=f"trend_{m['table']}",
                    title=f"{m['table'].title()} {num_name.replace('_', ' ').title()} Trend Over Time",
                    question=f"What is the {num_name} trend over time in {m['table']}?",
                    category="trend",
                    table=m["table"],
                    metric=num_name,
                )
            )
            break

    # 3. Top-N Ranking Action
    for m in metrics_info:
        if m["numeric_columns"]:
            num_name = m["numeric_columns"][0]["name"]
            cat_name = m["category_columns"][0]["name"] if m["category_columns"] else (m["primary_keys"][0] if m["primary_keys"] else "id")
            actions.append(
                QuickAction(
                    id=f"top_{m['table']}",
                    title=f"Top {m['table'].title()} by {num_name.replace('_', ' ').title()}",
                    question=f"Show top 10 {m['table']} by {num_name}",
                    category="ranking",
                    table=m["table"],
                    metric=num_name,
                )
            )
            break

    # 4. Distribution Action
    for m in metrics_info:
        if m["category_columns"]:
            cat_name = m["category_columns"][0]["name"]
            actions.append(
                QuickAction(
                    id=f"dist_{m['table']}_{cat_name}",
                    title=f"{m['table'].title()} Distribution by {cat_name.title()}",
                    question=f"How are {m['table']} distributed by {cat_name}?",
                    category="distribution",
                    table=m["table"],
                )
            )
            break

    # 5. Diagnostic Action
    for m in metrics_info:
        if m["numeric_columns"] and m["category_columns"]:
            num_name = m["numeric_columns"][0]["name"]
            actions.append(
                QuickAction(
                    id=f"why_{m['table']}",
                    title=f"Diagnose {m['table'].title()} {num_name.title()} Contributors",
                    question=f"Why are there differences in {m['table']} {num_name}?",
                    category="diagnostic",
                    table=m["table"],
                    metric=num_name,
                )
            )
            break

    return actions[:5]
