"""backend/tests/test_ai_analyst_sprint1.py

Comprehensive Sprint 1 Test Suite: Secure AI Data Analyst.
Tests:
1. Connection lookup isolation (no silent fallback).
2. Query and credential audit sanitization.
3. Live database profiling (tables, columns, types, keys, relationships).
4. Sensitive column sample value suppression and redaction.
5. Business entity auto-classification (Customer, Product, Order, Dimension, Log).
6. Metric, dimension, and date column discovery.
7. Data quality health audit (missing PKs, duplicate keys, high nulls, empty tables).
8. Health score calculation (10-100).
9. Non-relational connector profiling fallback.
10. Database profile caching and DDL invalidation.
11. Data-quality question handling ("Which tables contain missing or duplicate data?").
12. Chart auto-recommendation for multi-row query results.
13. Evidence-based explanation generation.
14. Correlation vs causation disclaimer enforcement.
15. Context-aware follow-up suggestion generation.
"""

import os
import sys
import tempfile
import unittest
import sqlite3
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, text
from app.agent.database_profile import DatabaseProfile, TableProfile, ColumnProfile, DataHealthFinding
from app.tools.analyze_database import analyze_database, _classify_entity_type
from app.tools.command_policy import sanitize_sql_for_audit
from app.tools.generate_chart import generate_chart
from app.database.database_context import (
    get_database_profile,
    refresh_database_profile,
    invalidate_database_profile,
    clear_database_profile,
)
from app.database.connection_context import (
    set_user_context_for_request,
    get_request_engine,
    get_request_db_type,
    clear_user_context,
)
from app.agent.orchestrator import (
    _is_data_quality_question,
    _handle_data_quality_question,
    _get_followups,
    run_agent,
)


class MockNonRelationalConnector:
    """Mock connector simulating MongoDB or Redis store."""
    def __init__(self, connection_id="conn_mongo_1", name="ProductCatalogDoc"):
        self.connection_id = connection_id
        self.name = name
        self.connector_type = "mongodb"
        self.category = type("Cat", (), {"value": "document"})()
        self.status = type("Stat", (), {"value": "connected"})()

    def get_schema(self, force_refresh=False):
        return {
            "collections": {
                "products_catalog": {
                    "count": 450,
                    "fields": {
                        "_id": "ObjectId",
                        "sku": "string",
                        "title": "string",
                        "price": "double",
                        "stock_quantity": "int",
                        "created_at": "date",
                    }
                },
                "customer_events": {
                    "count": 1200,
                    "fields": {
                        "_id": "ObjectId",
                        "event_name": "string",
                        "timestamp": "date",
                    }
                }
            }
        }

    def get_stats(self):
        return {"collections": 2, "documents": 1650}

    def execute_query(self, query, params=None):
        return type("Res", (), {
            "success": True,
            "columns": ["sku", "price"],
            "rows": [{"sku": "SKU-1", "price": 49.99}],
            "rows_returned": 1,
            "affected_rows": 0,
            "error": None,
            "execution_time_ms": 1.2,
        })()


class TestSecureAIDataAnalyst(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a temporary SQLite database with realistic business schema and deliberate health defects
        cls.temp_db_fd, cls.temp_db_path = tempfile.mkstemp(suffix=".db")
        cls.engine = create_engine(f"sqlite:///{cls.temp_db_path}")

        with cls.engine.connect() as conn:
            # 1. Customers table (Clean table with PK)
            conn.execute(text("""
                CREATE TABLE customers (
                    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    phone TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            conn.execute(text("""
                INSERT INTO customers (name, email, password_hash, phone) VALUES
                ('Alice Johnson', 'alice@corp.com', 'secret_hash_98765', '555-0101'),
                ('Bob Smith', 'bob@corp.com', 'secret_hash_54321', NULL),
                ('Charlie Brown', 'charlie@corp.com', 'secret_hash_11111', NULL);
            """))

            # 2. Products table (Table with high null column and metric measures)
            conn.execute(text("""
                CREATE TABLE products (
                    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL,
                    unit_price REAL NOT NULL,
                    discount_rate REAL,
                    supplier_notes TEXT
                );
            """))
            conn.execute(text("""
                INSERT INTO products (title, category, unit_price, discount_rate, supplier_notes) VALUES
                ('Enterprise Server', 'Hardware', 2499.00, 0.10, NULL),
                ('Cloud Gateway', 'Networking', 899.50, NULL, NULL),
                ('AI Accelerator', 'Hardware', 3200.00, NULL, NULL),
                ('Managed Switch', 'Networking', 450.00, NULL, NULL);
            """))

            # 3. Orders table (Transaction entity with dates and amounts)
            conn.execute(text("""
                CREATE TABLE orders (
                    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    total_amount REAL NOT NULL,
                    order_date DATE NOT NULL,
                    status TEXT NOT NULL,
                    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
                );
            """))
            conn.execute(text("""
                INSERT INTO orders (customer_id, product_id, total_amount, order_date, status) VALUES
                (1, 1, 2499.00, '2026-09-15', 'completed'),
                (1, 3, 3200.00, '2026-10-01', 'completed'),
                (2, 2, 899.50, '2026-10-12', 'pending');
            """))

            # 4. Defect Table A: Missing Primary Key & Duplicates
            conn.execute(text("""
                CREATE TABLE legacy_import_data (
                    item_code TEXT,
                    raw_val REAL,
                    constant_flag TEXT
                );
            """))
            conn.execute(text("""
                INSERT INTO legacy_import_data (item_code, raw_val, constant_flag) VALUES
                ('DUP-01', 10.5, 'ACTIVE'),
                ('DUP-01', 10.5, 'ACTIVE'),
                ('DUP-02', 20.0, 'ACTIVE');
            """))

            # 5. Defect Table B: Empty Table
            conn.execute(text("""
                CREATE TABLE obsolete_staging (
                    id INTEGER PRIMARY KEY,
                    payload TEXT
                );
            """))
            conn.commit()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        os.close(cls.temp_db_fd)
        try:
            os.remove(cls.temp_db_path)
        except Exception:
            pass

    def setUp(self):
        clear_database_profile()
        # Bind request context to test engine
        set_user_context_for_request("test_analyst_user", client_ip="127.0.0.1")
        # Direct context engine attachment
        from app.database.connection_context import set_user_engine
        set_user_engine("test_analyst_user", self.engine, "sqlite", f"sqlite:///{self.temp_db_path}")
        set_user_context_for_request("test_analyst_user")

    def tearDown(self):
        clear_user_context("test_analyst_user")
        clear_database_profile()

    # -------------------------------------------------------------------------
    # 1. Connection Isolation Test
    # -------------------------------------------------------------------------
    def test_connection_lookup_isolation_never_falls_back_silently(self):
        """Specifying an invalid connection ID must NOT fall back to another database engine."""
        ctx = set_user_context_for_request("test_analyst_user", connection_id="nonexistent_unowned_id")
        self.assertIsNone(get_request_engine(), "Engine must be None when connection_id is unowned/missing.")
        self.assertEqual(get_request_db_type(), "none", "DB type must be 'none' on missing connection.")
        self.assertFalse(ctx.to_info()["connected"], "DatabaseContext must report disconnected.")

    # -------------------------------------------------------------------------
    # 2. Query and Credential Audit Sanitization
    # -------------------------------------------------------------------------
    def test_audit_logging_sanitizes_credentials(self):
        """Verify that password literals, tokens, and secret parameters are redacted from audit logs."""
        raw_sql = "CREATE USER 'analyst'@'%' IDENTIFIED BY 'SuperSecretP@ss123';"
        sanitized = sanitize_sql_for_audit(raw_sql)
        self.assertNotIn("SuperSecretP@ss123", sanitized)
        self.assertIn("IDENTIFIED BY '***'", sanitized)

        token_sql = "SELECT * FROM api_logs WHERE auth_header = 'Bearer eyJhbGciOiJIUzI1NiIsIn...';"
        sanitized_token = sanitize_sql_for_audit(token_sql)
        self.assertNotIn("eyJhbGciOiJIUzI1NiIsIn...", sanitized_token)
        self.assertIn("Bearer ***", sanitized_token)

    # -------------------------------------------------------------------------
    # 3. Live Database Profiling
    # -------------------------------------------------------------------------
    def test_automatic_database_profiling(self):
        """Profile must automatically discover tables, columns, rows, types, and primary keys."""
        profile = analyze_database(user_id="test_analyst_user")
        self.assertTrue(profile.analyzed)
        self.assertEqual(profile.total_tables, 5)
        self.assertIn("customers", profile.tables)
        self.assertIn("products", profile.tables)
        self.assertIn("orders", profile.tables)

        cust_table = profile.tables["customers"]
        self.assertEqual(cust_table.row_count, 3)
        col_names = [c.name for c in cust_table.columns]
        self.assertIn("customer_id", col_names)
        self.assertIn("email", col_names)

        pk_col = next(c for c in cust_table.columns if c.name == "customer_id")
        self.assertTrue(pk_col.primary_key)

    # -------------------------------------------------------------------------
    # 4. Sensitive Column Sample Redaction
    # -------------------------------------------------------------------------
    def test_sensitive_column_sample_redaction(self):
        """Columns matching password, secret, or token patterns must never expose real sample values."""
        profile = analyze_database(user_id="test_analyst_user")
        cust_table = profile.tables["customers"]
        pwd_col = next(c for c in cust_table.columns if c.name == "password_hash")

        self.assertEqual(pwd_col.sample_values, ["[REDACTED]"])
        # Ensure sample rows also redact the sensitive field
        for row in cust_table.sample_rows:
            self.assertEqual(row.get("password_hash"), "[REDACTED]")

    # -------------------------------------------------------------------------
    # 5. Business Entity Auto-Classification
    # -------------------------------------------------------------------------
    def test_business_entity_classification(self):
        """Tables must be classified into semantic roles: CUSTOMER, PRODUCT, ORDER, etc."""
        profile = analyze_database(user_id="test_analyst_user")
        self.assertEqual(profile.tables["customers"].entity_type, "CUSTOMER")
        self.assertEqual(profile.tables["products"].entity_type, "PRODUCT")
        self.assertEqual(profile.tables["orders"].entity_type, "ORDER")

        self.assertIn("CUSTOMER", profile.business_entities)
        self.assertIn("customers", profile.business_entities["CUSTOMER"])
        self.assertIn("PRODUCT", profile.business_entities)
        self.assertIn("products", profile.business_entities["PRODUCT"])
        self.assertIn("ORDER", profile.business_entities)
        self.assertIn("orders", profile.business_entities["ORDER"])

    # -------------------------------------------------------------------------
    # 6. Column Role & Dimension Classification
    # -------------------------------------------------------------------------
    def test_metric_and_date_column_discovery(self):
        """Numeric measures must be tagged in metric_columns, dates in date_columns."""
        profile = analyze_database(user_id="test_analyst_user")
        orders_table = profile.tables["orders"]
        self.assertIn("total_amount", orders_table.metric_columns)
        self.assertIn("order_date", orders_table.date_columns)

        products_table = profile.tables["products"]
        self.assertIn("unit_price", products_table.metric_columns)
        self.assertIn("category", products_table.dimension_columns)

    # -------------------------------------------------------------------------
    # 7. Data Quality Health Finding Detection
    # -------------------------------------------------------------------------
    def test_data_quality_finding_detection(self):
        """Detect missing PKs, empty tables, and high null columns."""
        profile = analyze_database(user_id="test_analyst_user")
        findings = profile.data_health_findings

        # 1. Missing PK on legacy_import_data
        missing_pk = [f for f in findings if f.table == "legacy_import_data" and f.type == "Missing Primary Key"]
        self.assertTrue(len(missing_pk) > 0, "Expected Missing Primary Key finding on legacy_import_data.")

        # 2. Empty table on obsolete_staging
        empty_table = [f for f in findings if f.table == "obsolete_staging" and f.type == "Empty Table"]
        self.assertTrue(len(empty_table) > 0, "Expected Empty Table finding on obsolete_staging.")

        # 3. High null column on products.discount_rate (3/4 = 75% null)
        high_null = [f for f in findings if f.table == "products" and f.column == "discount_rate"]
        self.assertTrue(len(high_null) > 0, "Expected High Null Ratio finding on products.discount_rate.")

    # -------------------------------------------------------------------------
    # 8. Health Score Calculation
    # -------------------------------------------------------------------------
    def test_health_score_calculation(self):
        """Health score must deterministically penalize detected quality defects."""
        profile = analyze_database(user_id="test_analyst_user")
        self.assertLess(profile.health_score, 100, "Health score must be deducted when defects exist.")
        self.assertGreaterEqual(profile.health_score, 10, "Health score must not drop below minimum clamp.")

    # -------------------------------------------------------------------------
    # 9. Non-Relational Profiling Fallback
    # -------------------------------------------------------------------------
    def test_non_relational_connector_profiling(self):
        """Document/Vector stores must profile collection schemas without failing on inspect()."""
        from app.tools.analyze_database import _analyze_non_relational
        mock_conn = MockNonRelationalConnector()
        profile = DatabaseProfile()
        profile.database_type = "mongodb"

        res = _analyze_non_relational(mock_conn, profile)
        self.assertTrue(res.analyzed)
        self.assertEqual(res.total_tables, 2)
        self.assertIn("products_catalog", res.tables)
        self.assertEqual(res.tables["products_catalog"].entity_type, "PRODUCT")
        self.assertIn("price", res.tables["products_catalog"].metric_columns)

    # -------------------------------------------------------------------------
    # 10. Profile Caching & DDL Invalidation
    # -------------------------------------------------------------------------
    def test_profile_caching_and_invalidation(self):
        """Cached profile must be returned until invalidated."""
        prof1 = get_database_profile(user_id="test_analyst_user")
        prof2 = get_database_profile(user_id="test_analyst_user")
        self.assertIs(prof1, prof2, "Subsequent calls should return cached profile object.")

        invalidate_database_profile(user_id="test_analyst_user")
        from app.database.database_context import _profile_cache
        self.assertNotIn(("test_analyst_user", "default"), _profile_cache)

    # -------------------------------------------------------------------------
    # 11. Data Quality Question Routing
    # -------------------------------------------------------------------------
    def test_data_quality_question_handler(self):
        """User asking 'Which tables contain missing or duplicate data?' must get actionable report."""
        user_q = "Which tables contain missing or duplicate data?"
        self.assertTrue(_is_data_quality_question(user_q))

        ans = _handle_data_quality_question(user_q)
        self.assertTrue(ans["result"]["success"])
        self.assertGreater(ans["result"]["rows_returned"], 0)
        self.assertIsNotNone(ans["chart"])
        self.assertEqual(ans["chart"]["chart_type"], "bar")
        self.assertIn("Data Quality Diagnostic Findings", ans["explanation"])

    # -------------------------------------------------------------------------
    # 12. Chart Auto-Recommendation
    # -------------------------------------------------------------------------
    def test_chart_auto_recommendation(self):
        """Tabular query results with label + number must generate a suitable chart."""
        query_res = {
            "success": True,
            "columns": ["product_title", "revenue"],
            "rows": [
                {"product_title": "Enterprise Server", "revenue": 12500.0},
                {"product_title": "AI Accelerator", "revenue": 9600.0},
                {"product_title": "Cloud Gateway", "revenue": 3500.0},
            ],
            "rows_returned": 3,
        }
        chart = generate_chart("Which products generate the most revenue?", query_res)
        self.assertIsNotNone(chart)
        self.assertEqual(chart["chart_type"], "bar")
        self.assertEqual(len(chart["labels"]), 3)
        self.assertEqual(chart["values"], [12500.0, 9600.0, 3500.0])

        # Test line chart for monthly trend
        trend_res = {
            "success": True,
            "columns": ["month", "total_sales"],
            "rows": [
                {"month": "2026-08", "total_sales": 15000.0},
                {"month": "2026-09", "total_sales": 22000.0},
                {"month": "2026-10", "total_sales": 31000.0},
            ],
            "rows_returned": 3,
        }
        line_chart = generate_chart("Show monthly revenue trend", trend_res)
        self.assertIsNotNone(line_chart)
        self.assertEqual(line_chart["chart_type"], "line")

    # -------------------------------------------------------------------------
    # 13. Context-Aware Followups
    # -------------------------------------------------------------------------
    def test_context_aware_followups(self):
        """Follow-up questions must match the analytical topic and business entities."""
        rev_followups = _get_followups("Which products generate the most revenue?")
        self.assertTrue(any("revenue" in f.lower() or "sales" in f.lower() for f in rev_followups))

        cust_followups = _get_followups("Which customers have not placed recent orders?")
        self.assertTrue(any("customer" in f.lower() or "order" in f.lower() for f in cust_followups))

    # -------------------------------------------------------------------------
    # 14. Correlation Disclaimer Enforcement
    # -------------------------------------------------------------------------
    def test_correlation_disclaimer_preservation(self):
        """Questions inquiring about correlation must explicitly warn about causation vs association."""
        from unittest.mock import patch
        with patch("app.agent.orchestrator.ask_groq", return_value="SELECT category, AVG(total_amount) FROM orders JOIN products ON orders.product_id = products.product_id GROUP BY category"):
            res = run_agent("Which factors correlate with a decline in business metrics?")
            self.assertIn("Correlation", res["explanation"])
            self.assertIn("causal", res["explanation"].lower())

    # -------------------------------------------------------------------------
    # 15. Semantic Context Export
    # -------------------------------------------------------------------------
    def test_semantic_context_for_llm(self):
        """DatabaseProfile.to_context() must present entities, metrics, and health warnings to AI."""
        profile = analyze_database(user_id="test_analyst_user")
        ctx = profile.to_context()
        self.assertIn("Overall Data Health Score", ctx)
        self.assertIn("BUSINESS ENTITY CLASSIFICATIONS", ctx)
        self.assertIn("CUSTOMER", ctx)
        self.assertIn("DATA HEALTH FINDINGS", ctx)


if __name__ == "__main__":
    unittest.main()
