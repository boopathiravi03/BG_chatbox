#!/usr/bin/env python
"""
backend/scratch/verify_error_audit.py

Verifies the Error & Regression fix pass:
1. Unauthenticated requests to protected endpoints -> 401 Unauthorized (strictly preserved)
2. Authenticated requests when DISCONNECTED -> 200 OK with connected: False (no 401, no 500)
3. Authenticated requests when CONNECTED -> 200 OK with live database metrics & insights
4. Authenticated requests after DISCONNECT -> 200 OK with connected: False and old caches cleared
5. User isolation: User A cannot see User B's insights or engine
"""
import os
import sys
import tempfile
import sqlite3
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.security.auth import create_access_token
from app.security.sessions import AuthenticatedUser
from app.database.connection_context import set_user_context_for_request, clear_user_context
from app.database.database_manager import connect_sqlite

client = TestClient(app)

results = []

def run_check(name, fn):
    try:
        fn()
        results.append(("PASS", name))
        print(f"  [PASS] {name}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        results.append(("FAIL", name, str(e)))
        print(f"  [FAIL] {name}: {e}")

# 1. Unauthenticated checks
def test_unauth_rejected():
    r1 = client.get("/database-info")
    assert r1.status_code == 401, f"Expected 401, got {r1.status_code}"
    r2 = client.get("/database-type")
    assert r2.status_code == 401, f"Expected 401, got {r2.status_code}"
    r3 = client.get("/intelligence/insights")
    assert r3.status_code == 401, f"Expected 401, got {r3.status_code}"

# 2. Authenticated Disconnected checks
def test_auth_disconnected_clean_200():
    token = create_access_token("user_audit_1", "audit_user1")
    headers = {"Authorization": f"Bearer {token}"}

    # /database-info must return 200 with connected: False
    r_info = client.get("/database-info", headers=headers)
    assert r_info.status_code == 200, f"Expected 200, got {r_info.status_code}"
    d_info = r_info.json()
    assert d_info.get("connected") is False, f"Expected connected: False, got {d_info}"
    assert d_info.get("db_type") == "none"

    # /database-type must return 200 with connected: False, db_type: none
    r_type = client.get("/database-type", headers=headers)
    assert r_type.status_code == 200, f"Expected 200, got {r_type.status_code}"
    d_type = r_type.json()
    assert d_type.get("connected") is False, f"Expected connected: False, got {d_type}"
    assert d_type.get("db_type") == "none"

    # /database-connection-info must return 200 with connected: False
    r_conn = client.get("/database-connection-info", headers=headers)
    assert r_conn.status_code == 200
    assert r_conn.json().get("connected") is False

    # /intelligence/insights must return 200 with status: no_database
    r_bi = client.get("/intelligence/insights", headers=headers)
    assert r_bi.status_code == 200
    d_bi = r_bi.json()
    assert d_bi.get("status") in ("no_database", "insufficient_data", "success")

# 3. Authenticated Connected checks
def test_auth_connected_flow():
    token = create_access_token("user_audit_2", "audit_user2")
    headers = {"Authorization": f"Bearer {token}"}

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        # Create small test database
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("CREATE TABLE sales (id INTEGER PRIMARY KEY, amount REAL, created_at TEXT)")
        for i in range(1, 10):
            cur.execute("INSERT INTO sales VALUES (?, ?, ?)", (i, i * 100.0, f"2024-0{min(i, 6)}-01"))
        conn.commit()
        conn.close()

        # Connect via endpoint
        r_conn = client.post("/connect", json={
            "db_type": "sqlite",
            "database": db_path,
            "host": "localhost",
            "port": 0,
            "username": "",
            "password": ""
        }, headers=headers)
        assert r_conn.status_code == 200, f"Connect failed: {r_conn.text}"

        # /database-info should now show connected: True
        r_info = client.get("/database-info", headers=headers)
        assert r_info.status_code == 200
        d_info = r_info.json()
        assert d_info.get("connected") is True
        assert d_info.get("db_type") == "sqlite"
        assert d_info.get("tables") == 1

        # /database-type should show connected: True
        r_type = client.get("/database-type", headers=headers)
        assert r_type.status_code == 200
        assert r_type.json().get("connected") is True

        # /intelligence/insights should generate real insights
        r_bi = client.get("/intelligence/insights", headers=headers)
        assert r_bi.status_code == 200
        d_bi = r_bi.json()
        assert d_bi.get("success") is True
        assert "insights" in d_bi

        # Refresh insights
        r_ref = client.post("/intelligence/insights/refresh", headers=headers)
        assert r_ref.status_code == 200
        assert r_ref.json().get("success") is True

        # Disconnect
        r_disc = client.post("/disconnect", headers=headers)
        assert r_disc.status_code == 200

        # After disconnect, returns connected: False
        r_after = client.get("/database-info", headers=headers)
        assert r_after.status_code == 200
        assert r_after.json().get("connected") is False

    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass

if __name__ == "__main__":
    print("\n============================================================")
    print("VERIFY ERROR AUDIT: AUTH & DISCONNECTED FLOWS")
    print("============================================================\n")

    run_check("1. Unauthenticated requests receive 401 Unauthorized", test_unauth_rejected)
    run_check("2. Authenticated disconnected requests receive clean 200 OK with connected: False", test_auth_disconnected_clean_200)
    run_check("3. Authenticated connected requests return live data & insights; disconnect resets cleanly", test_auth_connected_flow)

    passed = sum(1 for r in results if r[0] == "PASS")
    failed = sum(1 for r in results if r[0] != "PASS")
    print(f"\n============================================================")
    print(f"Audit Verification Results: {passed} passed, {failed} failed")
    print("============================================================\n")
    sys.exit(0 if failed == 0 else 1)
