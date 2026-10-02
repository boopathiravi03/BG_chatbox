"""
backend/app/intelligence/decision/evidence.py

Phase 8.4: Multi-Source Evidence Aggregator
Consolidates verifiable database measurements across:
- Phase 8.1 Automated BI Engine (trends, decline, growth, concentration)
- Phase 8.2 Multi-Table / Cross-Table Intelligence
- Phase 4 Anomaly Detection
- Phase 4 Time-Series Forecasting
- Phase 8.3 Proactive Alert Store
- Phase 1 Schema & Table Profiles

Strict Read-Only Guarantee:
- Never alters database state or executes write queries.
- Extracts reproducible SQL lineage and deterministic metrics.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.intelligence.decision.models import EvidenceItem
from app.intelligence.business_intelligence.insight_engine import generate_business_intelligence_report
from app.intelligence.business_intelligence.multitable_engine import query_multitable_bi
from app.intelligence.anomaly.detector import detect_anomalies
from app.intelligence.proactive.alert_store import get_alerts

logger = logging.getLogger("bgai.decision.evidence")


def aggregate_multi_source_evidence(
    engine: Any,
    db_type: str,
    user_id: str,
    intent: Optional[str] = None,
    target_tables: Optional[list[str]] = None,
) -> list[EvidenceItem]:
    """
    Collects and synthesizes verified evidence items from all connected intelligence subsystems.
    Safely captures signals without failing if any individual subsystem returns empty results.
    """
    evidence_list: list[EvidenceItem] = []

    if engine is None or db_type == "none":
        return evidence_list

    # ── 1. Phase 8.1 Automated Business Intelligence ───────────────────────────
    try:
        bi_report = generate_business_intelligence_report(engine=engine, db_type=db_type, user_id=user_id)
        if bi_report and getattr(bi_report, "insights", None):
            for ins in bi_report.insights:
                # Capture volume, trends, drops, and concentration
                ev = EvidenceItem(
                    metric=ins.metric or ins.category,
                    title=ins.title,
                    current_value=ins.current_value,
                    previous_value=ins.previous_value,
                    delta=ins.change_value if isinstance(ins.change_value, (int, float)) else None,
                    delta_percent=ins.change_percent,
                    source_tables=ins.source_tables or [],
                    source_columns=ins.source_columns or [],
                    sql=ins.sql,
                    calculation=f"BI Insight ({ins.category}): {ins.headline}",
                    source_system="BI_ENGINE",
                    metadata={"priority": ins.priority, "severity": ins.severity},
                )
                evidence_list.append(ev)
    except Exception as e:
        logger.debug("Evidence aggregation from BI engine encountered: %s", str(e))

    # ── 2. Phase 8.2 Cross-Table Multi-Hop Relationships ───────────────────────
    try:
        # Check standard cross-table questions if intent indicates financial or order performance
        cross_q = "revenue by product" if intent == "PRODUCT_PERFORMANCE" else "revenue by category"
        ct_resp = query_multitable_bi(cross_q, engine=engine, db_type=db_type, user_id=user_id)
        if ct_resp and ct_resp.get("status") == "success" and ct_resp.get("data"):
            rows = ct_resp.get("data", [])
            sample_summary = f"{len(rows)} groups analyzed"
            ev = EvidenceItem(
                metric="cross_table_revenue_breakdown",
                title=f"Cross-Table Breakdown: {cross_q.title()}",
                current_value=sample_summary,
                source_tables=ct_resp.get("source_tables") or [],
                sql=ct_resp.get("sql"),
                calculation=ct_resp.get("ai_explanation") or "Cross-table foreign key aggregation",
                source_system="CROSS_TABLE_BI",
                metadata={"groups_count": len(rows), "lineage": ct_resp.get("lineage")},
            )
            evidence_list.append(ev)
    except Exception as e:
        logger.debug("Evidence aggregation from Cross-Table BI encountered: %s", str(e))


    # ── 3. Phase 8.3 Proactive Alerts ──────────────────────────────────────────
    try:
        active_alerts = get_alerts(user_id=user_id, status=None, limit=20)
        for alt in active_alerts:
            ev = EvidenceItem(
                metric=alt.metric,
                title=alt.title,
                current_value=alt.current_value,
                previous_value=alt.previous_value,
                delta=alt.delta,
                delta_percent=alt.delta_percent,
                source_tables=alt.source_tables,
                source_columns=alt.source_columns,
                sql=alt.sql,
                calculation=f"Proactive Alert ({alt.category}): {alt.explanation}",
                source_system="PROACTIVE_ALERTS",
                metadata={
                    "alert_id": alt.alert_id,
                    "severity": alt.severity,
                    "status": alt.status,
                    "threshold_applied": alt.threshold_applied,
                },
            )
            evidence_list.append(ev)
    except Exception as e:
        logger.debug("Evidence aggregation from Proactive Alert store encountered: %s", str(e))

    # ── 4. Phase 4 Statistical Anomaly Detection ──────────────────────────────
    try:
        anom_report = detect_anomalies(engine=engine, db_type=db_type)
        if anom_report and getattr(anom_report, "anomalies", None):
            for anom in anom_report.anomalies:
                ev = EvidenceItem(
                    metric=anom.column_name or anom.table_name,
                    title=f"Statistical Anomaly in '{anom.table_name}.{anom.column_name}'",
                    current_value=anom.observed_value,
                    previous_value=anom.baseline_value,
                    source_tables=[anom.table_name] if anom.table_name else [],
                    source_columns=[anom.column_name] if anom.column_name else [],
                    calculation=f"Anomaly z-score deviation ({anom.severity}): {anom.description}",
                    source_system="ANOMALY_DETECTOR",
                    metadata={"deviation_factor": anom.deviation_factor, "severity": anom.severity},
                )
                evidence_list.append(ev)
    except Exception as e:
        logger.debug("Evidence aggregation from Anomaly detector encountered: %s", str(e))

    return evidence_list

