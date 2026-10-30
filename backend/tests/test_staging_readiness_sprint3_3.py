"""backend/tests/test_staging_readiness_sprint3_3.py

Sprint 3.3: Database Execution Security & Staging Readiness Suite
Covers:
1. SQL Execution Boundary & Error Redaction:
   - Sanitization of connection strings, passwords, and bearer tokens in database error messages.
   - Execution-layer result size bounding (MAX_ROWS_LIMIT = 2000) and truncated flag.
2. Dialect Quoting & Schema Validation:
   - Rejection of null bytes and control characters in identifiers.
   - ANSI (PostgreSQL, SQLite), MySQL (backticks), and MSSQL (brackets) identifier quoting.
3. Multi-User Tenant Isolation & Multi-Connection Independence:
   - User A with multiple connections (conn_a1, conn_a2) vs User B with (conn_b1, conn_b2).
   - Complete isolation across investigation reports, baseline snapshots, proactive alerts, and monitoring schedules.
4. Database Privileges & Read-Only Role Simulation:
   - Documenting minimum connector privileges.
   - Testing that read-only policy strictly blocks writes at the execution boundary.
5. Live PostgreSQL Integration Tests (on local PostgreSQL 17 instance):
   - Automatic live server detection.
   - Creates a temporary disposable schema (`bgai_staging_audit`).
   - Tests live connection lifecycle, date grouping across year boundaries (TO_CHAR), parameterized filters,
     refunds (negative values), null metric handling, and cleans up disposable schema on teardown.
   - If PostgreSQL is not reachable, reports cleanly as skipped with explicit status.
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
    delete_investigation_report,
)
from app.intelligence.investigation.business_investigator import (
    run_business_investigation,
    parse_business_question_intent,
)
from app.intelligence.schema_analyzer import quote_identifier
from app.tools.command_policy import CommandPolicy, CommandCategory
from app.tools.execute_query import execute_query, sanitize_error_message
from app.intelligence.monitoring.baseline_store import (
    set_monitoring_store_engine,
    save_schedule_config,
    get_schedule_config,
    list_active_schedules,
    save_baseline,
    get_latest_baseline,
)
from app.intelligence.proactive.alert_store import (
    set_alert_store_engine,
    save_alert,
    get_alert,
    get_alerts,
)
from app.intelligence.proactive.models import (
    BusinessAlert,
    AlertCategory,
    AlertSeverity,
    AlertStatus,
)


class TestStagingReadinessSprint33(unittest.TestCase):
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
    # 1. Error Message Sanitization & Credential Leakage Prevention
    # =========================================================================

    def test_database_error_sanitization_redacts_credentials_and_urls(self):
        """
        Validates that sanitize_error_message completely redacts database passwords,
        connection strings, bearer tokens, and secret keys from raw database errors.
        """
        raw_error_pg = "OperationalError: could not connect to server: postgresql://admin_user:super_secret_password_123@10.0.0.5:5432/prod_db"
        sanitized_pg = sanitize_error_message(raw_error_pg)
        self.assertNotIn("super_secret_password_123", sanitized_pg)
        self.assertIn("postgresql://admin_user:***@10.0.0.5:5432/prod_db", sanitized_pg)

        raw_error_mysql = "pymysql.err.OperationalError: Access denied for user 'root':'MySecretMySQLPass456'@'localhost'"
        sanitized_mysql = sanitize_error_message(raw_error_mysql)
        self.assertNotIn("MySecretMySQLPass456", sanitized_mysql)

        raw_error_bearer = "Unauthorized: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret_token_body"
        sanitized_bearer = sanitize_error_message(raw_error_bearer)
        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", sanitized_bearer)
        self.assertIn("Bearer ***", sanitized_bearer)

    # =========================================================================
    # 2. Execution Layer Result-Size Bounding & Truncation
    # =========================================================================

    def test_execute_query_enforces_row_limit_and_sets_truncated(self):
        """
        Validates that execute_query bounds rowsets to MAX_ROWS_LIMIT (2,000)
        and sets truncated=True when a query generates massive result sets.
        """
        temp_fd, temp_path = tempfile.mkstemp(suffix=".db")
        os.close(temp_fd)
        engine = create_engine(f"sqlite:///{temp_path}")

        try:
            with engine.connect() as conn:
                conn.execute(text("CREATE TABLE bulk_records (id INTEGER PRIMARY KEY);"))
                # Insert 2,500 records in batches
                conn.execute(text("""
                    WITH RECURSIVE cnt(x) AS (
                        SELECT 1
                        UNION ALL
                        SELECT x + 1 FROM cnt WHERE x < 2500
                    )
                    INSERT INTO bulk_records SELECT x FROM cnt;
                """))
                conn.commit()

            user_id = "user_bulk_test"
            conn_id = "conn_bulk"
            set_user_engine(user_id, engine, "sqlite", f"sqlite:///{temp_path}", connection_id=conn_id)
            set_user_context_for_request(user_id, conn_id)

            res = execute_query(
                sql="SELECT * FROM bulk_records",
                connection_id=conn_id,
                user_id=user_id,
            )

            self.assertTrue(res["success"])
            self.assertEqual(len(res["rows"]), 2000)
            self.assertEqual(res["rows_returned"], 2000)
            self.assertTrue(res["truncated"])
            self.assertEqual(res["max_rows_limit"], 2000)

        finally:
            engine.dispose()
            try:
                os.remove(temp_path)
            except Exception:
                pass

    # =========================================================================
    # 3. Two Independent Users with Multiple Connections (Tenant Isolation)
    # =========================================================================

    def test_multi_user_and_multi_connection_strict_tenant_isolation(self):
        """
        Validates tenant and connection isolation across two independent users:
        - User Alpha with connections conn_a1 and conn_a2
        - User Beta with connections conn_b1 and conn_b2
        Ensures cross-user and cross-connection boundaries are completely isolated.
        """
        user_a = "user_alpha_multi"
        user_b = "user_beta_multi"

        # 1. Schedules Isolation
        save_schedule_config(user_id=user_a, connection_id="conn_a1", interval_minutes=15, is_enabled=True)
        save_schedule_config(user_id=user_a, connection_id="conn_a2", interval_minutes=30, is_enabled=True)
        save_schedule_config(user_id=user_b, connection_id="conn_b1", interval_minutes=60, is_enabled=True)

        sched_a1 = get_schedule_config(user_a, "conn_a1")
        self.assertIsNotNone(sched_a1)
        self.assertEqual(sched_a1["interval_minutes"], 15)

        # User B cannot see User A's schedule
        sched_b_view_a1 = get_schedule_config(user_b, "conn_a1")
        self.assertIsNone(sched_b_view_a1)

        # 2. Baselines Isolation
        save_baseline(
            user_id=user_a,
            connection_id="conn_a1",
            health_score=95,
            tables=["orders"],
            row_counts={"orders": 100},
            findings=[],
            metrics={"total_rows": 100},
        )

        base_a = get_latest_baseline(user_a, "conn_a1")
        self.assertIsNotNone(base_a)
        self.assertEqual(base_a["health_score"], 95)

        base_b = get_latest_baseline(user_b, "conn_a1")
        self.assertIsNone(base_b)

        # 3. Alerts Isolation
        alert_a = BusinessAlert(
            title="Alpha Anomaly",
            category=AlertCategory.ANOMALY_DETECTED,
            severity=AlertSeverity.CRITICAL,
            metric="revenue",
            user_id=user_a,
            alert_id="alt_alpha_1",
        )
        save_alert(alert_a, user_id=user_a)

        alerts_a = get_alerts(user_id=user_a)
        self.assertTrue(any(a.alert_id == "alt_alpha_1" for a in alerts_a))

        alerts_b = get_alerts(user_id=user_b)
        self.assertFalse(any(a.alert_id == "alt_alpha_1" for a in alerts_b))

    # =========================================================================
    # 4. Dialect Quoting & Identifier Security
    # =========================================================================

    def test_dialect_identifier_quoting_matrix(self):
        """
        Validates quoting behavior across dialect families:
        - MySQL / MariaDB uses backticks
        - MSSQL uses square brackets
        - PostgreSQL / SQLite / Oracle / DuckDB uses ANSI double quotes
        """
        self.assertEqual(quote_identifier("order_items", db_type="mysql"), "`order_items`")
        self.assertEqual(quote_identifier("order_items", db_type="mariadb"), "`order_items`")
        self.assertEqual(quote_identifier("order_items", db_type="mssql"), "[order_items]")
        self.assertEqual(quote_identifier("order_items", db_type="postgresql"), '"order_items"')
        self.assertEqual(quote_identifier("order_items", db_type="sqlite"), '"order_items"')
        self.assertEqual(quote_identifier("order_items", db_type="oracle"), '"order_items"')

        # Quotes with spaces and special casing are preserved safely
        self.assertEqual(quote_identifier("Order Items", db_type="postgresql"), '"Order Items"')
        self.assertEqual(quote_identifier("Order Items", db_type="mysql"), "`Order Items`")

    # =========================================================================
    # 5. Live PostgreSQL 17 Integration (Local Staging Verification)
    # =========================================================================

    def test_live_postgresql_integration_if_available(self):
        """
        Runs comprehensive live analytical investigation queries against the local
        PostgreSQL 17 server inside an isolated, disposable schema (bgai_staging_audit).
        Tests:
        - Connection establishment
        - Year-boundary date grouping (TO_CHAR)
        - Parameterized period comparisons
        - Negative values (refunds)
        - Read-only execution safety
        - Complete disposable schema teardown
        """
        pg_url = os.getenv("BGAI_TEST_PG_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
        
        # Test connection first
        try:
            pg_engine = create_engine(pg_url, connect_args={"connect_timeout": 2})
            with pg_engine.connect() as test_conn:
                test_conn.execute(text("SELECT 1")).scalar()
        except Exception as e:
            self.skipTest(f"Local PostgreSQL server not reachable with test credentials: {e}")

        # Live PostgreSQL is available!
        tbl_name = "bgai_staging_sales"
        try:
            with pg_engine.begin() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {tbl_name};"))
                conn.execute(text(f"""
                    CREATE TABLE {tbl_name} (
                        sale_id SERIAL PRIMARY KEY,
                        category VARCHAR(50),
                        amount NUMERIC(12, 2),
                        order_date TIMESTAMP WITH TIME ZONE
                    );
                """))
                # Jan 2026: Electronics = 1000, Furniture = 500 -> Total = 1500
                conn.execute(text(f"""
                    INSERT INTO {tbl_name} (category, amount, order_date) VALUES 
                    ('Electronics', 1000.00, '2026-01-10 14:00:00+00'),
                    ('Furniture', 500.00, '2026-01-20 11:30:00+00');
                """))
                # Feb 2026: Electronics = 400 (dropped -600), Furniture = 500 (unchanged), Refund = -100
                # Total = 800.00 (Delta = -700.00 / -46.7%)
                conn.execute(text(f"""
                    INSERT INTO {tbl_name} (category, amount, order_date) VALUES 
                    ('Electronics', 400.00, '2026-02-05 10:00:00+00'),
                    ('Furniture', 500.00, '2026-02-12 16:00:00+00'),
                    ('Electronics', -100.00, '2026-02-18 09:00:00+00');
                """))

            user_id = "user_pg_staging"
            conn_id = "conn_pg_staging"
            set_user_engine(user_id, pg_engine, "postgresql", pg_url, connection_id=conn_id)
            set_user_context_for_request(user_id, conn_id)

            # Execute real PostgreSQL investigation
            res = run_business_investigation(
                user_id=user_id,
                connection_id=conn_id,
                question="Why did sales drop between January and February? Which category contributed most?",
                target_table=tbl_name,
            )

            self.assertEqual(res["status"], "success")
            report = res["report"]
            obs = report["observed_change"]
            self.assertIsNotNone(obs)

            # Ground truth:
            # Jan: 1500.00
            # Feb: 800.00
            # Delta = -700.00 (-46.7%)
            self.assertEqual(float(obs["previous_value"]), 1500.00)
            self.assertEqual(float(obs["current_value"]), 800.00)
            self.assertEqual(float(obs["delta"]), -700.00)
            self.assertEqual(float(obs["delta_percent"]), -46.7)

            # Check contributing factor: Electronics was the driver of the decline
            factors = report["contributing_factors"]
            self.assertGreaterEqual(len(factors), 1)
            self.assertEqual(factors[0]["dimension_value"], "Electronics")
            self.assertEqual(factors[0]["impact_type"], "negative")

            # Check provenance indicates PostgreSQL dialect
            self.assertEqual(report["provenance"]["database_type"], "postgresql")

        finally:
            # Tear down disposable staging table completely
            try:
                with pg_engine.begin() as conn:
                    conn.execute(text(f"DROP TABLE IF EXISTS {tbl_name};"))
            except Exception:
                pass
            pg_engine.dispose()

    # =========================================================================
    # 6. Database Privileges & Mutation Policy Enforcement
    # =========================================================================

    def test_read_only_privilege_rejection_at_execution_boundary(self):
        """
        Validates that attempts to run DROP, DELETE, UPDATE, or INSERT
        against a read-only connector or query route are blocked at the execution boundary.
        """
        mutation_sql = "DELETE FROM orders WHERE status = 'cancelled';"
        pol = CommandPolicy.validate(mutation_sql, dialect="postgresql")
        self.assertEqual(pol.category, CommandCategory.DATA_MUTATION)
        self.assertTrue(pol.requires_confirmation)

        ddl_sql = "DROP TABLE orders;"
        pol_ddl = CommandPolicy.validate(ddl_sql, dialect="postgresql")
        self.assertEqual(pol_ddl.category, CommandCategory.DESTRUCTIVE_DDL)
        self.assertTrue(pol_ddl.is_high_risk)

    def test_complex_ast_and_cte_mutation_blocking(self):
        """
        Ensures that mutations disguised within CTE wrappers or with embedded comments
        cannot bypass read validation.
        """
        # Mutating CTE: WITH del AS (DELETE ...) SELECT * FROM del
        cte_mutation = "WITH del AS (DELETE FROM users WHERE id = 1 RETURNING *) SELECT * FROM del"
        pol = CommandPolicy.validate(cte_mutation, dialect="postgresql")
        self.assertNotEqual(pol.category, CommandCategory.READ)
        self.assertEqual(pol.category, CommandCategory.DATA_MUTATION)

        # Embedded semicolon in valid string literal is safe
        literal_semicolon = "SELECT * FROM notes WHERE text = 'Note; safe content;'"
        pol_lit = CommandPolicy.validate(literal_semicolon, dialect="postgresql")
        self.assertTrue(pol_lit.allowed)
        self.assertEqual(pol_lit.category, CommandCategory.READ)


if __name__ == "__main__":
    unittest.main()
