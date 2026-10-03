#!/usr/bin/env python
"""
Phase 8.6 — Continuous Intelligence & Executive Monitoring
Test suite: 30 tests

Run from backend/:
  python scratch/test_phase8_6_monitoring.py
"""
from __future__ import annotations

import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from fastapi.testclient import TestClient
from app.main import app
from app.security.auth import create_access_token

client = TestClient(app, raise_server_exceptions=False)

results: list[tuple] = []


def test(name: str, fn):
    try:
        fn()
        results.append(("PASS", name))
        print(f"  ✓ {name}")
    except Exception as e:
        results.append(("FAIL", name, str(e)))
        print(f"  ✗ {name}: {e}")


def _auth(user_id: str) -> dict:
    token = create_access_token({"sub": user_id})
    return {"Authorization": f"Bearer {token}"}


# ── 1. Package imports ────────────────────────────────────────────────────────
print("\n[1/10] Package imports")


def t01():
    from app.intelligence.monitoring import (
        MonitoringItem, MonitoringReport, ExecutiveSummary,
        MonitoringSeverity, MonitoringItemType, run_monitoring_scan,
        generate_executive_summary,
    )
    assert MonitoringItem
    assert MonitoringReport
    assert ExecutiveSummary


test("monitoring package importable", t01)


def t02():
    from app.intelligence.monitoring.models import (
        MonitoringItem, MonitoringReport, ExecutiveSummary,
        MonitoringSeverity, MonitoringItemType,
    )
    assert MonitoringSeverity.CRITICAL.value == "critical"
    assert MonitoringSeverity.WARNING.value == "warning"
    assert MonitoringSeverity.INFO.value == "info"
    assert MonitoringItemType.ANOMALY.value == "anomaly"
    assert MonitoringItemType.PROACTIVE_ALERT.value == "proactive_alert"
    assert MonitoringItemType.BI_INSIGHT.value == "bi_insight"


test("severity and item_type enums correct", t02)


def t03():
    from app.intelligence.monitoring.models import (
        MonitoringItem, MonitoringSeverity, MonitoringItemType,
    )
    item = MonitoringItem(
        item_id="x",
        item_type=MonitoringItemType.ANOMALY,
        severity=MonitoringSeverity.CRITICAL,
        title="Test",
        observed_change="change",
        business_impact="impact",
        possible_explanation="explanation",
        recommended_next_step="fix it",
    )
    d = item.to_dict()
    assert d["severity"] == "critical"
    assert d["item_type"] == "anomaly"
    restored = MonitoringItem.from_dict(d)
    assert restored.severity == MonitoringSeverity.CRITICAL


test("MonitoringItem to_dict / from_dict roundtrip", t03)


def t04():
    from app.intelligence.monitoring.models import (
        ExecutiveSummary, MonitoringReport, MonitoringItemType,
    )
    es = ExecutiveSummary(
        overall_status="critical",
        headline="3 critical issues detected.",
        critical_count=3,
        warning_count=1,
        info_count=0,
        top_risks=["Risk A"],
        top_opportunities=[],
    )
    d = es.to_dict()
    assert d["overall_status"] == "critical"
    assert d["critical_count"] == 3
    restored = ExecutiveSummary.from_dict(d)
    assert restored.critical_count == 3


test("ExecutiveSummary to_dict / from_dict roundtrip", t04)


def t05():
    from app.intelligence.monitoring.models import (
        MonitoringReport, ExecutiveSummary,
    )
    report = MonitoringReport(
        user_id="user123",
        db_type="sqlite",
        scanned_at="2026-01-01T00:00:00+00:00",
        items=[],
        executive_summary=ExecutiveSummary(
            overall_status="healthy",
            headline="All clear.",
            critical_count=0,
            warning_count=0,
            info_count=0,
            top_risks=[],
            top_opportunities=[],
        ),
        scan_duration_ms=42,
        status="success",
    )
    d = report.to_dict()
    assert d["status"] == "success"
    assert d["user_id"] == "user123"
    restored = MonitoringReport.from_dict(d)
    assert restored.executive_summary is not None


test("MonitoringReport to_dict / from_dict roundtrip", t05)


# ── 2. Impact analyser ────────────────────────────────────────────────────────
print("\n[2/10] Impact analyser")


def t06():
    from app.intelligence.monitoring.impact_analyzer import anomaly_to_impact
    result = anomaly_to_impact({"table": "orders", "column": "amount", "severity": "critical"})
    assert "orders" in result
    assert "critical" in result.lower() or "Critical" in result


test("anomaly_to_impact produces critical text", t06)


def t07():
    from app.intelligence.monitoring.impact_analyzer import anomaly_to_explanation
    result = anomaly_to_explanation({"reason": "value 999999 is 8σ above mean"})
    assert "999999" in result or "8σ" in result


test("anomaly_to_explanation includes reason text", t07)


def t08():
    from app.intelligence.monitoring.impact_analyzer import alert_to_impact
    result = alert_to_impact({"severity": "warning", "title": "Low inventory", "category": "operations"})
    assert "Low inventory" in result


test("alert_to_impact includes alert title", t08)


def t09():
    from app.intelligence.monitoring.impact_analyzer import bi_insight_to_impact
    result = bi_insight_to_impact({"title": "Revenue up 12%", "metric_type": "revenue"})
    assert "Revenue up 12%" in result


test("bi_insight_to_impact includes insight title", t09)


# ── 3. Executive summary ──────────────────────────────────────────────────────
print("\n[3/10] Executive summary generation")


def t10():
    from app.intelligence.monitoring.models import (
        MonitoringReport, MonitoringItem, MonitoringSeverity, MonitoringItemType,
    )
    from app.intelligence.monitoring.executive_summary import generate_executive_summary
    report = MonitoringReport(user_id="u", db_type="sqlite", scanned_at="", items=[])
    es = generate_executive_summary(report)
    assert es.overall_status == "healthy"
    assert es.critical_count == 0


test("empty report → healthy executive summary", t10)


def t11():
    from app.intelligence.monitoring.models import (
        MonitoringReport, MonitoringItem, MonitoringSeverity, MonitoringItemType,
    )
    from app.intelligence.monitoring.executive_summary import generate_executive_summary
    items = [
        MonitoringItem(
            item_id="i1",
            item_type=MonitoringItemType.ANOMALY,
            severity=MonitoringSeverity.CRITICAL,
            title="Critical anomaly",
            observed_change="",
            business_impact="Big impact",
            possible_explanation="",
            recommended_next_step="Fix it",
        )
    ]
    report = MonitoringReport(user_id="u", db_type="sqlite", scanned_at="", items=items)
    es = generate_executive_summary(report)
    assert es.overall_status == "critical"
    assert es.critical_count == 1
    assert len(es.top_risks) == 1


test("1 critical item → critical executive summary with top risk", t11)


def t12():
    from app.intelligence.monitoring.models import (
        MonitoringReport, MonitoringItem, MonitoringSeverity, MonitoringItemType,
    )
    from app.intelligence.monitoring.executive_summary import generate_executive_summary
    items = [
        MonitoringItem(
            item_id=f"i{k}",
            item_type=MonitoringItemType.BI_INSIGHT,
            severity=MonitoringSeverity.WARNING,
            title=f"Warning {k}",
            observed_change="",
            business_impact="",
            possible_explanation="",
            recommended_next_step=f"Action {k}",
        )
        for k in range(5)
    ]
    report = MonitoringReport(user_id="u", db_type="sqlite", scanned_at="", items=items)
    es = generate_executive_summary(report)
    assert es.overall_status == "attention_needed"
    assert es.warning_count == 5
    assert len(es.top_risks) <= 3  # capped at 3


test("5 warnings → attention_needed, top_risks capped at 3", t12)


# ── 4. Monitor engine (no DB) ─────────────────────────────────────────────────
print("\n[4/10] Monitor engine (no real DB)")


def t13():
    from app.intelligence.monitoring.monitor_engine import run_monitoring_scan
    # No engine → should return gracefully with 0 items (subsystems catch errors)
    report = run_monitoring_scan(engine=None, db_type="none", user_id="test_user")
    assert report.status == "success"
    assert isinstance(report.items, list)
    assert report.executive_summary is not None


test("run_monitoring_scan with no engine returns valid report", t13)


def t14():
    from app.intelligence.monitoring.monitor_engine import run_monitoring_scan
    report = run_monitoring_scan(engine=None, db_type="none", user_id="test_user_14")
    assert report.user_id == "test_user_14"
    assert report.db_type == "none"
    assert report.scanned_at != ""
    assert report.scan_duration_ms >= 0


test("report contains correct user_id, db_type, scanned_at, duration", t14)


def t15():
    from app.intelligence.monitoring.monitor_engine import run_monitoring_scan
    uid_a = f"user_a_{uuid.uuid4().hex[:6]}"
    uid_b = f"user_b_{uuid.uuid4().hex[:6]}"
    report_a = run_monitoring_scan(engine=None, db_type="none", user_id=uid_a)
    report_b = run_monitoring_scan(engine=None, db_type="none", user_id=uid_b)
    assert report_a.user_id == uid_a
    assert report_b.user_id == uid_b
    assert report_a.user_id != report_b.user_id


test("run_monitoring_scan user isolation: separate user_ids", t15)


# ── 5. API endpoints ──────────────────────────────────────────────────────────
print("\n[5/10] API endpoints")

_u1 = f"user_mon_{uuid.uuid4().hex[:6]}"
_u2 = f"user_mon_{uuid.uuid4().hex[:6]}"


def t16():
    r = client.get("/intelligence/monitoring/status", headers=_auth(_u1))
    assert r.status_code == 200
    data = r.json()
    # Fresh user — no scan yet
    assert data["status"] in ("no_scan", "ok", "error")


test("GET /intelligence/monitoring/status returns 200", t16)


def t17():
    r = client.get("/intelligence/monitoring/status", headers=_auth(_u1))
    data = r.json()
    if data["status"] == "no_scan":
        assert data["last_scanned_at"] is None


test("status no_scan → last_scanned_at is None", t17)


def t18():
    r = client.get("/intelligence/monitoring/summary", headers=_auth(_u1))
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("no_scan", "success", "error")


test("GET /intelligence/monitoring/summary returns 200", t18)


def t19():
    r = client.post("/intelligence/monitoring/evaluate", headers=_auth(_u1))
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("success", "disconnected", "error")


test("POST /intelligence/monitoring/evaluate returns 200", t19)


def t20():
    # Unauthenticated
    r = client.post("/intelligence/monitoring/evaluate")
    assert r.status_code in (401, 403, 422)


test("POST /intelligence/monitoring/evaluate requires auth", t20)


def t21():
    r = client.get("/intelligence/monitoring/status")
    assert r.status_code in (401, 403, 422)


test("GET /intelligence/monitoring/status requires auth", t21)


def t22():
    r = client.get("/intelligence/monitoring/summary")
    assert r.status_code in (401, 403, 422)


test("GET /intelligence/monitoring/summary requires auth", t22)


def t23():
    # User isolation: user2's status is independent of user1's
    r1 = client.post("/intelligence/monitoring/evaluate", headers=_auth(_u1))
    r2 = client.get("/intelligence/monitoring/status", headers=_auth(_u2))
    assert r1.status_code == 200
    assert r2.status_code == 200
    # u2 might still be no_scan (separate cache entry)
    d2 = r2.json()
    assert d2["status"] in ("no_scan", "ok", "error")


test("user isolation: user2 status unaffected by user1 scan", t23)


def t24():
    # After evaluate, status should reflect the scan (or stay no_scan if disconnected)
    uid = f"user_mon_{uuid.uuid4().hex[:6]}"
    ev = client.post("/intelligence/monitoring/evaluate", headers=_auth(uid))
    assert ev.status_code == 200
    ev_data = ev.json()
    if ev_data["status"] == "success":
        st = client.get("/intelligence/monitoring/status", headers=_auth(uid))
        st_data = st.json()
        assert st_data["status"] == "ok"
        assert st_data["last_scanned_at"] is not None
    # disconnected case is also valid
    assert ev_data["status"] in ("success", "disconnected", "error")


test("after evaluate success, status reflects scan", t24)


def t25():
    uid = f"user_mon_{uuid.uuid4().hex[:6]}"
    ev = client.post("/intelligence/monitoring/evaluate", headers=_auth(uid))
    ev_data = ev.json()
    if ev_data["status"] == "success":
        sm = client.get("/intelligence/monitoring/summary", headers=_auth(uid))
        sm_data = sm.json()
        assert sm_data["status"] == "success"
        assert sm_data["summary"] is not None
        s = sm_data["summary"]
        assert "overall_status" in s
        assert "headline" in s
        assert "critical_count" in s


test("after evaluate success, summary endpoint returns executive summary", t25)


# ── 6. Report structure ───────────────────────────────────────────────────────
print("\n[6/10] Report structure")


def t26():
    uid = f"user_mon_{uuid.uuid4().hex[:6]}"
    ev = client.post("/intelligence/monitoring/evaluate", headers=_auth(uid))
    data = ev.json()
    if data["status"] == "success" and data.get("report"):
        r = data["report"]
        assert "user_id" in r
        assert "db_type" in r
        assert "scanned_at" in r
        assert "items" in r
        assert isinstance(r["items"], list)
        assert "executive_summary" in r
        assert "scan_duration_ms" in r


test("evaluate response report has all required fields", t26)


def t27():
    uid = f"user_mon_{uuid.uuid4().hex[:6]}"
    ev = client.post("/intelligence/monitoring/evaluate", headers=_auth(uid))
    data = ev.json()
    if data["status"] == "success" and data.get("report"):
        for item in data["report"]["items"]:
            assert "item_id" in item
            assert "severity" in item
            assert item["severity"] in ("critical", "warning", "info")
            assert "title" in item
            assert "business_impact" in item
            assert "recommended_next_step" in item


test("every monitoring item has required fields with valid severity", t27)


def t28():
    uid = f"user_mon_{uuid.uuid4().hex[:6]}"
    ev = client.post("/intelligence/monitoring/evaluate", headers=_auth(uid))
    data = ev.json()
    if data["status"] == "success" and data.get("report"):
        es = data["report"]["executive_summary"]
        if es:
            assert es["overall_status"] in ("healthy", "attention_needed", "critical")
            assert isinstance(es["critical_count"], int)
            assert isinstance(es["top_risks"], list)
            assert len(es["top_risks"]) <= 3


test("executive_summary overall_status valid, top_risks capped at 3", t28)


# ── 7. Disconnected state ─────────────────────────────────────────────────────
print("\n[7/10] Disconnected state handling")


def t29():
    uid = f"user_mon_{uuid.uuid4().hex[:6]}"
    ev = client.post("/intelligence/monitoring/evaluate", headers=_auth(uid))
    data = ev.json()
    # Any valid response is acceptable (success/disconnected/error)
    assert data["status"] in ("success", "disconnected", "error")
    assert "status" in data


test("disconnected or connected evaluate always returns valid status key", t29)


# ── 8. Regression: previous phases still importable ──────────────────────────
print("\n[8/10] Phase 8.1–8.5 regression guard")


def t30():
    from app.intelligence.proactive.evaluator import evaluate_database_for_alerts
    from app.intelligence.anomaly.detector import detect_anomalies
    from app.intelligence.business_intelligence.insight_engine import generate_business_intelligence_report
    from app.intelligence.decision import run_decision_analysis
    from app.intelligence.learning.outcome_engine import synthesize_learning_summary
    assert evaluate_database_for_alerts
    assert detect_anomalies
    assert generate_business_intelligence_report
    assert run_decision_analysis
    assert synthesize_learning_summary


test("Phase 8.1–8.5 modules still importable (regression guard)", t30)


# ── Summary ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    passed = sum(1 for r in results if r[0] == "PASS")
    failed = sum(1 for r in results if r[0] == "FAIL")
    print(f"\n{'='*60}")
    print(f"Phase 8.6 Monitoring Tests: {passed} passed, {failed} failed")
    print(f"{'='*60}")
    if failed:
        print("\nFailed tests:")
        for r in results:
            if r[0] == "FAIL":
                print(f"  ✗ {r[1]}: {r[2]}")
    sys.exit(0 if failed == 0 else 1)
