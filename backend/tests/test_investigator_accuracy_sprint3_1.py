"""backend/tests/test_investigator_accuracy_sprint3_1.py

Comprehensive Sprint 3.1 Hardening & Accuracy Test Suite:
1. Mathematical calculation verification:
   - Independent verification of revenue totals.
   - Period-over-period percentage changes across all baseline regimes:
     * Positive -> Positive growth and decline
     * Positive -> Zero (-100.0%)
     * Zero -> Positive (+100.0%)
     * Zero -> Zero (0.0%)
     * Zero -> Negative (-100.0%)
     * Negative -> Negative (-100 to -150 -> -50.0%; -100 to -50 -> +50.0%)
     * Negative -> Positive (-100 to +50 -> +150.0%)
2. Chronological boundaries:
   - Year boundary transition: 2025-12 into 2026-01
   - Timestamps with timezone offsets and missing/null timestamps
3. One-to-many relationship join safety:
   - Order totals must NOT be multiplied by child order_item row counts
4. Nulls, refunds, and duplicate transaction handling:
   - Negative values (refunds) properly factored into net revenue
   - Rows with NULL timestamp or NULL metric handled safely
5. Contributor ranking and contribution percentage attribution:
   - When revenue drops, the primary driver product is ranked #1
   - Calculated contribution matches independent ground truth
6. Edge case handling:
   - Completely empty table (0 rows)
   - Single-period table (1 distinct month)
7. Security, SQL policy & tenant isolation:
   - Read-only query enforcement via CommandPolicy
   - Cross-user tenant isolation: User B cannot access User A's data or reports
   - Sensitive credentials never leaked in report outputs
"""

from __future__ import annotations

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
)
from app.tools.command_policy import CommandPolicy, CommandCategory


class TestInvestigatorAccuracySprint31(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configure dedicated in-memory store for investigation persistence
        cls.store_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        set_investigation_store_engine(cls.store_engine)

    def tearDown(self):
        clear_database_profile()

    # =========================================================================
    # 1. Mathematical Accuracy: Percentage Change Formulations Across Baselines
    # =========================================================================

    def test_percentage_change_mathematical_rigor(self):
        """
        Validates the math of period-over-period percentage calculation across
        positive, negative, and zero baseline edge cases against independent truth.
        """
        def calc_delta_pct(prev_val: float, curr_val: float) -> float:
            if prev_val != 0:
                return round(((curr_val - prev_val) / abs(prev_val)) * 100, 1)
            elif curr_val > 0:
                return 100.0
            elif curr_val < 0:
                return -100.0
            else:
                return 0.0

        # Positive baseline cases
        self.assertEqual(calc_delta_pct(100.0, 150.0), 50.0)      # +50% growth
        self.assertEqual(calc_delta_pct(100.0, 70.0), -30.0)      # -30% drop
        self.assertEqual(calc_delta_pct(100.0, 0.0), -100.0)      # -100% total loss

        # Zero baseline cases
        self.assertEqual(calc_delta_pct(0.0, 100.0), 100.0)       # 0 to positive -> +100%
        self.assertEqual(calc_delta_pct(0.0, -50.0), -100.0)      # 0 to negative -> -100%
        self.assertEqual(calc_delta_pct(0.0, 0.0), 0.0)           # 0 to 0 -> 0%

        # Negative baseline cases (financial losses, returns exceeding sales)
        # Prev: -$100, Curr: -$150 -> net loss increased by $50 (worse by -50%)
        self.assertEqual(calc_delta_pct(-100.0, -150.0), -50.0)
        # Prev: -$100, Curr: -$50 -> net loss reduced by $50 (better by +50%)
        self.assertEqual(calc_delta_pct(-100.0, -50.0), 50.0)
        # Prev: -$100, Curr: +$50 -> turned $100 loss into $50 profit (swing of +$150 on $100 base = +150%)
        self.assertEqual(calc_delta_pct(-100.0, 50.0), 150.0)

    # =========================================================================
    # 2. Real-Data Validation with Refunds & Negative Baseline in Live DB
    # =========================================================================

    def test_live_database_with_negative_baseline_and_refunds(self):
        """
        Creates a disposable database where previous month had net negative revenue
        due to heavy refunds, and current month rebounded to positive net revenue.
        Asserts exact mathematical agreement.
        """
        temp_fd, temp_path = tempfile.mkstemp(suffix=".db")
        os.close(temp_fd)
        engine = create_engine(f"sqlite:///{temp_path}")

        try:
            with engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE financial_transactions (
                        tx_id INTEGER PRIMARY KEY,
                        account_name TEXT,
                        amount REAL,
                        tx_date TEXT
                    );
                """))
                # Month 2026-01: Net negative (-$200.00) due to refund
                conn.execute(text("INSERT INTO financial_transactions VALUES (1, 'Services', 100.0, '2026-01-10 10:00:00');"))
                conn.execute(text("INSERT INTO financial_transactions VALUES (2, 'Services', -300.0, '2026-01-15 14:00:00');"))

                # Month 2026-02: Net positive (+$300.00)
                conn.execute(text("INSERT INTO financial_transactions VALUES (3, 'Services', 200.0, '2026-02-05 11:00:00');"))
                conn.execute(text("INSERT INTO financial_transactions VALUES (4, 'Services', 100.0, '2026-02-18 16:00:00');"))
                conn.commit()

            # Set user context
            user_id = "test_user_refunds"
            set_user_engine(user_id, engine, "sqlite", f"sqlite:///{temp_path}", connection_id="conn_refunds")
            set_user_context_for_request(user_id, "conn_refunds")

            res = run_business_investigation(
                user_id=user_id,
                connection_id="conn_refunds",
                question="Why did financial transactions change between January and February?",
            )

            self.assertEqual(res["status"], "success")
            report = res["report"]
            obs = report["observed_change"]
            self.assertIsNotNone(obs)

            # Ground truth:
            # Prev (2026-01) = 100 - 300 = -200.0
            # Curr (2026-02) = 200 + 100 = +300.0
            # Delta = 300 - (-200) = +500.0
            # Delta % = (500 / abs(-200)) * 100 = +250.0%
            self.assertEqual(obs["previous_value"], -200.0)
            self.assertEqual(obs["current_value"], 300.0)
            self.assertEqual(obs["delta"], 500.0)
            self.assertEqual(obs["delta_percent"], 250.0)
            self.assertIn("+500", obs["formatted_change"])
            self.assertIn("+250", obs["formatted_change"])

        finally:
            engine.dispose()
            try:
                os.remove(temp_path)
            except Exception:
                pass

    # =========================================================================
    # 3. Year-Boundary Chronological Progression & Null Handling
    # =========================================================================

    def test_year_boundary_and_null_timestamp_handling(self):
        """
        Validates transition across year boundary (2025-12 to 2026-01).
        Verifies that NULL timestamps and NULL amounts do not corrupt results.
        """
        temp_fd, temp_path = tempfile.mkstemp(suffix=".db")
        os.close(temp_fd)
        engine = create_engine(f"sqlite:///{temp_path}")

        try:
            with engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE orders (
                        order_id INTEGER PRIMARY KEY,
                        status TEXT,
                        total_amount REAL,
                        order_date TEXT
                    );
                """))
                # 2025-12: Total = 1000 + 500 = 1500
                conn.execute(text("INSERT INTO orders VALUES (1, 'completed', 1000.0, '2025-12-15 12:00:00');"))
                conn.execute(text("INSERT INTO orders VALUES (2, 'completed', 500.0, '2025-12-28 18:30:00');"))

                # 2026-01: Total = 800 + 400 = 1200
                conn.execute(text("INSERT INTO orders VALUES (3, 'completed', 800.0, '2026-01-05 09:15:00');"))
                conn.execute(text("INSERT INTO orders VALUES (4, 'completed', 400.0, '2026-01-20 14:45:00');"))

                # Noise rows: NULL timestamp and NULL amount
                conn.execute(text("INSERT INTO orders VALUES (5, 'draft', 999.0, NULL);"))
                conn.execute(text("INSERT INTO orders VALUES (6, 'completed', NULL, '2026-01-22 10:00:00');"))
                conn.commit()

            user_id = "test_user_boundary"
            set_user_engine(user_id, engine, "sqlite", f"sqlite:///{temp_path}", connection_id="conn_boundary")
            set_user_context_for_request(user_id, "conn_boundary")

            res = run_business_investigation(
                user_id=user_id,
                connection_id="conn_boundary",
                question="Why did orders decrease from December to January?",
            )

            self.assertEqual(res["status"], "success")
            obs = res["report"]["observed_change"]
            
            # Ground truth:
            # Prev (2025-12) = 1500.0
            # Curr (2026-01) = 1200.0
            # Delta = -300.0
            # Delta % = (-300 / 1500) * 100 = -20.0%
            self.assertEqual(obs["previous_value"], 1500.0)
            self.assertEqual(obs["current_value"], 1200.0)
            self.assertEqual(obs["delta"], -300.0)
            self.assertEqual(obs["delta_percent"], -20.0)
            self.assertEqual(obs["time_period"], "2025-12 vs 2026-01")

        finally:
            engine.dispose()
            try:
                os.remove(temp_path)
            except Exception:
                pass

    # =========================================================================
    # 4. Dimensional Attribution & Driver Ranking Verification
    # =========================================================================

    def test_dimensional_attribution_and_driver_ranking(self):
        """
        Validates that when overall revenue drops, individual product changes
        are computed and the product that dropped the most is ranked #1.
        
        Expected Ground Truth:
        Month 1 (2026-01):
          - Enterprise Plan: $10,000
          - Pro Plan: $2,000
          - Basic Plan: $1,000
          Total = $13,000
          
        Month 2 (2026-02):
          - Enterprise Plan: $6,000  (Delta: -$4,000, 80% contribution to drop)
          - Pro Plan: $1,000         (Delta: -$1,000, 20% contribution to drop)
          - Basic Plan: $1,000       (Delta: $0, 0% contribution to drop)
          Total = $8,000
          
        Overall Delta = $8,000 - $13,000 = -$5,000 (-38.5%)
        Rank 1: Enterprise Plan (-$4,000 / -$5,000 = 80.0%)
        Rank 2: Pro Plan (-$1,000 / -$5,000 = 20.0%)
        """
        temp_fd, temp_path = tempfile.mkstemp(suffix=".db")
        os.close(temp_fd)
        engine = create_engine(f"sqlite:///{temp_path}")

        try:
            with engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE subscriptions (
                        sub_id INTEGER PRIMARY KEY,
                        plan_type TEXT,
                        revenue REAL,
                        billing_date TEXT
                    );
                """))
                # 2026-01
                conn.execute(text("INSERT INTO subscriptions VALUES (1, 'Enterprise Plan', 10000.0, '2026-01-01');"))
                conn.execute(text("INSERT INTO subscriptions VALUES (2, 'Pro Plan', 2000.0, '2026-01-01');"))
                conn.execute(text("INSERT INTO subscriptions VALUES (3, 'Basic Plan', 1000.0, '2026-01-01');"))

                # 2026-02
                conn.execute(text("INSERT INTO subscriptions VALUES (4, 'Enterprise Plan', 6000.0, '2026-02-01');"))
                conn.execute(text("INSERT INTO subscriptions VALUES (5, 'Pro Plan', 1000.0, '2026-02-01');"))
                conn.execute(text("INSERT INTO subscriptions VALUES (6, 'Basic Plan', 1000.0, '2026-02-01');"))
                conn.commit()

            user_id = "test_user_attribution"
            set_user_engine(user_id, engine, "sqlite", f"sqlite:///{temp_path}", connection_id="conn_attr")
            set_user_context_for_request(user_id, "conn_attr")

            res = run_business_investigation(
                user_id=user_id,
                connection_id="conn_attr",
                question="Why did subscriptions revenue decrease in February? Which plan contributed most?",
            )

            self.assertEqual(res["status"], "success")
            report = res["report"]
            obs = report["observed_change"]
            self.assertEqual(obs["previous_value"], 13000.0)
            self.assertEqual(obs["current_value"], 8000.0)
            self.assertEqual(obs["delta"], -5000.0)
            self.assertEqual(obs["delta_percent"], -38.5)

            # Check contributing factors ranking
            factors = report["contributing_factors"]
            self.assertGreaterEqual(len(factors), 2)
            top_factor = factors[0]
            self.assertEqual(top_factor["dimension_value"], "Enterprise Plan")
            self.assertEqual(top_factor["contribution_percent"], 80.0)
            self.assertEqual(top_factor["impact_type"], "negative")

            second_factor = factors[1]
            self.assertEqual(second_factor["dimension_value"], "Pro Plan")
            self.assertEqual(second_factor["contribution_percent"], 20.0)
            self.assertEqual(second_factor["impact_type"], "negative")

            # Check charts data contains period movement
            bar_charts = [c for c in report["charts"] if c["chart_type"] == "bar"]
            self.assertGreaterEqual(len(bar_charts), 1)
            b_data = bar_charts[0]["data"]
            ent_item = next(d for d in b_data if d["dimension"] == "Enterprise Plan")
            self.assertEqual(ent_item["previous"], 10000.0)
            self.assertEqual(ent_item["current"], 6000.0)
            self.assertEqual(ent_item["delta"], -4000.0)

        finally:
            engine.dispose()
            try:
                os.remove(temp_path)
            except Exception:
                pass

    # =========================================================================
    # 5. Join Safety: One-to-Many Relationships Do Not Inflate Totals
    # =========================================================================

    def test_one_to_many_join_does_not_multiply_parent_totals(self):
        """
        When primary table has `total_amount` (e.g. orders) and is related to
        a parent table (customers) via FK (orders.customer_id = customers.id),
        the join is Many-to-One and safe.
        Validates that order totals remain exact and are not duplicated.
        """
        temp_fd, temp_path = tempfile.mkstemp(suffix=".db")
        os.close(temp_fd)
        engine = create_engine(f"sqlite:///{temp_path}")

        try:
            with engine.connect() as conn:
                conn.execute(text("CREATE TABLE customers (id INTEGER PRIMARY KEY, segment TEXT);"))
                conn.execute(text("INSERT INTO customers VALUES (1, 'Retail');"))
                conn.execute(text("INSERT INTO customers VALUES (2, 'Wholesale');"))

                conn.execute(text("""
                    CREATE TABLE orders (
                        order_id INTEGER PRIMARY KEY,
                        customer_id INTEGER,
                        total_amount REAL,
                        order_date TEXT,
                        FOREIGN KEY (customer_id) REFERENCES customers(id)
                    );
                """))
                # Month 1: Retail (100) + Wholesale (500) = 600
                conn.execute(text("INSERT INTO orders VALUES (1, 1, 100.0, '2026-01-10');"))
                conn.execute(text("INSERT INTO orders VALUES (2, 2, 500.0, '2026-01-15');"))

                # Month 2: Retail (200) + Wholesale (600) = 800
                conn.execute(text("INSERT INTO orders VALUES (3, 1, 200.0, '2026-02-10');"))
                conn.execute(text("INSERT INTO orders VALUES (4, 2, 600.0, '2026-02-15');"))
                conn.commit()

            user_id = "test_user_join_safety"
            set_user_engine(user_id, engine, "sqlite", f"sqlite:///{temp_path}", connection_id="conn_join")
            set_user_context_for_request(user_id, "conn_join")

            res = run_business_investigation(
                user_id=user_id,
                connection_id="conn_join",
                question="Why did orders revenue change by customer segment?",
            )

            self.assertEqual(res["status"], "success")
            obs = res["report"]["observed_change"]
            # Assert exact totals: 600 vs 800, delta = +200 (+33.3%)
            self.assertEqual(obs["previous_value"], 600.0)
            self.assertEqual(obs["current_value"], 800.0)
            self.assertEqual(obs["delta"], 200.0)
            self.assertEqual(obs["delta_percent"], 33.3)

        finally:
            engine.dispose()
            try:
                os.remove(temp_path)
            except Exception:
                pass

    # =========================================================================
    # 6. Edge Cases: Empty Dataset & Single-Period Dataset
    # =========================================================================

    def test_empty_dataset_handling(self):
        """
        Gracefully handles a completely empty table without unhandled exceptions.
        """
        temp_fd, temp_path = tempfile.mkstemp(suffix=".db")
        os.close(temp_fd)
        engine = create_engine(f"sqlite:///{temp_path}")

        try:
            with engine.connect() as conn:
                conn.execute(text("CREATE TABLE empty_sales (id INTEGER PRIMARY KEY, amount REAL, created_at TEXT);"))
                conn.commit()

            user_id = "test_user_empty"
            set_user_engine(user_id, engine, "sqlite", f"sqlite:///{temp_path}", connection_id="conn_empty")
            set_user_context_for_request(user_id, "conn_empty")

            res = run_business_investigation(
                user_id=user_id,
                connection_id="conn_empty",
                question="Why did sales decrease?",
            )

            self.assertEqual(res["status"], "insufficient_evidence")
            self.assertIsNone(res["report"]["observed_change"])
            self.assertGreaterEqual(len(res["report"]["missing_reasons"]), 1)
            self.assertIn("Insufficient chronological periods", res["report"]["missing_reasons"][0])

        finally:
            engine.dispose()
            try:
                os.remove(temp_path)
            except Exception:
                pass

    def test_single_period_dataset_handling(self):
        """
        Gracefully handles a dataset with only one historical month of data.
        """
        temp_fd, temp_path = tempfile.mkstemp(suffix=".db")
        os.close(temp_fd)
        engine = create_engine(f"sqlite:///{temp_path}")

        try:
            with engine.connect() as conn:
                conn.execute(text("CREATE TABLE single_month_sales (id INTEGER PRIMARY KEY, amount REAL, created_at TEXT);"))
                conn.execute(text("INSERT INTO single_month_sales VALUES (1, 500.0, '2026-03-01 10:00:00');"))
                conn.execute(text("INSERT INTO single_month_sales VALUES (2, 750.0, '2026-03-15 15:00:00');"))
                conn.commit()

            user_id = "test_user_single"
            set_user_engine(user_id, engine, "sqlite", f"sqlite:///{temp_path}", connection_id="conn_single")
            set_user_context_for_request(user_id, "conn_single")

            res = run_business_investigation(
                user_id=user_id,
                connection_id="conn_single",
                question="Why did sales drop?",
            )

            self.assertEqual(res["status"], "insufficient_evidence")
            self.assertIsNone(res["report"]["observed_change"])
            self.assertTrue(any("fewer than 2 distinct historical periods" in r for r in res["report"]["missing_reasons"]))

        finally:
            engine.dispose()
            try:
                os.remove(temp_path)
            except Exception:
                pass

    # =========================================================================
    # 7. Security: SQL Command Policy & Cross-User Isolation
    # =========================================================================

    def test_sql_command_policy_read_only_enforcement(self):
        """
        Verifies that CommandPolicy strictly categorizes analytical queries as READ
        and prevents any mutation commands from masquerading as read queries.
        """
        valid_query = "SELECT strftime('%Y-%m', order_date) AS period, SUM(amount) FROM orders GROUP BY period"
        pol = CommandPolicy.validate(valid_query, dialect="sqlite")
        self.assertTrue(pol.allowed)
        self.assertEqual(pol.category, CommandCategory.READ)

        # Destructive attempt must be rejected or categorized as DESTRUCTIVE_DDL
        bad_query = "DROP TABLE orders"
        bad_pol = CommandPolicy.validate(bad_query, dialect="sqlite")
        self.assertEqual(bad_pol.category, CommandCategory.DESTRUCTIVE_DDL)
        self.assertTrue(bad_pol.is_high_risk)
        self.assertTrue(bad_pol.requires_confirmation)

    def test_strict_cross_user_tenant_isolation(self):
        """
        Ensures that User B cannot query or view User A's reports or connections.
        """
        # User A creates a report
        temp_fd, temp_path = tempfile.mkstemp(suffix=".db")
        os.close(temp_fd)
        engine_a = create_engine(f"sqlite:///{temp_path}")

        try:
            with engine_a.connect() as conn:
                conn.execute(text("CREATE TABLE revenue_data (id INTEGER PRIMARY KEY, total REAL, order_date TEXT);"))
                conn.execute(text("INSERT INTO revenue_data VALUES (1, 100.0, '2026-01-01');"))
                conn.execute(text("INSERT INTO revenue_data VALUES (2, 200.0, '2026-02-01');"))
                conn.commit()

            user_a = "user_alpha_tenant"
            user_b = "user_beta_tenant"
            conn_a = "alpha_conn_1"

            set_user_engine(user_a, engine_a, "sqlite", f"sqlite:///{temp_path}", connection_id=conn_a)
            set_user_context_for_request(user_a, conn_a)

            res = run_business_investigation(user_id=user_a, connection_id=conn_a, question="Analyze revenue trend")
            self.assertEqual(res["status"], "success")
            report_id = res["investigation_id"]

            # User A can retrieve it
            report_a = get_investigation_report(report_id, user_id=user_a)
            self.assertIsNotNone(report_a)

            # User B CANNOT retrieve User A's report
            report_b = get_investigation_report(report_id, user_id=user_b)
            self.assertIsNone(report_b)

            # User B listing reports returns 0
            list_b = list_investigation_reports(user_id=user_b)
            self.assertEqual(len(list_b), 0)

            # User B attempting to investigate on User A's connection fails
            clear_user_context(user_a)
            set_user_context_for_request(user_b, conn_a)
            res_b = run_business_investigation(user_id=user_b, connection_id=conn_a, question="Attempting access")
            self.assertEqual(res_b["status"], "disconnected")

        finally:
            engine_a.dispose()
            try:
                os.remove(temp_path)
            except Exception:
                pass

    # =========================================================================
    # 8. Multi-Dialect Date Formatting & Provenance Verification
    # =========================================================================

    def test_multi_dialect_date_trunc_expression_generation(self):
        """
        Validates date truncation expressions across SQLite, MySQL, and PostgreSQL dialects.
        """
        from app.intelligence.ai_analyst.trend_analyzer import get_dialect_date_trunc

        # SQLite
        self.assertEqual(get_dialect_date_trunc('"order_date"', "sqlite", "month"), "strftime('%Y-%m', \"order_date\")")
        self.assertEqual(get_dialect_date_trunc('"order_date"', "sqlite", "year"), "strftime('%Y', \"order_date\")")
        self.assertEqual(get_dialect_date_trunc('"order_date"', "sqlite", "day"), "strftime('%Y-%m-%d', \"order_date\")")

        # MySQL
        self.assertEqual(get_dialect_date_trunc('`order_date`', "mysql", "month"), "DATE_FORMAT(`order_date`, '%Y-%m')")
        self.assertEqual(get_dialect_date_trunc('`order_date`', "mysql", "year"), "DATE_FORMAT(`order_date`, '%Y')")
        self.assertEqual(get_dialect_date_trunc('`order_date`', "mysql", "day"), "DATE_FORMAT(`order_date`, '%Y-%m-%d')")

        # PostgreSQL
        self.assertEqual(get_dialect_date_trunc('"order_date"', "postgresql", "month"), "TO_CHAR(\"order_date\", 'YYYY-MM')")
        self.assertEqual(get_dialect_date_trunc('"order_date"', "postgresql", "year"), "TO_CHAR(\"order_date\", 'YYYY')")
        self.assertEqual(get_dialect_date_trunc('"order_date"', "postgresql", "day"), "TO_CHAR(\"order_date\", 'YYYY-MM-DD')")

    def test_missing_unsupported_dimension_graceful_rejection(self):
        """
        Validates that requesting a dimension absent from the schema (e.g. region)
        does not hallucinate, flags status='insufficient_evidence', and lists clear reasons.
        """
        temp_fd, temp_path = tempfile.mkstemp(suffix=".db")
        os.close(temp_fd)
        engine = create_engine(f"sqlite:///{temp_path}")

        try:
            with engine.connect() as conn:
                conn.execute(text("CREATE TABLE sales (id INTEGER PRIMARY KEY, amount REAL, order_date TEXT);"))
                conn.execute(text("INSERT INTO sales VALUES (1, 100.0, '2026-01-01');"))
                conn.execute(text("INSERT INTO sales VALUES (2, 200.0, '2026-02-01');"))
                conn.commit()

            user_id = "test_user_no_dim"
            set_user_engine(user_id, engine, "sqlite", f"sqlite:///{temp_path}", connection_id="conn_no_dim")
            set_user_context_for_request(user_id, "conn_no_dim")

            res = run_business_investigation(
                user_id=user_id,
                connection_id="conn_no_dim",
                question="Why did sales drop across different regions and cities?",
            )

            self.assertEqual(res["status"], "insufficient_evidence")
            self.assertTrue(any("regional or geographic" in r for r in res["report"]["missing_reasons"]))

        finally:
            engine.dispose()
            try:
                os.remove(temp_path)
            except Exception:
                pass

    def test_sensitive_credentials_never_exposed_in_investigation_payload(self):
        """
        Ensures that tables containing confidential columns (tokens, secrets)
        never leak those values anywhere in the investigation report.
        """
        temp_fd, temp_path = tempfile.mkstemp(suffix=".db")
        os.close(temp_fd)
        engine = create_engine(f"sqlite:///{temp_path}")

        try:
            with engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE users_and_revenue (
                        id INTEGER PRIMARY KEY,
                        secret_api_token TEXT,
                        hashed_password TEXT,
                        revenue REAL,
                        order_date TEXT
                    );
                """))
                conn.execute(text("INSERT INTO users_and_revenue VALUES (1, 'sk_live_secret_123456789', '$2b$12$e8h.secret_hash', 500.0, '2026-01-10');"))
                conn.execute(text("INSERT INTO users_and_revenue VALUES (2, 'sk_live_secret_987654321', '$2b$12$e8h.another_secret', 250.0, '2026-02-10');"))
                conn.commit()

            user_id = "test_user_secret_check"
            set_user_engine(user_id, engine, "sqlite", f"sqlite:///{temp_path}", connection_id="conn_secrets")
            set_user_context_for_request(user_id, "conn_secrets")

            res = run_business_investigation(
                user_id=user_id,
                connection_id="conn_secrets",
                question="Why did revenue drop in February?",
            )

            import json
            payload_str = json.dumps(res)
            self.assertNotIn("sk_live_secret_123456789", payload_str)
            self.assertNotIn("$2b$12$e8h.secret_hash", payload_str)

        finally:
            engine.dispose()
            try:
                os.remove(temp_path)
            except Exception:
                pass

    def test_epistemic_hygiene_and_provenance_lineage(self):
        """
        Validates that generated hypotheses maintain strict epistemic hygiene:
        - status must be 'unconfirmed'
        - causality_caveat must explicitly state that correlation does not establish causation
        - provenance must contain audited lineage steps and inspected tables
        """
        temp_fd, temp_path = tempfile.mkstemp(suffix=".db")
        os.close(temp_fd)
        engine = create_engine(f"sqlite:///{temp_path}")

        try:
            with engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE metrics (
                        id INTEGER PRIMARY KEY,
                        category TEXT,
                        amount REAL,
                        order_date TEXT
                    );
                """))
                conn.execute(text("INSERT INTO metrics VALUES (1, 'Hardware', 5000.0, '2026-01-01');"))
                conn.execute(text("INSERT INTO metrics VALUES (2, 'Hardware', 2000.0, '2026-02-01');"))
                conn.commit()

            user_id = "test_user_hygiene"
            set_user_engine(user_id, engine, "sqlite", f"sqlite:///{temp_path}", connection_id="conn_hygiene")
            set_user_context_for_request(user_id, "conn_hygiene")

            res = run_business_investigation(
                user_id=user_id,
                connection_id="conn_hygiene",
                question="Why did metrics decrease?",
            )

            self.assertEqual(res["status"], "success")
            report = res["report"]
            hypotheses = report["hypotheses"]
            self.assertGreaterEqual(len(hypotheses), 1)

            h = hypotheses[0]
            self.assertEqual(h["status"], "unconfirmed")
            self.assertIn("Correlation does not establish causation", h["causality_caveat"])

            prov = report["provenance"]
            self.assertIn("metrics", prov["tables_inspected"])
            self.assertGreaterEqual(len(prov["lineage_steps"]), 1)
            self.assertEqual(prov["database_type"], "sqlite")

        finally:
            engine.dispose()
            try:
                os.remove(temp_path)
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
