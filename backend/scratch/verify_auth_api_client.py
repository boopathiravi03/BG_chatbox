#!/usr/bin/env python
"""
backend/scratch/verify_auth_api_client.py

Comprehensive regression test verifying the authentication, token validation,
and database status endpoints (/database-info, /database-type).

Tests:
1. No Authorization header:
   - /database-info -> 401
   - /database-type -> 401
2. Invalid / tampered JWT:
   - /database-info -> 401
   - /database-type -> 401
3. Valid JWT + disconnected database:
   - /database-info -> 200 (connected: False)
   - /database-type -> 200 (connected: False, db_type: 'none')
4. Valid JWT + connected database:
   - /database-info -> 200 (connected: True, db_type: 'sqlite')
   - /database-type -> 200 (connected: True, db_type: 'sqlite')

CRITICAL SECURITY RULE: NEVER print JWT values in output or logs.
"""
import os
import sys
import tempfile
import sqlite3

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app
from app.security.auth import create_access_token
from app.database.connection_context import clear_user_context

client = TestClient(app)

results = []

def run_test(name, fn):
    try:
        fn()
        results.append(("PASS", name))
        print(f"  [PASS] {name}")
    except Exception as e:
        results.append(("FAIL", name, str(e)))
        print(f"  [FAIL] {name}: {e}")


def test_no_auth_header():
    """Scenario 1: Requests without Authorization header must receive 401."""
    r_info = client.get("/database-info")
    assert r_info.status_code == 401, f"Expected 401, got {r_info.status_code}: {r_info.text}"
    assert "Authentication required" in r_info.text or "detail" in r_info.text

    r_type = client.get("/database-type")
    assert r_type.status_code == 401, f"Expected 401, got {r_type.status_code}: {r_type.text}"


def test_invalid_jwt():
    """Scenario 2: Requests with invalid or tampered JWT must receive 401."""
    invalid_headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature"}

    r_info = client.get("/database-info", headers=invalid_headers)
    assert r_info.status_code == 401, f"Expected 401, got {r_info.status_code}: {r_info.text}"

    r_type = client.get("/database-type", headers=invalid_headers)
    assert r_type.status_code == 401, f"Expected 401, got {r_type.status_code}: {r_type.text}"


def test_valid_jwt_disconnected():
    """Scenario 3: Valid JWT with no database connected must receive clean 200 OK."""
    user_id = "test_user_disc_123"
    token = create_access_token(user_id, "test_user_disc")
    clear_user_context(user_id)
    headers = {"Authorization": f"Bearer {token}"}

    r_info = client.get("/database-info", headers=headers)
    assert r_info.status_code == 200, f"Expected 200, got {r_info.status_code}: {r_info.text}"
    d_info = r_info.json()
    assert d_info.get("connected") is False, f"Expected connected: False, got {d_info}"
    assert d_info.get("db_type") == "none", f"Expected db_type: 'none', got {d_info}"

    r_type = client.get("/database-type", headers=headers)
    assert r_type.status_code == 200, f"Expected 200, got {r_type.status_code}: {r_type.text}"
    d_type = r_type.json()
    assert d_type.get("connected") is False, f"Expected connected: False, got {d_type}"
    assert d_type.get("db_type") == "none", f"Expected db_type: 'none', got {d_type}"


def test_valid_jwt_connected():
    """Scenario 4: Valid JWT with connected database must receive 200 OK with live details."""
    user_id = "test_user_conn_456"
    token = create_access_token(user_id, "test_user_conn")
    headers = {"Authorization": f"Bearer {token}"}

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, title TEXT, price REAL)")
        cur.execute("INSERT INTO products VALUES (1, 'Widget', 29.99)")
        conn.commit()
        conn.close()

        # Connect user to test DB
        r_conn = client.post("/connect", json={
            "db_type": "sqlite",
            "database": db_path,
            "host": "localhost",
            "port": 0,
            "username": "",
            "password": ""
        }, headers=headers)
        assert r_conn.status_code == 200, f"Connect failed: {r_conn.text}"

        r_info = client.get("/database-info", headers=headers)
        assert r_info.status_code == 200, f"Expected 200, got {r_info.status_code}: {r_info.text}"
        d_info = r_info.json()
        assert d_info.get("connected") is True, f"Expected connected: True, got {d_info}"
        assert d_info.get("db_type") == "sqlite", f"Expected db_type: 'sqlite', got {d_info}"
        assert d_info.get("tables") == 1, f"Expected 1 table, got {d_info.get('tables')}"

        r_type = client.get("/database-type", headers=headers)
        assert r_type.status_code == 200, f"Expected 200, got {r_type.status_code}: {r_type.text}"
        d_type = r_type.json()
        assert d_type.get("connected") is True, f"Expected connected: True, got {d_type}"
        assert d_type.get("db_type") == "sqlite", f"Expected db_type: 'sqlite', got {d_type}"

        # Disconnect clean up
        r_disc = client.post("/disconnect", headers=headers)
        assert r_disc.status_code == 200
    finally:
        clear_user_context(user_id)
        if os.path.exists(db_path):
            try:
                os.unlink(db_path)
            except Exception:
                pass


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("VERIFY AUTH & API CLIENT STATUS REGRESSION SUITE")
    print("=" * 60 + "\n")

    run_test("1. No Authorization header -> 401 Unauthorized", test_no_auth_header)
    run_test("2. Invalid / tampered JWT -> 401 Unauthorized", test_invalid_jwt)
    run_test("3. Valid JWT + disconnected database -> 200 OK (connected: False)", test_valid_jwt_disconnected)
    run_test("4. Valid JWT + connected database -> 200 OK (connected: True)", test_valid_jwt_connected)

    print("\n" + "=" * 60)
    passed = sum(1 for r in results if r[0] == "PASS")
    failed = sum(1 for r in results if r[0] == "FAIL")
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")

    sys.exit(0 if failed == 0 else 1)
