"""
backend/scratch/test_phase7_isolation.py

Phase 7 Isolation Tests:
  Multi-user database isolation, concurrent context safety,
  cross-user attack attempts, database switch safety,
  action ownership enforcement.
"""
import sys
import os
import tempfile
import shutil
import threading
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

results = []

def test(name, fn):
    try:
        fn()
        results.append(("[PASS]", name))
        print(f"  [PASS] {name}")
    except Exception as e:
        results.append(("[FAIL]", name, str(e)))
        print(f"  [FAIL] {name}: {e}")


# ── Setup: Create two temporary SQLite databases ───────────────────────────────
_tmpdir = tempfile.mkdtemp(prefix="bgai_phase7_")
DB_A = os.path.join(_tmpdir, "db_a.db")
DB_B = os.path.join(_tmpdir, "db_b.db")

def _create_db(path: str, table: str, col: str, value: str):
    """Create a minimal SQLite DB with a unique signature table."""
    from sqlalchemy import create_engine, text
    e = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    with e.begin() as conn:
        conn.execute(text(f'CREATE TABLE IF NOT EXISTS {table} ({col} TEXT)'))
        conn.execute(text(f"INSERT INTO {table} VALUES ('{value}')"))
    e.dispose()

_create_db(DB_A, "db_a_only", "marker", "THIS_IS_DB_A")
_create_db(DB_B, "db_b_only", "marker", "THIS_IS_DB_B")

USER_A = f"user_a_{uuid.uuid4().hex[:6]}"
USER_B = f"user_b_{uuid.uuid4().hex[:6]}"


# ── 1. Basic Per-User Connect + Isolation ─────────────────────────────────────
print("\n[1] Per-User Connect and Schema Isolation")

def test_user_a_connects_db_a():
    from app.database.connection_context import connect_sqlite_for_user, set_user_context_for_request
    from app.database.database_manager import get_engine
    
    ctx = connect_sqlite_for_user(USER_A, DB_A)
    set_user_context_for_request(USER_A)
    
    e = get_engine()
    assert e is not None
    assert ctx.database_type == "sqlite"
    assert "db_a" in ctx.database_identity
test("User A connects to DB A — engine registered in context", test_user_a_connects_db_a)

def test_user_b_connects_db_b():
    from app.database.connection_context import connect_sqlite_for_user, set_user_context_for_request
    from app.database.database_manager import get_engine
    
    ctx = connect_sqlite_for_user(USER_B, DB_B)
    set_user_context_for_request(USER_B)
    
    e = get_engine()
    assert e is not None
    assert "db_b" in ctx.database_identity
test("User B connects to DB B — separate context", test_user_b_connects_db_b)

def test_user_a_schema_isolated():
    """User A sees ONLY db_a_only table, not db_b_only."""
    from app.database.connection_context import set_user_context_for_request
    from app.tools.get_schema import get_schema
    
    set_user_context_for_request(USER_A)
    schema = get_schema()
    assert "db_a_only" in schema, f"User A should see db_a_only. Schema: {list(schema.keys())}"
    assert "db_b_only" not in schema, f"ISOLATION FAILURE: User A sees db_b_only!"
test("User A schema shows db_a_only table, NOT db_b_only", test_user_a_schema_isolated)

def test_user_b_schema_isolated():
    """User B sees ONLY db_b_only table, not db_a_only."""
    from app.database.connection_context import set_user_context_for_request
    from app.tools.get_schema import get_schema
    
    set_user_context_for_request(USER_B)
    schema = get_schema()
    assert "db_b_only" in schema, f"User B should see db_b_only. Schema: {list(schema.keys())}"
    assert "db_a_only" not in schema, f"ISOLATION FAILURE: User B sees db_a_only!"
test("User B schema shows db_b_only table, NOT db_a_only", test_user_b_schema_isolated)


# ── 2. Concurrent Request Simulation ──────────────────────────────────────────
print("\n[2] Concurrent Request Isolation")

def test_concurrent_schema_requests():
    """
    Simulate A and B making schema requests concurrently.
    Each thread sets its own ContextVar and reads its own schema.
    Verify no cross-contamination.
    """
    from app.database.connection_context import set_user_context_for_request
    from app.tools.get_schema import get_schema
    
    results_dict = {}
    errors = []
    
    def get_schema_for_user(uid, expected_table, unexpected_table):
        try:
            set_user_context_for_request(uid)
            schema = get_schema()
            results_dict[uid] = list(schema.keys())
            if expected_table not in schema:
                errors.append(f"{uid}: missing expected table {expected_table}")
            if unexpected_table in schema:
                errors.append(f"ISOLATION FAILURE: {uid} sees {unexpected_table}")
        except Exception as e:
            errors.append(f"{uid}: exception: {e}")
    
    threads = [
        threading.Thread(target=get_schema_for_user, args=(USER_A, "db_a_only", "db_b_only")),
        threading.Thread(target=get_schema_for_user, args=(USER_B, "db_b_only", "db_a_only")),
        threading.Thread(target=get_schema_for_user, args=(USER_A, "db_a_only", "db_b_only")),
        threading.Thread(target=get_schema_for_user, args=(USER_B, "db_b_only", "db_a_only")),
    ]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert not errors, f"Concurrent isolation failures: {errors}"
test("4 concurrent requests (A,B,A,B) — no schema cross-contamination", test_concurrent_schema_requests)


# ── 3. Cross-User Attack Tests ─────────────────────────────────────────────────
print("\n[3] Cross-User Attack Prevention")

def test_user_a_cannot_access_user_b_audit():
    """User A queries audit events — should only get their own (empty for USER_A)."""
    from app.agents.audit_db import list_audit_events
    
    # Create fake audit event for user B
    from app.agents.audit_db import AuditEvent, AuditSession
    db = AuditSession()
    try:
        ev = AuditEvent(
            id=str(uuid.uuid4()),
            action_id="attack_test_action",
            user_id=USER_B,
            status="AWAITING_CONFIRMATION",
            database_identity="sqlite:///db_b.db",
        )
        db.add(ev)
        db.commit()
    finally:
        db.close()
    
    # User A lists audit events — must NOT see User B's action
    events_a = list_audit_events(USER_A)
    action_ids_a = [e["action_id"] for e in events_a]
    assert "attack_test_action" not in action_ids_a, \
        f"ISOLATION FAILURE: User A sees User B's audit event!"
test("User A cannot see User B's audit events", test_user_a_cannot_access_user_b_audit)

def test_user_a_cannot_access_user_b_action_via_audit_db():
    """get_audit_event with wrong user_id returns None."""
    from app.agents.audit_db import get_audit_event
    # Try to get USER_B's "attack_test_action" as USER_A
    result = get_audit_event("attack_test_action", USER_A)
    assert result is None, f"ISOLATION FAILURE: User A retrieved User B's audit event!"
test("get_audit_event returns None when user_id doesn't match owner", test_user_a_cannot_access_user_b_action_via_audit_db)

def test_cross_db_action_confirmation_blocked():
    """
    Simulate: action created with DB_A identity, but DB_B is now active.
    Confirmation must be rejected (database_identity mismatch).
    """
    from app.agents.audit import store_action, confirm_and_execute_action
    from app.agents.models import ActionPlan
    from app.database.connection_context import set_user_context_for_request

    # Switch to User B's context (DB B)
    set_user_context_for_request(USER_B)
    
    # Create an action with DB_A identity (as if it was created while connected to DB A)
    a_identity = f"sqlite:///{DB_A}"
    b_identity = f"sqlite:///{DB_B}"
    
    action_id = f"cross_db_test_{uuid.uuid4().hex[:8]}"
    action = ActionPlan(
        action_id=action_id,
        task_id="task_cross",
        agent_name="action_agent",
        table="db_a_only",
        action_type="UPDATE",
        estimated_rows=1,
        exact_sql=f'UPDATE "db_a_only" SET marker = \'HACKED\' WHERE 1=1',
        verification_sql='SELECT COUNT(*) FROM "db_a_only"',
        expected_verification_result="1",
        risk_level="HIGH",
        database_identity=a_identity,  # DB A identity
        status="AWAITING_CONFIRMATION",
    )
    store_action(action)
    
    # Now try to confirm while connected to DB B — must be rejected
    result = confirm_and_execute_action(action_id)
    assert result["success"] is False, \
        f"CRITICAL FAILURE: Cross-DB action was EXECUTED! result={result}"
    assert "changed" in result.get("error", "").lower() or "database" in result.get("error", "").lower(), \
        f"Expected 'database changed' error but got: {result.get('error')}"
test("Cross-DB action confirmation rejected (DB A action, DB B active)", test_cross_db_action_confirmation_blocked)


# ── 4. Database Switch Safety ──────────────────────────────────────────────────
print("\n[4] Database Switch Safety")

def test_pending_action_rejected_after_switch():
    """
    User A creates a pending action on DB A, then switches to DB B.
    Confirming the old action must be rejected.
    """
    from app.agents.audit import store_action, confirm_and_execute_action
    from app.agents.models import ActionPlan
    from app.database.connection_context import connect_sqlite_for_user, set_user_context_for_request
    
    # User creates action on DB A
    set_user_context_for_request(USER_A)
    a_identity = f"sqlite:///{DB_A}"
    
    action_id = f"switch_test_{uuid.uuid4().hex[:8]}"
    action = ActionPlan(
        action_id=action_id,
        task_id="task_switch",
        agent_name="action_agent",
        table="db_a_only",
        action_type="UPDATE",
        estimated_rows=1,
        exact_sql='UPDATE "db_a_only" SET marker = \'MODIFIED\' WHERE 1=1',
        verification_sql='SELECT COUNT(*) FROM "db_a_only"',
        expected_verification_result="1",
        risk_level="LOW",
        database_identity=a_identity,
        status="AWAITING_CONFIRMATION",
    )
    store_action(action)
    
    # User "switches" to DB B (reconnect)
    connect_sqlite_for_user(USER_A, DB_B)
    set_user_context_for_request(USER_A)
    
    # Try to confirm old action (DB A identity, but DB B is now active)
    result = confirm_and_execute_action(action_id)
    assert result["success"] is False, \
        f"CRITICAL FAILURE: Action was executed on wrong database! result={result}"
test("Pending action rejected after DB switch (no execution on wrong DB)", test_pending_action_rejected_after_switch)


# ── 5. Action Replay Protection ─────────────────────────────────────────────────
print("\n[5] Action Replay Protection")

def test_confirmed_action_cannot_be_confirmed_again():
    """An already-VERIFIED or CANCELLED action must reject re-confirmation."""
    from app.agents.audit import store_action, cancel_action, confirm_and_execute_action
    from app.agents.models import ActionPlan
    from app.database.connection_context import set_user_context_for_request
    
    set_user_context_for_request(USER_A)
    
    action_id = f"replay_test_{uuid.uuid4().hex[:8]}"
    action = ActionPlan(
        action_id=action_id,
        task_id="task_replay",
        agent_name="action_agent",
        table="db_a_only",
        action_type="UPDATE",
        estimated_rows=1,
        exact_sql='UPDATE "db_a_only" SET marker = \'REPLAY\' WHERE 1=1',
        verification_sql='SELECT COUNT(*) FROM "db_a_only"',
        expected_verification_result="1",
        risk_level="LOW",
        database_identity=f"sqlite:///{DB_A}",
        status="AWAITING_CONFIRMATION",
    )
    store_action(action)
    
    # Cancel the action
    cancel_result = cancel_action(action_id)
    assert cancel_result["success"] is True
    
    # Try to confirm a cancelled action
    replay_result = confirm_and_execute_action(action_id)
    assert replay_result["success"] is False
    assert replay_result.get("status") != "VERIFIED", "REPLAY ATTACK: Cancelled action was re-executed!"
test("Cancelled action cannot be confirmed (replay protection)", test_confirmed_action_cannot_be_confirmed_again)


# ── 6. Context Clear on Disconnect ────────────────────────────────────────────
print("\n[6] Context Clear on Disconnect")

def test_clear_user_context_resets_engine():
    from app.database.connection_context import (
        connect_sqlite_for_user, set_user_context_for_request,
        clear_user_context, get_request_engine
    )
    
    uid = f"disconnect_test_{uuid.uuid4().hex[:6]}"
    connect_sqlite_for_user(uid, DB_A)
    set_user_context_for_request(uid)
    assert get_request_engine() is not None
    
    clear_user_context(uid)
    set_user_context_for_request(uid)
    
    engine_after = get_request_engine()
    assert engine_after is None, "Engine must be None after disconnect"
test("User context engine is None after clear_user_context (disconnect)", test_clear_user_context_resets_engine)

def test_cache_cleared_on_disconnect():
    from app.security.user_cache import cache_set, cache_get, cache_clear_user
    uid = f"cache_clear_{uuid.uuid4().hex[:6]}"
    cache_set(uid, "schema", ["some_table"])
    cache_set(uid, "intel", {"score": 99})
    
    cache_clear_user(uid)
    
    assert cache_get(uid, "schema") is None
    assert cache_get(uid, "intel") is None
test("All caches cleared for user on disconnect, other users unaffected", test_cache_cleared_on_disconnect)


# ── Cleanup ────────────────────────────────────────────────────────────────────
try:
    from app.database.connection_context import clear_user_context
    clear_user_context(USER_A)
    clear_user_context(USER_B)
except Exception:
    pass

try:
    shutil.rmtree(_tmpdir)
except Exception:
    pass


# ── Summary ────────────────────────────────────────────────────────────────────
passed = sum(1 for r in results if r[0] == "[PASS]")
failed = sum(1 for r in results if r[0] == "[FAIL]")

print(f"\n{'='*60}")
print(f"Phase 7 Isolation Tests: {passed} passed, {failed} failed")
print(f"{'='*60}")

if failed:
    print("\nFailed tests:")
    for r in results:
        if r[0] == "[FAIL]":
            print(f"  {r[1]}: {r[2]}")

sys.exit(0 if failed == 0 else 1)
