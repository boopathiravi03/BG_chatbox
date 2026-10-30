"""backend/tests/test_autonomous_bi_sprint2.py

Comprehensive Test Suite for Sprint 2: Autonomous Business Intelligence & Scheduled Monitoring.
Covers:
1. Baseline creation and snapshot storage.
2. Baseline comparison (detects new vs. resolved data-quality findings).
3. Schema change and row-count shift detection.
4. Business anomaly detection: sudden metric drops and surges.
5. Mathematical resilience: zero denominators and insufficient historical periods.
6. Multi-user and multi-connection isolation.
7. Unauthorized or invalid connection ID rejection (no silent fallback).
8. Scheduler configuration, pause, resume, and execution interval tracking.
9. Concurrency lock: prevention of overlapping scans for the same connection.
10. Alert generation, deduplication, and lifecycle (acknowledge, resolve).
11. Credential, token, and sensitive sample value redaction.
12. Read-only scan enforcement (zero automated mutations).
13. API endpoint integration (/monitoring/schedule, /monitoring/scan, /monitoring/history, /monitoring/anomalies).
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, text
from fastapi.testclient import TestClient

from app.agent.database_profile import DatabaseProfile, DataHealthFinding
from app.tools.analyze_database import analyze_database
from app.database.connection_context import (
    set_user_context_for_request,
    set_user_engine,
    clear_user_context,
)
from app.database.database_context import clear_database_profile
from app.intelligence.monitoring.baseline_store import (
    set_monitoring_store_engine,
    save_baseline,
    get_latest_baseline,
    save_schedule_config,
    get_schedule_config,
    record_scan_history,
    get_scan_history,
)
from app.intelligence.proactive.models import AlertStatus
from app.intelligence.proactive.alert_store import (
    set_alert_store_engine,
    get_alerts,
    update_alert_status,
    clear_user_alerts,
)
from app.intelligence.anomaly.business_anomaly import (
    detect_business_anomalies,
    BusinessAnomaly,
)
from app.intelligence.monitoring.quality_monitor import (
    run_database_health_monitoring,
    _active_scans,
)
from app.intelligence.monitoring.scheduler import (
    configure_schedule,
    pause_schedule,
    resume_schedule,
    trigger_immediate_scan,
    get_schedule_status,
)
from app.main import app
from app.security.auth import create_access_token


class TestAutonomousBISprint2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 1. Disposable SQLite user database A
        cls.db_fd_a, cls.db_path_a = tempfile.mkstemp(suffix=".db")
        cls.engine_a = create_engine(f"sqlite:///{cls.db_path_a}", connect_args={"check_same_thread": False})

        # 2. Disposable SQLite user database B (for multi-tenant isolation testing)
        cls.db_fd_b, cls.db_path_b = tempfile.mkstemp(suffix=".db")
        cls.engine_b = create_engine(f"sqlite:///{cls.db_path_b}", connect_args={"check_same_thread": False})

        # 3. Isolated in-memory engines for monitoring store and alert store with StaticPool
        from sqlalchemy.pool import StaticPool
        from app.intelligence.monitoring.scheduler import stop_monitoring_scheduler
        stop_monitoring_scheduler()

        cls.mon_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        set_monitoring_store_engine(cls.mon_engine)

        cls.alert_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        set_alert_store_engine(cls.alert_engine)

        # Populate User DB A with realistic business entities and time-series drops
        with cls.engine_a.connect() as conn:
            conn.execute(text("""
                CREATE TABLE customers (
                    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    password_hash TEXT NOT NULL
                );
            """))
            conn.execute(text("""
                INSERT INTO customers (name, email, password_hash) VALUES
                ('Alice Johnson', 'alice@corp.com', 'secret_hash_999'),
                ('Bob Smith', 'bob@corp.com', 'secret_hash_888');
            """))

            conn.execute(text("""
                CREATE TABLE orders (
                    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id INTEGER NOT NULL,
                    total_amount REAL NOT NULL,
                    order_date DATE NOT NULL
                );
            """))
            # Month 2026-08: 2000, Month 2026-09: 3000, Month 2026-10: 500 (Sudden 83% drop!)
            conn.execute(text("""
                INSERT INTO orders (customer_id, total_amount, order_date) VALUES
                (1, 1000.0, '2026-08-10'),
                (2, 1000.0, '2026-08-20'),
                (1, 1500.0, '2026-09-05'),
                (2, 1500.0, '2026-09-25'),
                (1, 500.0,  '2026-10-02');
            """))

            # Defect Table: Missing primary key and null column
            conn.execute(text("""
                CREATE TABLE defect_import_staging (
                    item_sku TEXT,
                    optional_rating REAL
                );
            """))
            conn.execute(text("""
                INSERT INTO defect_import_staging (item_sku, optional_rating) VALUES
                ('SKU-1', 4.5),
                ('SKU-2', NULL),
                ('SKU-3', NULL),
                ('SKU-4', NULL);
            """))
            conn.commit()

        # Populate User DB B with distinct data
        with cls.engine_b.connect() as conn:
            conn.execute(text("""
                CREATE TABLE tenant_b_data (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL
                );
            """))
            conn.execute(text("INSERT INTO tenant_b_data (title) VALUES ('Project B');"))
            conn.commit()

    @classmethod
    def tearDownClass(cls):
        cls.engine_a.dispose()
        cls.engine_b.dispose()
        os.close(cls.db_fd_a)
        os.close(cls.db_fd_b)
        try:
            os.remove(cls.db_path_a)
            os.remove(cls.db_path_b)
        except Exception:
            pass

    def setUp(self):
        clear_database_profile()
        clear_user_alerts("user_alice")
        clear_user_alerts("user_bob")
        set_user_engine("user_alice", self.engine_a, "sqlite", f"sqlite:///{self.db_path_a}", connection_id="conn_alice_main")
        set_user_engine("user_bob", self.engine_b, "sqlite", f"sqlite:///{self.db_path_b}", connection_id="conn_bob_main")
        set_user_context_for_request("user_alice", connection_id="conn_alice_main")

    def tearDown(self):
        clear_user_context("user_alice")
        clear_user_context("user_bob")
        clear_database_profile()
        _active_scans.clear()

    # -------------------------------------------------------------------------
    # 1. Baseline Creation & Snapshot Storage
    # -------------------------------------------------------------------------
    def test_baseline_creation_and_snapshot_storage(self):
        """Initial scan must store baseline with tables, row counts, and health score."""
        res = run_database_health_monitoring(user_id="user_alice", connection_id="conn_alice_main")
        self.assertEqual(res["status"], "success")
        self.assertGreater(res["health_score"], 0)
        self.assertGreater(len(res["new_findings"]), 0)

        baseline = get_latest_baseline(user_id="user_alice", connection_id="conn_alice_main")
        self.assertIsNotNone(baseline)
        self.assertIn("customers", baseline["tables"])
        self.assertIn("orders", baseline["tables"])
        self.assertEqual(baseline["row_counts"]["customers"], 2)
        self.assertEqual(baseline["row_counts"]["orders"], 5)

    # -------------------------------------------------------------------------
    # 2. Baseline Comparison (Detects New vs. Resolved Findings)
    # -------------------------------------------------------------------------
    def test_baseline_comparison_detects_new_and_resolved_findings(self):
        """Comparing against baseline must identify newly added defects and resolved defects."""
        # 1. Establish initial baseline
        run_database_health_monitoring(user_id="user_alice", connection_id="conn_alice_main")

        # 2. Introduce a new defect: create an empty table
        with self.engine_a.connect() as conn:
            conn.execute(text("CREATE TABLE newly_added_empty_table (id INTEGER PRIMARY KEY);"))
            # And resolve an old defect by adding a PK to defect_import_staging (simulated via drop table)
            conn.execute(text("DROP TABLE defect_import_staging;"))
            conn.commit()

        try:
            clear_database_profile("user_alice", "conn_alice_main")
            res2 = run_database_health_monitoring(user_id="user_alice", connection_id="conn_alice_main")

            # Check new findings contains the new empty table
            new_types = [f["type"] for f in res2["new_findings"]]
            self.assertIn("Empty Table", new_types)

            # Check resolved findings contains the missing PK and high null from the dropped table
            resolved_tables = [f["table"] for f in res2["resolved_findings"]]
            self.assertIn("defect_import_staging", resolved_tables)
        finally:
            with self.engine_a.connect() as conn:
                conn.execute(text("DROP TABLE IF EXISTS newly_added_empty_table;"))
                conn.execute(text("""
                    CREATE TABLE defect_import_staging (
                        item_sku TEXT,
                        optional_rating REAL
                    );
                """))
                conn.execute(text("INSERT INTO defect_import_staging VALUES ('SKU-1', 4.5), ('SKU-2', NULL);"))
                conn.commit()

    # -------------------------------------------------------------------------
    # 3. Schema Change and Row Count Shift Detection
    # -------------------------------------------------------------------------
    def test_schema_change_and_row_count_shift_detection(self):
        """Scans must detect added tables and significant row count shifts."""
        run_database_health_monitoring(user_id="user_alice", connection_id="conn_alice_main")

        # Insert 10 additional customers (a 500% increase over 2)
        with self.engine_a.connect() as conn:
            for i in range(10):
                conn.execute(text(f"INSERT INTO customers (name, email, password_hash) VALUES ('User {i}', 'u{i}@test.com', 'h');"))
            conn.commit()

        try:
            clear_database_profile("user_alice", "conn_alice_main")
            res = run_database_health_monitoring(user_id="user_alice", connection_id="conn_alice_main")

            shifts = {s["table"]: s for s in res["row_count_shifts"]}
            self.assertIn("customers", shifts)
            self.assertEqual(shifts["customers"]["previous_count"], 2)
            self.assertEqual(shifts["customers"]["current_count"], 12)
            self.assertGreaterEqual(shifts["customers"]["percentage_change"], 100.0)
        finally:
            # Clean up added customers
            with self.engine_a.connect() as conn:
                conn.execute(text("DELETE FROM customers WHERE email LIKE 'u%@test.com';"))
                conn.commit()

    # -------------------------------------------------------------------------
    # 4. Business Anomaly Detection: Metric Drop
    # -------------------------------------------------------------------------
    def test_business_anomaly_sudden_metric_decline(self):
        """Sudden period-over-period metric drops must generate an explainable BusinessAnomaly."""
        profile = analyze_database(user_id="user_alice", connection_id="conn_alice_main")
        anomalies = detect_business_anomalies(
            engine=self.engine_a,
            db_type="sqlite",
            profile=profile,
            drop_threshold_pct=30.0,
        )

        drop_anoms = [a for a in anomalies if "Decline" in a.title or a.percentage_change and a.percentage_change < -30]
        self.assertTrue(len(drop_anoms) > 0, "Expected a sudden metric decline anomaly on orders table.")

        anom = drop_anoms[0]
        self.assertEqual(anom.table, "orders")
        self.assertEqual(anom.severity, "critical")  # Drop from 3000 to 500 is -83% (> 50% critical threshold)
        self.assertLess(anom.observed_value, anom.expected_value)
        self.assertFalse(anom.is_root_cause_confirmed, "Anomaly must NOT be claimed as a confirmed root cause.")
        self.assertGreater(len(anom.recommended_steps), 0)

    # -------------------------------------------------------------------------
    # 5. Insufficient History & Zero Denominator Protection
    # -------------------------------------------------------------------------
    def test_insufficient_history_and_zero_denominator_protection(self):
        """Tables with single periods or zero previous values must not cause exceptions."""
        with self.engine_a.connect() as conn:
            conn.execute(text("CREATE TABLE single_period_table (id INTEGER, val REAL, log_date DATE);"))
            conn.execute(text("INSERT INTO single_period_table VALUES (1, 100.0, '2026-10-01');"))
            conn.execute(text("CREATE TABLE zero_prev_table (id INTEGER, val REAL, log_date DATE);"))
            conn.execute(text("INSERT INTO zero_prev_table VALUES (1, 0.0, '2026-09-01'), (2, 50.0, '2026-10-01');"))
            conn.commit()

        try:
            profile = analyze_database(user_id="user_alice", connection_id="conn_alice_main")
            # Must run safely without division by zero or crashing
            anomalies = detect_business_anomalies(
                engine=self.engine_a,
                db_type="sqlite",
                profile=profile,
            )
            self.assertIsInstance(anomalies, list)
        finally:
            with self.engine_a.connect() as conn:
                conn.execute(text("DROP TABLE IF EXISTS single_period_table;"))
                conn.execute(text("DROP TABLE IF EXISTS zero_prev_table;"))
                conn.commit()

    # -------------------------------------------------------------------------
    # 6. Multi-User & Multi-Connection Isolation
    # -------------------------------------------------------------------------
    def test_multi_user_and_connection_isolation(self):
        """User Alice and User Bob must have completely isolated baselines, histories, and schedules."""
        # Alice scan
        run_database_health_monitoring(user_id="user_alice", connection_id="conn_alice_main")
        # Bob scan
        run_database_health_monitoring(user_id="user_bob", connection_id="conn_bob_main")

        alice_hist = get_scan_history(user_id="user_alice")
        bob_hist = get_scan_history(user_id="user_bob")

        self.assertTrue(all(h["connection_id"] != "conn_bob_main" for h in alice_hist))
        self.assertTrue(all(h["connection_id"] == "conn_bob_main" for h in bob_hist))

        # Alice cannot fetch Bob's baseline
        alice_baseline_for_bob = get_latest_baseline(user_id="user_alice", connection_id="conn_bob_main")
        self.assertIsNone(alice_baseline_for_bob, "User Alice must not access User Bob's baseline.")

    # -------------------------------------------------------------------------
    # 7. Unauthorized / Invalid Connection ID Handling
    # -------------------------------------------------------------------------
    def test_invalid_connection_returns_disconnected_without_fallback(self):
        """Invalid connection_id must return disconnected without executing against another DB."""
        res = run_database_health_monitoring(user_id="user_alice", connection_id="nonexistent_unowned_id")
        self.assertEqual(res["status"], "disconnected")
        self.assertEqual(res["health_score"], 0)

    # -------------------------------------------------------------------------
    # 8. Scheduler Configuration, Pause & Resume
    # -------------------------------------------------------------------------
    def test_scheduler_configuration_and_pause_resume(self):
        """Scheduler configuration must support interval setting, pausing, and resuming."""
        cfg = configure_schedule("user_alice", "conn_alice_main", interval_minutes=15, is_enabled=True)
        self.assertEqual(cfg["interval_minutes"], 15)
        self.assertTrue(cfg["is_enabled"])
        self.assertEqual(cfg["status"], "idle")

        # Pause
        p_cfg = pause_schedule("user_alice", "conn_alice_main")
        self.assertFalse(p_cfg["is_enabled"])
        self.assertEqual(p_cfg["status"], "paused")

        # Resume
        r_cfg = resume_schedule("user_alice", "conn_alice_main")
        self.assertTrue(r_cfg["is_enabled"])
        self.assertEqual(r_cfg["status"], "idle")

        status = get_schedule_status("user_alice", "conn_alice_main")
        self.assertEqual(status["interval_minutes"], 15)

    # -------------------------------------------------------------------------
    # 9. Concurrency Lock: Prevents Overlapping Scans
    # -------------------------------------------------------------------------
    def test_concurrency_lock_prevents_overlapping_scans(self):
        """Attempting to start a scan while one is in progress must return 'already_scanning'."""
        key = ("user_alice", "conn_alice_main")
        _active_scans.add(key)
        try:
            res = run_database_health_monitoring(user_id="user_alice", connection_id="conn_alice_main")
            self.assertEqual(res["status"], "already_scanning")
        finally:
            _active_scans.discard(key)

    # -------------------------------------------------------------------------
    # 10. Proactive Alert Generation & Lifecycle
    # -------------------------------------------------------------------------
    def test_alert_generation_and_lifecycle(self):
        """New critical/warning findings must create alerts that can be acknowledged and resolved."""
        run_database_health_monitoring(user_id="user_alice", connection_id="conn_alice_main")

        alerts = get_alerts(user_id="user_alice")
        self.assertGreater(len(alerts), 0, "Expected proactive alerts to be created.")

        first_alert = alerts[0]
        self.assertIn(first_alert.status, [AlertStatus.NEW, "new", "NEW"])

        # Acknowledge
        ack_alert = update_alert_status(first_alert.alert_id, AlertStatus.ACKNOWLEDGED, user_id="user_alice")
        self.assertIsNotNone(ack_alert)
        self.assertEqual(ack_alert.status, AlertStatus.ACKNOWLEDGED)

        # Resolve
        res_alert = update_alert_status(first_alert.alert_id, AlertStatus.RESOLVED, user_id="user_alice")
        self.assertIsNotNone(res_alert)
        self.assertEqual(res_alert.status, AlertStatus.RESOLVED)
        self.assertIsNotNone(res_alert.resolved_at)

    # -------------------------------------------------------------------------
    # 11. Sensitive Data Redaction in Monitoring & Alerts
    # -------------------------------------------------------------------------
    def test_sensitive_data_redaction(self):
        """Password hashes and credentials must never appear in alert evidence or scan summaries."""
        res = run_database_health_monitoring(user_id="user_alice", connection_id="conn_alice_main")
        res_str = str(res)
        self.assertNotIn("secret_hash_999", res_str)
        self.assertNotIn("secret_hash_888", res_str)

        alerts = get_alerts(user_id="user_alice")
        for a in alerts:
            a_str = str(a.to_dict())
            self.assertNotIn("secret_hash_999", a_str)

    # -------------------------------------------------------------------------
    # 12. Read-Only Scan Enforcement
    # -------------------------------------------------------------------------
    def test_read_only_scan_enforcement(self):
        """Health monitoring must never modify, delete, or insert rows into user tables."""
        with self.engine_a.connect() as conn:
            cust_before = conn.execute(text("SELECT COUNT(*) FROM customers")).scalar()
            orders_before = conn.execute(text("SELECT COUNT(*) FROM orders")).scalar()

        run_database_health_monitoring(user_id="user_alice", connection_id="conn_alice_main")

        with self.engine_a.connect() as conn:
            cust_after = conn.execute(text("SELECT COUNT(*) FROM customers")).scalar()
            orders_after = conn.execute(text("SELECT COUNT(*) FROM orders")).scalar()

        self.assertEqual(cust_before, cust_after, "Customer row count must not change.")
        self.assertEqual(orders_before, orders_after, "Orders row count must not change.")

    # -------------------------------------------------------------------------
    # 13. API Endpoints Integration
    # -------------------------------------------------------------------------
    def test_api_endpoints_integration(self):
        """FastAPI endpoints for /monitoring/schedule, /monitoring/scan, /monitoring/history must work."""
        client = TestClient(app)
        token = create_access_token("user_alice", "alice")
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Connection-ID": "conn_alice_main",
        }

        # 1. Schedule config endpoint
        sched_res = client.post(
            "/monitoring/schedule",
            json={"connection_id": "conn_alice_main", "interval_minutes": 30, "is_enabled": True},
            headers=headers,
        )
        self.assertEqual(sched_res.status_code, 200)
        self.assertEqual(sched_res.json()["schedule"]["interval_minutes"], 30)

        # 2. Schedule get endpoint
        get_sched = client.get("/monitoring/schedule?connection_id=conn_alice_main", headers=headers)
        self.assertEqual(get_sched.status_code, 200)
        self.assertEqual(get_sched.json()["schedule"]["status"], "idle")

        # 3. Manual scan trigger endpoint
        scan_res = client.post(
            "/monitoring/scan",
            json={"connection_id": "conn_alice_main"},
            headers=headers,
        )
        self.assertEqual(scan_res.status_code, 200)
        self.assertEqual(scan_res.json()["status"], "success")

        # 4. History endpoint
        hist_res = client.get("/monitoring/history?connection_id=conn_alice_main", headers=headers)
        self.assertEqual(hist_res.status_code, 200)
        self.assertGreater(len(hist_res.json()["history"]), 0)

        # 5. Anomalies endpoint
        anom_res = client.get("/monitoring/anomalies?connection_id=conn_alice_main", headers=headers)
        self.assertEqual(anom_res.status_code, 200)
        self.assertEqual(anom_res.json()["status"], "success")


if __name__ == "__main__":
    unittest.main()
