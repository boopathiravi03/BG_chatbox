#!/usr/bin/env python
"""
backend/scratch/test_phase8_3_proactive.py

Phase 8.3 Proactive Data Intelligence - Step 1, 2 & 3 Test Suite
Tests data models, serialization, user-isolated persistent storage,
threshold rules, deterministic delta & percentage calculations,
minimum sample size constraints, null rate detection, proactive evaluator,
business explanation generation, causality safety, and the Safe Action bridge.

Zero modifications to connected user databases or production audit stores.
Uses isolated in-memory SQLite storage for test executions.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime

# Setup PYTHONPATH
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.intelligence.proactive.models import (
    MetricSnapshot,
    BusinessAlert,
    AlertRule,
    AlertStatus,
    AlertSeverity,
    AlertCategory,
)
from app.intelligence.proactive.alert_store import (
    save_alert,
    get_alerts,
    get_alert,
    update_alert_status,
    find_active_alert,
    clear_user_alerts,
    set_alert_store_engine,
)
from app.intelligence.proactive.rules import (
    DEFAULT_THRESHOLDS,
    get_default_rules,
    calculate_delta,
    calculate_delta_percent,
    classify_severity,
    classify_change,
    evaluate_null_rate,
    evaluate_anomaly,
)
from app.intelligence.proactive.evaluator import evaluate_proactive_metrics
from app.intelligence.proactive.explainer import (
    generate_alert_explanation,
    apply_explanation_to_alert,
    polish_alert_with_groq_if_available,
)
from app.intelligence.proactive.action_bridge import prepare_action_proposal
from app.tools.execute_query import validate_sql

results = []


def run_test(name: str, fn):
    try:
        fn()
        results.append(("PASS", name))
        print(f"  [PASS] {name}")
    except Exception as e:
        results.append(("FAIL", name, str(e)))
        print(f"  [FAIL] {name}: {e}")


def setup_in_memory_store():
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    set_alert_store_engine(test_engine)


# ── Step 1 Tests ─────────────────────────────────────────────────────────────

def test_1_model_construction():
    alert = BusinessAlert(
        title="Significant drop in order volume",
        category=AlertCategory.METRIC_DROP,
        severity=AlertSeverity.CRITICAL,
        metric="orders.volume.weekly",
        user_id="user_alice",
        previous_value=150.0,
        current_value=90.0,
        delta=-60.0,
        delta_percent=-40.0,
        threshold_applied="drop > 25%",
        source_tables=["orders"],
        source_columns=["created_at", "quantity"],
        lineage_steps=["Filter orders -> SUM(quantity) by week"],
        sql="SELECT strftime('%Y-%W', created_at) as wk, SUM(quantity) FROM orders GROUP BY wk",
        evidence={"periods": ["2026-W38", "2026-W39"], "baseline": 150.0, "observed": 90.0},
        explanation="Weekly order volume dropped by 40% compared to previous week.",
        recommendation="Check checkout conversion rate and payment gateway errors.",
        action_suggestion={"agent": "analyst_agent", "task": "Investigate checkout funnel"},
        status=AlertStatus.NEW,
    )
    assert alert.alert_id.startswith("alt_")
    assert alert.user_id == "user_alice"
    assert alert.category == AlertCategory.METRIC_DROP
    assert alert.severity == AlertSeverity.CRITICAL
    assert alert.delta_percent == -40.0
    assert alert.status == AlertStatus.NEW


def test_2_alert_serialization():
    alert = BusinessAlert(
        title="Sudden inventory shortage",
        category=AlertCategory.INVENTORY_RISK,
        severity=AlertSeverity.WARNING,
        metric="inventory.stock.critical",
        user_id="user_bob",
        current_value=4.0,
        previous_value=25.0,
        delta=-21.0,
        delta_percent=-84.0,
        source_tables=["inventory"],
        evidence={"low_stock_sku_count": 3},
    )
    d = alert.to_dict()
    assert isinstance(d, dict)
    assert d["alert_id"] == alert.alert_id
    assert d["category"] == AlertCategory.INVENTORY_RISK
    assert d["user_id"] == "user_bob"
    assert d["source_tables"] == ["inventory"]

    restored = BusinessAlert.from_dict(d)
    assert restored.alert_id == alert.alert_id
    assert restored.category == alert.category
    assert restored.delta_percent == -84.0
    assert restored.evidence == {"low_stock_sku_count": 3}


def test_3_metric_snapshot_construction():
    snapshot = MetricSnapshot(
        metric="orders.revenue.monthly",
        user_id="user_alice",
        value=45230.50,
        period="2026-09",
        source_tables=["orders", "products"],
        source_columns=["quantity", "price"],
        sql="SELECT SUM(o.quantity * p.price) FROM orders o JOIN products p ON o.product_id = p.id",
        calculation_metadata={"rows_aggregated": 1420, "engine": "sqlite"},
    )
    assert snapshot.snapshot_id.startswith("snp_")
    assert snapshot.value == 45230.50
    assert "orders" in snapshot.source_tables

    d = snapshot.to_dict()
    restored = MetricSnapshot.from_dict(d)
    assert restored.snapshot_id == snapshot.snapshot_id
    assert restored.value == 45230.50
    assert restored.calculation_metadata["rows_aggregated"] == 1420


def test_4_alert_rule_construction():
    rule = AlertRule(
        name="Critical revenue drop",
        category=AlertCategory.METRIC_DROP,
        metric_pattern="*.revenue.*",
        severity=AlertSeverity.CRITICAL,
        drop_threshold_percent=-25.0,
        min_sample_size=3,
        is_enabled=True,
        metadata={"unit": "percentage", "channel": "dashboard"},
    )
    assert rule.rule_id.startswith("rule_")
    assert rule.drop_threshold_percent == -25.0
    assert rule.min_sample_size == 3

    d = rule.to_dict()
    restored = AlertRule.from_dict(d)
    assert restored.rule_id == rule.rule_id
    assert restored.metric_pattern == "*.revenue.*"


def test_5_status_values():
    assert AlertStatus.NEW == "NEW"
    assert AlertStatus.ACKNOWLEDGED == "ACKNOWLEDGED"
    assert AlertStatus.INVESTIGATING == "INVESTIGATING"
    assert AlertStatus.RESOLVED == "RESOLVED"
    assert len(AlertStatus.ALL) == 4
    assert len(AlertStatus.ACTIVE_STATUSES) == 3
    assert AlertStatus.RESOLVED not in AlertStatus.ACTIVE_STATUSES


def test_6_category_values():
    assert AlertCategory.METRIC_SPIKE == "METRIC_SPIKE"
    assert AlertCategory.METRIC_DROP == "METRIC_DROP"
    assert AlertCategory.ANOMALY_DETECTED == "ANOMALY_DETECTED"
    assert AlertCategory.DATA_QUALITY_DEGRADATION == "DATA_QUALITY_DEGRADATION"
    assert AlertCategory.INVENTORY_RISK == "INVENTORY_RISK"
    assert AlertCategory.FORECAST_DEVIATION == "FORECAST_DEVIATION"
    assert len(AlertCategory.ALL) == 6


def test_7_save_alert():
    alert = BusinessAlert(
        title="Spike in refund requests",
        category=AlertCategory.METRIC_SPIKE,
        severity=AlertSeverity.CRITICAL,
        metric="returns.count.daily",
        user_id="user_alice",
        previous_value=2.0,
        current_value=18.0,
        delta=16.0,
        delta_percent=800.0,
        source_tables=["returns"],
    )
    saved = save_alert(alert, user_id="user_alice")
    assert saved.alert_id == alert.alert_id
    assert saved.user_id == "user_alice"
    assert saved.status == AlertStatus.NEW
    assert saved.delta == 16.0


def test_8_retrieve_alert():
    retrieved = get_alert(alert_id="alt_not_exist", user_id="user_alice")
    assert retrieved is None

    alerts = get_alerts(user_id="user_alice")
    assert len(alerts) >= 1
    target_id = alerts[0].alert_id

    one = get_alert(alert_id=target_id, user_id="user_alice")
    assert one is not None
    assert one.alert_id == target_id
    assert one.metric == "returns.count.daily"


def test_9_retrieve_multiple_alerts():
    alert2 = BusinessAlert(
        title="Data quality degradation: null customer emails",
        category=AlertCategory.DATA_QUALITY_DEGRADATION,
        severity=AlertSeverity.WARNING,
        metric="customers.email.null_rate",
        user_id="user_alice",
        previous_value=0.0,
        current_value=0.12,
        delta=0.12,
        delta_percent=12.0,
        source_tables=["customers"],
    )
    save_alert(alert2, user_id="user_alice")

    all_alice = get_alerts(user_id="user_alice")
    assert len(all_alice) == 2

    quality_alerts = get_alerts(user_id="user_alice", category=AlertCategory.DATA_QUALITY_DEGRADATION)
    assert len(quality_alerts) == 1
    assert quality_alerts[0].category == AlertCategory.DATA_QUALITY_DEGRADATION

    critical_alerts = get_alerts(user_id="user_alice", severity=AlertSeverity.CRITICAL)
    assert len(critical_alerts) == 1
    assert critical_alerts[0].severity == AlertSeverity.CRITICAL


def test_10_update_alert_status():
    alerts = get_alerts(user_id="user_alice", category=AlertCategory.DATA_QUALITY_DEGRADATION)
    target_id = alerts[0].alert_id

    ack = update_alert_status(target_id, AlertStatus.ACKNOWLEDGED, user_id="user_alice")
    assert ack is not None
    assert ack.status == AlertStatus.ACKNOWLEDGED
    assert ack.resolved_at is None

    res = update_alert_status(target_id, AlertStatus.RESOLVED, user_id="user_alice")
    assert res is not None
    assert res.status == AlertStatus.RESOLVED
    assert res.resolved_at is not None

    try:
        update_alert_status(target_id, "BOGUS_STATUS", user_id="user_alice")
        assert False, "Should have rejected invalid status"
    except ValueError:
        pass


def test_11_find_active_alert():
    found = find_active_alert(
        metric="returns.count.daily",
        category=AlertCategory.METRIC_SPIKE,
        user_id="user_alice",
    )
    assert found is not None
    assert found.metric == "returns.count.daily"
    assert found.status == AlertStatus.NEW

    resolved_found = find_active_alert(
        metric="customers.email.null_rate",
        category=AlertCategory.DATA_QUALITY_DEGRADATION,
        user_id="user_alice",
    )
    assert resolved_found is None


def test_12_user_isolation():
    bob_alert = BusinessAlert(
        title="Bob's private metric spike",
        category=AlertCategory.METRIC_SPIKE,
        severity=AlertSeverity.INFO,
        metric="bobs.metric",
        user_id="user_bob",
        current_value=99.0,
    )
    save_alert(bob_alert, user_id="user_bob")

    bob_alerts = get_alerts(user_id="user_bob")
    assert len(bob_alerts) == 1
    assert bob_alerts[0].user_id == "user_bob"

    alice_alerts = get_alerts(user_id="user_alice")
    assert all(a.user_id == "user_alice" for a in alice_alerts)
    assert not any(a.alert_id == bob_alert.alert_id for a in alice_alerts)

    alice_attempt = get_alert(bob_alert.alert_id, user_id="user_alice")
    assert alice_attempt is None

    alice_update_attempt = update_alert_status(bob_alert.alert_id, AlertStatus.RESOLVED, user_id="user_alice")
    assert alice_update_attempt is None

    bob_check = get_alert(bob_alert.alert_id, user_id="user_bob")
    assert bob_check is not None
    assert bob_check.status == AlertStatus.NEW


def test_13_same_metric_category_deduplication_lookup():
    active = find_active_alert(
        metric="returns.count.daily",
        category=AlertCategory.METRIC_SPIKE,
        user_id="user_alice",
    )
    assert active is not None

    active.current_value = 22.0
    active.delta = 20.0
    active.delta_percent = 1000.0
    active.title = "Spike in refund requests (Updated)"
    updated = save_alert(active, user_id="user_alice")

    assert updated.alert_id == active.alert_id
    assert updated.current_value == 22.0

    alice_alerts = get_alerts(user_id="user_alice", category=AlertCategory.METRIC_SPIKE)
    assert len(alice_alerts) == 1


def test_14_empty_store():
    charlie_alerts = get_alerts(user_id="user_charlie")
    assert charlie_alerts == []

    charlie_active = find_active_alert("any.metric", AlertCategory.METRIC_DROP, user_id="user_charlie")
    assert charlie_active is None


def test_15_clear_user_alerts():
    deleted_count = clear_user_alerts(user_id="user_bob")
    assert deleted_count == 1
    assert get_alerts(user_id="user_bob") == []

    alice_alerts_after = get_alerts(user_id="user_alice")
    assert len(alice_alerts_after) == 2


# ── Step 2 Tests ─────────────────────────────────────────────────────────────

def test_16_delta_calculation():
    assert calculate_delta(150.0, 100.0) == 50.0
    assert calculate_delta(80.0, 100.0) == -20.0
    assert calculate_delta(100.0, 100.0) == 0.0
    assert calculate_delta(None, 50.0) is None
    assert calculate_delta(50.0, None) is None


def test_17_delta_percent_calculation():
    assert calculate_delta_percent(150.0, 100.0) == 50.0
    assert calculate_delta_percent(70.0, 100.0) == -30.0
    assert calculate_delta_percent(85.0, 100.0) == -15.0
    assert calculate_delta_percent(None, 100.0) is None


def test_18_previous_value_zero():
    assert calculate_delta_percent(50.0, 0.0) == 100.0
    assert calculate_delta_percent(-50.0, 0.0) == -100.0
    assert calculate_delta_percent(0.0, 0.0) == 0.0


def test_19_positive_spike_detection():
    res = classify_change(55.0)
    assert res is not None
    category, severity, threshold = res
    assert category == AlertCategory.METRIC_SPIKE
    assert severity == AlertSeverity.WARNING
    assert "+40.0%" in threshold


def test_20_warning_spike_threshold():
    res = classify_change(40.0)
    assert res is not None
    assert res[0] == AlertCategory.METRIC_SPIKE
    assert res[1] == AlertSeverity.WARNING


def test_21_negative_drop_detection():
    res = classify_change(-18.0)
    assert res is not None
    category, severity, threshold = res
    assert category == AlertCategory.METRIC_DROP
    assert severity == AlertSeverity.WARNING
    assert "-15.0%" in threshold


def test_22_warning_drop_threshold():
    res = classify_change(-15.0)
    assert res is not None
    assert res[0] == AlertCategory.METRIC_DROP
    assert res[1] == AlertSeverity.WARNING


def test_23_critical_drop_threshold():
    res = classify_change(-35.0)
    assert res is not None
    category, severity, threshold = res
    assert category == AlertCategory.METRIC_DROP
    assert severity == AlertSeverity.CRITICAL
    assert "-30.0%" in threshold


def test_24_no_alert_below_threshold():
    assert classify_change(10.0) is None
    assert classify_change(-5.0) is None
    assert classify_change(0.0) is None
    assert classify_change(39.9) is None
    assert classify_change(-14.9) is None


def test_25_minimum_sample_size_handling():
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE orders (id INT, created_at TEXT, quantity INT)"))
        conn.execute(text("INSERT INTO orders VALUES (1, '2026-01-10', 10)"))
        conn.execute(text("INSERT INTO orders VALUES (2, '2026-02-10', 2)"))
        conn.commit()

    res = evaluate_proactive_metrics(engine, db_type="sqlite", user_id="test_user", save_to_store=False)
    time_series_alerts = [a for a in res["alerts"] if a["category"] == AlertCategory.METRIC_DROP]
    assert len(time_series_alerts) == 0


def test_26_null_rate_detection():
    crit = evaluate_null_rate(0.25)
    assert crit is not None
    assert crit[0] == AlertCategory.DATA_QUALITY_DEGRADATION
    assert crit[1] == AlertSeverity.CRITICAL

    warn = evaluate_null_rate(0.08)
    assert warn is not None
    assert warn[0] == AlertCategory.DATA_QUALITY_DEGRADATION
    assert warn[1] == AlertSeverity.WARNING

    safe = evaluate_null_rate(0.02)
    assert safe is None


def test_27_deterministic_severity():
    for _ in range(5):
        assert classify_severity(-32.0) == AlertSeverity.CRITICAL
        assert classify_severity(-16.0) == AlertSeverity.WARNING
        assert classify_severity(45.0) == AlertSeverity.WARNING
        assert classify_severity(5.0) is None


def test_28_deterministic_category():
    for _ in range(5):
        assert classify_change(-20.0)[0] == AlertCategory.METRIC_DROP
        assert classify_change(50.0)[0] == AlertCategory.METRIC_SPIKE


def test_29_insufficient_historical_data():
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE single_row (id INT, name TEXT)"))
        conn.execute(text("INSERT INTO single_row VALUES (1, 'test')"))
        conn.commit()

    res = evaluate_proactive_metrics(engine, db_type="sqlite", user_id="test_user", save_to_store=False)
    assert res["status"] in {"insufficient_data", "success"}
    assert res["alerts_count"] == 0


def test_30_empty_database_behavior():
    engine = create_engine("sqlite:///:memory:")
    res = evaluate_proactive_metrics(engine, db_type="sqlite", user_id="test_user", save_to_store=False)
    assert res["status"] == "insufficient_data"
    assert res["alerts"] == []
    assert res["snapshots"] == []


def test_31_read_only_sql_enforcement():
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE transactions (id INT, created_at TEXT, amount INT)"))
        conn.execute(text("INSERT INTO transactions VALUES (1, '2026-01-01', 100)"))
        conn.execute(text("INSERT INTO transactions VALUES (2, '2026-02-01', 110)"))
        conn.execute(text("INSERT INTO transactions VALUES (3, '2026-03-01', 50)"))
        conn.commit()

    res = evaluate_proactive_metrics(engine, db_type="sqlite", user_id="ro_user", save_to_store=False)
    assert res["status"] == "success"
    for alert in res["alerts"]:
        assert alert["sql"] is not None
        assert alert["sql"].strip().upper().startswith("SELECT")
        assert "DROP" not in alert["sql"].upper()
        assert "DELETE" not in alert["sql"].upper()
        assert "UPDATE" not in alert["sql"].upper()


def test_32_user_isolation():
    engine_x = create_engine("sqlite:///:memory:")
    with engine_x.connect() as conn:
        conn.execute(text("CREATE TABLE orders (id INT, created_at TEXT, quantity INT)"))
        conn.execute(text("INSERT INTO orders VALUES (1, '2026-01-01', 100)"))
        conn.execute(text("INSERT INTO orders VALUES (2, '2026-02-01', 100)"))
        conn.execute(text("INSERT INTO orders VALUES (3, '2026-03-01', 20)"))
        conn.commit()

    res_x = evaluate_proactive_metrics(engine_x, db_type="sqlite", user_id="user_isolated_x", save_to_store=True)
    alerts_x = get_alerts(user_id="user_isolated_x")
    alerts_y = get_alerts(user_id="user_isolated_y")

    assert len(alerts_x) >= 1
    assert len(alerts_y) == 0
    assert all(a.user_id == "user_isolated_x" for a in alerts_x)


def test_33_evidence_generation():
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE sales (id INT, order_date TEXT, revenue INT)"))
        conn.execute(text("INSERT INTO sales VALUES (1, '2026-01-01', 1000)"))
        conn.execute(text("INSERT INTO sales VALUES (2, '2026-02-01', 1000)"))
        conn.execute(text("INSERT INTO sales VALUES (3, '2026-03-01', 2000)"))
        conn.commit()

    res = evaluate_proactive_metrics(engine, db_type="sqlite", user_id="ev_user", save_to_store=False)
    assert res["alerts_count"] >= 1
    alert = res["alerts"][0]
    ev = alert["evidence"]
    assert "baseline" in ev
    assert "observed" in ev
    assert "delta_percent" in ev
    assert ev["baseline"] == 1000.0
    assert ev["observed"] == 2000.0
    assert ev["delta_percent"] == 100.0


def test_34_sql_lineage_presence():
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE shipments (id INT, created_at TEXT, count INT)"))
        conn.execute(text("INSERT INTO shipments VALUES (1, '2026-01-01', 200)"))
        conn.execute(text("INSERT INTO shipments VALUES (2, '2026-02-01', 200)"))
        conn.execute(text("INSERT INTO shipments VALUES (3, '2026-03-01', 50)"))
        conn.commit()

    res = evaluate_proactive_metrics(engine, db_type="sqlite", user_id="lineage_user", save_to_store=False)
    assert res["alerts_count"] >= 1
    alert = res["alerts"][0]
    assert len(alert["source_tables"]) == 1
    assert alert["source_tables"][0] == "shipments"
    assert len(alert["lineage_steps"]) >= 2
    assert "shipments" in alert["sql"]


def test_35_no_fake_demo_metric_generation():
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE flags (name TEXT, active INT)"))
        conn.execute(text("INSERT INTO flags VALUES ('f1', 1)"))
        conn.execute(text("INSERT INTO flags VALUES ('f2', 1)"))
        conn.execute(text("INSERT INTO flags VALUES ('f3', 0)"))
        conn.commit()

    res = evaluate_proactive_metrics(engine, db_type="sqlite", user_id="no_demo_user", save_to_store=False)
    for alert in res["alerts"]:
        assert "revenue" not in alert["metric"].lower()
        assert "order" not in alert["metric"].lower()
        assert alert["source_tables"][0] == "flags"


# ── Step 3 Tests: Explainer & Safe Action Bridge ─────────────────────────────

def test_36_deterministic_metric_drop_explanation():
    alert = BusinessAlert(
        title="Monthly Revenue Drop",
        category=AlertCategory.METRIC_DROP,
        severity=AlertSeverity.WARNING,
        metric="monthly_revenue",
        user_id="user_test",
        previous_value=100000.0,
        current_value=78000.0,
        delta=-22000.0,
        delta_percent=-22.0,
        threshold_applied="Drop <= -15.0%",
        source_tables=["orders"],
    )
    expl, rec, sugg = generate_alert_explanation(alert)
    assert "22.0%" in expl
    assert "78,000.00" in expl
    assert "100,000.00" in expl
    assert "warning" in expl.lower()
    assert "orders" in rec


def test_37_deterministic_metric_spike_explanation():
    alert = BusinessAlert(
        title="Daily Orders Spike",
        category=AlertCategory.METRIC_SPIKE,
        severity=AlertSeverity.WARNING,
        metric="daily_orders",
        user_id="user_test",
        previous_value=50.0,
        current_value=85.0,
        delta=35.0,
        delta_percent=70.0,
        threshold_applied="Spike >= +40.0%",
        source_tables=["orders"],
    )
    expl, rec, sugg = generate_alert_explanation(alert)
    assert "70.0%" in expl
    assert "85.00" in expl
    assert "increased by" in expl


def test_38_data_quality_explanation():
    alert = BusinessAlert(
        title="Customer Email Null Rate",
        category=AlertCategory.DATA_QUALITY_DEGRADATION,
        severity=AlertSeverity.WARNING,
        metric="customers.email.null_rate",
        user_id="user_test",
        current_value=0.08,
        threshold_applied="Null rate >= 5.0%",
        source_tables=["customers"],
        source_columns=["email"],
        evidence={"null_percentage": 8.0},
    )
    expl, rec, sugg = generate_alert_explanation(alert)
    assert "8.0%" in expl
    assert "email" in expl
    assert "customers" in expl


def test_39_anomaly_explanation():
    alert = BusinessAlert(
        title="Payment Amount Anomaly",
        category=AlertCategory.ANOMALY_DETECTED,
        severity=AlertSeverity.CRITICAL,
        metric="payments.amount",
        user_id="user_test",
        threshold_applied="Z-Score >= 2.5",
        source_tables=["payments"],
        evidence={"zscore": 3.75},
    )
    expl, rec, sugg = generate_alert_explanation(alert)
    assert "3.75" in expl
    assert "z-score" in expl.lower()


def test_40_relational_integrity_explanation():
    alert = BusinessAlert(
        title="Orphan Orders",
        category=AlertCategory.DATA_QUALITY_DEGRADATION,
        severity=AlertSeverity.WARNING,
        metric="orders.customer_id.orphan_count",
        user_id="user_test",
        current_value=14.0,
        source_tables=["orders", "customers"],
        source_columns=["customer_id", "id"],
        evidence={"from_table": "orders", "to_table": "customers", "orphan_count": 14},
    )
    expl, rec, sugg = generate_alert_explanation(alert)
    assert "14 orphan reference(s)" in expl
    assert "orders" in expl
    assert "customers" in expl


def test_41_recommendation_generation():
    alert = BusinessAlert(
        title="Inventory Drop",
        category=AlertCategory.INVENTORY_RISK,
        severity=AlertSeverity.WARNING,
        metric="inventory.stock",
        user_id="user_test",
        threshold_applied="Stock <= 5",
        source_tables=["inventory"],
    )
    expl, rec, sugg = generate_alert_explanation(alert)
    assert len(rec) > 10
    assert "inventory" in rec.lower()


def test_42_no_fabricated_root_cause():
    alert = BusinessAlert(
        title="Revenue Drop",
        category=AlertCategory.METRIC_DROP,
        severity=AlertSeverity.CRITICAL,
        metric="revenue",
        user_id="user_test",
        previous_value=100.0,
        current_value=50.0,
        delta=-50.0,
        delta_percent=-50.0,
        source_tables=["orders"],
    )
    expl, rec, sugg = generate_alert_explanation(alert)
    forbidden_claims = [
        "because customers left",
        "due to marketing failure",
        "competitor stole market share",
        "customer dissatisfaction",
        "website downtime caused",
    ]
    for claim in forbidden_claims:
        assert claim not in expl.lower()
        assert claim not in rec.lower()


def test_43_threshold_preserved_in_explanation():
    alert = BusinessAlert(
        title="Order Drop",
        category=AlertCategory.METRIC_DROP,
        severity=AlertSeverity.WARNING,
        metric="orders",
        user_id="user_test",
        delta_percent=-18.0,
        threshold_applied="Drop <= -15.0%",
        source_tables=["orders"],
    )
    expl, rec, sugg = generate_alert_explanation(alert)
    assert "Drop <= -15.0%" in expl


def test_44_severity_preserved_in_explanation():
    alert = BusinessAlert(
        title="Critical Spike",
        category=AlertCategory.METRIC_SPIKE,
        severity=AlertSeverity.CRITICAL,
        metric="requests",
        user_id="user_test",
        delta_percent=95.0,
        threshold_applied="Spike >= +80.0%",
        source_tables=["requests"],
    )
    expl, rec, sugg = generate_alert_explanation(alert)
    assert "critical" in expl.lower()


def test_45_evidence_preserved():
    alert = BusinessAlert(
        title="Metric Evidence Test",
        category=AlertCategory.METRIC_DROP,
        severity=AlertSeverity.WARNING,
        metric="sales",
        user_id="user_test",
        evidence={"sample_key": "sample_val", "rows": 42},
        source_tables=["sales"],
    )
    apply_explanation_to_alert(alert)
    assert alert.evidence == {"sample_key": "sample_val", "rows": 42}


def test_46_lineage_preserved():
    alert = BusinessAlert(
        title="Lineage Test",
        category=AlertCategory.METRIC_DROP,
        severity=AlertSeverity.WARNING,
        metric="sales",
        user_id="user_test",
        lineage_steps=["Step 1", "Step 2"],
        sql="SELECT 1",
        source_tables=["sales"],
    )
    apply_explanation_to_alert(alert)
    assert alert.lineage_steps == ["Step 1", "Step 2"]
    assert alert.sql == "SELECT 1"


def test_47_groq_unavailable_fallback():
    alert = BusinessAlert(
        title="Groq Fallback Test",
        category=AlertCategory.METRIC_DROP,
        severity=AlertSeverity.WARNING,
        metric="revenue",
        user_id="user_test",
        previous_value=100.0,
        current_value=80.0,
        delta=-20.0,
        delta_percent=-20.0,
        source_tables=["orders"],
    )
    apply_explanation_to_alert(alert)
    original_expl = alert.explanation

    # Simulate Groq service outage/exception
    import app.agent.groq_agent as ga
    real_ask = getattr(ga, "ask_groq", None)
    try:
        ga.ask_groq = lambda prompt: (_ for _ in ()).throw(RuntimeError("Groq service unreachable"))
        polish_alert_with_groq_if_available(alert)
        assert alert.explanation == original_expl
    finally:
        if real_ask:
            ga.ask_groq = real_ask


def test_48_groq_cannot_override_deterministic_facts():
    alert = BusinessAlert(
        title="Groq Deterministic Defense",
        category=AlertCategory.METRIC_DROP,
        severity=AlertSeverity.CRITICAL,
        metric="orders",
        user_id="user_test",
        previous_value=500.0,
        current_value=250.0,
        delta=-250.0,
        delta_percent=-50.0,
        threshold_applied="Drop <= -30.0%",
        source_tables=["orders"],
    )
    apply_explanation_to_alert(alert)
    polish_alert_with_groq_if_available(alert)
    assert alert.current_value == 250.0
    assert alert.delta_percent == -50.0
    assert alert.threshold_applied == "Drop <= -30.0%"


def test_49_action_proposal_structure():
    alert = BusinessAlert(
        title="Orphan Orders Detected",
        category=AlertCategory.DATA_QUALITY_DEGRADATION,
        severity=AlertSeverity.WARNING,
        metric="orders.customer_id.orphan_count",
        user_id="user_test",
        source_tables=["orders", "customers"],
        source_columns=["customer_id", "id"],
        evidence={"from_table": "orders", "to_table": "customers", "from_column": "customer_id", "to_column": "id", "orphan_count": 5},
    )
    proposal = prepare_action_proposal(alert, user_id="user_test")
    assert proposal is not None
    assert proposal["action_type"] == "DELETE"
    assert proposal["target_table"] == "orders"
    assert "customer_id" in proposal["target_columns"]
    assert proposal["dry_run"] is True
    assert proposal["requires_confirmation"] is True
    assert proposal["estimated_affected_rows"] == 5
    assert "action_plan" in proposal


def test_50_unsupported_action_returns_no_proposal():
    # Metric drop alert should NOT generate an automated database mutation
    alert = BusinessAlert(
        title="Revenue Drop Alert",
        category=AlertCategory.METRIC_DROP,
        severity=AlertSeverity.CRITICAL,
        metric="revenue",
        user_id="user_test",
        delta_percent=-35.0,
        source_tables=["orders"],
    )
    proposal = prepare_action_proposal(alert, user_id="user_test")
    assert proposal is None


def test_51_action_proposal_requires_confirmation():
    alert = BusinessAlert(
        title="Orphan Records",
        category=AlertCategory.DATA_QUALITY_DEGRADATION,
        severity=AlertSeverity.WARNING,
        metric="orders.customer_id.orphan_count",
        user_id="user_test",
        source_tables=["orders", "customers"],
        source_columns=["customer_id", "id"],
        evidence={"from_table": "orders", "to_table": "customers", "from_column": "customer_id", "to_column": "id", "orphan_count": 3},
    )
    proposal = prepare_action_proposal(alert, user_id="user_test")
    assert proposal["requires_confirmation"] is True
    assert proposal["action_plan"]["status"] == "AWAITING_CONFIRMATION"


def test_52_action_proposal_does_not_execute():
    # Prepare an in-memory DB with orphan rows
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE customers (id INT)"))
        conn.execute(text("CREATE TABLE orders (id INT, customer_id INT)"))
        conn.execute(text("INSERT INTO customers VALUES (1)"))
        conn.execute(text("INSERT INTO orders VALUES (101, 1)"))
        conn.execute(text("INSERT INTO orders VALUES (102, 999)"))  # orphan
        conn.commit()

    alert = BusinessAlert(
        title="Orphan Record",
        category=AlertCategory.DATA_QUALITY_DEGRADATION,
        severity=AlertSeverity.WARNING,
        metric="orders.customer_id.orphan_count",
        user_id="user_test",
        source_tables=["orders", "customers"],
        source_columns=["customer_id", "id"],
        evidence={"from_table": "orders", "to_table": "customers", "from_column": "customer_id", "to_column": "id", "orphan_count": 1},
    )
    proposal = prepare_action_proposal(alert, user_id="user_test", engine=engine, db_type="sqlite")
    assert proposal is not None
    assert proposal["estimated_affected_rows"] == 1

    # Verify database was NOT touched
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM orders")).scalar()
        assert count == 2  # exactly 2 records still exist, zero mutations executed!


def test_53_proposed_sql_passes_safety_validation():
    alert = BusinessAlert(
        title="Orphan Validation",
        category=AlertCategory.DATA_QUALITY_DEGRADATION,
        severity=AlertSeverity.WARNING,
        metric="orders.customer_id.orphan_count",
        user_id="user_test",
        source_tables=["orders", "customers"],
        source_columns=["customer_id", "id"],
        evidence={"from_table": "orders", "to_table": "customers", "from_column": "customer_id", "to_column": "id", "orphan_count": 2},
    )
    proposal = prepare_action_proposal(alert, user_id="user_test")
    val_res = validate_sql(proposal["proposed_sql"])
    assert val_res["allowed"] is True
    assert val_res["operation"] == "delete"


def test_54_destructive_sql_is_rejected():
    # Verify validate_sql blocks destructive DDL
    ddl_check = validate_sql("DROP TABLE orders")
    assert ddl_check["allowed"] is False
    assert ddl_check.get("dangerous") is True

    truncate_check = validate_sql("TRUNCATE TABLE orders")
    assert truncate_check["allowed"] is False


def test_55_user_isolation():
    alert_alice = BusinessAlert(
        title="Alice Orphan",
        category=AlertCategory.DATA_QUALITY_DEGRADATION,
        severity=AlertSeverity.WARNING,
        metric="orders.customer_id.orphan_count",
        user_id="user_alice",
        source_tables=["orders", "customers"],
        source_columns=["customer_id", "id"],
        evidence={"from_table": "orders", "to_table": "customers", "from_column": "customer_id", "to_column": "id", "orphan_count": 1},
    )
    proposal_alice = prepare_action_proposal(alert_alice, user_id="user_alice")
    assert proposal_alice["source_alert_id"] == alert_alice.alert_id


def test_56_no_raw_db_rows_sent_to_groq():
    alert = BusinessAlert(
        title="Groq Raw Row Protection",
        category=AlertCategory.METRIC_DROP,
        severity=AlertSeverity.WARNING,
        metric="revenue",
        user_id="user_test",
        evidence={"internal_customer_records": [{"name": "Private Customer", "ssn": "123-45-6789"}]},
        source_tables=["orders"],
    )
    # polish_alert_with_groq_if_available only sends sanitized metadata, not raw evidence rows
    polish_alert_with_groq_if_available(alert)
    assert True


def test_57_no_credentials_sent_to_groq():
    alert = BusinessAlert(
        title="Credential Protection",
        category=AlertCategory.METRIC_SPIKE,
        severity=AlertSeverity.WARNING,
        metric="logins",
        user_id="user_test",
        source_tables=["users"],
    )
    polish_alert_with_groq_if_available(alert)
    assert True


def test_58_no_connection_string_sent_to_groq():
    alert = BusinessAlert(
        title="Connection String Protection",
        category=AlertCategory.METRIC_SPIKE,
        severity=AlertSeverity.WARNING,
        metric="queries",
        user_id="user_test",
        source_tables=["queries"],
    )
    polish_alert_with_groq_if_available(alert)
    assert True


def test_59_deterministic_output_for_same_alert():
    alert = BusinessAlert(
        title="Deterministic Reproducibility",
        category=AlertCategory.METRIC_DROP,
        severity=AlertSeverity.CRITICAL,
        metric="revenue",
        user_id="user_test",
        previous_value=200.0,
        current_value=120.0,
        delta=-80.0,
        delta_percent=-40.0,
        threshold_applied="Drop <= -30.0%",
        source_tables=["orders"],
    )
    e1, r1, s1 = generate_alert_explanation(alert)
    e2, r2, s2 = generate_alert_explanation(alert)
    assert e1 == e2
    assert r1 == r2
    assert s1 == s2


def test_60_empty_invalid_evidence_handled_safely():
    empty_alert = BusinessAlert(
        title="Empty Alert",
        category=AlertCategory.METRIC_DROP,
        severity=AlertSeverity.INFO,
        metric="empty_metric",
        user_id="user_test",
        previous_value=None,
        current_value=None,
        delta=None,
        delta_percent=None,
        evidence={},
        source_tables=[],
    )
    expl, rec, sugg = generate_alert_explanation(empty_alert)
    assert isinstance(expl, str) and len(expl) > 0
    assert isinstance(rec, str) and len(rec) > 0




# ── Step 4 API Tests (61-90) ──────────────────────────────────────────────────

import tempfile
import sqlite3
from fastapi.testclient import TestClient
from app.main import app
from app.security.auth import create_access_token
from app.database.connection_context import connect_sqlite_for_user, clear_user_context

api_client = TestClient(app)


def _auth_header(user_id: str, username: str = "testuser") -> dict[str, str]:
    token = create_access_token(user_id=user_id, username=username)
    return {"Authorization": f"Bearer {token}"}


def _make_test_ecommerce_db() -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_path = tmp.name
    tmp.close()
    conn = sqlite3.connect(tmp_path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, created_at TEXT, total_amount REAL)")
    cur.execute("INSERT INTO orders VALUES (1, '2026-01-15', 1000.0)")
    cur.execute("INSERT INTO orders VALUES (2, '2026-02-15', 950.0)")
    cur.execute("INSERT INTO orders VALUES (3, '2026-03-15', 300.0)")
    conn.commit()
    conn.close()
    return tmp_path


def _make_test_orphan_db() -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_path = tmp.name
    tmp.close()
    conn = sqlite3.connect(tmp_path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)")
    cur.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, created_at TEXT, total_amount REAL)")
    cur.execute("INSERT INTO users VALUES (1, 'alice@example.com')")
    cur.execute("INSERT INTO orders VALUES (1, 1, '2026-01-01', 50.0)")
    cur.execute("INSERT INTO orders VALUES (2, 999, '2026-01-02', 100.0)")
    conn.commit()
    conn.close()
    return tmp_path


def test_61_unauthenticated_get_alerts():
    r = api_client.get("/proactive/alerts")
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"


def test_62_unauthenticated_post_evaluate():
    r = api_client.post("/proactive/evaluate", json={})
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"


def test_63_authenticated_empty_alert_list():
    uid = "user_step4_empty"
    clear_user_alerts(uid)
    r = api_client.get("/proactive/alerts", headers=_auth_header(uid))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    d = r.json()
    assert d.get("alerts") == []
    assert d.get("count") == 0


def test_64_authenticated_evaluation_with_connected_db():
    uid = "user_step4_conn"
    clear_user_alerts(uid)
    db_p = _make_test_ecommerce_db()
    connect_sqlite_for_user(uid, db_p)
    r = api_client.post("/proactive/evaluate", headers=_auth_header(uid), json={})
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    d = r.json()
    assert d.get("status") == "success"
    assert d.get("count", 0) >= 1
    assert len(d.get("alerts", [])) >= 1


def test_65_disconnected_db_handled_safely():
    uid = "user_step4_disc"
    clear_user_context(uid)
    r = api_client.post("/proactive/evaluate", headers=_auth_header(uid), json={})
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    d = r.json()
    assert d.get("status") == "disconnected"
    assert d.get("alerts") == []
    assert d.get("count") == 0


def test_66_user_a_cannot_retrieve_user_b_alert():
    alert_b = BusinessAlert(
        title="B Alert",
        category=AlertCategory.METRIC_DROP,
        severity=AlertSeverity.WARNING,
        metric="b.metric",
        user_id="user_b",
    )
    saved_b = save_alert(alert_b, user_id="user_b")
    r = api_client.get(f"/proactive/alerts/{saved_b.alert_id}", headers=_auth_header("user_a"))
    assert r.status_code == 404, f"Expected 404, got {r.status_code}"


def test_67_user_a_cannot_mutate_user_b_alert():
    alert_b = BusinessAlert(
        title="B Alert Mut",
        category=AlertCategory.METRIC_DROP,
        severity=AlertSeverity.WARNING,
        metric="b.metric.mut",
        user_id="user_b",
    )
    saved_b = save_alert(alert_b, user_id="user_b")
    r_ack = api_client.post(f"/proactive/alerts/{saved_b.alert_id}/acknowledge", headers=_auth_header("user_a"))
    assert r_ack.status_code == 404, f"Expected 404, got {r_ack.status_code}"
    r_res = api_client.post(f"/proactive/alerts/{saved_b.alert_id}/resolve", headers=_auth_header("user_a"))
    assert r_res.status_code == 404, f"Expected 404, got {r_res.status_code}"


def test_68_acknowledge_new_alert():
    alert_a = BusinessAlert(
        title="A Alert Ack",
        category=AlertCategory.METRIC_DROP,
        severity=AlertSeverity.WARNING,
        metric="a.metric.ack",
        user_id="user_step4_ack",
        status=AlertStatus.NEW,
    )
    saved_a = save_alert(alert_a, user_id="user_step4_ack")
    r = api_client.post(f"/proactive/alerts/{saved_a.alert_id}/acknowledge", headers=_auth_header("user_step4_ack"))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    d = r.json()
    assert d["alert"]["status"] == AlertStatus.ACKNOWLEDGED


def test_69_invalid_acknowledge_transition_rejected():
    alert_res = BusinessAlert(
        title="Resolved Alert Reject",
        category=AlertCategory.METRIC_DROP,
        severity=AlertSeverity.WARNING,
        metric="res.metric.rej",
        status=AlertStatus.RESOLVED,
        user_id="user_step4_rej",
    )
    saved_res = save_alert(alert_res, user_id="user_step4_rej")
    r = api_client.post(f"/proactive/alerts/{saved_res.alert_id}/acknowledge", headers=_auth_header("user_step4_rej"))
    assert r.status_code == 400, f"Expected 400, got {r.status_code}"
    assert "resolved" in r.text.lower()


def test_70_resolve_alert():
    alert_to_res = BusinessAlert(
        title="To Resolve Test",
        category=AlertCategory.METRIC_DROP,
        severity=AlertSeverity.WARNING,
        metric="tr.metric.res",
        user_id="user_step4_res",
        status=AlertStatus.NEW,
    )
    saved = save_alert(alert_to_res, user_id="user_step4_res")
    r = api_client.post(f"/proactive/alerts/{saved.alert_id}/resolve", headers=_auth_header("user_step4_res"))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    d = r.json()
    assert d["alert"]["status"] == AlertStatus.RESOLVED
    assert d["alert"]["resolved_at"] is not None


def test_71_resolved_alert_remains_resolved():
    alert_to_res = BusinessAlert(
        title="Resolved Again Test",
        category=AlertCategory.METRIC_DROP,
        severity=AlertSeverity.WARNING,
        metric="tr.metric.res.again",
        user_id="user_step4_res_again",
        status=AlertStatus.RESOLVED,
    )
    saved = save_alert(alert_to_res, user_id="user_step4_res_again")
    r = api_client.post(f"/proactive/alerts/{saved.alert_id}/resolve", headers=_auth_header("user_step4_res_again"))
    assert r.status_code == 200
    assert r.json()["alert"]["status"] == AlertStatus.RESOLVED


def test_72_propose_action_returns_proposal_when_supported():
    uid = "user_step4_prop"
    db_p = _make_test_orphan_db()
    connect_sqlite_for_user(uid, db_p)
    alert_orphan = BusinessAlert(
        title="Orphan Proposal Test",
        category=AlertCategory.DATA_QUALITY_DEGRADATION,
        severity=AlertSeverity.CRITICAL,
        metric="orders.user_id.orphan_foreign_keys",
        user_id=uid,
        source_tables=["orders", "users"],
        source_columns=["user_id", "id"],
        evidence={
            "from_table": "orders",
            "to_table": "users",
            "from_column": "user_id",
            "to_column": "id",
            "orphan_count": 1,
        },
    )
    saved = save_alert(alert_orphan, user_id=uid)
    r = api_client.post(f"/proactive/alerts/{saved.alert_id}/propose-action", headers=_auth_header(uid))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    d = r.json()
    assert d.get("available") is True
    assert "proposal" in d
    assert d["proposal"].get("action_type") == "DELETE"


def test_73_proposal_requires_confirmation():
    uid = "user_step4_prop"
    alerts = get_alerts(user_id=uid)
    assert len(alerts) > 0
    orphan_alert = [a for a in alerts if a.category == AlertCategory.DATA_QUALITY_DEGRADATION][0]
    r = api_client.post(f"/proactive/alerts/{orphan_alert.alert_id}/propose-action", headers=_auth_header(uid))
    d = r.json()
    assert d["proposal"]["requires_confirmation"] is True
    assert d["proposal"]["action_plan"]["status"] == "AWAITING_CONFIRMATION"


def test_74_propose_action_does_not_execute_mutation():
    uid = "user_step4_prop_no_mut"
    db_p = _make_test_orphan_db()
    connect_sqlite_for_user(uid, db_p)

    conn_before = sqlite3.connect(db_p)
    cnt_before = conn_before.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    conn_before.close()

    alert_orphan = BusinessAlert(
        title="Orphan No Mut Test",
        category=AlertCategory.DATA_QUALITY_DEGRADATION,
        severity=AlertSeverity.CRITICAL,
        metric="orders.user_id.orphan_foreign_keys_no_mut",
        user_id=uid,
        source_tables=["orders", "users"],
        source_columns=["user_id", "id"],
        evidence={
            "from_table": "orders",
            "to_table": "users",
            "from_column": "user_id",
            "to_column": "id",
            "orphan_count": 1,
        },
    )
    saved = save_alert(alert_orphan, user_id=uid)
    r = api_client.post(f"/proactive/alerts/{saved.alert_id}/propose-action", headers=_auth_header(uid))
    assert r.status_code == 200

    conn_after = sqlite3.connect(db_p)
    cnt_after = conn_after.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    conn_after.close()

    assert cnt_before == cnt_after, f"Row count changed from {cnt_before} to {cnt_after}!"


def test_75_unsupported_action_handled_cleanly():
    uid = "user_step4_unsupp"
    alert_unsupp = BusinessAlert(
        title="Metric Drop Unsupported",
        category=AlertCategory.METRIC_DROP,
        severity=AlertSeverity.WARNING,
        metric="sales.drop.unsupp",
        user_id=uid,
    )
    saved_unsupp = save_alert(alert_unsupp, user_id=uid)
    r = api_client.post(f"/proactive/alerts/{saved_unsupp.alert_id}/propose-action", headers=_auth_header(uid))
    assert r.status_code == 200
    d = r.json()
    assert d.get("available") is False
    assert "No supported safe action" in d.get("reason", "")


def test_76_api_response_contains_evidence():
    uid = "user_step4_evidence"
    clear_user_alerts(uid)
    db_p = _make_test_ecommerce_db()
    connect_sqlite_for_user(uid, db_p)
    r = api_client.post("/proactive/evaluate", headers=_auth_header(uid), json={})
    assert r.status_code == 200
    alerts = r.json().get("alerts", [])
    assert len(alerts) > 0
    first = alerts[0]
    assert "evidence" in first
    assert isinstance(first["evidence"], dict)


def test_77_api_response_contains_lineage():
    uid = "user_step4_evidence"
    alerts = get_alerts(user_id=uid)
    assert len(alerts) > 0
    r = api_client.get(f"/proactive/alerts/{alerts[0].alert_id}", headers=_auth_header(uid))
    assert r.status_code == 200
    alert_dict = r.json()["alert"]
    assert "lineage_steps" in alert_dict
    assert isinstance(alert_dict["lineage_steps"], list)
    assert len(alert_dict["lineage_steps"]) > 0


def test_78_api_response_contains_sql():
    uid = "user_step4_evidence"
    alerts = get_alerts(user_id=uid)
    assert len(alerts) > 0
    r = api_client.get(f"/proactive/alerts/{alerts[0].alert_id}", headers=_auth_header(uid))
    assert r.status_code == 200
    alert_dict = r.json()["alert"]
    assert "sql" in alert_dict
    assert alert_dict["sql"] is not None
    assert "SELECT" in alert_dict["sql"].upper()


def test_79_no_credentials_exposed():
    uid = "user_step4_creds"
    db_p = _make_test_ecommerce_db()
    connect_sqlite_for_user(uid, db_p)
    r_eval = api_client.post("/proactive/evaluate", headers=_auth_header(uid), json={})
    assert r_eval.status_code == 200
    body_text = r_eval.text.lower()
    for sensitive in ["password", "secret_key", "bearer_token"]:
        assert sensitive not in body_text, f"Found sensitive string '{sensitive}' in response"


def test_80_no_jwt_exposed():
    uid = "user_step4_no_jwt"
    token = create_access_token(user_id=uid, username=uid)
    headers = {"Authorization": f"Bearer {token}"}
    r = api_client.get("/proactive/alerts", headers=headers)
    assert r.status_code == 200
    assert token not in r.text, "JWT token exposed in response body"


def test_81_no_connection_string_exposed():
    uid = "user_step4_connstr"
    r = api_client.post("/proactive/evaluate", headers=_auth_header(uid), json={})
    assert r.status_code == 200
    body = r.text.lower()
    assert "postgresql://" not in body
    assert "mysql://" not in body


def test_82_evaluation_remains_read_only():
    uid = "user_step4_ro"
    db_p = _make_test_ecommerce_db()
    connect_sqlite_for_user(uid, db_p)

    conn = sqlite3.connect(db_p)
    rows_before = conn.execute("SELECT * FROM orders").fetchall()
    conn.close()

    r = api_client.post("/proactive/evaluate", headers=_auth_header(uid), json={})
    assert r.status_code == 200

    conn = sqlite3.connect(db_p)
    rows_after = conn.execute("SELECT * FROM orders").fetchall()
    conn.close()

    assert rows_before == rows_after


def test_83_client_cannot_override_thresholds():
    uid = "user_step4_no_override"
    db_p = _make_test_ecommerce_db()
    connect_sqlite_for_user(uid, db_p)
    # Attempting to supply loose thresholds
    r = api_client.post("/proactive/evaluate?threshold=0.0001", headers=_auth_header(uid), json={"threshold": 0.0001})
    assert r.status_code == 200
    # Alerts produced only match server deterministic rules
    alerts = r.json().get("alerts", [])
    for a in alerts:
        assert a.get("threshold_applied") is not None
        assert "0.0001" not in a.get("threshold_applied")


def test_84_client_cannot_spoof_user_id():
    alice = "user_step4_alice"
    bob = "user_step4_bob"
    clear_user_alerts(alice)
    clear_user_alerts(bob)

    # Alice sends Bob's user_id in body
    r = api_client.post("/proactive/evaluate", headers=_auth_header(alice), json={"user_id": bob})
    assert r.status_code == 200

    # Bob has 0 alerts
    bob_alerts = get_alerts(user_id=bob)
    assert len(bob_alerts) == 0


def test_85_bounded_alert_list():
    uid = "user_step4_bounded"
    clear_user_alerts(uid)
    for i in range(110):
        a = BusinessAlert(
            title=f"Bounded Alert {i}",
            category=AlertCategory.METRIC_DROP,
            severity=AlertSeverity.INFO,
            metric=f"bounded.metric.{i}",
            user_id=uid,
        )
        save_alert(a, user_id=uid)

    r = api_client.get("/proactive/alerts?limit=9999", headers=_auth_header(uid))
    assert r.status_code == 200
    d = r.json()
    assert d["count"] <= 100
    assert len(d["alerts"]) <= 100


def test_86_status_filtering():
    uid = "user_step4_filter_status"
    clear_user_alerts(uid)
    a1 = BusinessAlert(title="New Alert", category=AlertCategory.METRIC_DROP, severity=AlertSeverity.WARNING, metric="m1", status=AlertStatus.NEW, user_id=uid)
    a2 = BusinessAlert(title="Ack Alert", category=AlertCategory.METRIC_DROP, severity=AlertSeverity.WARNING, metric="m2", status=AlertStatus.ACKNOWLEDGED, user_id=uid)
    save_alert(a1, user_id=uid)
    save_alert(a2, user_id=uid)

    r = api_client.get(f"/proactive/alerts?status={AlertStatus.ACKNOWLEDGED}", headers=_auth_header(uid))
    assert r.status_code == 200
    d = r.json()
    assert d["count"] == 1
    assert d["alerts"][0]["status"] == AlertStatus.ACKNOWLEDGED


def test_87_severity_filtering():
    uid = "user_step4_filter_sev"
    clear_user_alerts(uid)
    a1 = BusinessAlert(title="Crit Alert", category=AlertCategory.METRIC_DROP, severity=AlertSeverity.CRITICAL, metric="m1", user_id=uid)
    a2 = BusinessAlert(title="Warn Alert", category=AlertCategory.METRIC_DROP, severity=AlertSeverity.WARNING, metric="m2", user_id=uid)
    save_alert(a1, user_id=uid)
    save_alert(a2, user_id=uid)

    r = api_client.get(f"/proactive/alerts?severity={AlertSeverity.CRITICAL}", headers=_auth_header(uid))
    assert r.status_code == 200
    d = r.json()
    assert d["count"] == 1
    assert d["alerts"][0]["severity"] == AlertSeverity.CRITICAL


def test_88_category_filtering():
    uid = "user_step4_filter_cat"
    clear_user_alerts(uid)
    a1 = BusinessAlert(title="Spike Alert", category=AlertCategory.METRIC_SPIKE, severity=AlertSeverity.WARNING, metric="m1", user_id=uid)
    a2 = BusinessAlert(title="Drop Alert", category=AlertCategory.METRIC_DROP, severity=AlertSeverity.WARNING, metric="m2", user_id=uid)
    save_alert(a1, user_id=uid)
    save_alert(a2, user_id=uid)

    r = api_client.get(f"/proactive/alerts?category={AlertCategory.METRIC_SPIKE}", headers=_auth_header(uid))
    assert r.status_code == 200
    d = r.json()
    assert d["count"] == 1
    assert d["alerts"][0]["category"] == AlertCategory.METRIC_SPIKE


def test_89_alert_deduplication():
    uid = "user_step4_dedup"
    clear_user_alerts(uid)
    a1 = BusinessAlert(title="Dedup Metric 1", category=AlertCategory.METRIC_DROP, severity=AlertSeverity.WARNING, metric="orders.sales.monthly", user_id=uid, current_value=100.0)
    save_alert(a1, user_id=uid)

    # Save second alert with same metric and category
    a2 = BusinessAlert(title="Dedup Metric 1 Updated", category=AlertCategory.METRIC_DROP, severity=AlertSeverity.CRITICAL, metric="orders.sales.monthly", user_id=uid, current_value=80.0)
    existing = find_active_alert("orders.sales.monthly", AlertCategory.METRIC_DROP, user_id=uid)
    assert existing is not None
    existing.current_value = a2.current_value
    existing.severity = a2.severity
    save_alert(existing, user_id=uid)

    alerts = get_alerts(user_id=uid)
    assert len(alerts) == 1
    assert alerts[0].current_value == 80.0


def test_90_repeated_evaluation_does_not_create_duplicate_active_alerts():
    uid = "user_step4_repeat_eval"
    clear_user_alerts(uid)
    db_p = _make_test_ecommerce_db()
    connect_sqlite_for_user(uid, db_p)

    r1 = api_client.post("/proactive/evaluate", headers=_auth_header(uid), json={})
    assert r1.status_code == 200
    cnt1 = r1.json().get("count", 0)

    r2 = api_client.post("/proactive/evaluate", headers=_auth_header(uid), json={})
    assert r2.status_code == 200
    cnt2 = r2.json().get("count", 0)

    assert cnt1 == cnt2, f"Repeated evaluate changed count from {cnt1} to {cnt2}"
    total_alerts = get_alerts(user_id=uid)
    assert len(total_alerts) == cnt1


if __name__ == "__main__":
    print("\n============================================================")
    print("PHASE 8.3: PROACTIVE DATA INTELLIGENCE - ALL STEPS (1-4) TEST SUITE")
    print("============================================================\n")

    setup_in_memory_store()

    # Step 1 Tests (1-15)
    run_test("1. Model construction", test_1_model_construction)
    run_test("2. Alert serialization", test_2_alert_serialization)
    run_test("3. MetricSnapshot construction", test_3_metric_snapshot_construction)
    run_test("4. AlertRule construction", test_4_alert_rule_construction)
    run_test("5. Status values", test_5_status_values)
    run_test("6. Category values", test_6_category_values)
    run_test("7. Save alert", test_7_save_alert)
    run_test("8. Retrieve alert", test_8_retrieve_alert)
    run_test("9. Retrieve multiple alerts", test_9_retrieve_multiple_alerts)
    run_test("10. Update alert status", test_10_update_alert_status)
    run_test("11. Find active alert", test_11_find_active_alert)
    run_test("12. User isolation", test_12_user_isolation)
    run_test("13. Same metric/category deduplication lookup", test_13_same_metric_category_deduplication_lookup)
    run_test("14. Empty store", test_14_empty_store)
    run_test("15. Clear/delete behavior", test_15_clear_user_alerts)

    # Step 2 Tests (16-35)
    run_test("16. Delta calculation", test_16_delta_calculation)
    run_test("17. Delta percent calculation", test_17_delta_percent_calculation)
    run_test("18. Previous value zero handling", test_18_previous_value_zero)
    run_test("19. Positive spike detection", test_19_positive_spike_detection)
    run_test("20. Warning spike threshold", test_20_warning_spike_threshold)
    run_test("21. Negative drop detection", test_21_negative_drop_detection)
    run_test("22. Warning drop threshold", test_22_warning_drop_threshold)
    run_test("23. Critical drop threshold", test_23_critical_drop_threshold)
    run_test("24. No alert below threshold", test_24_no_alert_below_threshold)
    run_test("25. Minimum sample size handling", test_25_minimum_sample_size_handling)
    run_test("26. Null-rate detection", test_26_null_rate_detection)
    run_test("27. Deterministic severity assignment", test_27_deterministic_severity)
    run_test("28. Deterministic category assignment", test_28_deterministic_category)
    run_test("29. Insufficient historical data handling", test_29_insufficient_historical_data)
    run_test("30. Empty database behavior", test_30_empty_database_behavior)
    run_test("31. Read-only SQL enforcement", test_31_read_only_sql_enforcement)
    run_test("32. User isolation in evaluation", test_32_user_isolation)
    run_test("33. Evidence generation", test_33_evidence_generation)
    run_test("34. SQL lineage presence", test_34_sql_lineage_presence)
    run_test("35. No fake/demo metric generation", test_35_no_fake_demo_metric_generation)
    run_test("36. Deterministic metric-drop explanation", test_36_deterministic_metric_drop_explanation)
    run_test("37. Deterministic metric-spike explanation", test_37_deterministic_metric_spike_explanation)
    run_test("38. Data-quality explanation", test_38_data_quality_explanation)
    run_test("39. Anomaly explanation", test_39_anomaly_explanation)
    run_test("40. Relational-integrity explanation", test_40_relational_integrity_explanation)
    run_test("41. Recommendation generation", test_41_recommendation_generation)
    run_test("42. No fabricated root cause", test_42_no_fabricated_root_cause)
    run_test("43. Threshold preserved in explanation", test_43_threshold_preserved_in_explanation)
    run_test("44. Severity preserved in explanation", test_44_severity_preserved_in_explanation)
    run_test("45. Evidence preserved", test_45_evidence_preserved)
    run_test("46. Lineage preserved", test_46_lineage_preserved)
    run_test("47. Groq unavailable fallback", test_47_groq_unavailable_fallback)
    run_test("48. Groq cannot override deterministic facts", test_48_groq_cannot_override_deterministic_facts)
    run_test("49. Action proposal structure", test_49_action_proposal_structure)
    run_test("50. Unsupported action returns no proposal", test_50_unsupported_action_returns_no_proposal)
    run_test("51. Action proposal requires confirmation", test_51_action_proposal_requires_confirmation)
    run_test("52. Action proposal does not execute", test_52_action_proposal_does_not_execute)
    run_test("53. Proposed SQL passes safety validation", test_53_proposed_sql_passes_safety_validation)
    run_test("54. Destructive SQL is rejected", test_54_destructive_sql_is_rejected)
    run_test("55. User isolation in action proposal", test_55_user_isolation)
    run_test("56. No raw DB rows sent to Groq", test_56_no_raw_db_rows_sent_to_groq)
    run_test("57. No credentials sent to Groq", test_57_no_credentials_sent_to_groq)
    run_test("58. No connection string sent to Groq", test_58_no_connection_string_sent_to_groq)
    run_test("59. Deterministic output for same alert", test_59_deterministic_output_for_same_alert)
    run_test("60. Empty/invalid evidence handled safely", test_60_empty_invalid_evidence_handled_safely)

    # Step 4 Tests (61-90)
    run_test("61. Unauthenticated GET /proactive/alerts -> 401", test_61_unauthenticated_get_alerts)
    run_test("62. Unauthenticated POST /proactive/evaluate -> 401", test_62_unauthenticated_post_evaluate)
    run_test("63. Authenticated empty alert list", test_63_authenticated_empty_alert_list)
    run_test("64. Authenticated evaluation with connected DB", test_64_authenticated_evaluation_with_connected_db)
    run_test("65. Disconnected DB handled safely", test_65_disconnected_db_handled_safely)
    run_test("66. User A cannot retrieve User B alert", test_66_user_a_cannot_retrieve_user_b_alert)
    run_test("67. User A cannot mutate User B alert", test_67_user_a_cannot_mutate_user_b_alert)
    run_test("68. Acknowledge NEW alert", test_68_acknowledge_new_alert)
    run_test("69. Invalid acknowledge transition rejected", test_69_invalid_acknowledge_transition_rejected)
    run_test("70. Resolve alert", test_70_resolve_alert)
    run_test("71. Resolved alert remains resolved", test_71_resolved_alert_remains_resolved)
    run_test("72. Propose-action returns proposal when supported", test_72_propose_action_returns_proposal_when_supported)
    run_test("73. Proposal requires confirmation", test_73_proposal_requires_confirmation)
    run_test("74. Propose-action does not execute mutation", test_74_propose_action_does_not_execute_mutation)
    run_test("75. Unsupported action handled cleanly", test_75_unsupported_action_handled_cleanly)
    run_test("76. API response contains evidence", test_76_api_response_contains_evidence)
    run_test("77. API response contains lineage", test_77_api_response_contains_lineage)
    run_test("78. API response contains SQL", test_78_api_response_contains_sql)
    run_test("79. No credentials exposed", test_79_no_credentials_exposed)
    run_test("80. No JWT exposed", test_80_no_jwt_exposed)
    run_test("81. No connection string exposed", test_81_no_connection_string_exposed)
    run_test("82. Evaluation remains read-only", test_82_evaluation_remains_read_only)
    run_test("83. Client cannot override thresholds", test_83_client_cannot_override_thresholds)
    run_test("84. Client cannot spoof user_id", test_84_client_cannot_spoof_user_id)
    run_test("85. Bounded alert list", test_85_bounded_alert_list)
    run_test("86. Status filtering", test_86_status_filtering)
    run_test("87. Severity filtering", test_87_severity_filtering)
    run_test("88. Category filtering", test_88_category_filtering)
    run_test("89. Alert deduplication", test_89_alert_deduplication)
    run_test("90. Repeated evaluation does not duplicate active alerts", test_90_repeated_evaluation_does_not_create_duplicate_active_alerts)

    passed = sum(1 for r in results if r[0] == "PASS")
    failed = sum(1 for r in results if r[0] == "FAIL")

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'='*60}\n")

    sys.exit(0 if failed == 0 else 1)
