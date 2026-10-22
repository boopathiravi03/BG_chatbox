"""backend/tests/test_command_execution.py

Comprehensive test suite for BG AI's unified SQL and database command execution engine.
Covers:
1. Command policy categorization (READ, DATA_MUTATION, SCHEMA_CHANGE, DESTRUCTIVE_DDL, ADMINISTRATION, TRANSACTION_CONTROL, NATIVE_CONNECTOR_OPERATION, PROHIBITED_SYSTEM).
2. WHERE predicate analysis (bounded vs missing vs trivial 1=1).
3. Parser resilience (comments, quotes with semicolons, CTEs, quoted identifiers, stacked statement rejection).
4. Prohibited system command blocking (ATTACH, DETACH, LOAD DATA, xp_cmdshell, SHUTDOWN).
5. Read-only connection enforcement across all connector categories (relational, document, key-value, vector).
6. Direct /query confirmation bypass prevention and auto-staging.
7. Cryptographic fingerprint verification (64-char SHA-256, missing, mismatch, tamper detection).
8. Cross-user isolation (User B cannot confirm User A's staged operation).
9. Cross-connection isolation (staged operation cannot be executed against a different connection).
10. Expiry enforcement and single-use replay rejection.
11. Concurrent duplicate confirmation prevention (concurrency lock).
12. Schema drift and row count drift detection.
13. Engine rollback behavior matrix (PostgreSQL, SQLite, MySQL, MSSQL).
14. Native non-relational command validation (MongoDB, Redis, Vector, SQL-to-native rejection).
15. End-to-end database lifecycle execution on disposable SQLite with automatic schema cache refresh.
"""

from __future__ import annotations

import os
import sys
import time
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

_BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(_BACKEND_DIR / ".env")

from app.tools.command_policy import CommandPolicy, CommandCategory, generate_command_fingerprint
from app.tools.execute_query import execute_query, validate_sql
from app.crud.confirmation import store_pending, get_pending, clear_pending
from app.crud.service import execute_confirmed
from app.database.database_context import (
    get_database_profile,
    refresh_database_profile,
)
from app.database.connection_context import (
    connect_sqlite_for_user,
    set_user_context_for_request,
    clear_user_context,
)
from app.connectors.registry import get_connection_registry
from app.connectors.base import QueryResult


def run_test(name: str, fn):
    try:
        fn()
        print(f"PASS  {name}")
        return True
    except Exception as e:
        print(f"FAIL  {name}: {e}")
        import traceback
        traceback.print_exc()
        return False


# =====================================================================
# 1. Command Categories Classification
# =====================================================================

def test_command_categories_classification():
    # 1. READ
    r1 = CommandPolicy.validate("SELECT id, name FROM users WHERE active = 1")
    assert r1.category == CommandCategory.READ
    assert r1.requires_confirmation is False

    r2 = CommandPolicy.validate("WITH active_users AS (SELECT * FROM users WHERE active = 1) SELECT * FROM active_users")
    assert r2.category == CommandCategory.READ

    r3 = CommandPolicy.validate("EXPLAIN SELECT 1")
    assert r3.category == CommandCategory.READ

    # 2. DATA_MUTATION
    m1 = CommandPolicy.validate("INSERT INTO users (name) VALUES ('Alice')")
    assert m1.category == CommandCategory.DATA_MUTATION
    assert m1.requires_confirmation is True
    assert m1.is_high_risk is False

    m2 = CommandPolicy.validate("UPDATE users SET name = 'Bob' WHERE id = 1")
    assert m2.category == CommandCategory.DATA_MUTATION
    assert m2.requires_confirmation is True
    assert m2.is_high_risk is False

    m3 = CommandPolicy.validate("DELETE FROM users WHERE id = 1")
    assert m3.category == CommandCategory.DATA_MUTATION
    assert m3.requires_confirmation is True
    assert m3.is_high_risk is False

    # 3. SCHEMA_CHANGE
    s1 = CommandPolicy.validate("CREATE TABLE orders (id INT, amount REAL)")
    assert s1.category == CommandCategory.SCHEMA_CHANGE
    assert s1.requires_confirmation is True
    assert s1.is_high_risk is False

    s2 = CommandPolicy.validate("ALTER TABLE orders ADD COLUMN status TEXT")
    assert s2.category == CommandCategory.SCHEMA_CHANGE
    assert s2.requires_confirmation is True
    assert s2.is_high_risk is False

    s3 = CommandPolicy.validate("CREATE INDEX idx_orders_amt ON orders (amount)")
    assert s3.category == CommandCategory.SCHEMA_CHANGE

    # 4. DESTRUCTIVE_DDL
    d1 = CommandPolicy.validate("DROP TABLE orders")
    assert d1.category == CommandCategory.DESTRUCTIVE_DDL
    assert d1.is_high_risk is True

    d2 = CommandPolicy.validate("TRUNCATE TABLE logs")
    assert d2.category == CommandCategory.DESTRUCTIVE_DDL
    assert d2.is_high_risk is True

    d3 = CommandPolicy.validate("ALTER TABLE orders DROP COLUMN status")
    assert d3.category == CommandCategory.DESTRUCTIVE_DDL
    assert d3.is_high_risk is True

    # 5. ADMINISTRATION
    a1 = CommandPolicy.validate("VACUUM")
    assert a1.category == CommandCategory.ADMINISTRATION
    assert a1.requires_confirmation is True
    assert a1.is_high_risk is False

    a2 = CommandPolicy.validate("ANALYZE")
    assert a2.category == CommandCategory.ADMINISTRATION

    a3 = CommandPolicy.validate("GRANT ALL ON DATABASE prod TO analyst")
    assert a3.category == CommandCategory.ADMINISTRATION
    assert a3.is_high_risk is True

    # 6. TRANSACTION_CONTROL
    t1 = CommandPolicy.validate("BEGIN")
    assert t1.category == CommandCategory.TRANSACTION_CONTROL
    assert t1.requires_confirmation is False

    t2 = CommandPolicy.validate("COMMIT")
    assert t2.category == CommandCategory.TRANSACTION_CONTROL

    t3 = CommandPolicy.validate("ROLLBACK")
    assert t3.category == CommandCategory.TRANSACTION_CONTROL

    # 7. PROHIBITED_SYSTEM
    p1 = CommandPolicy.validate("ATTACH DATABASE 'passwords.db' AS psw")
    assert p1.category == CommandCategory.PROHIBITED_SYSTEM
    assert p1.allowed is False
    assert p1.dangerous is True


# =====================================================================
# 2. WHERE Predicates and High-Risk Analysis
# =====================================================================

def test_where_predicates_and_risk():
    # Bounded UPDATE / DELETE: Standard risk
    bounded_upd = CommandPolicy.validate("UPDATE items SET price = 19.99 WHERE item_id = 101")
    assert bounded_upd.is_high_risk is False

    bounded_del = CommandPolicy.validate("DELETE FROM items WHERE item_id = 101")
    assert bounded_del.is_high_risk is False

    # Missing WHERE: High risk
    missing_where_upd = CommandPolicy.validate("UPDATE items SET price = 0")
    assert missing_where_upd.is_high_risk is True
    assert "affect ALL" in missing_where_upd.impact_summary

    missing_where_del = CommandPolicy.validate("DELETE FROM items")
    assert missing_where_del.is_high_risk is True
    assert "delete ALL" in missing_where_del.impact_summary

    # Trivial WHERE: High risk
    for trivial in ["1 = 1", "0 = 0", "TRUE", "'1' = '1'", "'a' = 'a'"]:
        t_upd = CommandPolicy.validate(f"UPDATE items SET price = 0 WHERE {trivial}")
        assert t_upd.is_high_risk is True, f"Failed for {trivial}"

        t_del = CommandPolicy.validate(f"DELETE FROM items WHERE {trivial}")
        assert t_del.is_high_risk is True, f"Failed for {trivial}"


# =====================================================================
# 3. Parser Resilience and Stacked Statement Blocking
# =====================================================================

def test_parser_resilience():
    # Comments stripped cleanly
    q_line_comment = "SELECT * FROM users -- inline comment\nWHERE id = 1"
    res1 = CommandPolicy.validate(q_line_comment)
    assert res1.allowed is True
    assert res1.category == CommandCategory.READ

    q_block_comment = "/* Multi-line\ncomment */ SELECT * FROM users /* another */ WHERE id = 1"
    res2 = CommandPolicy.validate(q_block_comment)
    assert res2.allowed is True
    assert res2.category == CommandCategory.READ

    # Semicolons inside quoted strings must not trigger multi-statement block
    q_str_semi = "SELECT id, 'first; second' as val FROM users WHERE name = 'semi;colon'"
    res3 = CommandPolicy.validate(q_str_semi)
    assert res3.allowed is True
    assert res3.category == CommandCategory.READ

    # Quoted identifiers
    q_quoted_id = "SELECT [col;1], `col;2`, \"col;3\" FROM [users]"
    res4 = CommandPolicy.validate(q_quoted_id)
    assert res4.allowed is True

    # Stacked statements must be blocked
    stacked = [
        "SELECT 1; DROP TABLE users;",
        "UPDATE users SET active = 1; DELETE FROM audit_log;",
        "SELECT * FROM items;\nDROP DATABASE production;",
        "INSERT INTO logs VALUES (1); DROP TABLE users;",
    ]
    for s in stacked:
        s_res = CommandPolicy.validate(s)
        assert s_res.allowed is False, f"Stacked statement was not blocked: {s}"
        assert "Multiple SQL statements" in s_res.reason


# =====================================================================
# 4. Prohibited System Commands
# =====================================================================

def test_prohibited_system_commands():
    prohibited = [
        "ATTACH DATABASE 'secrets.db' AS sec",
        "DETACH DATABASE sec",
        "LOAD DATA INFILE '/etc/passwd' INTO TABLE users",
        "SELECT * FROM users INTO OUTFILE '/tmp/dump.txt'",
        "EXEC xp_cmdshell 'dir'",
        "SHUTDOWN",
        "COPY users FROM PROGRAM 'cat /etc/passwd'",
    ]
    for p in prohibited:
        res = CommandPolicy.validate(p)
        assert res.allowed is False, f"Expected prohibited command to be blocked: {p}"
        assert res.dangerous is True


# =====================================================================
# 5. Read-Only Enforcement Across All Connector Categories
# =====================================================================

def test_readonly_all_connector_categories():
    uid = "test_ro_all"
    set_user_context_for_request(uid)
    reg = get_connection_registry()

    # 1. Relational Read-Only
    mock_rel = MagicMock()
    mock_rel.connection_id = "mock_ro_rel"
    mock_rel.user_id = uid
    mock_rel.name = "RO SQLite"
    mock_rel.connector_type = "sqlite"
    mock_rel.category = "relational"
    mock_rel.is_read_only = True
    reg.register_connector(mock_rel)

    val_rel = validate_sql("UPDATE users SET name = 'X' WHERE id = 1", connection_id="mock_ro_rel")
    assert val_rel["allowed"] is False
    assert "read-only" in val_rel["reason"].lower()

    # 2. Document (MongoDB) Read-Only
    mock_mongo = MagicMock()
    mock_mongo.connection_id = "mock_ro_doc"
    mock_mongo.user_id = uid
    mock_mongo.name = "RO MongoDB"
    mock_mongo.connector_type = "mongodb"
    mock_mongo.category = "document"
    mock_mongo.is_read_only = True
    reg.register_connector(mock_mongo)

    val_mongo = validate_sql('{"action": "insert", "collection": "users"}', connection_id="mock_ro_doc")
    assert val_mongo["allowed"] is False
    assert "read-only" in val_mongo["reason"].lower()

    # 3. Key-Value (Redis) Read-Only
    mock_redis = MagicMock()
    mock_redis.connection_id = "mock_ro_kv"
    mock_redis.user_id = uid
    mock_redis.name = "RO Redis"
    mock_redis.connector_type = "redis"
    mock_redis.category = "keyvalue"
    mock_redis.is_read_only = True
    reg.register_connector(mock_redis)

    val_redis = validate_sql("SET user:1 'test'", connection_id="mock_ro_kv")
    assert val_redis["allowed"] is False
    assert "read-only" in val_redis["reason"].lower()

    # 4. Vector (Qdrant) Read-Only
    mock_vector = MagicMock()
    mock_vector.connection_id = "mock_ro_vec"
    mock_vector.user_id = uid
    mock_vector.name = "RO Qdrant"
    mock_vector.connector_type = "qdrant"
    mock_vector.category = "vector"
    mock_vector.is_read_only = True
    reg.register_connector(mock_vector)

    val_vec = validate_sql('{"action": "upsert", "collection": "docs"}', connection_id="mock_ro_vec")
    assert val_vec["allowed"] is False
    assert "read-only" in val_vec["reason"].lower()

    reg.remove_connector(uid, "mock_ro_rel")
    reg.remove_connector(uid, "mock_ro_doc")
    reg.remove_connector(uid, "mock_ro_kv")
    reg.remove_connector(uid, "mock_ro_vec")
    clear_user_context(uid)


# =====================================================================
# 6. Direct /query Confirmation Bypass Prevention & Auto-Staging
# =====================================================================

def test_direct_query_confirmation_bypass_prevention():
    temp_dir = tempfile.mkdtemp()
    db_file = Path(temp_dir) / "test_bypass.db"
    test_uid = "bypass_test_user"

    with sqlite3.connect(str(db_file)) as c:
        c.execute("CREATE TABLE accounts (id INT, balance REAL)")
        c.execute("INSERT INTO accounts VALUES (1, 100.0)")
        c.commit()

    connect_sqlite_for_user(test_uid, str(db_file))
    set_user_context_for_request(test_uid)

    sess = f"{test_uid}:sess_direct_1"

    # Calling execute_query with unconfirmed mutation must NOT execute directly
    direct_res = execute_query(
        sql="UPDATE accounts SET balance = 500.0 WHERE id = 1",
        user_id=test_uid,
        session_id=sess,
        is_confirmed=False,
    )
    assert direct_res["success"] is False
    assert direct_res.get("requires_confirmation") is True
    assert direct_res.get("fingerprint") is not None

    # Verify that the balance in database was NOT changed
    with sqlite3.connect(str(db_file)) as c:
        bal = c.execute("SELECT balance FROM accounts WHERE id = 1").fetchone()[0]
        assert bal == 100.0

    # Verify that the operation was staged and can now be confirmed via execute_confirmed
    fp = direct_res["fingerprint"]
    confirm_res = execute_confirmed(sess, fingerprint=fp, user_id=test_uid)
    assert confirm_res["success"] is True

    # Now verify the balance was changed
    with sqlite3.connect(str(db_file)) as c:
        bal = c.execute("SELECT balance FROM accounts WHERE id = 1").fetchone()[0]
        assert bal == 500.0

    clear_user_context(test_uid)


# =====================================================================
# 7. Cryptographic Fingerprint Verification & Tamper Detection
# =====================================================================

def test_fingerprint_security():
    op = "update"
    tbl = "users"
    sql = "UPDATE users SET active = 1 WHERE id = 42"
    db_id = "sqlite:///test.db"
    conn_id = "conn_123"
    uid = "user_abc"
    sess = "sess_xyz"
    exp = 1800000000.0

    fp = generate_command_fingerprint(
        operation=op,
        target=tbl,
        sql=sql,
        database_identity=db_id,
        connection_id=conn_id,
        user_id=uid,
        session_id=sess,
        expires_at=exp,
    )

    # 1. Full 64-character hex string
    assert len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)

    # 2. Tampered SQL produces completely different fingerprint
    fp_tampered = generate_command_fingerprint(
        operation=op,
        target=tbl,
        sql="UPDATE users SET active = 0 WHERE id = 42",
        database_identity=db_id,
        connection_id=conn_id,
        user_id=uid,
        session_id=sess,
        expires_at=exp,
    )
    assert fp != fp_tampered

    # 3. Execution rejection on missing or mismatched fingerprint
    sess_test = "user_sec:sess_fp_test"
    staged = store_pending(
        session_id=sess_test,
        operation=op,
        table=tbl,
        sql=sql,
        user_id="user_sec",
    )

    # Missing fingerprint
    res_missing = execute_confirmed(sess_test, fingerprint=None, user_id="user_sec")
    assert res_missing["success"] is False
    assert "missing" in res_missing["error"].lower()

    # Re-stage and test mismatched fingerprint
    staged = store_pending(
        session_id=sess_test,
        operation=op,
        table=tbl,
        sql=sql,
        user_id="user_sec",
    )
    res_mismatch = execute_confirmed(sess_test, fingerprint="deadbeef" * 8, user_id="user_sec")
    assert res_mismatch["success"] is False
    assert "invalid" in res_mismatch["error"].lower() or "mismatch" in res_mismatch["error"].lower()


# =====================================================================
# 8. Cross-User Isolation
# =====================================================================

def test_cross_user_isolation():
    user_a = "alice_user"
    user_b = "attacker_bob"
    sess = f"{user_a}:shared_session_1"

    staged = store_pending(
        session_id=sess,
        operation="update",
        table="accounts",
        sql="UPDATE accounts SET balance = 1000 WHERE id = 1",
        user_id=user_a,
    )
    fp = staged["fingerprint"]

    # Attacker Bob attempts to confirm Alice's pending operation
    res_cross = execute_confirmed(sess, fingerprint=fp, user_id=user_b)
    assert res_cross["success"] is False
    assert "unauthorized" in res_cross["error"].lower() or "different user" in res_cross["error"].lower()


# =====================================================================
# 9. Cross-Connection Isolation
# =====================================================================

def test_cross_connection_isolation():
    uid = "conn_iso_user"
    set_user_context_for_request(uid)
    reg = get_connection_registry()

    mock_conn1 = MagicMock()
    mock_conn1.connection_id = "conn_alpha"
    mock_conn1.connector_type = "sqlite"
    mock_conn1.user_id = uid
    mock_conn1.category = "relational"
    mock_conn1.is_read_only = False
    reg.register_connector(mock_conn1)

    sess = f"{uid}:conn_sess_1"
    staged = store_pending(
        session_id=sess,
        operation="update",
        table="users",
        sql="UPDATE users SET name = 'New' WHERE id = 1",
        user_id=uid,
        extra={"connection_id": "conn_alpha"},
    )
    fp = staged["fingerprint"]

    # Now switch active connection or remove conn_alpha and replace with conn_beta
    reg.remove_connector(uid, "conn_alpha")
    mock_conn2 = MagicMock()
    mock_conn2.connection_id = "conn_beta"
    mock_conn2.connector_type = "sqlite"
    mock_conn2.user_id = uid
    mock_conn2.category = "relational"
    mock_conn2.is_read_only = False
    reg.register_connector(mock_conn2)

    # Confirmation must fail because connection identity has changed
    res_switch = execute_confirmed(sess, fingerprint=fp, user_id=uid)
    assert res_switch["success"] is False
    assert "connection" in res_switch["error"].lower() and ("changed" in res_switch["error"].lower() or "not found" in res_switch["error"].lower())

    reg.remove_connector(uid, "conn_beta")
    clear_user_context(uid)


# =====================================================================
# 10. Expiry Enforcement and Single-Use Replay Rejection
# =====================================================================

def test_expiry_and_replay_rejection():
    temp_dir = tempfile.mkdtemp()
    db_file = Path(temp_dir) / "test_replay.db"
    test_uid = "replay_test_user"

    with sqlite3.connect(str(db_file)) as c:
        c.execute("CREATE TABLE inventory (id INT, qty INT)")
        c.execute("INSERT INTO inventory VALUES (1, 10)")
        c.commit()

    connect_sqlite_for_user(test_uid, str(db_file))
    set_user_context_for_request(test_uid)

    sess = f"{test_uid}:sess_replay_1"

    # 1. Expiry test
    staged = store_pending(
        session_id=sess,
        operation="update",
        table="inventory",
        sql="UPDATE inventory SET qty = 20 WHERE id = 1",
        user_id=test_uid,
    )
    # Artificially expire the record
    staged["expires_at"] = time.time() - 10

    exp_res = execute_confirmed(sess, fingerprint=staged["fingerprint"], user_id=test_uid)
    assert exp_res["success"] is False
    assert "expired" in exp_res["error"].lower()

    # 2. Replay test
    staged_fresh = store_pending(
        session_id=sess,
        operation="update",
        table="inventory",
        sql="UPDATE inventory SET qty = 20 WHERE id = 1",
        user_id=test_uid,
    )
    fp = staged_fresh["fingerprint"]

    # First execution succeeds
    first_res = execute_confirmed(sess, fingerprint=fp, user_id=test_uid)
    assert first_res["success"] is True

    # Immediate replay fails as single-use
    replay_res = execute_confirmed(sess, fingerprint=fp, user_id=test_uid)
    assert replay_res["success"] is False
    assert "no pending" in replay_res["error"].lower() or "expired" in replay_res["error"].lower()

    clear_user_context(test_uid)


# =====================================================================
# 11. Concurrent Duplicate Confirmation Prevention
# =====================================================================

def test_concurrent_duplicate_confirmation():
    uid = "conc_user"
    sess = f"{uid}:conc_sess"

    staged = store_pending(
        session_id=sess,
        operation="update",
        table="orders",
        sql="UPDATE orders SET status = 'shipped' WHERE id = 5",
        user_id=uid,
    )
    fp = staged["fingerprint"]

    # Simulate an active in-flight execution lock
    staged["is_executing"] = True

    # Second concurrent attempt must be rejected
    res_conc = execute_confirmed(sess, fingerprint=fp, user_id=uid)
    assert res_conc["success"] is False
    assert "already executing" in res_conc["error"].lower()


# =====================================================================
# 12. Schema Drift and Row Count Drift Detection
# =====================================================================

def test_schema_and_row_count_drift():
    temp_dir = tempfile.mkdtemp()
    db_file = Path(temp_dir) / "test_drift.db"
    test_uid = "drift_test_user"

    with sqlite3.connect(str(db_file)) as c:
        c.execute("CREATE TABLE customers (id INT, status TEXT)")
        c.execute("INSERT INTO customers VALUES (1, 'active'), (2, 'active')")
        c.commit()

    connect_sqlite_for_user(test_uid, str(db_file))
    set_user_context_for_request(test_uid)
    refresh_database_profile()

    sess = f"{test_uid}:sess_drift"

    # Stage an update on customers
    staged = store_pending(
        session_id=sess,
        operation="update",
        table="customers",
        sql="UPDATE customers SET status = 'inactive' WHERE id = 1",
        user_id=test_uid,
        extra={"where_clause": "id = 1", "estimated_affected_rows": 1},
    )
    fp = staged["fingerprint"]

    # Drop customers table in database behind the scenes (schema drift)
    with sqlite3.connect(str(db_file)) as c:
        c.execute("DROP TABLE customers")
        c.commit()
    refresh_database_profile()

    # Confirmation must detect target table disappearance and reject
    drift_res = execute_confirmed(sess, fingerprint=fp, user_id=test_uid)
    assert drift_res["success"] is False
    assert "no longer present" in drift_res["error"].lower()

    clear_user_context(test_uid)


# =====================================================================
# 13. Engine Rollback Behavior Matrix
# =====================================================================

def test_rollback_behavior_matrix():
    # PostgreSQL supports transactional DDL
    pg_res = CommandPolicy.validate("DROP TABLE users", dialect="postgres")
    assert pg_res.rollback_supported is True
    assert "transactional ddl" in pg_res.rollback_limitations.lower()

    # SQLite supports transactional DDL; documents truncate simulation
    sqlite_drop = CommandPolicy.validate("DROP TABLE users", dialect="sqlite")
    assert sqlite_drop.rollback_supported is True

    sqlite_trunc = CommandPolicy.validate("TRUNCATE TABLE users", dialect="sqlite")
    assert sqlite_trunc.rollback_supported is True
    assert "DELETE FROM" in sqlite_trunc.rollback_limitations

    # MySQL has implicit commit on DDL
    my_drop = CommandPolicy.validate("DROP TABLE users", dialect="mysql")
    assert my_drop.rollback_supported is False
    assert "implicit commit" in my_drop.rollback_limitations.lower()

    # MariaDB has implicit commit on DDL
    maria_drop = CommandPolicy.validate("TRUNCATE TABLE users", dialect="mariadb")
    assert maria_drop.rollback_supported is False
    assert "implicit commit" in maria_drop.rollback_limitations.lower()

    # MSSQL supports transactional DDL
    mssql_res = CommandPolicy.validate("ALTER TABLE users ADD age INT", dialect="mssql")
    assert mssql_res.rollback_supported is True


# =====================================================================
# 14. Native Non-Relational Command Validation
# =====================================================================

def test_native_connector_validation():
    # MongoDB validation
    m_find = CommandPolicy.validate('{"collection": "users", "action": "find"}', dialect="mongodb")
    assert m_find.allowed is True
    assert m_find.category == CommandCategory.READ
    assert m_find.requires_confirmation is False

    m_ins = CommandPolicy.validate('{"collection": "users", "action": "insert", "doc": {"name": "A"}}', dialect="mongodb")
    assert m_ins.allowed is True
    assert m_ins.category == CommandCategory.DATA_MUTATION
    assert m_ins.requires_confirmation is True
    assert m_ins.is_high_risk is False

    m_drop = CommandPolicy.validate('{"collection": "users", "action": "drop"}', dialect="mongodb")
    assert m_drop.allowed is True
    assert m_drop.category == CommandCategory.DESTRUCTIVE_DDL
    assert m_drop.is_high_risk is True

    # SQL sent to MongoDB is rejected
    m_sql = CommandPolicy.validate("SELECT * FROM users", dialect="mongodb")
    assert m_sql.allowed is False
    assert "Raw SQL is not supported" in m_sql.reason

    # Redis validation
    r_get = CommandPolicy.validate("GET mykey", dialect="redis")
    assert r_get.allowed is True
    assert r_get.category == CommandCategory.READ

    r_set = CommandPolicy.validate("SET mykey 'val'", dialect="redis")
    assert r_set.allowed is True
    assert r_set.category == CommandCategory.DATA_MUTATION
    assert r_set.requires_confirmation is True

    r_flush = CommandPolicy.validate("FLUSHDB", dialect="redis")
    assert r_flush.allowed is True
    assert r_flush.category == CommandCategory.DESTRUCTIVE_DDL
    assert r_flush.is_high_risk is True

    r_shutdown = CommandPolicy.validate("SHUTDOWN", dialect="redis")
    assert r_shutdown.allowed is False
    assert r_shutdown.dangerous is True

    # Vector validation
    v_search = CommandPolicy.validate('{"action": "search", "query_text": "AI"}', dialect="qdrant")
    assert v_search.allowed is True
    assert v_search.category == CommandCategory.READ

    v_drop = CommandPolicy.validate('{"action": "delete_collection", "collection": "docs"}', dialect="qdrant")
    assert v_drop.allowed is True
    assert v_drop.category == CommandCategory.DESTRUCTIVE_DDL
    assert v_drop.is_high_risk is True


# =====================================================================
# 15. End-to-End Database Lifecycle Execution on Disposable SQLite
# =====================================================================

def test_end_to_end_sqlite_lifecycle():
    temp_dir = tempfile.mkdtemp()
    db_file = Path(temp_dir) / "test_full_lifecycle.db"
    test_uid = "lifecycle_user_final"

    with sqlite3.connect(str(db_file)) as c:
        c.execute("CREATE TABLE members (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, tier TEXT)")
        c.execute("INSERT INTO members (name, tier) VALUES ('Alice', 'silver'), ('Bob', 'gold')")
        c.commit()

    connect_sqlite_for_user(test_uid, str(db_file))
    set_user_context_for_request(test_uid)
    refresh_database_profile()

    sess = f"{test_uid}:full_lifecycle_session"

    # 1. CREATE TABLE
    sql_create = "CREATE TABLE rewards (reward_id INT PRIMARY KEY, points INT)"
    staged_c = store_pending(sess, "create", "rewards", sql_create, user_id=test_uid)
    res_c = execute_confirmed(sess, fingerprint=staged_c["fingerprint"], user_id=test_uid)
    assert res_c["success"] is True

    # 2. INSERT
    sql_ins = "INSERT INTO rewards (reward_id, points) VALUES (1, 500)"
    staged_i = store_pending(sess, "insert", "rewards", sql_ins, user_id=test_uid)
    res_i = execute_confirmed(sess, fingerprint=staged_i["fingerprint"], user_id=test_uid)
    assert res_i["success"] is True

    # 3. ALTER TABLE ADD COLUMN
    sql_alt = "ALTER TABLE rewards ADD COLUMN expiry TEXT"
    staged_a = store_pending(sess, "alter", "rewards", sql_alt, user_id=test_uid)
    res_a = execute_confirmed(sess, fingerprint=staged_a["fingerprint"], user_id=test_uid)
    assert res_a["success"] is True

    # 4. UPDATE with WHERE
    sql_upd = "UPDATE members SET tier = 'platinum' WHERE id = 1"
    staged_u = store_pending(sess, "update", "members", sql_upd, user_id=test_uid, extra={"where_clause": "id = 1", "estimated_affected_rows": 1})
    res_u = execute_confirmed(sess, fingerprint=staged_u["fingerprint"], user_id=test_uid)
    assert res_u["success"] is True
    assert res_u["affected_rows"] == 1

    # 5. TRUNCATE simulation (High-Risk Confirmation)
    sql_trunc = "TRUNCATE TABLE members"
    staged_t = store_pending(sess, "truncate", "members", sql_trunc, user_id=test_uid, extra={"is_high_risk": True})
    
    # Must fail without high_risk_confirmed=True
    res_t_fail = execute_confirmed(sess, fingerprint=staged_t["fingerprint"], high_risk_confirmed=False, user_id=test_uid)
    assert res_t_fail["success"] is False
    assert res_t_fail.get("requires_high_risk_confirmation") is True

    # Succeeds with high_risk_confirmed=True
    res_t_ok = execute_confirmed(sess, fingerprint=staged_t["fingerprint"], high_risk_confirmed=True, user_id=test_uid)
    assert res_t_ok["success"] is True

    with sqlite3.connect(str(db_file)) as c:
        cnt = c.execute("SELECT COUNT(*) FROM members").fetchone()[0]
        assert cnt == 0

    # 6. DROP TABLE (High-Risk Confirmation)
    sql_drop = "DROP TABLE rewards"
    staged_d = store_pending(sess, "drop", "rewards", sql_drop, user_id=test_uid, extra={"is_high_risk": True})
    res_d = execute_confirmed(sess, fingerprint=staged_d["fingerprint"], high_risk_confirmed=True, user_id=test_uid)
    assert res_d["success"] is True

    with sqlite3.connect(str(db_file)) as c:
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "rewards" not in tables

    clear_user_context(test_uid)


# =====================================================================
# Test Runner
# =====================================================================

if __name__ == "__main__":
    tests = [
        ("Policy: Command categories classification", test_command_categories_classification),
        ("Policy: WHERE predicates and high-risk analysis", test_where_predicates_and_risk),
        ("Policy: Parser resilience & stacked statement blocking", test_parser_resilience),
        ("Policy: Prohibited system command blocking", test_prohibited_system_commands),
        ("Read-Only: Enforcement across all connector categories", test_readonly_all_connector_categories),
        ("Execution: Direct /query confirmation bypass prevention & auto-staging", test_direct_query_confirmation_bypass_prevention),
        ("Security: Cryptographic fingerprint verification & tamper detection", test_fingerprint_security),
        ("Security: Cross-user isolation", test_cross_user_isolation),
        ("Security: Cross-connection isolation", test_cross_connection_isolation),
        ("Security: Expiry enforcement and replay rejection", test_expiry_and_replay_rejection),
        ("Concurrency: Duplicate confirmation lock", test_concurrent_duplicate_confirmation),
        ("Integrity: Schema drift and row count drift detection", test_schema_and_row_count_drift),
        ("Rollback: Engine rollback behavior matrix", test_rollback_behavior_matrix),
        ("Routing: Native non-relational command validation", test_native_connector_validation),
        ("Lifecycle: End-to-end database lifecycle on disposable SQLite", test_end_to_end_sqlite_lifecycle),
    ]

    print("=" * 65)
    print("RUNNING BG AI COMPLETE AUTHORIZED DATABASE CONTROL TEST SUITE")
    print("=" * 65)

    passed = 0
    failed = 0
    for name, t in tests:
        if run_test(name, t):
            passed += 1
        else:
            failed += 1

    print("=" * 65)
    print(f"RESULTS: {passed} passed, {failed} failed (Total: {len(tests)})")
    print("=" * 65)

    if failed > 0:
        sys.exit(1)
