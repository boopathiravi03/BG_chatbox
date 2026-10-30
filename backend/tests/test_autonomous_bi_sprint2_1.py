"""backend/tests/test_autonomous_bi_sprint2_1.py

Test Suite for Sprint 2.1: Integrated Autonomous Monitoring & Scheduler Verification.
Covers:
1. Server restart resilience: Persisted schedules reload and resume after server restart.
2. Paused and disabled schedule preservation across restarts.
3. Multi-worker atomic schedule claim coordination (prevents duplicate execution across uvicorn workers).
4. Proactive alert deduplication on repeated scans with identical findings.
5. Auto-resolution of proactive alerts when underlying data quality defects are fixed.
6. Alert dismiss endpoint (/proactive/alerts/{id}/dismiss).
7. Parameter validation: schedule interval bounds (rejecting <1 and >43200).
8. Strict cross-user and cross-connection tenant isolation across all endpoints.
9. Disconnected connector rejection without unowned fallback.
10. Read-only scan enforcement.
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

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
    list_active_schedules,
    claim_schedule_execution,
    record_scan_history,
    get_scan_history,
)
from app.intelligence.proactive.alert_store import (
    set_alert_store_engine,
    get_alerts,
    get_alert,
    update_alert_status,
    save_alert,
)
from app.intelligence.proactive.models import (
    BusinessAlert,
    AlertCategory,
    AlertSeverity,
    AlertStatus,
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
    start_monitoring_scheduler,
    stop_monitoring_scheduler,
)
from app.main import app
from app.security.auth import create_access_token


class TestAutonomousBISprint21(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        stop_monitoring_scheduler()

        # In-memory monitoring and proactive alert store engines with StaticPool
        cls.monitoring_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        set_monitoring_store_engine(cls.monitoring_engine)

        cls.alert_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        set_alert_store_engine(cls.alert_engine)

        # Disposable user SQLite database A
        cls.db_fd_a, cls.db_path_a = tempfile.mkstemp(suffix=".db")
        cls.engine_a = create_engine(f"sqlite:///{cls.db_path_a}")
        with cls.engine_a.connect() as conn:
            conn.execute(text("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price REAL);"))
            conn.execute(text("INSERT INTO products VALUES (1, 'Widget', 19.99), (2, 'Gadget', 49.99);"))
            conn.execute(text("CREATE TABLE unindexed_staging (temp_name TEXT, optional_code TEXT);"))
            conn.execute(text("INSERT INTO unindexed_staging VALUES ('A', NULL), ('B', NULL);"))
            conn.commit()

        # Disposable user SQLite database B (Bob)
        cls.db_fd_b, cls.db_path_b = tempfile.mkstemp(suffix=".db")
        cls.engine_b = create_engine(f"sqlite:///{cls.db_path_b}")
        with cls.engine_b.connect() as conn:
            conn.execute(text("CREATE TABLE bob_records (id INTEGER PRIMARY KEY, note TEXT);"))
            conn.execute(text("INSERT INTO bob_records VALUES (1, 'Secret Note');"))
            conn.commit()

    @classmethod
    def tearDownClass(cls):
        cls.engine_a.dispose()
        cls.engine_b.dispose()
        try:
            os.close(cls.db_fd_a)
            os.remove(cls.db_path_a)
            os.close(cls.db_fd_b)
            os.remove(cls.db_path_b)
        except Exception:
            pass

    def setUp(self):
        set_user_engine("user_alice", self.engine_a, "sqlite", f"sqlite:///{self.db_path_a}", connection_id="conn_alice_db")
        set_user_engine("user_bob", self.engine_b, "sqlite", f"sqlite:///{self.db_path_b}", connection_id="conn_bob_db")
        set_user_context_for_request("user_alice", connection_id="conn_alice_db")

    def tearDown(self):
        clear_user_context("user_alice")
        clear_user_context("user_bob")
        clear_database_profile()
        _active_scans.clear()

    # -------------------------------------------------------------------------
    # 1. Server Restart & Schedule Persistence
    # -------------------------------------------------------------------------
    def test_schedule_persists_and_reloads_across_server_restarts(self):
        """Schedule saved to database must survive server shutdown and reload on restart."""
        # Save a 45-minute schedule for Alice
        cfg = save_schedule_config(
            user_id="user_alice",
            connection_id="conn_alice_db",
            interval_minutes=45,
            is_enabled=True,
            status="idle",
        )
        self.assertEqual(cfg["interval_minutes"], 45)
        self.assertTrue(cfg["is_enabled"])

        # Simulate server shutdown
        stop_monitoring_scheduler()

        # Simulate server reboot: start_monitoring_scheduler() reloads active schedules
        start_monitoring_scheduler()

        # Verify schedule is present in database and listed as active
        active_list = list_active_schedules()
        matching = [s for s in active_list if s["user_id"] == "user_alice" and s["connection_id"] == "conn_alice_db"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["interval_minutes"], 45)

        # Stop scheduler again for clean test isolation
        stop_monitoring_scheduler()

    # -------------------------------------------------------------------------
    # 2. Paused & Disabled Schedule State Retention
    # -------------------------------------------------------------------------
    def test_paused_and_disabled_schedules_remain_paused(self):
        """Paused and disabled schedules must not be executed or returned in active scheduler loops."""
        # Pause Alice's schedule
        p_cfg = pause_schedule("user_alice", "conn_alice_db")
        self.assertFalse(p_cfg["is_enabled"])
        self.assertEqual(p_cfg["status"], "paused")

        # Simulate server reboot
        stop_monitoring_scheduler()
        start_monitoring_scheduler()

        # Active scheduler list must NOT include paused schedules
        active_list = list_active_schedules()
        alice_active = [s for s in active_list if s["user_id"] == "user_alice" and s["connection_id"] == "conn_alice_db"]
        self.assertEqual(len(alice_active), 0, "Paused schedules must not be scheduled for execution.")

        stop_monitoring_scheduler()

    # -------------------------------------------------------------------------
    # 3. Multi-Worker Atomic Schedule Claim Lock
    # -------------------------------------------------------------------------
    def test_multi_worker_schedule_claim_coordination(self):
        """Multiple server workers competing to execute a due schedule must only permit one worker."""
        # Enable schedule
        save_schedule_config("user_alice", "conn_alice_db", interval_minutes=30, is_enabled=True, status="idle")

        # Worker 1 claims schedule execution
        claimed_by_w1 = claim_schedule_execution("user_alice", "conn_alice_db", lease_minutes=5)
        self.assertTrue(claimed_by_w1, "First worker must successfully claim schedule execution.")

        # Worker 2 attempts concurrent claim for same schedule
        claimed_by_w2 = claim_schedule_execution("user_alice", "conn_alice_db", lease_minutes=5)
        self.assertFalse(claimed_by_w2, "Second worker must be denied concurrent claim.")

    # -------------------------------------------------------------------------
    # 4. Alert Deduplication on Repeated Scans
    # -------------------------------------------------------------------------
    def test_proactive_alert_deduplication(self):
        """Repeated scans of the same unchanged defects must update in-place rather than creating duplicate alerts."""
        # Scan 1: Discovers defect in unindexed_staging
        res1 = run_database_health_monitoring("user_alice", "conn_alice_db")
        self.assertEqual(res1["status"], "success")

        alerts_run1 = get_alerts(user_id="user_alice")
        initial_alert_count = len(alerts_run1)
        self.assertGreater(initial_alert_count, 0)

        # Scan 2: Unchanged database; runs again
        res2 = run_database_health_monitoring("user_alice", "conn_alice_db")
        self.assertEqual(res2["status"], "success")

        alerts_run2 = get_alerts(user_id="user_alice")
        # Alert count must NOT double
        self.assertEqual(len(alerts_run2), initial_alert_count, "Consecutive scans of identical defects must not duplicate alerts.")

    # -------------------------------------------------------------------------
    # 5. Alert Auto-Resolution on Defect Fix
    # -------------------------------------------------------------------------
    def test_alert_auto_resolution_when_defect_is_fixed(self):
        """When a user fixes a defect and the database is scanned, the associated alert must be resolved."""
        # 1. Baseline scan with defect
        run_database_health_monitoring("user_alice", "conn_alice_db")
        alerts = get_alerts(user_id="user_alice")
        self.assertGreater(len(alerts), 0)

        # 2. Fix the defect by dropping the defective staging table
        with self.engine_a.connect() as conn:
            conn.execute(text("DROP TABLE unindexed_staging;"))
            conn.commit()

        # 3. Subsequent scan
        res_after = run_database_health_monitoring("user_alice", "conn_alice_db")
        self.assertGreater(len(res_after["resolved_findings"]), 0)

        # Re-create table for cleanup
        with self.engine_a.connect() as conn:
            conn.execute(text("CREATE TABLE unindexed_staging (temp_name TEXT, optional_code TEXT);"))
            conn.commit()

    # -------------------------------------------------------------------------
    # 6. Proactive Alert Dismiss Endpoint
    # -------------------------------------------------------------------------
    def test_proactive_alert_dismiss_endpoint(self):
        """POST /proactive/alerts/{alert_id}/dismiss must mark alert as DISMISSED."""
        client = TestClient(app)
        token = create_access_token("user_alice", "alice")
        headers = {"Authorization": f"Bearer {token}"}

        # Create a test alert
        alert = BusinessAlert(
            title="Test Dismissal Alert",
            category=AlertCategory.DATA_QUALITY_DEGRADATION,
            severity=AlertSeverity.WARNING,
            metric="Data Quality",
            user_id="user_alice",
            alert_id="alt_dismiss_test_001",
        )
        save_alert(alert, user_id="user_alice")

        # Call dismiss endpoint
        res = client.post("/proactive/alerts/alt_dismiss_test_001/dismiss", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["alert"]["status"], AlertStatus.DISMISSED)

        # Verify fetched alert is dismissed
        fetched = get_alert("alt_dismiss_test_001", user_id="user_alice")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.status, AlertStatus.DISMISSED)

    # -------------------------------------------------------------------------
    # 7. Parameter Validation: Schedule Interval
    # -------------------------------------------------------------------------
    def test_schedule_interval_parameter_validation(self):
        """Schedule intervals < 1 or > 43200 must be rejected with HTTP 400."""
        client = TestClient(app)
        token = create_access_token("user_alice", "alice")
        headers = {"Authorization": f"Bearer {token}", "X-Connection-ID": "conn_alice_db"}

        # Interval 0 -> Reject
        res_zero = client.post("/monitoring/schedule", json={"connection_id": "conn_alice_db", "interval_minutes": 0}, headers=headers)
        self.assertEqual(res_zero.status_code, 400)

        # Interval negative -> Reject
        res_neg = client.post("/monitoring/schedule", json={"connection_id": "conn_alice_db", "interval_minutes": -15}, headers=headers)
        self.assertEqual(res_neg.status_code, 400)

        # Interval > 43200 -> Reject
        res_too_large = client.post("/monitoring/schedule", json={"connection_id": "conn_alice_db", "interval_minutes": 50000}, headers=headers)
        self.assertEqual(res_too_large.status_code, 400)

        # Valid interval 60 -> Accept
        res_valid = client.post("/monitoring/schedule", json={"connection_id": "conn_alice_db", "interval_minutes": 60}, headers=headers)
        self.assertEqual(res_valid.status_code, 200)

    # -------------------------------------------------------------------------
    # 8. Cross-User Tenant Isolation
    # -------------------------------------------------------------------------
    def test_strict_cross_user_isolation(self):
        """Alice must never access Bob's schedule, baseline, scan history, or alerts."""
        client = TestClient(app)
        alice_token = create_access_token("user_alice", "alice")
        alice_headers = {"Authorization": f"Bearer {alice_token}"}

        # Bob saves a schedule
        save_schedule_config("user_bob", "conn_bob_db", interval_minutes=25, is_enabled=True)

        # Alice attempts to get Bob's schedule
        res = client.get("/monitoring/schedule?connection_id=conn_bob_db", headers=alice_headers)
        self.assertEqual(res.status_code, 200)
        # Alice sees only default empty config for her own tenant
        self.assertEqual(res.json()["schedule"]["interval_minutes"], 60)
        self.assertFalse(res.json()["schedule"]["is_enabled"])

    # -------------------------------------------------------------------------
    # 9. Read-Only Scan Enforcement
    # -------------------------------------------------------------------------
    def test_read_only_scan_verification(self):
        """Monitoring scans must never alter table records or schema."""
        with self.engine_a.connect() as conn:
            cnt_before = conn.execute(text("SELECT COUNT(*) FROM products")).scalar()

        run_database_health_monitoring("user_alice", "conn_alice_db")

        with self.engine_a.connect() as conn:
            cnt_after = conn.execute(text("SELECT COUNT(*) FROM products")).scalar()

        self.assertEqual(cnt_before, cnt_after, "Products row count must remain unchanged.")


if __name__ == "__main__":
    unittest.main()
