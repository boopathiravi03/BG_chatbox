"""backend/tests/test_staging_acceptance_sprint3_4.py

Sprint 3.4: Staging Acceptance, Security Sign-off & Release Gate Suite

Validation Areas:
1. SQL Policy Behavior & Edge Cases:
   - Read-only CTEs, multiple CTE definitions, and nested CTEs.
   - Mutating CTEs (INSERT, UPDATE, DELETE, RETURNING) disguised within WITH expressions.
   - Mutation keywords in string literals and comments (never falsely flagged as mutations).
   - Stacked statement chaining prevention (semicolon injection outside and inside strings).
   - Malformed parser inputs and unsupported statement types (fail closed).
2. Query Resource Controls & Memory Bounding:
   - 2,000-row limit enforced before unbounded results are materialized in memory.
   - Exact boundary checks: 50 rows (not truncated), 2,000 rows (not truncated), 2,001 rows (truncated).
   - Cursor closing and resource cleanup upon reaching limit.
3. Secret Handling & Error Redaction:
   - Connection URLs (PostgreSQL, MySQL, SQLite).
   - Passwords with special characters (@, !, #, $, %, etc.).
   - Nested driver exception messages.
   - Bearer tokens, secret keys (sk_live_*), and sensitive parameter assignments.
4. Staging Acceptance & Tenant Isolation (SQLite & PostgreSQL):
   - Read-only role guardrails.
   - Multi-tenant user and connection isolation.
   - Autonomous monitoring and anomaly alert lifecycle.
   - Live PostgreSQL 17 execution if available on localhost.
"""

from __future__ import annotations

import os
import sys
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
from app.tools.command_policy import CommandPolicy, CommandCategory, sanitize_sql_for_audit
from app.tools.execute_query import execute_query, sanitize_error_message
from app.intelligence.monitoring.baseline_store import (
    set_monitoring_store_engine,
    save_baseline,
    get_latest_baseline,
)
from app.intelligence.proactive.alert_store import (
    set_alert_store_engine,
    save_alert,
    get_alerts,
    update_alert_status,
)
from app.intelligence.proactive.models import (
    BusinessAlert,
    AlertCategory,
    AlertSeverity,
    AlertStatus,
)


class TestSQLPolicyEdgeCases(unittest.TestCase):
    """Rigorous validation of SQL policy parsing, classification, and edge-case handling."""

    def test_readonly_ctes_allowed_as_read(self):
        # Single CTE
        sql1 = "WITH active_users AS (SELECT id, name FROM users WHERE is_active = 1) SELECT * FROM active_users;"
        res1 = CommandPolicy.validate(sql1, dialect="sqlite")
        self.assertTrue(res1.allowed)
        self.assertEqual(res1.category, CommandCategory.READ)
        self.assertFalse(res1.requires_confirmation)

        # Multiple CTEs
        sql2 = (
            "WITH regional_sales AS ("
            "  SELECT region, SUM(amount) AS total FROM orders GROUP BY region"
            "), "
            "top_regions AS ("
            "  SELECT region FROM regional_sales WHERE total > 10000"
            ") "
            "SELECT * FROM top_regions;"
        )
        res2 = CommandPolicy.validate(sql2, dialect="postgres")
        self.assertTrue(res2.allowed)
        self.assertEqual(res2.category, CommandCategory.READ)
        self.assertFalse(res2.requires_confirmation)

        # Nested subquery inside CTE
        sql3 = (
            "WITH summary AS ("
            "  SELECT id, (SELECT AVG(price) FROM products) AS avg_price FROM items"
            ") SELECT * FROM summary;"
        )
        res3 = CommandPolicy.validate(sql3, dialect="sqlite")
        self.assertTrue(res3.allowed)
        self.assertEqual(res3.category, CommandCategory.READ)
        self.assertFalse(res3.requires_confirmation)

    def test_mutating_cte_detected_and_classified_as_mutation(self):
        # DELETE inside CTE
        sql_del = (
            "WITH deleted_rows AS ("
            "  DELETE FROM sessions WHERE expired_at < '2026-01-01' RETURNING user_id"
            ") SELECT * FROM deleted_rows;"
        )
        res_del = CommandPolicy.validate(sql_del, dialect="postgres")
        self.assertEqual(res_del.category, CommandCategory.DATA_MUTATION)
        self.assertEqual(res_del.operation, "DELETE")
        self.assertTrue(res_del.requires_confirmation)

        # INSERT inside CTE
        sql_ins = (
            "WITH new_orders AS ("
            "  INSERT INTO orders (id, amount) VALUES (1, 100) RETURNING id"
            ") SELECT * FROM new_orders;"
        )
        res_ins = CommandPolicy.validate(sql_ins, dialect="postgres")
        self.assertEqual(res_ins.category, CommandCategory.DATA_MUTATION)
        self.assertEqual(res_ins.operation, "INSERT")
        self.assertTrue(res_ins.requires_confirmation)

        # UPDATE inside CTE
        sql_upd = (
            "WITH updated AS ("
            "  UPDATE accounts SET balance = 0 WHERE is_closed = 1 RETURNING id"
            ") SELECT * FROM updated;"
        )
        res_upd = CommandPolicy.validate(sql_upd, dialect="postgres")
        self.assertEqual(res_upd.category, CommandCategory.DATA_MUTATION)
        self.assertEqual(res_upd.operation, "UPDATE")
        self.assertTrue(res_upd.requires_confirmation)

    def test_mutating_cte_blocked_on_readonly_connection(self):
        class ReadOnlyConn:
            name = "analytics_replica"
            is_read_only = True
            connector_type = "postgres"
            category = "relational"

        sql = "WITH del AS (DELETE FROM audit_logs RETURNING id) SELECT * FROM del;"
        res = CommandPolicy.validate(sql, dialect="postgres", connector=ReadOnlyConn())
        self.assertFalse(res.allowed)
        self.assertIn("READ-ONLY", res.reason)

    def test_mutation_keyword_in_string_literals_not_flagged(self):
        # Keyword in single quotes
        sql1 = "SELECT id, 'DELETE FROM customers WHERE id = 1' AS log_message FROM audit_trail;"
        res1 = CommandPolicy.validate(sql1, dialect="sqlite")
        self.assertTrue(res1.allowed)
        self.assertEqual(res1.category, CommandCategory.READ)
        self.assertFalse(res1.requires_confirmation)

        # Keyword in CTE string literal
        sql2 = (
            "WITH event_types AS ("
            "  SELECT id, 'DROP TABLE users' AS action_name FROM event_logs"
            ") SELECT * FROM event_types;"
        )
        res2 = CommandPolicy.validate(sql2, dialect="sqlite")
        self.assertTrue(res2.allowed)
        self.assertEqual(res2.category, CommandCategory.READ)
        self.assertFalse(res2.requires_confirmation)

    def test_mutation_keyword_in_comment_not_flagged(self):
        sql = "SELECT id, amount /* UPDATE orders SET amount = 0 */ FROM orders;"
        res = CommandPolicy.validate(sql, dialect="sqlite")
        self.assertTrue(res.allowed)
        self.assertEqual(res.category, CommandCategory.READ)
        self.assertFalse(res.requires_confirmation)

    def test_stacked_statements_prevented(self):
        # Classic semicolon injection
        sql = "SELECT * FROM orders; DROP TABLE users;"
        res = CommandPolicy.validate(sql, dialect="sqlite")
        self.assertFalse(res.allowed)
        self.assertEqual(res.operation, "MULTIPLE")
        self.assertIn("Multiple SQL statements", res.reason)

    def test_semicolon_inside_string_literal_not_flagged_as_stacked(self):
        sql = "SELECT 'hello; world' AS greeting FROM dual;"
        res = CommandPolicy.validate(sql, dialect="sqlite")
        self.assertTrue(res.allowed)
        self.assertEqual(res.category, CommandCategory.READ)

    def test_malformed_and_unsupported_statements_fail_closed(self):
        # Completely invalid syntax / unsupported statement
        sql = "FOOBAR SYSTEM DUMP ALL MEMORY;"
        res = CommandPolicy.validate(sql, dialect="sqlite")
        self.assertFalse(res.allowed)
        self.assertEqual(res.category, CommandCategory.PROHIBITED_SYSTEM)
        self.assertIn("not a recognized or supported", res.reason)

        # Empty or whitespace query
        res_empty = CommandPolicy.validate("   ", dialect="sqlite")
        self.assertFalse(res_empty.allowed)
        self.assertEqual(res_empty.reason, "Empty database command.")

    def test_prohibited_system_patterns_blocked(self):
        prohibited = [
            "ATTACH DATABASE '/etc/shadow' AS pwn;",
            "DETACH DATABASE pwn;",
            "LOAD DATA LOCAL INFILE '/var/log' INTO TABLE stolen;",
            "SELECT * INTO OUTFILE '/var/www/shell.php' FROM users;",
            "SHUTDOWN IMMEDIATE;",
        ]
        for cmd in prohibited:
            res = CommandPolicy.validate(cmd, dialect="sqlite")
            self.assertFalse(res.allowed, f"Expected {cmd} to be blocked")
            self.assertEqual(res.category, CommandCategory.PROHIBITED_SYSTEM)


class TestQueryResourceControls(unittest.TestCase):
    """Verification of bounded streaming, row limits, and connection cleanup."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        with self.engine.begin() as conn:
            conn.execute(text("CREATE TABLE test_items (id INTEGER PRIMARY KEY, val TEXT)"))
            # Insert 2,500 items to test pagination and memory bounding
            conn.execute(
                text(
                    "WITH RECURSIVE cnt(x) AS ("
                    "  SELECT 1 UNION ALL SELECT x+1 FROM cnt WHERE x < 2500"
                    ") INSERT INTO test_items SELECT x, 'val_' || x FROM cnt"
                )
            )

    def tearDown(self):
        self.engine.dispose()

    def test_small_result_is_not_truncated(self):
        res = execute_query(
            sql="SELECT * FROM test_items WHERE id <= 50",
            engine=self.engine,
            db_type="sqlite",
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["rows_returned"], 50)
        self.assertEqual(len(res["rows"]), 50)
        self.assertFalse(res["truncated"])
        self.assertEqual(res["max_rows_limit"], 2000)

    def test_exact_limit_boundary_is_not_truncated(self):
        res = execute_query(
            sql="SELECT * FROM test_items WHERE id <= 2000",
            engine=self.engine,
            db_type="sqlite",
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["rows_returned"], 2000)
        self.assertEqual(len(res["rows"]), 2000)
        self.assertFalse(res["truncated"])

    def test_limit_plus_one_is_accurately_truncated(self):
        res = execute_query(
            sql="SELECT * FROM test_items WHERE id <= 2001",
            engine=self.engine,
            db_type="sqlite",
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["rows_returned"], 2000)
        self.assertEqual(len(res["rows"]), 2000)
        self.assertTrue(res["truncated"])

    def test_large_unbounded_query_enforces_limit_without_oom(self):
        # Querying all 2,500 rows
        res = execute_query(
            sql="SELECT * FROM test_items",
            engine=self.engine,
            db_type="sqlite",
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["rows_returned"], 2000)
        self.assertEqual(len(res["rows"]), 2000)
        self.assertTrue(res["truncated"])
        self.assertEqual(res["max_rows_limit"], 2000)

    def test_query_error_cleans_up_connection_and_redacts(self):
        res = execute_query(
            sql="SELECT * FROM non_existent_table_xyz",
            engine=self.engine,
            db_type="sqlite",
        )
        self.assertFalse(res["success"])
        self.assertIn("error", res)
        # Verify subsequent query on engine succeeds (connection pool not poisoned or leaked)
        subsequent = execute_query(
            sql="SELECT 1 AS num",
            engine=self.engine,
            db_type="sqlite",
        )
        self.assertTrue(subsequent["success"])
        self.assertEqual(subsequent["rows"][0]["num"], 1)


class TestSecretRedactionExhaustiveMatrix(unittest.TestCase):
    """Verification of credential, connection URL, and token sanitization."""

    def test_postgres_url_redaction_with_special_characters(self):
        err = "OperationalError: connection to 'postgresql://admin:P@ss!#$99@db.prod.internal:5432/corp' failed"
        sanitized = sanitize_error_message(err)
        self.assertNotIn("P@ss!#$99", sanitized)
        self.assertIn("postgresql://admin:***@db.prod.internal:5432/corp", sanitized)

    def test_mysql_url_redaction_with_complex_password(self):
        err = "pymysql.err.OperationalError: (2003, \"Can't connect to MySQL server on 'mysql+pymysql://root:MySecret%40Pass!@10.0.0.1:3306/sales'\")"
        sanitized = sanitize_error_message(err)
        self.assertNotIn("MySecret%40Pass!", sanitized)
        self.assertIn("mysql+pymysql://root:***@10.0.0.1:3306/sales", sanitized)

    def test_pymysql_user_password_error_format(self):
        err = "Access denied for user 'db_user':'super_secret_pw'@'192.168.1.10'"
        sanitized = sanitize_error_message(err)
        self.assertNotIn("super_secret_pw", sanitized)
        self.assertIn("'db_user':'***'@'192.168.1.10'", sanitized)

    def test_bearer_token_and_api_keys(self):
        err = "Failed request: Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz and key sk_live_998877665544332211"
        sanitized = sanitize_error_message(err)
        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz", sanitized)
        self.assertNotIn("sk_live_998877665544332211", sanitized)
        self.assertIn("Bearer ***", sanitized)
        self.assertIn("[REDACTED_SECRET]", sanitized)

    def test_audit_sql_sanitization(self):
        raw_sql = "CREATE USER app_user IDENTIFIED BY 'SuperSecret1234!';"
        sanitized = sanitize_sql_for_audit(raw_sql)
        self.assertNotIn("SuperSecret1234!", sanitized)
        self.assertIn("IDENTIFIED BY '***'", sanitized)


class TestStagingAcceptanceTenantIsolationAndLifecycle(unittest.TestCase):
    """End-to-end multi-tenant isolation, investigator attribution, and monitoring lifecycle."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        set_investigation_store_engine(self.engine)
        set_monitoring_store_engine(self.engine)
        set_alert_store_engine(self.engine)

        # Setup test business data
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE orders ("
                    "  order_id INTEGER PRIMARY KEY,"
                    "  customer_id INTEGER,"
                    "  order_date TEXT,"
                    "  total_amount REAL,"
                    "  region TEXT"
                    ")"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO orders VALUES "
                    "(1, 101, '2026-03-01', 500.0, 'North'),"
                    "(2, 102, '2026-03-05', 1200.0, 'South'),"
                    "(3, 103, '2026-03-10', 800.0, 'North'),"
                    "(4, 104, '2026-03-15', -150.0, 'East'),"  # Refund
                    "(5, 105, '2026-03-20', 2500.0, 'West')"
                )
            )

    def tearDown(self):
        clear_user_context("usr_stage_alpha")
        clear_user_context("usr_stage_beta")
        clear_user_context("usr_stage_monitor")
        clear_database_profile()
        self.engine.dispose()

    def test_investigator_attribution_and_tenant_ownership(self):
        user_alpha = "usr_stage_alpha"
        conn_alpha = "conn_stage_northwind"
        set_user_context_for_request(user_alpha, conn_alpha)
        set_user_engine(
            user_id=user_alpha,
            engine=self.engine,
            database_type="sqlite",
            database_identity="sqlite:///:memory:",
            connection_id=conn_alpha,
        )

        res = run_business_investigation(
            user_id=user_alpha,
            connection_id=conn_alpha,
            question="Analyze total revenue in orders",
            target_table="orders",
            target_metric="total_amount",
        )

        self.assertIsNotNone(res)
        self.assertEqual(res["user_id"], user_alpha)
        self.assertEqual(res["connection_id"], conn_alpha)
        self.assertEqual(res["report"]["primary_table"], "orders")

        # User Beta should NOT see User Alpha's reports
        user_beta = "usr_stage_beta"
        conn_beta = "conn_stage_orders"
        reports_beta = list_investigation_reports(user_id=user_beta, connection_id=conn_beta)
        self.assertEqual(len(reports_beta), 0)

        reports_alpha = list_investigation_reports(user_id=user_alpha, connection_id=conn_alpha)
        self.assertEqual(len(reports_alpha), 1)
        self.assertEqual(reports_alpha[0]["report_id"], res["investigation_id"])

    def test_autonomous_monitoring_and_alert_lifecycle(self):
        user_id = "usr_stage_monitor"
        conn_id = "conn_stage_db"

        # 1. Record healthy baseline snapshot
        b1 = save_baseline(
            user_id=user_id,
            connection_id=conn_id,
            health_score=95,
            tables=["orders"],
            row_counts={"orders": 1000},
            findings=[],
            metrics={"total_amount": 970.0},
        )
        self.assertIsNotNone(b1)

        latest_b = get_latest_baseline(user_id=user_id, connection_id=conn_id)
        self.assertIsNotNone(latest_b)
        self.assertEqual(latest_b["health_score"], 95)
        self.assertEqual(latest_b["row_counts"]["orders"], 1000)

        # 2. Save Business Alert
        alert = BusinessAlert(
            alert_id="alt_stage_test_1",
            category=AlertCategory.ANOMALY_DETECTED,
            title="Unusual Revenue Spike",
            explanation="Revenue in orders exceeded historical standard deviation.",
            severity=AlertSeverity.CRITICAL,
            status=AlertStatus.NEW,
            metric="total_amount",
            user_id=user_id,
        )
        save_alert(alert, user_id=user_id)

        alerts = get_alerts(user_id=user_id)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].alert_id, "alt_stage_test_1")
        self.assertEqual(alerts[0].status, AlertStatus.NEW)

        # 3. Resolve alert and verify status change
        update_alert_status("alt_stage_test_1", AlertStatus.RESOLVED, user_id=user_id)
        updated_alerts = get_alerts(user_id=user_id, status=AlertStatus.RESOLVED)
        self.assertEqual(len(updated_alerts), 1)
        self.assertEqual(updated_alerts[0].status, AlertStatus.RESOLVED)


class TestLivePostgreSQLStagingAcceptance(unittest.TestCase):
    """
    Staging acceptance testing against live PostgreSQL 17 if reachable.
    Validates transactional integrity, date functions, parameterization, and clean teardown.
    """

    def setUp(self):
        self.pg_url = os.getenv("BGAI_TEST_PG_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
        self.pg_engine = None
        try:
            temp_engine = create_engine(self.pg_url, connect_args={"connect_timeout": 3})
            with temp_engine.connect() as conn:
                conn.execute(text("SELECT 1;"))
            self.pg_engine = temp_engine
        except Exception:
            self.pg_engine = None

    def tearDown(self):
        if self.pg_engine:
            try:
                with self.pg_engine.begin() as conn:
                    conn.execute(text("DROP TABLE IF EXISTS bgai_staging_acceptance_orders CASCADE;"))
            except Exception:
                pass
            self.pg_engine.dispose()

    def test_live_postgresql_staging_acceptance_if_available(self):
        if not self.pg_engine:
            self.skipTest("Live PostgreSQL instance not reachable on localhost:5432. Skipped.")

        with self.pg_engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE bgai_staging_acceptance_orders ("
                "  order_id INT PRIMARY KEY,"
                "  customer_id INT,"
                "  order_date TIMESTAMP,"
                "  amount NUMERIC(10, 2),"
                "  status VARCHAR(50)"
                ");"
            ))
            conn.execute(text(
                "INSERT INTO bgai_staging_acceptance_orders VALUES "
                "(1, 1001, '2026-01-15 10:00:00', 250.50, 'COMPLETED'),"
                "(2, 1002, '2026-02-20 14:30:00', 500.00, 'COMPLETED'),"
                "(3, 1003, '2026-03-01 09:15:00', -50.50, 'REFUND'),"
                "(4, 1004, '2026-03-10 16:45:00', 1200.00, 'COMPLETED');"
            ))

        # 1. Parameterized Read Query Execution
        read_res = execute_query(
            sql="SELECT status, SUM(amount) AS total FROM bgai_staging_acceptance_orders WHERE amount > :min_val GROUP BY status;",
            params={"min_val": 0},
            engine=self.pg_engine,
            db_type="postgres",
        )
        self.assertTrue(read_res["success"])
        self.assertEqual(read_res["operation"], "select")
        self.assertEqual(len(read_res["rows"]), 1)
        self.assertAlmostEqual(float(read_res["rows"][0]["total"]), 1950.50, places=2)

        # 2. Mutating CTE Execution Policy Check
        val = CommandPolicy.validate(
            sql=(
                "WITH updated_orders AS ("
                "  UPDATE bgai_staging_acceptance_orders SET status = 'AUDITED' WHERE order_id = 1 RETURNING order_id"
                ") SELECT * FROM updated_orders;"
            ),
            dialect="postgres",
        )
        self.assertEqual(val.category, CommandCategory.DATA_MUTATION)
        self.assertTrue(val.requires_confirmation)


if __name__ == "__main__":
    unittest.main()
