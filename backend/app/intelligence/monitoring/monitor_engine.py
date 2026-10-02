"""Phase 8.6 — Monitor engine.

Orchestrates on-demand scan across Phase 8.1–8.3 subsystems.
Returns a MonitoringReport.  Never duplicates subsystem logic.
Never modifies user databases.
"""
from __future__ import annotations

import uuid
import time
from datetime import datetime, timezone
from typing import Any

from .models import (
    MonitoringItem,
    MonitoringReport,
    MonitoringSeverity,
    MonitoringItemType,
)
from .impact_analyzer import (
    anomaly_to_impact,
    anomaly_to_explanation,
    alert_to_impact,
    alert_to_explanation,
    bi_insight_to_impact,
    bi_insight_to_explanation,
)
from .executive_summary import generate_executive_summary


# ── Converters ────────────────────────────────────────────────────────────────

def _severity_from_str(s: str) -> MonitoringSeverity:
    s = (s or "").lower()
    if s == "critical":
        return MonitoringSeverity.CRITICAL
    if s in ("warning", "high", "medium"):
        return MonitoringSeverity.WARNING
    return MonitoringSeverity.INFO


def _items_from_anomalies(anomalies: list[dict[str, Any]]) -> list[MonitoringItem]:
    items = []
    for a in anomalies:
        table = a.get("table", "?")
        col = a.get("column", "")
        label = f"{table}.{col}" if col else table
        sev = _severity_from_str(a.get("severity", "warning"))
        items.append(MonitoringItem(
            item_id=f"anom-{uuid.uuid4().hex[:8]}",
            item_type=MonitoringItemType.ANOMALY,
            severity=sev,
            title=a.get("title", f"Anomaly in {label}"),
            observed_change=a.get("description", f"Statistical anomaly detected in {label}."),
            business_impact=anomaly_to_impact(a),
            possible_explanation=anomaly_to_explanation(a),
            recommended_next_step=a.get("recommendation", "Investigate the anomalous values manually."),
            evidence={"raw": a},
            source_component="phase_8_2_anomaly_detection",
        ))
    return items


def _items_from_alerts(alerts: list[dict[str, Any]]) -> list[MonitoringItem]:
    items = []
    for al in alerts:
        sev = _severity_from_str(al.get("severity", "warning"))
        items.append(MonitoringItem(
            item_id=f"alert-{al.get('alert_id', uuid.uuid4().hex[:8])}",
            item_type=MonitoringItemType.PROACTIVE_ALERT,
            severity=sev,
            title=al.get("title", "Proactive Alert"),
            observed_change=al.get("description", ""),
            business_impact=alert_to_impact(al),
            possible_explanation=alert_to_explanation(al),
            recommended_next_step=al.get("recommendation", "Review alert details."),
            evidence={"raw": al},
            source_component="phase_8_3_proactive_intelligence",
        ))
    return items


def _items_from_bi(insights: list[dict[str, Any]]) -> list[MonitoringItem]:
    items = []
    for ins in insights:
        sev_raw = ins.get("severity", "info")
        sev = _severity_from_str(sev_raw)
        items.append(MonitoringItem(
            item_id=f"bi-{uuid.uuid4().hex[:8]}",
            item_type=MonitoringItemType.BI_INSIGHT,
            severity=sev,
            title=ins.get("title", "BI Insight"),
            observed_change=ins.get("description", ins.get("summary", "")),
            business_impact=bi_insight_to_impact(ins),
            possible_explanation=bi_insight_to_explanation(ins),
            recommended_next_step=ins.get("action", "Review the insight and validate with domain experts."),
            evidence={k: v for k, v in ins.items() if k not in ("title", "description", "summary")},
            source_component="phase_8_1_business_intelligence",
        ))
    return items


# ── Main scan ─────────────────────────────────────────────────────────────────

def run_monitoring_scan(
    engine: Any,
    db_type: str,
    user_id: str,
) -> MonitoringReport:
    """
    Execute a full on-demand monitoring scan.

    Parameters
    ----------
    engine : SQLAlchemy engine (already user-bound via ContextVar)
    db_type : str
    user_id : str
    """
    start_ms = int(time.time() * 1000)
    scanned_at = datetime.now(tz=timezone.utc).isoformat()
    all_items: list[MonitoringItem] = []

    # ── Phase 8.3: Proactive Alerts ──────────────────────────────────────────
    try:
        from app.intelligence.proactive.alert_store import get_alerts
        raw_alerts = get_alerts(user_id=user_id, limit=20)
        alert_dicts = [
            a.to_dict() if hasattr(a, "to_dict") else a
            for a in raw_alerts
        ]
        all_items.extend(_items_from_alerts(alert_dicts))
    except Exception:
        pass

    # ── Phase 8.2: Anomaly Detection ─────────────────────────────────────────
    try:
        from app.intelligence.anomaly.detector import detect_anomalies
        result = detect_anomalies(engine, db_type)
        anomalies_raw = result if isinstance(result, list) else (result or {}).get("anomalies", [])
        if isinstance(anomalies_raw, list):
            all_items.extend(_items_from_anomalies(anomalies_raw))
    except Exception:
        pass

    # ── Phase 8.1: Business Intelligence Report ───────────────────────────────
    try:
        from app.intelligence.business_intelligence.insight_engine import (
            generate_business_intelligence_report,
        )
        bi_result = generate_business_intelligence_report(engine, db_type, user_id)
        insights_raw = []
        if isinstance(bi_result, dict):
            insights_raw = bi_result.get("insights", [])
        elif hasattr(bi_result, "insights"):
            insights_raw = bi_result.insights or []
        all_items.extend(_items_from_bi(insights_raw))
    except Exception:
        pass

    elapsed_ms = int(time.time() * 1000) - start_ms

    report = MonitoringReport(
        user_id=user_id,
        db_type=db_type,
        scanned_at=scanned_at,
        items=all_items,
        scan_duration_ms=elapsed_ms,
        status="success",
    )

    # Build executive summary from collected items
    report.executive_summary = generate_executive_summary(report)

    return report
