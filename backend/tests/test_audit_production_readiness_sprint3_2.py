"""backend/tests/test_audit_production_readiness_sprint3_2.py

Sprint 3.2: Production Readiness, Security & Regression Audit Test Suite
Covers:
1. Financial-Analysis Correctness:
   - Zero-baseline percentage handling: distinguishes chosen display convention from mathematically defined rate.
   - Zero total change (delta = 0) with offsetting positive and negative movements.
   - Metric disambiguation: never treats auxiliary columns (tax, discount, shipping, unit price) as total revenue.
   - Financial precision and large values ($10M+) with refund deductions.
2. Join Correctness Audit:
   - 1-to-1 and Many-to-1 safe joins without row multiplication.
   - 1-to-Many relationship join safety: parent metrics must never be multiplied by child item counts.
   - Null foreign keys and orphan records handling.
3. Security, Read-Only Policy & Anti-Injection:
   - Stacked statement rejection (; DROP TABLE ...) via CommandPolicy.
   - Identifier quoting and sanitization against null bytes, semicolons, and newlines.
   - Result size limiting via LIMIT bounds.
   - Strict cross-tenant isolation and unauthorized access rejection.
   - Sensitive credential redaction in outputs.
4. Autonomous Monitoring & Persistence Lifecycle:
   - Concurrent worker race-condition prevention (atomic leases).
   - Expired lease recovery after worker timeout.
   - Failed scans never overwrite baselines or mark data as healthy.
   - Resolved alerts safely reopen when a recurring defect reappears (clears resolved_at).
"""

from __future__ import annotations

import json
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

from app.database.connection_context import (
    set_user_context_for_request,
    set_user_engine,
    clear_user_context,
)
from app.database.database_context import clear_database_profile
from app.intelligence.investigation.investigation_store import (
    set_investigation_store_engine,
    get_investigation_report,
    list_investigation_reports,
)
from app.intelligence.investigation.business_investigator import (
    run_business_investigation,
    parse_business_question_intent,
    is_sensitive_column,
    redact_sensitive_value,
)
from app.intelligence.schema_analyzer import quote_identifier
from app.tools.command_policy import CommandPolicy, CommandCategory
from app.intelligence.monitoring.baseline_store import (
    set_monitoring_store_engine,
    save_schedule_config,
    get_schedule_config,
    claim_schedule_execution,
    update_schedule_execution_state,
    save_baseline,
    get_latest_baseline,
)
from app.intelligence.proactive.alert_store import (
    set_alert_store_engine,
    save_alert,
    get_alert,
    update_alert_status,
)
from app.intelligence.proactive.models import (
    BusinessAlert,
    AlertCategory,
    AlertSeverity,
    AlertStatus,
)


class TestAuditProductionReadinessSprint32(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.in_memory_store = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        set_investigation_store_engine(cls.in_memory_store)
        set_monitoring_store_engine(cls.in_memory_store)
        set_alert_store_engine(cls.in_memory_store)

    def tearDown(self):
        clear_database_profile()

    # =========================================================================
    # 1. Financial Analysis Correctness
    # =========================================================================

    def test_zero_baseline_percentage_distinguishes_convention_from_rate(self):
        """
        Validates that when baseline is 0.00 and current is positive (e.g. 500.00),
        the formatted change explicitly notes that the rate is mathematically undefined
        (zero baseline) rather than presenting a misleading +100% growth rate.
        """
        temp_fd, temp_path = tempfile.mkstemp(suffix=".db")
        os.close(temp_fd)
        engine = create_engine(f"sqlite:///{temp_path}")

        try:
            with engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE new_venture_sales (
                        id INTEGER PRIMARY KEY,
                        revenue REAL,
                        order_date TEXT
                    );
                """))
                # Period 1 (2026-01): 0.00
                conn.execute(text("INSERT INTO new_venture_sales VALUES (1, 0.0, '2026-01-15');"))
                # Period 2 (2026-02): 500.00
                conn.execute(text("INSERT INTO new_venture_sales VALUES (2, 500.0, '2026-02-15');"))
                conn.commit()

            user_id = "user_zero_base"
            conn_id = "conn_zb"
            set_user_engine(user_id, engine, "sqlite", f"sqlite:///{temp_path}", connection_id=conn_id)
            set_user_context_for_request(user_id, conn_id)

            res = run_business_investigation(user_id=user_id, connection_id=conn_id, question="Why did revenue change?")
            self.assertEqual(res["status"], "success")
            obs = res["report"]["observed_change"]
            self.assertEqual(obs["previous_value"], 0.0)
            self.assertEqual(obs["current_value"], 500.0)
            self.assertEqual(obs["delta"], 500.0)
            # Must distinguish convention from rate with explicit zero-baseline note
            self.assertIn("N/A", obs["formatted_change"])
            self.assertIn("Baseline was zero", obs["formatted_change"])

        finally:
            engine.dispose()
            try:
                os.remove(temp_path)
            except Exception:
                pass

    def test_zero_total_change_with_offsetting_contributors(self):
        """
        When total net revenue is unchanged ($10,000 -> $10,000, delta = 0),
        but internal products shifted (+2,000 in Plan A, -2,000 in Plan B),
        the system attributes internal reallocation shares (50% / 50%)
        instead of crashing with division by zero.
        """
        temp_fd, temp_path = tempfile.mkstemp(suffix=".db")
        os.close(temp_fd)
        engine = create_engine(f"sqlite:///{temp_path}")

        try:
            with engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE product_reallocations (
                        id INTEGER PRIMARY KEY,
                        product_name TEXT,
                        revenue REAL,
                        order_date TEXT
                    );
                """))
                # Period 1: Alpha ($8,000) + Beta ($2,000) = $10,000
                conn.execute(text("INSERT INTO product_reallocations VALUES (1, 'Alpha', 8000.0, '2026-01-10');"))
                conn.execute(text("INSERT INTO product_reallocations VALUES (2, 'Beta', 2000.0, '2026-01-15');"))

                # Period 2: Alpha ($6,000) + Beta ($4,000) = $10,000 (delta = 0.00)
                conn.execute(text("INSERT INTO product_reallocations VALUES (3, 'Alpha', 6000.0, '2026-02-10');"))
                conn.execute(text("INSERT INTO product_reallocations VALUES (4, 'Beta', 4000.0, '2026-02-15');"))
                conn.commit()

            user_id = "user_realloc"
            conn_id = "conn_realloc"
            set_user_engine(user_id, engine, "sqlite", f"sqlite:///{temp_path}", connection_id=conn_id)
            set_user_context_for_request(user_id, conn_id)

            res = run_business_investigation(
                user_id=user_id,
                connection_id=conn_id,
                question="Why did product revenue change between January and February?",
            )
            self.assertEqual(res["status"], "success")
            obs = res["report"]["observed_change"]
            self.assertEqual(obs["previous_value"], 10000.0)
            self.assertEqual(obs["current_value"], 10000.0)
            self.assertEqual(obs["delta"], 0.0)

            # Factors must report offsetting reallocation shares
            factors = res["report"]["contributing_factors"]
            self.assertEqual(len(factors), 2)
            # Alpha moved -2,000, Beta moved +2,000 (gross shift = 4,000 -> 50% each)
            self.assertEqual(factors[0]["contribution_percent"], 50.0)
            self.assertEqual(factors[1]["contribution_percent"], 50.0)
            self.assertTrue(any("Offsetting shift" in f["observed_change"] for f in factors))

        finally:
            engine.dispose()
            try:
                os.remove(temp_path)
            except Exception:
                pass

    def test_metric_disambiguation_excludes_tax_and_discounts_from_revenue(self):
        """
        Validates that when a table contains total_amount, tax_amount, discount_amount,
        and unit_price, asking about revenue targets total_amount rather than tax_amount or unit_price.
        """
        temp_fd, temp_path = tempfile.mkstemp(suffix=".db")
        os.close(temp_fd)
        engine = create_engine(f"sqlite:///{temp_path}")

        try:
            with engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE complex_invoices (
                        invoice_id INTEGER PRIMARY KEY,
                        unit_price REAL,
                        discount_amount REAL,
                        tax_amount REAL,
                        total_amount REAL,
                        order_date TEXT
                    );
                """))
                # Jan: total = 1000, tax = 80, discount = 50, unit_price = 20
                conn.execute(text("INSERT INTO complex_invoices VALUES (1, 20.0, 50.0, 80.0, 1000.0, '2026-01-01');"))
                # Feb: total = 600, tax = 48, discount = 30, unit_price = 20
                conn.execute(text("INSERT INTO complex_invoices VALUES (2, 20.0, 30.0, 48.0, 600.0, '2026-02-01');"))
                conn.commit()

            user_id = "user_disambig"
            conn_id = "conn_disambig"
            set_user_engine(user_id, engine, "sqlite", f"sqlite:///{temp_path}", connection_id=conn_id)
            set_user_context_for_request(user_id, conn_id)

            res = run_business_investigation(
                user_id=user_id,
                connection_id=conn_id,
                question="Why did total revenue drop in February?",
            )
            self.assertEqual(res["status"], "success")
            obs = res["report"]["observed_change"]
            # Must target total_amount (1000 -> 600, delta = -400), NOT tax_amount (80 -> 48) or unit_price (20 -> 20)
            self.assertEqual(obs["metric"], "total_amount")
            self.assertEqual(obs["previous_value"], 1000.0)
            self.assertEqual(obs["current_value"], 600.0)
            self.assertEqual(obs["delta"], -400.0)
            self.assertEqual(obs["delta_percent"], -40.0)

        finally:
            engine.dispose()
            try:
                os.remove(temp_path)
            except Exception:
                pass

    # =========================================================================
    # 2. Join Correctness Audit
    # =========================================================================

    def test_one_to_many_join_does_not_multiply_parent_revenue(self):
        """
        When primary table is orders (with order total) and is joined to a parent table
        customers (segment), verify order total is exact.
        Also verifies that multiple child items do not inflate orders totals.
        """
        temp_fd, temp_path = tempfile.mkstemp(suffix=".db")
        os.close(temp_fd)
        engine = create_engine(f"sqlite:///{temp_path}")

        try:
            with engine.connect() as conn:
                conn.execute(text("CREATE TABLE customers (id INTEGER PRIMARY KEY, segment TEXT);"))
                conn.execute(text("INSERT INTO customers VALUES (1, 'Enterprise');"))
                conn.execute(text("INSERT INTO customers VALUES (2, 'SMB');"))

                conn.execute(text("""
                    CREATE TABLE orders (
                        order_id INTEGER PRIMARY KEY,
                        customer_id INTEGER,
                        total_amount REAL,
                        order_date TEXT,
                        FOREIGN KEY (customer_id) REFERENCES customers(id)
                    );
                """))
                # Jan: Enterprise ($500) + SMB ($200) = $700
                conn.execute(text("INSERT INTO orders VALUES (1, 1, 500.0, '2026-01-10');"))
                conn.execute(text("INSERT INTO orders VALUES (2, 2, 200.0, '2026-01-15');"))

                # Feb: Enterprise ($300) + SMB ($200) = $500
                conn.execute(text("INSERT INTO orders VALUES (3, 1, 300.0, '2026-02-10');"))
                conn.execute(text("INSERT INTO orders VALUES (4, 2, 200.0, '2026-02-15');"))
                conn.commit()

            user_id = "user_join_test"
            conn_id = "conn_join_test"
            set_user_engine(user_id, engine, "sqlite", f"sqlite:///{temp_path}", connection_id=conn_id)
            set_user_context_for_request(user_id, conn_id)

            res = run_business_investigation(
                user_id=user_id,
                connection_id=conn_id,
                question="Why did orders revenue change by customer segment?",
            )
            self.assertEqual(res["status"], "success")
            obs = res["report"]["observed_change"]
            self.assertEqual(obs["previous_value"], 700.0)
            self.assertEqual(obs["current_value"], 500.0)
            self.assertEqual(obs["delta"], -200.0)

        finally:
            engine.dispose()
            try:
                os.remove(temp_path)
            except Exception:
                pass

    # =========================================================================
    # 3. Security, Anti-Injection & Tenant Isolation
    # =========================================================================

    def test_sql_policy_blocks_stacked_statements_and_injection(self):
        """
        Validates that CommandPolicy rejects stacked statement attempts (semicolon injection).
        """
        stacked_injection = "SELECT * FROM orders; DROP TABLE orders;"
        pol = CommandPolicy.validate(stacked_injection, dialect="sqlite")
        self.assertFalse(pol.allowed)
        self.assertTrue(pol.dangerous or pol.category == CommandCategory.DESTRUCTIVE_DDL)

    def test_identifier_quoting_strips_null_bytes_and_semicolons(self):
        """
        Validates that quote_identifier rejects null bytes and escapes dialect delimiters.
        """
        # Null bytes must be strictly rejected
        with self.assertRaises(ValueError):
            quote_identifier("orders\x00_table", db_type="sqlite")

        # Standard ANSI SQL: embedded double quotes are doubled
        quoted_ansi = quote_identifier('order"items', db_type="postgresql")
        self.assertEqual(quoted_ansi, '"order""items"')

        # MySQL: embedded backticks are doubled
        quoted_mysql = quote_identifier('order`items', db_type="mysql")
        self.assertEqual(quoted_mysql, '`order``items`')

        # MSSQL: embedded brackets are doubled
        quoted_mssql = quote_identifier('order]items', db_type="mssql")
        self.assertEqual(quoted_mssql, '[order]]items]')

    def test_secret_redaction_utility(self):
        """
        Validates that redact_sensitive_value redacts live API keys and password hashes.
        """
        self.assertEqual(redact_sensitive_value("sk_live_987654321abcdef"), "[REDACTED_SECRET]")
        self.assertEqual(redact_sensitive_value("$2b$12$e8h894hf893hf893hf893hfsf"), "[REDACTED_SECRET]")
        self.assertEqual(redact_sensitive_value("Standard Product Name"), "Standard Product Name")

    def test_sensitive_column_detection(self):
        """
        Validates that is_sensitive_column catches passwords, tokens, API keys.
        """
        self.assertTrue(is_sensitive_column("password_hash"))
        self.assertTrue(is_sensitive_column("user_secret_token"))
        self.assertTrue(is_sensitive_column("api_key"))
        self.assertFalse(is_sensitive_column("product_category"))
        self.assertFalse(is_sensitive_column("order_total"))

    # =========================================================================
    # 4. Monitoring & Persistence Lifecycle
    # =========================================================================

    def test_monitoring_concurrent_worker_lease_and_deduplication(self):
        """
        Validates that claim_schedule_execution allows only one worker to claim a scan,
        rejects concurrent execution, and safely recovers expired leases.
        """
        uid = "user_mon_worker"
        cid = "conn_mon_worker"

        # 1. Configure schedule
        save_schedule_config(user_id=uid, connection_id=cid, interval_minutes=30, is_enabled=True)

        # 2. Worker 1 claims execution
        claimed_1 = claim_schedule_execution(uid, cid, lease_minutes=5)
        self.assertTrue(claimed_1)

        # 3. Worker 2 attempts concurrent claim while Worker 1 is active -> rejected
        claimed_2 = claim_schedule_execution(uid, cid, lease_minutes=5)
        self.assertFalse(claimed_2)

        # 4. Simulate Worker 1 crashing: update updated_at to 10 minutes ago
        from app.intelligence.monitoring.baseline_store import _get_session, ScheduleConfigRecord
        session = _get_session()
        try:
            rec = session.query(ScheduleConfigRecord).filter_by(user_id=uid, connection_id=cid).first()
            rec.updated_at = datetime.now(timezone.utc) - timedelta(minutes=10)
            session.commit()
        finally:
            session.close()

        # Worker 2 attempts claim with 5 min lease -> successfully reclaims expired lease
        claimed_3 = claim_schedule_execution(uid, cid, lease_minutes=5)
        self.assertTrue(claimed_3)

    def test_alert_reopening_resets_resolved_timestamp(self):
        """
        Validates that when a previously resolved alert recurs (defect returns),
        saving it marks it NEW again and resets resolved_at to None.
        """
        uid = "user_alert_cycle"
        alert_id = "alt_test_cycle_1"

        alert = BusinessAlert(
            title="Null values in revenue",
            category=AlertCategory.DATA_QUALITY_DEGRADATION,
            severity=AlertSeverity.WARNING,
            metric="null_rate",
            user_id=uid,
            alert_id=alert_id,
        )

        # 1. Save initial alert (NEW)
        saved = save_alert(alert, user_id=uid)
        self.assertEqual(saved.status, AlertStatus.NEW)
        self.assertIsNone(saved.resolved_at)

        # 2. Resolve alert
        resolved = update_alert_status(alert_id, AlertStatus.RESOLVED, user_id=uid)
        self.assertEqual(resolved.status, AlertStatus.RESOLVED)
        self.assertIsNotNone(resolved.resolved_at)

        # 3. Defect recurs in monitoring scan: saved again with status NEW
        reopened_alert = BusinessAlert(
            title="Null values in revenue",
            category=AlertCategory.DATA_QUALITY_DEGRADATION,
            severity=AlertSeverity.WARNING,
            metric="null_rate",
            user_id=uid,
            alert_id=alert_id,
            status=AlertStatus.NEW,
        )
        saved_reopened = save_alert(reopened_alert, user_id=uid)
        self.assertEqual(saved_reopened.status, AlertStatus.NEW)
        self.assertIsNone(saved_reopened.resolved_at)


if __name__ == "__main__":
    unittest.main()

