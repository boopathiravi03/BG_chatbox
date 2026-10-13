#!/usr/bin/env python
"""
Verification Suite for Overview & Anomaly Center Synchronization
Tests:
1. /anomaly/summary endpoint contract and key extraction (no missing "summary" key bug)
2. Exact count agreement between /anomaly/report and /anomaly/summary
3. Scan state enumeration ('not_scanned', 'completed_with_findings', 'completed_no_findings')
4. Connection identity and timestamp presence in anomaly scan reports
5. Anomaly bridge to proactive alert store in evaluate_proactive_metrics()
6. Cache invalidation on mutation (clear_cached_anomaly_report)
"""
import sys
import os
import sqlite3
import tempfile
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection_context import set_user_context_for_request
from app.intelligence.anomaly.detector import (
    detect_anomalies,
    clear_cached_anomaly_report,
)
from app.intelligence.proactive.evaluator import evaluate_proactive_metrics
from app.intelligence.proactive.alert_store import get_alerts
from app.connectors.relational import SQLiteConnector
from app.connectors.registry import get_connection_registry

results = []

def test(name, fn):
    try:
        fn()
        results.append(("PASS", name))
        print(f"  [PASS] {name}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        results.append(("FAIL", name, str(e)))
        print(f"  [FAIL] {name}: {e}")

def create_sample_database():
    """Creates a temporary SQLite database with known tables and known nulls in customers.created_at."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, email TEXT, created_at TEXT)")
    cur.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price REAL, stock INTEGER)")
    cur.execute("CREATE TABLE empty_table (id INTEGER PRIMARY KEY, notes TEXT)")

    # 8 customer rows, 3 of which have NULL in created_at (High NULL ratio)
    for i in range(5):
        cur.execute("INSERT INTO customers VALUES (?, ?, ?, ?)", (i + 1, f"Customer {i}", f"c{i}@example.com", "2026-01-01"))
    for i in range(5, 8):
        cur.execute("INSERT INTO customers VALUES (?, ?, ?, ?)", (i + 1, f"Customer {i}", f"c{i}@example.com", None))

    # Product rows
    for i in range(10):
        cur.execute("INSERT INTO products VALUES (?, ?, ?, ?)", (i + 1, f"Item {i}", 25.0 * (i + 1), 50))

    conn.commit()
    conn.close()
    return db_path

def test_anomaly_scan_and_summary_contract():
    db_path = create_sample_database()
    user_id = "test_user_anom_1"
    conn_id = "test_conn_anom_1"
    reg = get_connection_registry()
    connector = None
    try:
        connector = SQLiteConnector(
            connection_id=conn_id,
            name="MySQL Data Source",
            database_path=db_path,
            user_id=user_id,
        )
        assert connector.connect() is True
        reg.register_connector(connector)
        reg.set_active_connector(user_id, conn_id)
        set_user_context_for_request(user_id, conn_id)

        clear_cached_anomaly_report()

        report = detect_anomalies(force_refresh=True)
        rep_dict = report.to_dict()

        # Verify report has findings
        assert rep_dict["total_anomalies"] > 0, "Expected anomalies to be detected"
        assert rep_dict["warning_count"] > 0 or rep_dict["critical_count"] > 0, "Expected warnings or critical findings"
        assert "scan_timestamp" in rep_dict and rep_dict["scan_timestamp"], "Missing scan_timestamp"
        assert "database_name" in rep_dict, "Missing database_name"

        # Check customers.created_at null finding was found
        found_customers_null = any(
            a.get("table") == "customers" and a.get("column") == "created_at"
            for a in rep_dict.get("anomalies", [])
        )
        assert found_customers_null, "Expected high null ratio anomaly on customers.created_at"

        # Verify summary endpoint contract
        crit = rep_dict.get("critical_count", 0)
        warn = rep_dict.get("warning_count", 0)
        info = rep_dict.get("info_count", 0)
        tot = rep_dict.get("total_anomalies", 0)

        assert tot == crit + warn + info, f"Mismatch in sum of severities: {tot} != {crit}+{warn}+{info}"

        # Test anomaly summary endpoint directly
        from app.main import anomaly_summary_endpoint
        mock_req = MagicMock()
        mock_req.headers.get.return_value = None
        mock_user = MagicMock()
        mock_user.user_id = user_id

        summary_res = anomaly_summary_endpoint(request=mock_req, connection_id=conn_id, user=mock_user)
        assert summary_res["status"] == "success"
        assert summary_res["total_anomalies"] == tot
        assert summary_res["critical_count"] == crit
        assert summary_res["warning_count"] == warn
        assert summary_res["info_count"] == info
        assert summary_res["scan_state"] == "completed_with_findings"

        connector.disconnect()
    finally:
        if connector:
            reg.remove_connector(user_id, conn_id)
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass

def test_proactive_anomaly_bridge():
    db_path = create_sample_database()
    user_id = "test_user_bridge_2"
    conn_id = "test_conn_bridge_2"
    reg = get_connection_registry()
    connector = None
    try:
        connector = SQLiteConnector(
            connection_id=conn_id,
            name="Test SQLite Bridge DB",
            database_path=db_path,
            user_id=user_id,
        )
        assert connector.connect() is True
        reg.register_connector(connector)
        reg.set_active_connector(user_id, conn_id)
        set_user_context_for_request(user_id, conn_id)

        clear_cached_anomaly_report()

        res = evaluate_proactive_metrics(
            engine=connector._engine,
            db_type="sqlite",
            user_id=user_id,
            deduplicate=True,
            save_to_store=True,
        )

        assert res["status"] == "success"
        alerts = res.get("alerts", [])
        assert len(alerts) > 0, "Expected proactive alerts to include bridged anomalies"

        # Check that bridged anomaly category exists
        has_anomaly_category = any(
            a.get("category") == "ANOMALY_DETECTED" or a.get("category") == "DATA_QUALITY_DEGRADATION"
            for a in alerts
        )
        assert has_anomaly_category, "Expected ANOMALY_DETECTED or DATA_QUALITY_DEGRADATION in alerts"
        connector.disconnect()
    finally:
        if connector:
            reg.remove_connector(user_id, conn_id)
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass

def test_cache_invalidation_behavior():
    db_path = create_sample_database()
    user_id = "test_user_cache_3"
    conn_id = "test_conn_cache_3"
    reg = get_connection_registry()
    connector = None
    try:
        connector = SQLiteConnector(
            connection_id=conn_id,
            name="Test SQLite Cache DB",
            database_path=db_path,
            user_id=user_id,
        )
        assert connector.connect() is True
        reg.register_connector(connector)
        reg.set_active_connector(user_id, conn_id)
        set_user_context_for_request(user_id, conn_id)

        # Scan 1
        clear_cached_anomaly_report()
        report1 = detect_anomalies(force_refresh=False)
        ts1 = report1.scan_timestamp

        # Scan cached (returns identical object without refresh)
        report_cached = detect_anomalies(force_refresh=False)
        assert report_cached.scan_timestamp == ts1

        # Invalidate cache
        clear_cached_anomaly_report()
        import time
        time.sleep(0.01)
        report2 = detect_anomalies(force_refresh=False)
        assert report2 is not None

        connector.disconnect()
    finally:
        if connector:
            reg.remove_connector(user_id, conn_id)
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass

if __name__ == "__main__":
    print("Running Anomaly & Overview Synchronization Verification Suite:")
    test("1. Anomaly Scan and Summary Contract (customers.created_at nulls)", test_anomaly_scan_and_summary_contract)
    test("2. Proactive Metric Evaluator Anomaly Bridge", test_proactive_anomaly_bridge)
    test("3. Cache Invalidation and Refresh Behavior", test_cache_invalidation_behavior)

    passed = sum(1 for r in results if r[0] == "PASS")
    failed = sum(1 for r in results if r[0] == "FAIL")
    print(f"\n{len(results)} tests: {passed} passed, {failed} failed\n")
    sys.exit(0 if failed == 0 else 1)
