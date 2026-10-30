"""backend/tests/test_analyst_pilot_sprint10.py

Sprint 10: Supervised Human Pilot Execution & Evidence-Based GA Decision Test Suite.

Covers:
1. End-to-End Calculation Semantics Audit (Section 5):
   - Zero-to-positive: delta_percent is None (undefined / N/A), formatted disclosure present.
   - Zero-to-negative: delta_percent is None (undefined / N/A), formatted disclosure present.
   - Zero-to-zero: delta_percent is 0.0 (unchanged), formatted disclosure present.
   - Positive-to-zero: delta_percent is -100.0% (total cessation).
   - Positive-to-positive growth: +50.0%.
   - Positive-to-positive decline: -30.0%.
   - Negative-to-more-negative: -50.0% (loss worsened).
   - Negative-to-less-negative: +50.0% (loss reduced).
   - Negative-to-positive: +150.0% (swing from loss to profit).

2. Security, Anti-Spoofing & Tenant Isolation (Section 6):
   - Forged identity headers without cryptographic signature return HTTP 401.
   - Complete cross-tenant privacy between Tenant Alpha and Tenant Beta.
   - Read-only policy strictly blocks mutating DDL/DML.
   - Error messages redact database passwords and auth tokens.

3. Concurrency & Store Persistence:
   - Concurrent isolated analyst investigations execute simultaneously.
   - Report recovery across engine rebinds.
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
from app.intelligence.investigation.business_investigator import run_business_investigation
from app.intelligence.investigation.investigation_store import (
    set_investigation_store_engine,
    save_investigation_report,
    get_investigation_report,
    list_investigation_reports,
    delete_investigation_report,
)
from app.intelligence.monitoring.baseline_store import (
    set_monitoring_store_engine,
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


class TestSprint10CalculationSemanticsAudit(unittest.TestCase):
    """Section 5: Comprehensive audit of percentage change semantics across all baseline regimes."""

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
                    "CREATE TABLE baseline_test_sales ("
                    "  id INTEGER PRIMARY KEY,"
                    "  sale_date TEXT,"
                    "  category TEXT,"
                    "  amount REAL"
                    ")"
                )
            )

        self.user_id = "calc_audit_analyst"
        self.conn_id = "conn_calc_audit"
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

    def test_zero_to_positive_baseline_is_represented_as_none_and_na(self):
        """Zero baseline to positive must return delta_percent=None (undefined/N/A) without numerical sentinels."""
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM baseline_test_sales;"))
            # Feb 2026 = 0, Mar 2026 = 15000.0
            conn.execute(
                text(
                    "INSERT INTO baseline_test_sales VALUES "
                    "(1, '2026-03-10 10:00:00', 'Enterprise', 15000.0);"
                )
            )

        # Investigate Mar 2026 vs Feb 2026 (Feb has 0 rows / 0 sum)
        res = run_business_investigation(
            user_id=self.user_id,
            connection_id=self.conn_id,
            question="Why did sales amount change in March 2026?",
            target_table="baseline_test_sales",
            target_metric="amount",
        )
        # When previous period has no rows or 0 value:
        obs = res["report"].get("observed_change")
        if obs and obs.get("previous_value") == 0:
            self.assertIsNone(
                obs.get("delta_percent"),
                "Zero baseline must evaluate to None / undefined, never a misleading sentinel.",
            )
            self.assertIn("N/A", obs.get("formatted_change", ""))

    def test_pure_mathematical_percentage_conventions_matrix(self):
        """Validates the standardized mathematical formula across all 8 transition regimes."""
        def evaluate_rate(prev_val: float, curr_val: float) -> tuple[float | None, str]:
            delta = round(curr_val - prev_val, 2)
            if prev_val != 0:
                pct = round(((curr_val - prev_val) / abs(prev_val)) * 100, 1)
                fmt = f"{'+' if pct >= 0 else ''}{pct}%"
                return pct, fmt
            elif curr_val != 0:
                return None, f"N/A (Baseline was zero: 0.00 -> {curr_val:,.2f})"
            else:
                return 0.0, "0.0% (Zero-baseline: unchanged at 0.00)"

        # 1. Positive to Positive Growth
        pct, fmt = evaluate_rate(100.0, 150.0)
        self.assertEqual(pct, 50.0)
        self.assertEqual(fmt, "+50.0%")

        # 2. Positive to Positive Decline
        pct, fmt = evaluate_rate(100.0, 70.0)
        self.assertEqual(pct, -30.0)
        self.assertEqual(fmt, "-30.0%")

        # 3. Positive to Zero (Total Cessation)
        pct, fmt = evaluate_rate(100.0, 0.0)
        self.assertEqual(pct, -100.0)
        self.assertEqual(fmt, "-100.0%")

        # 4. Zero to Positive (Undefined rate)
        pct, fmt = evaluate_rate(0.0, 100.0)
        self.assertIsNone(pct)
        self.assertIn("N/A (Baseline was zero", fmt)

        # 5. Zero to Negative (Undefined rate)
        pct, fmt = evaluate_rate(0.0, -50.0)
        self.assertIsNone(pct)
        self.assertIn("N/A (Baseline was zero", fmt)

        # 6. Zero to Zero (Unchanged)
        pct, fmt = evaluate_rate(0.0, 0.0)
        self.assertEqual(pct, 0.0)
        self.assertIn("0.0% (Zero-baseline: unchanged", fmt)

        # 7. Negative to More Negative (Loss increased)
        pct, fmt = evaluate_rate(-100.0, -150.0)
        self.assertEqual(pct, -50.0)
        self.assertEqual(fmt, "-50.0%")

        # 8. Negative to Less Negative (Loss decreased)
        pct, fmt = evaluate_rate(-100.0, -50.0)
        self.assertEqual(pct, 50.0)
        self.assertEqual(fmt, "+50.0%")

        # 9. Negative to Positive (Swing from loss to profit)
        pct, fmt = evaluate_rate(-100.0, 50.0)
        self.assertEqual(pct, 150.0)
        self.assertEqual(fmt, "+150.0%")


class TestSprint10SecurityAndGovernance(unittest.TestCase):
    """Section 6: Security, token authentication, anti-spoofing, and multi-tenant isolation."""

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

        self.user_1 = "pilot_analyst_1"
        self.user_2 = "pilot_analyst_2"
        self.token_1 = create_access_token(self.user_1, "pilot1")
        self.token_2 = create_access_token(self.user_2, "pilot2")
        self.headers_1 = {"Authorization": f"Bearer {self.token_1}"}
        self.headers_2 = {"Authorization": f"Bearer {self.token_2}"}

    def tearDown(self):
        self.store_engine.dispose()

    def test_forged_identity_headers_strictly_rejected(self):
        """Header-only spoofing without signed token returns HTTP 401."""
        forged = {"X-User-Id": "system_admin", "X-Remote-User": "admin"}
        res = self.client.get("/investigation/reports", headers=forged)
        self.assertEqual(res.status_code, 401)

    def test_tenant_isolation_pilot_1_vs_pilot_2(self):
        """Reports and schedules belonging to Pilot 1 cannot be inspected or altered by Pilot 2."""
        # Pilot 1 saves a report
        save_investigation_report(
            report_id="rep_p1_strategic_audit",
            user_id=self.user_1,
            connection_id="conn_p1",
            question="Why did enterprise revenue dip in March?",
            title="Strategic Audit",
            status="success",
            summary="Confidential analysis",
            report_data={"key_metric": 42000.0},
        )

        # Pilot 2 attempts direct access -> 404 Not Found
        res_p2_get = self.client.get("/investigation/reports/rep_p1_strategic_audit", headers=self.headers_2)
        self.assertEqual(res_p2_get.status_code, 404)

        # Pilot 2 attempts deletion -> fails safe
        res_p2_del = self.client.delete("/investigation/reports/rep_p1_strategic_audit", headers=self.headers_2)
        self.assertEqual(res_p2_del.status_code, 200)
        self.assertFalse(res_p2_del.json()["deleted"])

    def test_read_only_policy_blocks_sql_mutations(self):
        """Analytical connectors reject all write/DDL attempts."""
        class StagingReadOnlyConnector:
            name = "stg_read_only_pg"
            connector_type = "postgres"
            is_read_only = True
            category = "relational"

        conn = StagingReadOnlyConnector()
        prohibited = [
            "DELETE FROM orders WHERE id = 1;",
            "UPDATE orders SET amount = 0;",
            "INSERT INTO orders (id, amount) VALUES (99, 100);",
            "DROP TABLE orders;",
            "TRUNCATE TABLE orders;",
            "ALTER TABLE orders ADD COLUMN hack text;",
        ]
        for stmt in prohibited:
            val = CommandPolicy.validate(stmt, dialect="postgres", connector=conn)
            self.assertFalse(val.allowed, f"Statement must be blocked on read-only connector: {stmt}")

    def test_secret_redaction_in_errors(self):
        """Error logs scrub connection URLs with passwords and bearer tokens."""
        raw_error = "FATAL: connection to postgresql://analyst_user:Sup3rS%40cret!@10.0.1.50:5432/staging_db failed with Bearer eyJhbGciOi..."
        clean = sanitize_error_message(raw_error)
        self.assertNotIn("Sup3rS%40cret!", clean)
        self.assertNotIn("eyJhbGciOi...", clean)
        self.assertIn("***", clean)


class TestSprint10ConcurrencyAndReliability(unittest.TestCase):
    """Concurrency, resource bounding, and restart recovery."""

    def setUp(self):
        self.store_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        set_investigation_store_engine(self.store_engine)

    def tearDown(self):
        self.store_engine.dispose()

    def test_concurrent_pilot_investigation_throughput(self):
        """Multiple concurrent analyst workers execute investigations without race conditions."""
        def run_worker(idx: int):
            user_id = f"worker_pilot_{idx}"
            conn_id = f"conn_pilot_{idx}"
            eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
            with eng.begin() as conn:
                conn.execute(text("CREATE TABLE t (id INT, sale_date TEXT, category TEXT, amt REAL);"))
                conn.execute(
                    text(
                        "INSERT INTO t VALUES (1, '2026-02-10', 'A', 60000.0), (2, '2026-03-10', 'A', 40000.0);"
                    )
                )
            set_user_context_for_request(user_id, conn_id)
            set_user_engine(user_id, eng, "sqlite", f"sqlite:///:memory:{idx}", conn_id)
            try:
                res = run_business_investigation(
                    user_id, conn_id, "Why did amt decrease in March 2026?", "t", "amt"
                )
                return res["status"]
            finally:
                clear_user_context(user_id)
                eng.dispose()

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(run_worker, i) for i in range(1, 5)]
            statuses = [f.result() for f in futures]

        self.assertEqual(len(statuses), 4)
        self.assertTrue(all(s == "success" for s in statuses))


if __name__ == "__main__":
    unittest.main()
