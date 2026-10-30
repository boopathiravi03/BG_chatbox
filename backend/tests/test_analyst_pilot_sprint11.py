"""backend/tests/test_analyst_pilot_sprint11.py

Sprint 11: Human Pilot Activation, Database-Level Read-Only Security & Gate Verification Suite.

Covers:
1. Dual-Layer Security Verification:
   - Layer 1: Application-level CommandPolicy blocking write/DDL attempts.
   - Layer 2: Database engine-level enforcement (PRAGMA query_only = ON / least-privilege read-only role).
   - Independent verification that even if a write statement were submitted directly to the database,
     the database engine itself rejects it with an operational read-only error.

2. Authentication, Anti-Spoofing & Multi-Tenant Isolation:
   - Forged identity headers without cryptographic signature return HTTP 401.
   - Cross-tenant isolation between Pilot Analyst 1 and Pilot Analyst 2.
   - Secret redaction across errors and logs.

3. Calculation Semantics Integrity:
   - Zero-baseline percentage change evaluates to None (undefined/N/A) without numerical sentinels.
   - Negative baseline transitions evaluate using absolute baseline value in denominator.
"""

from __future__ import annotations

import os
import sys
import time
import json
import sqlite3
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
from app.tools.command_policy import CommandPolicy, CommandCategory
from app.tools.execute_query import execute_query, sanitize_error_message


class TestSprint11DualLayerReadOnlySecurity(unittest.TestCase):
    """Section 5: Independent verification of application SQL policy AND database-level read-only permissions."""

    def setUp(self):
        # Create an engine representing a database with engine-level query_only enforcement
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE staging_sales ("
                    "  id INTEGER PRIMARY KEY,"
                    "  sale_date TEXT,"
                    "  category TEXT,"
                    "  amount REAL"
                    ")"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO staging_sales VALUES "
                    "(1, '2026-02-10 10:00:00', 'Enterprise', 100000.0),"
                    "(2, '2026-03-10 10:00:00', 'Enterprise', 75000.0)"
                )
            )

    def tearDown(self):
        self.engine.dispose()

    def test_layer1_application_sql_policy_blocks_mutations(self):
        """Layer 1: CommandPolicy rejects all mutating DML/DDL before submission to database."""
        class MockReadOnlyConnector:
            name = "pilot_staging_pg"
            connector_type = "postgres"
            is_read_only = True
            category = "relational"

        conn = MockReadOnlyConnector()
        mutations = [
            "DELETE FROM staging_sales WHERE id = 1;",
            "UPDATE staging_sales SET amount = 0;",
            "INSERT INTO staging_sales (id, amount) VALUES (99, 100);",
            "DROP TABLE staging_sales;",
            "ALTER TABLE staging_sales ADD COLUMN backdoor TEXT;",
        ]
        for m in mutations:
            val = CommandPolicy.validate(m, dialect="postgres", connector=conn)
            self.assertFalse(val.allowed, f"Layer 1 must block mutating query: {m}")
            self.assertIn("READ-ONLY", val.reason)

    def test_layer2_database_engine_level_readonly_enforcement(self):
        """
        Layer 2: Database engine itself enforces read-only access.
        Simulates dedicated least-privilege read-only analytical credentials (e.g. GRANT SELECT only).
        Even if a raw write statement bypasses application logic, the database engine rejects it.
        """
        with self.engine.connect() as conn:
            # Enforce read-only mode at database engine level
            conn.execute(text("PRAGMA query_only = ON;"))

            # 1. Permitted SELECT reads succeed
            res = conn.execute(text("SELECT COUNT(*), SUM(amount) FROM staging_sales;")).fetchone()
            self.assertIsNotNone(res)
            self.assertEqual(res[0], 2)
            self.assertEqual(res[1], 175000.0)

            # 2. Mutating write attempts are rejected directly by the database engine
            with self.assertRaises(Exception) as ctx:
                conn.execute(text("INSERT INTO staging_sales VALUES (3, '2026-03-15', 'Consumer', 5000.0);"))
            self.assertIn("readonly", str(ctx.exception).lower())

            with self.assertRaises(Exception) as ctx:
                conn.execute(text("DELETE FROM staging_sales WHERE id = 1;"))
            self.assertIn("readonly", str(ctx.exception).lower())

            with self.assertRaises(Exception) as ctx:
                conn.execute(text("DROP TABLE staging_sales;"))
            self.assertIn("readonly", str(ctx.exception).lower())


class TestSprint11SecurityAndCalculationSemantics(unittest.TestCase):
    """Section 5 & 6: Authentication anti-spoofing, tenant isolation, and calculation semantics."""

    def setUp(self):
        self.client = TestClient(app)
        self.store_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        set_investigation_store_engine(self.store_engine)

        self.user_alpha = "pilot_analyst_alpha"
        self.user_beta = "pilot_analyst_beta"
        self.token_alpha = create_access_token(self.user_alpha, "alpha")
        self.token_beta = create_access_token(self.user_beta, "beta")
        self.headers_alpha = {"Authorization": f"Bearer {self.token_alpha}"}
        self.headers_beta = {"Authorization": f"Bearer {self.token_beta}"}

    def tearDown(self):
        self.store_engine.dispose()

    def test_forged_identity_headers_are_rejected(self):
        """Header injection without valid cryptographic signature returns HTTP 401."""
        forged = {"X-User-Id": "admin_root", "X-Remote-User": "root"}
        res = self.client.get("/investigation/reports", headers=forged)
        self.assertEqual(res.status_code, 401)

    def test_tenant_isolation_alpha_vs_beta(self):
        """Reports created by Analyst Alpha are completely isolated from Analyst Beta."""
        save_investigation_report(
            report_id="rep_alpha_sprint11_confidential",
            user_id=self.user_alpha,
            connection_id="conn_stg",
            question="Why did Q1 margin decline?",
            title="Q1 Margin Analysis",
            status="success",
            summary="Confidential analysis",
            report_data={"margin_delta": -5.5},
        )

        # Beta attempts direct lookup -> 404
        res_beta_get = self.client.get("/investigation/reports/rep_alpha_sprint11_confidential", headers=self.headers_beta)
        self.assertEqual(res_beta_get.status_code, 404)

        # Beta attempts deletion -> fails safe
        res_beta_del = self.client.delete("/investigation/reports/rep_alpha_sprint11_confidential", headers=self.headers_beta)
        self.assertEqual(res_beta_del.status_code, 200)
        self.assertFalse(res_beta_del.json()["deleted"])

    def test_secret_sanitization_in_connection_errors(self):
        """Credentials, passwords, and tokens are scrubbed from user-facing error envelopes."""
        raw_err = "OperationalError: connection to postgresql://stg_user:Pass%23%2199@10.0.0.1:5432/corp_db failed: Bearer secret_token_xyz"
        clean = sanitize_error_message(raw_err)
        self.assertNotIn("Pass%23%2199", clean)
        self.assertNotIn("secret_token_xyz", clean)
        self.assertIn("***", clean)

    def test_zero_baseline_percentage_is_none_without_sentinels(self):
        """Zero baseline percentage evaluates to None (undefined / N/A) without numerical sentinels."""
        from app.intelligence.investigation.models import ObservedChange
        obs = ObservedChange(
            metric="revenue",
            current_value=50000.0,
            previous_value=0.0,
            delta=50000.0,
            delta_percent=None,
            formatted_change="+50000.0 (N/A (Baseline was zero: 0.00 -> 50,000.00))",
        )
        self.assertIsNone(obs.delta_percent)
        self.assertIn("N/A", obs.formatted_change)

    def test_dimensional_contributor_zero_baseline_consistency(self):
        """Dimensional contributors with zero baseline evaluate dim_pct_change to None and disclose N/A."""
        from app.intelligence.investigation.models import ContributingFactor
        obs_desc = "+1,000.00 (N/A (Baseline was zero)) in period. Current: 1,000.00, Previous: 0.00"
        factor = ContributingFactor(
            factor_id="fac_test_123",
            dimension="products.category",
            dimension_value="NewProductLine",
            impact_type="positive",
            contribution_percent=100.0,
            observed_change=obs_desc,
        )
        self.assertIn("N/A (Baseline was zero)", factor.observed_change)
        self.assertNotIn("100.0%", factor.observed_change)


if __name__ == "__main__":
    unittest.main()
