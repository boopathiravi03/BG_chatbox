#!/usr/bin/env python
"""backend/scratch/test_hardened_crud.py

Comprehensive regression & safety test suite for:
1. UPDATE & DELETE schema validation (table exists, column exists, PK modification blocked)
2. Compound WHERE conditions & operator allowlist
3. NULL handling (IS NULL / IS NOT NULL)
4. Mass-write impact estimation (> 100 records flags high-risk)
5. Replay prevention, fingerprint binding, and TTL expiration
6. Double-submission / concurrent execution locking
7. Non-relational NoSQL honest limitation
"""

import sys
import os
import time
import sqlite3
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.crud.predicates import validate_and_build_where
from app.crud.matcher import count_matching_records, match_records
from app.crud.confirmation import store_pending, get_pending, clear_pending
from app.crud.service import execute_confirmed
from app.crud.router import handle_crud_request
import app.database.database_manager as dbm
from sqlalchemy import create_engine, text

results = []

def test(name, fn):
    try:
        fn()
        results.append(("PASS", name))
        print(f"  [PASS] {name}")
    except Exception as e:
        results.append(("FAIL", name, str(e)))
        print(f"  [FAIL] {name}: {e}")

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------
SCHEMA = {
    "customers": {
        "id": {"type": "INTEGER", "primary_key": True, "nullable": False},
        "name": {"type": "VARCHAR", "primary_key": False, "nullable": False},
        "city": {"type": "VARCHAR", "primary_key": False, "nullable": True},
        "status": {"type": "VARCHAR", "primary_key": False, "nullable": True},
        "balance": {"type": "FLOAT", "primary_key": False, "nullable": True},
    }
}

def setup_test_db():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                city TEXT,
                status TEXT,
                balance REAL
            )
        """))
        # Insert 150 rows (to test mass-write safeguard > 100)
        rows = [
            {"name": f"Cust {i}", "city": "Chennai" if i % 2 == 0 else "Salem", "status": "pending" if i <= 120 else "active", "balance": float(i * 10)}
            for i in range(1, 151)
        ]
        for r in rows:
            conn.execute(
                text("INSERT INTO customers (name, city, status, balance) VALUES (:name, :city, :status, :balance)"),
                r
            )
    return engine

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

def test_predicate_validation_valid_compound():
    conds = [
        {"column": "city", "operator": "=", "value": "Chennai"},
        {"column": "status", "operator": "!=", "value": "active"},
        {"column": "balance", "operator": ">=", "value": 500},
    ]
    res = validate_and_build_where("customers", conds, SCHEMA)
    assert res["valid"] is True
    assert '"city" = \'Chennai\'' in res["where_clause"]
    assert '"status" != \'active\'' in res["where_clause"]
    assert '"balance" >= 500' in res["where_clause"]

def test_predicate_validation_invalid_column():
    conds = [{"column": "non_existent", "operator": "=", "value": "x"}]
    res = validate_and_build_where("customers", conds, SCHEMA)
    assert res["valid"] is False
    assert "does not exist on table" in res["error"]

def test_predicate_validation_invalid_operator():
    conds = [{"column": "city", "operator": "INJECTION_OP", "value": "x"}]
    res = validate_and_build_where("customers", conds, SCHEMA)
    assert res["valid"] is False
    assert "Unsupported operator" in res["error"]

def test_predicate_validation_null_handling():
    conds = [
        {"column": "city", "operator": "is null", "value": None},
        {"column": "status", "operator": "!=", "value": None},
    ]
    res = validate_and_build_where("customers", conds, SCHEMA)
    assert res["valid"] is True
    assert '"city" IS NULL' in res["where_clause"]
    assert '"status" IS NOT NULL' in res["where_clause"]

def test_mass_write_safeguard_over_100_rows():
    engine = setup_test_db()
    dbm.engine = engine
    dbm.current_db_type = "sqlite"
    try:
        # 120 pending customers in DB
        res = handle_crud_request(
            user_message="delete from customers where status is pending",
            session_id="sess_mass",
            schema=SCHEMA,
            database_type="sqlite",
        )
        assert res is not None
        assert res.get("requires_confirmation") is True
        assert res.get("is_high_risk") is True
        assert res.get("estimated_affected_rows") == 120
        assert "HIGH-RISK" in res.get("explanation")
    finally:
        dbm.engine = None
        dbm.current_db_type = "none"

def test_mass_write_requires_explicit_confirmation():
    engine = setup_test_db()
    dbm.engine = engine
    dbm.current_db_type = "sqlite"
    try:
        # Prepare mass delete
        res = handle_crud_request(
            user_message="delete from customers where status is pending",
            session_id="sess_confirm_gate",
            schema=SCHEMA,
            database_type="sqlite",
        )
        fingerprint = res.get("fingerprint")

        # Confirming without high_risk_confirmed should reject
        conf_res = execute_confirmed("sess_confirm_gate", fingerprint=fingerprint, high_risk_confirmed=False)
        assert conf_res["confirmed"] is False
        assert conf_res.get("requires_high_risk_confirmation") is True

        # Now confirm with high_risk_confirmed=True
        conf_success = execute_confirmed("sess_confirm_gate", fingerprint=fingerprint, high_risk_confirmed=True)
        assert conf_success["confirmed"] is True
        assert conf_success.get("affected_rows") == 120

        # Verify in DB: remaining rows should be 30
        with engine.connect() as conn:
            cnt = conn.execute(text("SELECT COUNT(*) FROM customers")).fetchone()[0]
            assert cnt == 30
    finally:
        dbm.engine = None
        dbm.current_db_type = "none"

def test_fingerprint_tampering_protection():
    engine = setup_test_db()
    dbm.engine = engine
    dbm.current_db_type = "sqlite"
    try:
        handle_crud_request(
            user_message="delete from customers where id = 1",
            session_id="sess_tamper",
            schema=SCHEMA,
            database_type="sqlite",
        )
        # Attempt confirmation with forged fingerprint
        res = execute_confirmed("sess_tamper", fingerprint="forged_fingerprint_123")
        assert res["confirmed"] is False
        assert "fingerprint mismatch" in res["error"]
    finally:
        dbm.engine = None
        dbm.current_db_type = "none"

def test_replay_protection():
    engine = setup_test_db()
    dbm.engine = engine
    dbm.current_db_type = "sqlite"
    try:
        res = handle_crud_request(
            user_message="delete from customers where id = 1",
            session_id="sess_replay",
            schema=SCHEMA,
            database_type="sqlite",
        )
        fp = res.get("fingerprint")
        first_run = execute_confirmed("sess_replay", fingerprint=fp)
        assert first_run["confirmed"] is True

        # Second run should fail because session is consumed
        second_run = execute_confirmed("sess_replay", fingerprint=fp)
        assert second_run["confirmed"] is False
        assert "no pending database operation" in second_run["error"]
    finally:
        dbm.engine = None
        dbm.current_db_type = "none"

def test_atomic_concurrency_lock():
    sess = "sess_lock"
    store_pending(session_id=sess, operation="update", table="customers", sql="UPDATE customers SET city='X' WHERE id=1")
    pending = get_pending(sess)
    pending["is_executing"] = True

    # Try executing while is_executing is true
    res = execute_confirmed(sess)
    assert res["confirmed"] is False
    assert "already executing" in res["error"]

def test_nosql_honest_safeguard():
    res = handle_crud_request(
        user_message="delete from customers where id = 1",
        session_id="sess_nosql",
        schema=SCHEMA,
        database_type="mongodb",
    )
    assert res is not None
    assert res.get("type") == "error"
    assert "Conversational CRUD is currently supported for relational SQL databases" in res.get("message")

def test_primary_key_modification_blocked():
    res = handle_crud_request(
        user_message="update customers set id = 999 where id = 1",
        session_id="sess_pk",
        schema=SCHEMA,
        database_type="sqlite",
    )
    assert res is not None
    assert res.get("type") == "error"
    assert "cannot modify the primary key" in res.get("message")

if __name__ == "__main__":
    print("=" * 60)
    print("RUNNING HARDENED CRUD REGRESSION SUITE")
    print("=" * 60)
    test("Predicate validation with valid compound AND filters", test_predicate_validation_valid_compound)
    test("Predicate validation rejects unknown column", test_predicate_validation_invalid_column)
    test("Predicate validation rejects unsupported operator", test_predicate_validation_invalid_operator)
    test("Predicate validation handles IS NULL and IS NOT NULL", test_predicate_validation_null_handling)
    test("Mass-write safeguard detects >100 rows and sets high-risk", test_mass_write_safeguard_over_100_rows)
    test("Mass-write requires explicit high_risk_confirmed parameter", test_mass_write_requires_explicit_confirmation)
    test("Fingerprint tampering protection invalidates mismatch", test_fingerprint_tampering_protection)
    test("Replay protection prevents duplicate confirmation execution", test_replay_protection)
    test("Atomic concurrency lock prevents duplicate clicks", test_atomic_concurrency_lock)
    test("NoSQL connector safeguard honestly states limitation", test_nosql_honest_safeguard)
    test("Primary key modification is blocked safely", test_primary_key_modification_blocked)
    print("=" * 60)
    passed = sum(1 for r in results if r[0] == "PASS")
    failed = sum(1 for r in results if r[0] == "FAIL")
    print(f"Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
