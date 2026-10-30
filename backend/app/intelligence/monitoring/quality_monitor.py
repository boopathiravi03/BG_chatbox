"""backend/app/intelligence/monitoring/quality_monitor.py

Core monitoring and baseline comparison engine for Sprint 2.
Executes read-only health audits, compares against historical baselines,
detects new vs resolved data quality findings and business anomalies,
and dispatches deduplicated alerts.
"""

from __future__ import annotations

import time
import uuid
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.agent.database_profile import DatabaseProfile, DataHealthFinding
from app.tools.analyze_database import analyze_database
from app.database.connection_context import (
    set_user_context_for_request,
    get_request_engine,
    get_request_db_type,
    get_request_user_id,
)
from app.intelligence.monitoring.baseline_store import (
    get_latest_baseline,
    save_baseline,
    record_scan_history,
)
from app.intelligence.anomaly.business_anomaly import detect_business_anomalies, BusinessAnomaly
from app.intelligence.proactive.alert_store import save_alert, update_alert_status
from app.intelligence.proactive.models import (
    BusinessAlert,
    AlertCategory,
    AlertSeverity,
    AlertStatus,
)

_active_scans_lock = threading.Lock()
_active_scans: set[tuple[str, str]] = set()  # (user_id, connection_id) lock to prevent overlap


def run_database_health_monitoring(
    user_id: str,
    connection_id: Optional[str] = None,
    manual: bool = False,
) -> Dict[str, Any]:
    """
    Executes a comprehensive, read-only health and data-quality monitoring scan.
    Compares latest findings against previous baseline to detect newly emerging
    defects, resolved issues, schema drift, and business anomalies.
    """
    conn_id = connection_id or "default"
    scan_key = (user_id, conn_id)

    # 1. Concurrency Lock: Prevent duplicate overlapping scans for same connection
    with _active_scans_lock:
        if scan_key in _active_scans:
            return {
                "status": "already_scanning",
                "message": f"A monitoring scan is already in progress for connection '{conn_id}'.",
                "scanned_at": datetime.now(timezone.utc).isoformat(),
                "scan_id": None,
            }
        _active_scans.add(scan_key)

    scan_id = f"scan_{uuid.uuid4().hex[:10]}"
    start_time = time.perf_counter()
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        # 2. Activate request context safely
        ctx = set_user_context_for_request(user_id=user_id, connection_id=connection_id)
        engine = get_request_engine()
        db_type = get_request_db_type()

        if engine is None or db_type == "none":
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            record_scan_history(
                scan_id=scan_id,
                user_id=user_id,
                connection_id=conn_id,
                health_score=0,
                total_findings=0,
                new_findings=0,
                resolved_findings=0,
                anomalies_detected=0,
                scan_duration_ms=elapsed_ms,
                status="disconnected",
                error_message="Database is disconnected or unreachable.",
            )
            return {
                "status": "disconnected",
                "scan_id": scan_id,
                "message": "Database is disconnected or not found. Scan skipped.",
                "scanned_at": now_iso,
                "health_score": 0,
                "total_findings": 0,
                "new_findings": [],
                "resolved_findings": [],
                "anomalies": [],
            }

        # 3. Execute live database profiling
        profile = analyze_database(user_id=user_id, connection_id=connection_id)
        if not profile or not profile.analyzed:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return {
                "status": "error",
                "scan_id": scan_id,
                "message": f"Profiling failed: {profile.summary if profile else 'Unknown error'}",
                "scanned_at": now_iso,
            }

        # 4. Retrieve previous baseline
        prev_baseline = get_latest_baseline(user_id=user_id, connection_id=conn_id)

        # 5. Extract current findings & metrics
        curr_findings = [f.to_dict() for f in profile.data_health_findings]
        curr_findings_map = {f["id"]: f for f in curr_findings}

        curr_tables = list(profile.tables.keys())
        curr_row_counts = {t_name: t.row_count for t_name, t in profile.tables.items()}

        # 6. Compare with baseline to detect new vs resolved findings
        new_findings: List[Dict[str, Any]] = []
        resolved_findings: List[Dict[str, Any]] = []
        persistent_findings: List[Dict[str, Any]] = []
        schema_changes: List[str] = []
        row_count_shifts: List[Dict[str, Any]] = []

        if prev_baseline:
            prev_findings_map = {f["id"]: f for f in prev_baseline.get("findings", [])}

            # Detect new findings
            for fid, f in curr_findings_map.items():
                if fid not in prev_findings_map:
                    new_findings.append(f)
                else:
                    persistent_findings.append(f)

            # Detect resolved findings
            for fid, f in prev_findings_map.items():
                if fid not in curr_findings_map:
                    resolved_findings.append(f)

            # Detect schema changes (tables added/dropped)
            prev_tables = set(prev_baseline.get("tables", []))
            curr_tables_set = set(curr_tables)
            added_tables = curr_tables_set - prev_tables
            dropped_tables = prev_tables - curr_tables_set

            for t in added_tables:
                schema_changes.append(f"Table '{t}' was added.")
            for t in dropped_tables:
                schema_changes.append(f"Table '{t}' was dropped.")

            # Detect row count shifts
            prev_rows = prev_baseline.get("row_counts", {})
            for t_name, cur_cnt in curr_row_counts.items():
                if t_name in prev_rows:
                    old_cnt = prev_rows[t_name]
                    if old_cnt > 0:
                        pct_diff = round(((cur_cnt - old_cnt) / old_cnt) * 100, 1)
                        if abs(pct_diff) >= 25.0:
                            row_count_shifts.append({
                                "table": t_name,
                                "previous_count": old_cnt,
                                "current_count": cur_cnt,
                                "percentage_change": pct_diff,
                            })
        else:
            # First scan: all findings are initial
            new_findings = list(curr_findings)

        # 7. Detect explainable business anomalies
        business_anomalies = detect_business_anomalies(
            engine=engine,
            db_type=db_type,
            profile=profile,
        )

        # 8. Create Proactive Alerts for new critical issues or anomalies (with deduplication)
        for nf in new_findings:
            if nf.get("severity") in ("high", "critical", "medium"):
                try:
                    defect_id = nf.get("id") or f"{nf.get('table')}_{nf.get('column')}_{nf.get('type')}"
                    deterministic_alert_id = f"alt_dq_{conn_id}_{defect_id}"
                    alert = BusinessAlert(
                        title=f"New Data Quality Defect: {nf.get('type')} in '{nf.get('table')}'",
                        category=AlertCategory.DATA_QUALITY_DEGRADATION,
                        severity=AlertSeverity.CRITICAL if nf.get("severity") in ("high", "critical") else AlertSeverity.WARNING,
                        metric=nf.get("type", "Data Health"),
                        user_id=user_id,
                        alert_id=deterministic_alert_id,
                        previous_value=None,
                        current_value=float(nf.get("metric_value")) if isinstance(nf.get("metric_value"), (int, float)) else None,
                        source_tables=[nf.get("table", "")] if nf.get("table") else [],
                        source_columns=[nf.get("column")] if nf.get("column") else [],
                        explanation=nf.get("description", ""),
                        recommendation=nf.get("suggested_action", ""),
                        evidence={"finding": nf, "connection_id": conn_id},
                    )
                    save_alert(alert, user_id=user_id)
                except Exception as alert_err:
                    pass

        # Auto-resolve existing alerts for resolved findings
        for rf in resolved_findings:
            try:
                defect_id = rf.get("id") or f"{rf.get('table')}_{rf.get('column')}_{rf.get('type')}"
                resolved_alert_id = f"alt_dq_{conn_id}_{defect_id}"
                update_alert_status(resolved_alert_id, AlertStatus.RESOLVED, user_id=user_id)
            except Exception:
                pass

        for anom in business_anomalies:
            try:
                sev = AlertSeverity.CRITICAL if anom.severity == "critical" else AlertSeverity.WARNING
                anom_key = getattr(anom, "anomaly_id", None) or f"{anom.metric}_{anom.table}"
                deterministic_anom_id = f"alt_anom_{conn_id}_{anom_key}"
                alert = BusinessAlert(
                    title=anom.title,
                    category=AlertCategory.ANOMALY_DETECTED,
                    severity=sev,
                    metric=anom.metric,
                    user_id=user_id,
                    alert_id=deterministic_anom_id,
                    previous_value=anom.expected_value,
                    current_value=anom.observed_value,
                    delta=round(anom.observed_value - anom.expected_value, 2),
                    delta_percent=anom.percentage_change,
                    source_tables=[anom.table],
                    source_columns=[anom.column] if anom.column else [],
                    explanation=anom.explanation,
                    recommendation=anom.recommended_steps[0] if anom.recommended_steps else "Investigate anomaly.",
                    evidence=anom.evidence,
                )
                save_alert(alert, user_id=user_id)
            except Exception as anom_alert_err:
                pass

        # 9. Save current snapshot as new baseline
        baseline_metrics = {
            "total_tables": profile.total_tables,
            "total_rows": profile.total_rows,
            "total_columns": profile.total_columns,
        }
        save_baseline(
            user_id=user_id,
            connection_id=conn_id,
            health_score=profile.health_score,
            tables=curr_tables,
            row_counts=curr_row_counts,
            findings=curr_findings,
            metrics=baseline_metrics,
        )

        # 10. Record scan history
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        summary_payload = {
            "total_tables": profile.total_tables,
            "total_rows": profile.total_rows,
            "health_score": profile.health_score,
            "new_findings_count": len(new_findings),
            "resolved_findings_count": len(resolved_findings),
            "schema_changes": schema_changes,
            "row_count_shifts": row_count_shifts,
        }
        record_scan_history(
            scan_id=scan_id,
            user_id=user_id,
            connection_id=conn_id,
            health_score=profile.health_score,
            total_findings=len(curr_findings),
            new_findings=len(new_findings),
            resolved_findings=len(resolved_findings),
            anomalies_detected=len(business_anomalies),
            scan_duration_ms=elapsed_ms,
            status="success",
            summary=summary_payload,
        )

        return {
            "status": "success",
            "scan_id": scan_id,
            "connection_id": conn_id,
            "scanned_at": now_iso,
            "health_score": profile.health_score,
            "total_findings": len(curr_findings),
            "new_findings": new_findings,
            "resolved_findings": resolved_findings,
            "persistent_findings": persistent_findings,
            "schema_changes": schema_changes,
            "row_count_shifts": row_count_shifts,
            "anomalies": [a.to_dict() for a in business_anomalies],
            "scan_duration_ms": elapsed_ms,
            "is_manual": manual,
        }

    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        record_scan_history(
            scan_id=scan_id,
            user_id=user_id,
            connection_id=conn_id,
            health_score=0,
            total_findings=0,
            new_findings=0,
            resolved_findings=0,
            anomalies_detected=0,
            scan_duration_ms=elapsed_ms,
            status="error",
            error_message=str(e),
        )
        return {
            "status": "error",
            "scan_id": scan_id,
            "connection_id": conn_id,
            "scanned_at": now_iso,
            "error": str(e),
            "scan_duration_ms": elapsed_ms,
        }

    finally:
        with _active_scans_lock:
            _active_scans.discard(scan_key)
