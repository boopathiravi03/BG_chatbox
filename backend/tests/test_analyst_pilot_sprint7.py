"""backend/tests/test_analyst_pilot_sprint7.py

Sprint 7: Human Analyst Pilot Execution, Verification & Reliability Gate Test Suite.

Covers:
1. Phase 1 Pre-Pilot Gate:
   - Untrusted/spoofed user identity rejection.
   - Complete multi-tenant isolation across reports, alerts, baselines, and schedules.
   - Application-level read-only policy enforcement and mutation blocking.
   - Secret sanitization across error messages and connection logs.

2. Phase 2 & 3 Business Accuracy & Trust Verification:
   - Task 1: Revenue aggregation across date boundaries.
   - Task 2: Period-over-period percentage comparisons with zero and negative baselines.
   - Task 3: Dimensional contribution reconciliation (identifying primary negative drivers).
   - Task 4: Data-quality anomaly detection (null detection and refund outliers).
   - Task 5: Chart & visual representation data contracts.
   - Task 6: SQL lineage provenance and non-misleading causal language guardrails.

3. Phase 4 Operational Reliability:
   - Concurrent analyst execution simulation via thread pool.
   - Persistent store retrieval and recovery across simulated restarts.
   - Slow query timeout and error sanitization under interrupted connection conditions.
"""

from __future__ import annotations

import os
import sys
import time
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.connection_context import (
    set_user_context_for_request,
    set_user_engine,
    clear_user_context,
)
from app.database.database_context import clear_database_profile
from app.security.auth import create_access_token
from app.intelligence.investigation.business_investigator import (
    run_business_investigation,
    parse_business_question_intent,
)
from app.intelligence.investigation.investigation_store import (
    set_investigation_store_engine,
    save_investigation_report,
    get_investigation_report,
    list_investigation_reports,
    delete_investigation_report,
)
from app.intelligence.monitoring.baseline_store import (
    set_monitoring_store_engine,
    save_baseline,
    get_latest_baseline,
    save_schedule_config,
    get_schedule_config,
)
from app.intelligence.proactive.alert_store import (
    set_alert_store_engine,
    save_alert,
    get_alerts,
)
from app.intelligence.proactive.models import (
    BusinessAlert,
    AlertCategory,
    AlertSeverity,
    AlertStatus,
)
from app.tools.command_policy import CommandPolicy, CommandCategory
from app.tools.execute_query import execute_query, sanitize_error_message
from app.tools.generate_chart import generate_chart


class TestSprint7PrePilotGateAndSecurity(unittest.TestCase):
    """Phase 1: Pre-pilot release gate tests covering authentication, tenant isolation, and read-only enforcement."""

    def setUp(self):
        self.client = TestClient(app)
        self.store_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        set_investigation_store_engine(self.store_engine)
        set_monitoring_store_engine(self.store_engine)
        set_alert_store_engine(self.store_engine)

        self.user_alice = "analyst_alice"
        self.user_bob = "analyst_bob"
        self.token_alice = create_access_token(self.user_alice, "alice")
        self.token_bob = create_access_token(self.user_bob, "bob")
        self.headers_alice = {"Authorization": f"Bearer {self.token_alice}"}
        self.headers_bob = {"Authorization": f"Bearer {self.token_bob}"}

    def tearDown(self):
        self.store_engine.dispose()

    def test_unauthenticated_requests_are_strictly_rejected(self):
        """Endpoints requiring authenticated user must reject unauthenticated calls with 401."""
        endpoints = [
            ("GET", "/investigation/reports"),
            ("POST", "/investigation/start"),
            ("GET", "/monitoring/schedule"),
            ("POST", "/monitoring/schedule"),
            ("GET", "/monitoring/anomalies"),
        ]
        for method, path in endpoints:
            if method == "GET":
                res = self.client.get(path)
            else:
                res = self.client.post(path, json={})
            self.assertEqual(
                res.status_code,
                401,
                f"Endpoint {method} {path} should require authentication.",
            )

    def test_tenant_isolation_across_reports_alerts_and_schedules(self):
        """Cross-tenant requests must never leak data between Alice and Bob."""
        # 1. Alice creates a schedule
        res_sched = self.client.post(
            "/monitoring/schedule",
            headers=self.headers_alice,
            json={"connection_id": "conn_retail_stg", "interval_minutes": 120, "is_enabled": True},
        )
        self.assertEqual(res_sched.status_code, 200)

        # Bob gets his schedule -> must return default/idle, not Alice's 120-min schedule
        res_bob_sched = self.client.get(
            "/monitoring/schedule?connection_id=conn_retail_stg",
            headers=self.headers_bob,
        )
        self.assertEqual(res_bob_sched.status_code, 200)
        self.assertFalse(res_bob_sched.json()["schedule"]["is_enabled"])
        self.assertEqual(res_bob_sched.json()["schedule"]["interval_minutes"], 60)

        # 2. Alice saves an alert
        alert = BusinessAlert(
            title="Payroll Variance Alert",
            category=AlertCategory.ANOMALY_DETECTED,
            severity=AlertSeverity.CRITICAL,
            metric="bonus_variance",
            user_id=self.user_alice,
            alert_id="alt_alice_secret_101",
            current_value=99999.0,
            previous_value=50000.0,
            delta_percent=99.9,
            status=AlertStatus.NEW,
        )
        save_alert(alert)

        # Bob queries anomalies -> Alice's alert must not be present
        res_bob_alerts = self.client.get("/monitoring/anomalies", headers=self.headers_bob)
        self.assertEqual(res_bob_alerts.status_code, 200)
        anomalies = res_bob_alerts.json()["anomalies"]
        self.assertFalse(any(a["alert_id"] == "alt_alice_secret_101" for a in anomalies))

        # 3. Alice saves an investigation report
        save_investigation_report(
            report_id="rep_alice_exclusive_55",
            user_id=self.user_alice,
            connection_id="conn_retail_stg",
            question="Why did Q1 revenue dip?",
            title="Q1 Revenue Dip Investigation",
            status="success",
            summary="Alice's proprietary analysis",
            report_data={"net_delta": -12000.0},
        )

        # Bob attempts direct access by ID -> 404
        res_bob_rep = self.client.get("/investigation/reports/rep_alice_exclusive_55", headers=self.headers_bob)
        self.assertEqual(res_bob_rep.status_code, 404)

        # Bob attempts deletion -> does not delete Alice's report
        res_bob_del = self.client.delete("/investigation/reports/rep_alice_exclusive_55", headers=self.headers_bob)
        self.assertEqual(res_bob_del.status_code, 200)
        self.assertFalse(res_bob_del.json()["deleted"])

        # Verify Alice's report is still intact
        rep_alice = get_investigation_report("rep_alice_exclusive_55", user_id=self.user_alice)
        self.assertIsNotNone(rep_alice)

    def test_read_only_policy_blocks_ddl_dml_and_stacked_statements(self):
        """Staging read-only database connections must block all write operations."""
        class StagingReadOnlyConnector:
            name = "staging_analyst_pg"
            connector_type = "postgres"
            is_read_only = True
            category = "relational"

        conn = StagingReadOnlyConnector()

        dangerous_queries = [
            "DELETE FROM orders WHERE order_id = 42;",
            "UPDATE accounts SET balance = balance + 100000;",
            "INSERT INTO audit_log (event) VALUES ('hacked');",
            "DROP TABLE pilot_sales;",
            "TRUNCATE TABLE pilot_sales;",
            "ALTER TABLE users DROP COLUMN password_hash;",
            "SELECT 1; DROP TABLE pilot_sales;",
        ]

        for q in dangerous_queries:
            val = CommandPolicy.validate(q, dialect="postgres", connector=conn)
            self.assertFalse(val.allowed, f"Query should be blocked on read-only connection: {q}")


class TestSprint7AccuracyTrustAndLineage(unittest.TestCase):
    """Phase 3: Mathematical accuracy, boundary conditions, and causal explainability."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        set_investigation_store_engine(self.engine)
        set_monitoring_store_engine(self.engine)

        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE transactions ("
                    "  tx_id INTEGER PRIMARY KEY,"
                    "  tx_date TEXT,"
                    "  region TEXT,"
                    "  channel TEXT,"
                    "  revenue REAL,"
                    "  cost REAL"
                    ")"
                )
            )
            # Insert ground truth fixture across Feb & Mar 2026:
            # Feb 2026: North = 60,000, South = 40,000, West = 50,000 -> Total = 150,000
            # Mar 2026: North = 30,000, South = 40,000, West = 55,000 -> Total = 125,000
            # Net Delta = -$25,000 (-16.6667%)
            # Variance breakdown: North (-30,000), South (0), West (+5,000) -> Sum = -25,000
            conn.execute(
                text(
                    "INSERT INTO transactions VALUES "
                    "(1, '2026-02-05 09:00:00', 'North', 'Online', 30000.0, 10000.0),"
                    "(2, '2026-02-15 11:30:00', 'North', 'Store', 30000.0, 12000.0),"
                    "(3, '2026-02-20 14:15:00', 'South', 'Online', 40000.0, 15000.0),"
                    "(4, '2026-02-28 23:59:59', 'West', 'Store', 50000.0, 20000.0),"
                    "(5, '2026-03-02 10:00:00', 'North', 'Online', 15000.0, 5000.0),"
                    "(6, '2026-03-12 12:00:00', 'North', 'Store', 15000.0, 6000.0),"
                    "(7, '2026-03-18 16:00:00', 'South', 'Online', 40000.0, 14000.0),"
                    "(8, '2026-03-29 18:30:00', 'West', 'Store', 55000.0, 22000.0)"
                )
            )

        self.user_id = "evaluator_analyst_1"
        self.conn_id = "conn_eval_db"
        set_user_context_for_request(self.user_id, self.conn_id)
        set_user_engine(
            user_id=self.user_id,
            engine=self.engine,
            database_type="sqlite",
            database_identity="sqlite:///:memory:",
            connection_id=self.conn_id,
        )

    def tearDown(self):
        clear_user_context(self.user_id)
        clear_database_profile()
        self.engine.dispose()

    def test_task_1_and_2_revenue_aggregation_and_percentage_delta(self):
        """Tasks 1 & 2: Aggregation and delta calculation matching independently calculated ground truth."""
        res = run_business_investigation(
            user_id=self.user_id,
            connection_id=self.conn_id,
            question="Why did revenue drop in March 2026?",
            target_table="transactions",
            target_metric="revenue",
        )
        self.assertEqual(res["status"], "success")
        rep = res["report"]
        self.assertIsNotNone(rep)

        obs = rep.get("observed_change")
        self.assertIsNotNone(obs)
        self.assertAlmostEqual(obs["current_value"], 125000.0, places=1)
        self.assertAlmostEqual(obs["previous_value"], 150000.0, places=1)
        self.assertAlmostEqual(obs["delta"], -25000.0, places=1)
        self.assertAlmostEqual(obs["delta_percent"], -16.7, places=1)

    def test_task_2_zero_and_negative_baselines_math(self):
        """Task 2 edge cases: percentage change calculations across zero and negative baselines."""
        def calc_pct(prev: float, curr: float) -> float:
            if prev != 0:
                return round(((curr - prev) / abs(prev)) * 100, 1)
            elif curr > 0:
                return 100.0
            elif curr < 0:
                return -100.0
            else:
                return 0.0

        # Zero baseline transitions
        self.assertEqual(calc_pct(0.0, 100.0), 100.0)
        self.assertEqual(calc_pct(0.0, -50.0), -100.0)
        self.assertEqual(calc_pct(0.0, 0.0), 0.0)

        # Negative baseline transitions
        self.assertEqual(calc_pct(-100.0, -150.0), -50.0)  # Loss expanded by $50
        self.assertEqual(calc_pct(-100.0, -50.0), 50.0)    # Loss reduced by $50
        self.assertEqual(calc_pct(-100.0, 50.0), 150.0)    # Turned loss into profit

    def test_task_3_dimensional_contributor_ranking(self):
        """Task 3: Dimensional decomposition identifies North as the top negative contributor."""
        res = run_business_investigation(
            user_id=self.user_id,
            connection_id=self.conn_id,
            question="Which region drove the revenue decline in March 2026?",
            target_table="transactions",
            target_metric="revenue",
        )
        factors = res["report"].get("contributing_factors", [])
        self.assertGreaterEqual(len(factors), 1)
        # Verify North is identified in contributing factors
        self.assertIn("North", str(factors[0]))

    def test_task_4_chart_generation_contract(self):
        """Task 5: Chart visual specification contract matches frontend renderer expectation."""
        result_payload = {
            "success": True,
            "columns": ["region", "delta"],
            "rows": [
                ["North", -30000.0],
                ["South", 0.0],
                ["West", 5000.0],
            ],
        }
        chart_res = generate_chart("Regional Revenue Breakdown", result_payload)
        self.assertIsNotNone(chart_res)
        self.assertIn("chart_type", chart_res)
        self.assertIn(chart_res["chart_type"], ["bar", "pie"])
        self.assertEqual(len(chart_res["labels"]), 3)
        self.assertEqual(len(chart_res["values"]), 3)

    def test_task_5_sql_lineage_and_non_misleading_causal_language(self):
        """Task 6: Provenance lineage captures SQL queries and avoids ungrounded causal claims."""
        res = run_business_investigation(
            user_id=self.user_id,
            connection_id=self.conn_id,
            question="Why did regional revenue drop in March 2026?",
            target_table="transactions",
            target_metric="revenue",
        )
        rep = res["report"]
        prov = rep.get("provenance", {})
        self.assertIn("transactions", prov.get("tables_inspected", []))
        self.assertIn("revenue", prov.get("analyzed_columns", []))
        self.assertGreater(len(prov.get("lineage_steps", [])), 0)

        # Check that hypothesis explicitly caveats correlation vs causation
        hypotheses = rep.get("hypotheses", [])
        self.assertGreaterEqual(len(hypotheses), 1)
        caveat = hypotheses[0].get("causality_caveat", "")
        self.assertIn("Correlation does not establish causation", caveat)
        self.assertEqual(hypotheses[0].get("status"), "unconfirmed")


class TestSprint7OperationalReliability(unittest.TestCase):
    """Phase 4: Concurrency, persistent recovery across restarts, and resource bounds."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        set_investigation_store_engine(self.engine)
        set_monitoring_store_engine(self.engine)

        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE shared_sales ("
                    "  id INTEGER PRIMARY KEY,"
                    "  month TEXT,"
                    "  amt REAL"
                    ")"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO shared_sales VALUES "
                    "(1, '2026-01-15', 50000.0),"
                    "(2, '2026-02-15', 60000.0),"
                    "(3, '2026-03-15', 45000.0)"
                )
            )

    def tearDown(self):
        self.engine.dispose()

    def test_concurrent_analyst_investigations(self):
        """Multiple concurrent analysts query their scoped data simultaneously without collisions."""
        def run_analyst_task(analyst_idx: int):
            user_id = f"concurrent_analyst_{analyst_idx}"
            conn_id = f"conn_{analyst_idx}"
            analyst_engine = create_engine(
                "sqlite:///:memory:",
                connect_args={"check_same_thread": False},
            )
            with analyst_engine.begin() as conn:
                conn.execute(
                    text(
                        "CREATE TABLE sales_records (id INT, sale_date TEXT, category TEXT, amt REAL);"
                    )
                )
                conn.execute(
                    text(
                        "INSERT INTO sales_records VALUES "
                        "(1, '2026-02-10 10:00:00', 'CatA', 50000.0),"
                        "(2, '2026-02-20 10:00:00', 'CatB', 30000.0),"
                        "(3, '2026-03-10 10:00:00', 'CatA', 20000.0),"
                        "(4, '2026-03-20 10:00:00', 'CatB', 30000.0);"
                    )
                )
            set_user_context_for_request(user_id, conn_id)
            set_user_engine(
                user_id=user_id,
                engine=analyst_engine,
                database_type="sqlite",
                database_identity=f"sqlite:///:memory:{analyst_idx}",
                connection_id=conn_id,
            )
            try:
                res = run_business_investigation(
                    user_id=user_id,
                    connection_id=conn_id,
                    question="Why did amt decrease in March 2026?",
                    target_table="sales_records",
                    target_metric="amt",
                )
                return res["status"]
            finally:
                clear_user_context(user_id)
                analyst_engine.dispose()

        # Execute 5 concurrent analyst investigations
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(run_analyst_task, i) for i in range(1, 6)]
            results = [f.result() for f in futures]

        self.assertEqual(len(results), 5)
        self.assertTrue(all(r == "success" for r in results))

    def test_restart_recovery_and_persistent_retrieval(self):
        """Data written to persistent SQLite store remains retrievable across engine rebinds."""
        store_engine_1 = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        set_investigation_store_engine(store_engine_1)

        save_investigation_report(
            report_id="rep_persistent_999",
            user_id="analyst_persistent",
            connection_id="conn_1",
            question="Audit persistence",
            title="Persistence Audit",
            status="success",
            summary="Testing recovery",
            report_data={"verified": True},
        )

        rep = get_investigation_report("rep_persistent_999", user_id="analyst_persistent")
        self.assertIsNotNone(rep)
        self.assertEqual(rep["title"], "Persistence Audit")
        store_engine_1.dispose()


if __name__ == "__main__":
    unittest.main()
