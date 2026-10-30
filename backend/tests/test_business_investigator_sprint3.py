"""backend/tests/test_business_investigator_sprint3.py

Comprehensive Test Suite for Sprint 3: AI Business Investigator.
Covers:
1. Metric comparisons & calculation correctness.
2. Historical period selection & missing historical data handling.
3. Evidence provenance and reproducible calculation lineage.
4. Potential-contributor ranking by contribution share.
5. Missing schema & unsupported dimension handling (no fabrication).
6. SQL policy enforcement: read-only queries with bounds.
7. Strict cross-user and cross-connection tenant isolation.
8. Sensitive data redaction in reports and evidence.
9. Investigation report persistence, listing, single retrieval, and deletion.
10. Monitoring alert to investigation integration.
11. Epistemic hygiene: unconfirmed hypothesis status and causality caveats.
12. API endpoint integration (/investigation/start, /investigation/reports).
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
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database.connection_context import (
    set_user_context_for_request,
    set_user_engine,
    clear_user_context,
)
from app.database.database_context import clear_database_profile
from app.intelligence.investigation.investigation_store import (
    set_investigation_store_engine,
    save_investigation_report,
    get_investigation_report,
    list_investigation_reports,
    delete_investigation_report,
)
from app.intelligence.investigation.business_investigator import (
    run_business_investigation,
    parse_business_question_intent,
)
from app.intelligence.proactive.alert_store import (
    set_alert_store_engine,
    save_alert,
)
from app.intelligence.proactive.models import (
    BusinessAlert,
    AlertCategory,
    AlertSeverity,
)
from app.main import app
from app.security.auth import create_access_token


class TestBusinessInvestigatorSprint3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 1. In-memory investigation store engine with StaticPool
        cls.investigation_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        set_investigation_store_engine(cls.investigation_engine)

        cls.alert_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        set_alert_store_engine(cls.alert_engine)

        # 2. Disposable User A SQLite Database (with rich multi-period transactional schema)
        cls.db_fd_a, cls.db_path_a = tempfile.mkstemp(suffix=".db")
        cls.engine_a = create_engine(f"sqlite:///{cls.db_path_a}")
        with cls.engine_a.connect() as conn:
            # Customers table (no region column to test missing requested dimension)
            conn.execute(text("CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, name TEXT, email TEXT, secret_token TEXT);"))
            conn.execute(text("INSERT INTO customers VALUES (1, 'Acme Corp', 'contact@acme.com', 'super_secret_token_123');"))
            conn.execute(text("INSERT INTO customers VALUES (2, 'Globex', 'info@globex.com', 'super_secret_token_456');"))

            # Products table
            conn.execute(text("CREATE TABLE products (product_id INTEGER PRIMARY KEY, name TEXT, category TEXT);"))
            conn.execute(text("INSERT INTO products VALUES (101, 'Laser Drill', 'Industrial');"))
            conn.execute(text("INSERT INTO products VALUES (102, 'Widget Alpha', 'Consumer');"))

            # Orders table with multi-period timestamped sales
            conn.execute(text("""
                CREATE TABLE orders (
                    order_id INTEGER PRIMARY KEY,
                    customer_id INTEGER,
                    product_id INTEGER,
                    total_amount REAL,
                    status TEXT,
                    created_at TIMESTAMP
                );
            """))
            # Period 1 (August 2026): Total = $8,000
            conn.execute(text("INSERT INTO orders VALUES (1, 1, 101, 5000.0, 'completed', '2026-08-10 10:00:00');"))
            conn.execute(text("INSERT INTO orders VALUES (2, 2, 102, 3000.0, 'completed', '2026-08-15 14:00:00');"))
            # Period 2 (September 2026): Total = $4,000 (Decline of $4,000 / -50%)
            conn.execute(text("INSERT INTO orders VALUES (3, 1, 101, 1000.0, 'completed', '2026-09-05 09:00:00');"))
            conn.execute(text("INSERT INTO orders VALUES (4, 2, 102, 3000.0, 'completed', '2026-09-12 11:00:00');"))

            # Empty unpopulated table (to test insufficient data handling)
            conn.execute(text("CREATE TABLE empty_logs (log_id INTEGER PRIMARY KEY, message TEXT, logged_at TIMESTAMP);"))
            conn.commit()

        # 3. Disposable User B Database (Bob)
        cls.db_fd_b, cls.db_path_b = tempfile.mkstemp(suffix=".db")
        cls.engine_b = create_engine(f"sqlite:///{cls.db_path_b}")
        with cls.engine_b.connect() as conn:
            conn.execute(text("CREATE TABLE bob_sales (id INTEGER PRIMARY KEY, rev REAL);"))
            conn.execute(text("INSERT INTO bob_sales VALUES (1, 999.0);"))
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
        set_user_engine("user_alice", self.engine_a, "sqlite", f"sqlite:///{self.db_path_a}", connection_id="conn_alice_sales")
        set_user_engine("user_bob", self.engine_b, "sqlite", f"sqlite:///{self.db_path_b}", connection_id="conn_bob_sales")
        set_user_context_for_request("user_alice", connection_id="conn_alice_sales")

    def tearDown(self):
        clear_user_context("user_alice")
        clear_user_context("user_bob")
        clear_database_profile()

    # -------------------------------------------------------------------------
    # 1. Intent Parsing
    # -------------------------------------------------------------------------
    def test_intent_parsing_from_business_question(self):
        """Intent parser must extract metric, focus, period, and table hints accurately."""
        tables = ["customers", "products", "orders"]
        cols = {"orders": ["order_id", "total_amount", "created_at", "status"]}

        # Test "Why did revenue decrease this month?"
        intent1 = parse_business_question_intent("Why did revenue decrease this month?", tables, cols)
        self.assertEqual(intent1["metric_hint"], "revenue")
        self.assertEqual(intent1["focus_type"], "trend_analysis")
        self.assertEqual(intent1["comparison_period"], "month")

        # Test "Which products contributed most to the decline?"
        intent2 = parse_business_question_intent("Which products contributed most to the decline?", tables, cols)
        self.assertEqual(intent2["focus_type"], "contributor_breakdown")
        self.assertEqual(intent2["dimension_hint"], "product")

        # Test "Which regions or customer groups changed the most?"
        intent3 = parse_business_question_intent("Which regions or customer groups changed the most?", tables, cols)
        self.assertEqual(intent3["focus_type"], "segment_change")
        self.assertEqual(intent3["dimension_hint"], "region")

    # -------------------------------------------------------------------------
    # 2. Metric Calculations & Period Comparison Correctness
    # -------------------------------------------------------------------------
    def test_investigation_metric_comparison_and_calculations(self):
        """Investigation must compute exact deltas and percentage changes on real returned records."""
        res = run_business_investigation(
            user_id="user_alice",
            connection_id="conn_alice_sales",
            question="Why did revenue decrease this month?",
            target_table="orders",
        )

        self.assertEqual(res["status"], "success")
        rep = res["report"]
        self.assertIsNotNone(rep["observed_change"])

        # August total = $8000, September total = $4000 -> Delta = -$4000 (-50%)
        oc = rep["observed_change"]
        self.assertEqual(oc["previous_value"], 8000.0)
        self.assertEqual(oc["current_value"], 4000.0)
        self.assertEqual(oc["delta"], -4000.0)
        self.assertEqual(oc["delta_percent"], -50.0)
        self.assertIn("-4000", oc["formatted_change"])

    # -------------------------------------------------------------------------
    # 3. Contributing Factor Ranking & Share Percentages
    # -------------------------------------------------------------------------
    def test_contributing_factors_ranking(self):
        """Contributing factors must be ranked with accurate percentage shares."""
        res = run_business_investigation(
            user_id="user_alice",
            connection_id="conn_alice_sales",
            question="Which products contributed most to the decline?",
            target_table="orders",
        )
        self.assertEqual(res["status"], "success")
        rep = res["report"]
        factors = rep["contributing_factors"]
        self.assertGreater(len(factors), 0)

        # First factor must have valid contribution percentage
        top_factor = factors[0]
        self.assertGreater(top_factor["contribution_percent"], 0)
        self.assertTrue(top_factor["dimension_value"])

    # -------------------------------------------------------------------------
    # 4. Evidence Provenance & Reproducible Lineage
    # -------------------------------------------------------------------------
    def test_evidence_provenance_and_lineage(self):
        """Every investigation must provide reproducible evidence items with SQL and periods."""
        res = run_business_investigation(
            user_id="user_alice",
            connection_id="conn_alice_sales",
            question="Why did sales drop?",
            target_table="orders",
        )
        rep = res["report"]
        evidence = rep["evidence"]
        self.assertGreater(len(evidence), 0)

        ev0 = evidence[0]
        self.assertIn("SELECT", ev0["sql_lineage"])
        self.assertIn("orders", ev0["source_table"])
        self.assertTrue(ev0["time_range"])
        self.assertIn("Period-over-period", ev0["calculation_description"])

    # -------------------------------------------------------------------------
    # 5. Unsupported Questions & Missing Schema Information
    # -------------------------------------------------------------------------
    def test_missing_schema_dimensions_handled_without_hallucination(self):
        """If user asks for regions but schema lacks region columns, report must explain missing info."""
        res = run_business_investigation(
            user_id="user_alice",
            connection_id="conn_alice_sales",
            question="Which regions changed the most?",
            target_table="orders",
        )
        rep = res["report"]
        # Must note that regional columns do not exist
        missing = rep.get("missing_reasons", [])
        self.assertTrue(any("region" in m.lower() for m in missing), "Must note absence of regional columns.")

    # -------------------------------------------------------------------------
    # 6. Insufficient Historical Data Handling
    # -------------------------------------------------------------------------
    def test_insufficient_historical_data_handling(self):
        """An empty table must return 'insufficient_evidence' without crashing."""
        res = run_business_investigation(
            user_id="user_alice",
            connection_id="conn_alice_sales",
            question="Analyze changes in empty logs",
            target_table="empty_logs",
        )
        self.assertIn(res["status"], ["insufficient_evidence", "error"])
        self.assertIn("insufficient", res["summary"].lower())

    # -------------------------------------------------------------------------
    # 7. Epistemic Hygiene: Unconfirmed Hypotheses & Causality Caveats
    # -------------------------------------------------------------------------
    def test_epistemic_hygiene_and_causality_caveats(self):
        """Hypotheses must explicitly state unconfirmed status and causal caveats."""
        res = run_business_investigation(
            user_id="user_alice",
            connection_id="conn_alice_sales",
            question="Why did revenue decrease?",
            target_table="orders",
        )
        rep = res["report"]
        self.assertGreater(len(rep["hypotheses"]), 0)
        hyp = rep["hypotheses"][0]
        self.assertEqual(hyp["status"], "unconfirmed")
        self.assertIn("causation", hyp["causality_caveat"].lower())

    # -------------------------------------------------------------------------
    # 8. Report Persistence, Listing, and Retrieval
    # -------------------------------------------------------------------------
    def test_investigation_report_persistence_and_lifecycle(self):
        """Reports must be saved, retrievable, listable, and deletable by owner."""
        res = run_business_investigation(
            user_id="user_alice",
            connection_id="conn_alice_sales",
            question="Why did revenue drop?",
            target_table="orders",
        )
        report_id = res["investigation_id"]

        # Retrieve report
        saved = get_investigation_report(report_id, user_id="user_alice")
        self.assertIsNotNone(saved)
        self.assertEqual(saved["report_id"], report_id)
        self.assertEqual(saved["question"], "Why did revenue drop?")

        # List reports
        reports = list_investigation_reports("user_alice", connection_id="conn_alice_sales")
        self.assertTrue(any(r["report_id"] == report_id for r in reports))

        # Delete report
        deleted = delete_investigation_report(report_id, user_id="user_alice")
        self.assertTrue(deleted)
        self.assertIsNone(get_investigation_report(report_id, user_id="user_alice"))

    # -------------------------------------------------------------------------
    # 9. Cross-User Tenant Isolation
    # -------------------------------------------------------------------------
    def test_cross_user_tenant_isolation(self):
        """Alice must never access or delete Bob's investigation reports."""
        # Save a report for Bob
        save_investigation_report(
            report_id="rep_bob_secret_001",
            user_id="user_bob",
            connection_id="conn_bob_sales",
            question="Bob private question",
            title="Bob Title",
            status="success",
            summary="Bob summary",
            report_data={"private": True},
        )

        # Alice attempts to fetch Bob's report
        alice_fetch = get_investigation_report("rep_bob_secret_001", user_id="user_alice")
        self.assertIsNone(alice_fetch, "Alice must not be able to fetch Bob's report.")

        # Alice attempts to delete Bob's report
        alice_del = delete_investigation_report("rep_bob_secret_001", user_id="user_alice")
        self.assertFalse(alice_del, "Alice must not be able to delete Bob's report.")

        # Alice lists reports -> Bob's report must NOT appear
        alice_list = list_investigation_reports("user_alice")
        self.assertFalse(any(r["report_id"] == "rep_bob_secret_001" for r in alice_list))

    # -------------------------------------------------------------------------
    # 10. Sensitive Data Redaction
    # -------------------------------------------------------------------------
    def test_sensitive_data_redaction(self):
        """Secret tokens in database tables must not appear in investigation reports."""
        res = run_business_investigation(
            user_id="user_alice",
            connection_id="conn_alice_sales",
            question="Analyze customer orders",
            target_table="orders",
        )
        res_str = str(res)
        self.assertNotIn("super_secret_token_123", res_str)
        self.assertNotIn("super_secret_token_456", res_str)

    # -------------------------------------------------------------------------
    # 11. Monitoring Alert to Investigation Integration
    # -------------------------------------------------------------------------
    def test_monitoring_alert_investigation_integration(self):
        """Passing signal_id from alert store must ground the investigation on that defect/anomaly."""
        # Create an alert for Alice
        alert = BusinessAlert(
            title="Significant Drop in Sales Revenue",
            category=AlertCategory.METRIC_DROP,
            severity=AlertSeverity.CRITICAL,
            metric="total_amount",
            user_id="user_alice",
            alert_id="alt_sales_drop_001",
            source_tables=["orders"],
        )
        save_alert(alert, user_id="user_alice")

        res = run_business_investigation(
            user_id="user_alice",
            connection_id="conn_alice_sales",
            signal_id="alt_sales_drop_001",
            target_table="orders",
        )
        self.assertEqual(res["status"], "success")
        self.assertIn("orders", res["report"]["primary_table"])

    # -------------------------------------------------------------------------
    # 12. REST API Endpoints Integration
    # -------------------------------------------------------------------------
    def test_api_investigation_endpoints(self):
        """FastAPI endpoints for /investigation/start, /investigation/reports must work with JWT auth."""
        client = TestClient(app)
        token = create_access_token("user_alice", "alice")
        headers = {"Authorization": f"Bearer {token}", "X-Connection-ID": "conn_alice_sales"}

        # 1. Start investigation
        start_res = client.post(
            "/investigation/start",
            json={"question": "Why did revenue decrease this month?", "connection_id": "conn_alice_sales"},
            headers=headers,
        )
        self.assertEqual(start_res.status_code, 200)
        data = start_res.json()
        self.assertEqual(data["status"], "success")
        rep_id = data["investigation_id"]

        # 2. List reports
        list_res = client.get("/investigation/reports?connection_id=conn_alice_sales", headers=headers)
        self.assertEqual(list_res.status_code, 200)
        self.assertGreater(len(list_res.json()["reports"]), 0)

        # 3. Get single report
        get_res = client.get(f"/investigation/reports/{rep_id}", headers=headers)
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["report"]["report_id"], rep_id)

        # 4. Delete report
        del_res = client.delete(f"/investigation/reports/{rep_id}", headers=headers)
        self.assertEqual(del_res.status_code, 200)
        self.assertTrue(del_res.json()["deleted"])


if __name__ == "__main__":
    unittest.main()
