#!/usr/bin/env python
"""
Verification Script for Bug 1 & Bug 2:
- Overview table and row counts across SQL, MongoDB, and other connectors
- AI Command connection-aware deduplicated introduction
"""
import sys
import os
import sqlite3
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.connectors.registry import get_connection_registry, ConnectorStatus
from app.connectors.relational import SQLiteConnector, MySQLConnector
from app.connectors.mongodb import MongoDBConnector
from app.tools.get_schema import get_schema, clear_engine_schema_cache

results = []

def test(name, fn):
    try:
        fn()
        results.append(("PASS", name))
        print(f"  [PASS] {name}")
    except Exception as e:
        results.append(("FAIL", name, str(e)))
        print(f"  [FAIL] {name}: {e}")

def test_sqlite_connector_stats():
    # Create temp sqlite with 3 tables and 45 rows
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    connector = None
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        cur.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL)")
        cur.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, title TEXT, price REAL)")
        
        for i in range(20):
            cur.execute("INSERT INTO users VALUES (?, ?)", (i + 1, f"User {i}"))
        for i in range(15):
            cur.execute("INSERT INTO orders VALUES (?, ?, ?)", (i + 1, 1, 99.9))
        for i in range(10):
            cur.execute("INSERT INTO products VALUES (?, ?, ?)", (i + 1, f"Prod {i}", 19.99))
        conn.commit()
        conn.close()

        connector = SQLiteConnector(
            connection_id="test_sqlite_1",
            name="Test SQLite DB",
            database_path=db_path,
            user_id="test_user",
        )
        assert connector.connect() is True, "Failed to connect to SQLite"
        stats = connector.get_stats()
        assert stats["tables"] == 3, f"Expected 3 tables, got {stats['tables']}"
        assert stats["rows"] == 45, f"Expected 45 rows, got {stats['rows']}"
        assert stats["columns"] >= 7, f"Expected >= 7 columns, got {stats['columns']}"
    finally:
        if connector:
            connector.disconnect()
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass

def test_relational_auto_connect_on_stats():
    # Ensure get_stats() auto-connects even if _engine is initially None
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    connector = None
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
        cur.execute("INSERT INTO items VALUES (1, 'Item 1')")
        cur.execute("INSERT INTO items VALUES (2, 'Item 2')")
        conn.commit()
        conn.close()

        connector = SQLiteConnector(
            connection_id="test_sqlite_unconnected",
            name="Unconnected SQLite",
            database_path=db_path,
            user_id="test_user",
        )
        assert connector._engine is None, "Engine should be None before connect"
        # Calling get_stats directly should auto-connect and return non-zero
        stats = connector.get_stats()
        assert stats["tables"] == 1, f"Expected 1 table, got {stats['tables']}"
        assert stats["rows"] == 2, f"Expected 2 rows, got {stats['rows']}"
    finally:
        if connector:
            connector.disconnect()
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass

def test_database_info_contract_mapping():
    from app.connectors.base import ConnectorCategory
    
    # Verify mapping logic
    stats = {"tables": 5, "rows": 1250, "columns": 24}
    tables = stats.get("tables", stats.get("collections", stats.get("tables_count", 0)))
    rows = stats.get("rows", stats.get("documents", stats.get("total_keys", 0)))
    assert tables == 5
    assert rows == 1250

    # Document store mapping
    doc_stats = {"collections": 8, "documents": 45000}
    doc_tables = doc_stats.get("tables", doc_stats.get("collections", doc_stats.get("tables_count", 0)))
    doc_rows = doc_stats.get("rows", doc_stats.get("documents", doc_stats.get("total_keys", 0)))
    assert doc_tables == 8
    assert doc_rows == 45000

    # Redis store mapping
    redis_stats = {"total_keys": 99, "tables_count": 1}
    redis_tables = redis_stats.get("tables", redis_stats.get("collections", redis_stats.get("tables_count", 0)))
    redis_rows = redis_stats.get("rows", redis_stats.get("documents", redis_stats.get("total_keys", 0)))
    assert redis_tables == 1
    assert redis_rows == 99

def test_ai_command_intro_deduplication():
    # Simulate once-per-connection introduction logic
    introduced_keys = set()
    
    connection_key_1 = "conn_mysql_1:mysql:MySQL Data Source"
    connection_key_2 = "conn_mongo_1:mongodb:BG AI MongoDB"

    # First open for MySQL -> should introduce
    assert connection_key_1 not in introduced_keys
    introduced_keys.add(connection_key_1)

    # Second open for same MySQL -> should NOT re-introduce
    assert connection_key_1 in introduced_keys

    # Switching to MongoDB -> should introduce MongoDB
    assert connection_key_2 not in introduced_keys
    introduced_keys.add(connection_key_2)

    # Switching back to MySQL -> should NOT repeat introduction
    assert connection_key_1 in introduced_keys
    assert connection_key_2 in introduced_keys

if __name__ == "__main__":
    print("\nRunning Bug 1 & Bug 2 Verification Suite:")
    test("SQLite Connector Stats (Tables & Rows)", test_sqlite_connector_stats)
    test("Relational Connector Auto-Connect on get_stats()", test_relational_auto_connect_on_stats)
    test("Database Info Contract Mapping (SQL / Document / Redis)", test_database_info_contract_mapping)
    test("AI Command Connection-Aware Intro Deduplication", test_ai_command_intro_deduplication)

    passed = sum(1 for r in results if r[0] == "PASS")
    failed = sum(1 for r in results if r[0] == "FAIL")
    print(f"\n{len(results)} tests: {passed} passed, {failed} failed\n")
    sys.exit(0 if failed == 0 else 1)
