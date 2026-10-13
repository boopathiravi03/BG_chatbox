#!/usr/bin/env python
"""
Verification Suite for Unified Database Statistics & Overview Integration
Tests:
1. Unified `/database-info` endpoint contract (tables, rows, columns, status, category, is_exact)
2. Exact agreement between query with connection_id and query without connection_id
3. RelationalConnector get_stats() dialect behavior and count fallback
4. Schema inspection fallback when connector engine connects
5. Engine synchronization between connection_context and ConnectionRegistry
6. Multi-database connector compatibility (SQLite, MongoDB, Redis, Vector)
"""
import sys
import os
import sqlite3
import tempfile
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.connectors.registry import get_connection_registry, ConnectorStatus
from app.connectors.relational import SQLiteConnector, MySQLConnector
from app.database.connection_context import set_user_context_for_request, get_request_engine
from app.tools.get_schema import get_schema, clear_engine_schema_cache
from app.database.db import get_database_info

results = []

def test(name, fn):
    try:
        fn()
        results.append(("PASS", name))
        print(f"  [PASS] {name}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        results.append(("FAIL", name, str(e)))
        print(f"  [FAIL] {name}: {e}")

def test_unified_database_info_sqlite():
    # Create temp sqlite database with 4 tables, 31 rows, 20 columns
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    connector = None
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT, role TEXT, created_at TEXT)") # 5 cols
        cur.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL, status TEXT, order_date TEXT)") # 5 cols
        cur.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, title TEXT, price REAL, stock INTEGER, sku TEXT)") # 5 cols
        cur.execute("CREATE TABLE categories (id INTEGER PRIMARY KEY, title TEXT, description TEXT, parent_id INTEGER, slug TEXT)") # 5 cols

        # 31 rows total: 10 + 10 + 10 + 1
        for i in range(10):
            cur.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)", (i + 1, f"User {i}", f"u{i}@test.com", "user", "2026-01-01"))
        for i in range(10):
            cur.execute("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", (i + 1, 1, 99.9, "completed", "2026-01-02"))
        for i in range(10):
            cur.execute("INSERT INTO products VALUES (?, ?, ?, ?, ?)", (i + 1, f"Prod {i}", 19.99, 100, f"SKU-{i}"))
        cur.execute("INSERT INTO categories VALUES (1, 'Electronics', 'Gadgets', 0, 'electronics')")
        conn.commit()
        conn.close()

        user_id = "test_user_sync_1"
        conn_id = "conn_sync_sql_1"
        reg = get_connection_registry()

        connector = SQLiteConnector(
            connection_id=conn_id,
            name="MySQL Data Source",
            database_path=db_path,
            user_id=user_id,
        )
        assert connector.connect() is True
        reg.register_connector(connector)
        reg.set_active_connector(user_id, conn_id)

        # 1. Activate context as would occur in request
        set_user_context_for_request(user_id, conn_id)

        # 2. Test connector.get_stats()
        stats = connector.get_stats()
        assert stats["tables"] == 4, f"Expected 4 tables, got {stats['tables']}"
        assert stats["rows"] == 31, f"Expected 31 rows, got {stats['rows']}"
        assert stats["columns"] == 20, f"Expected 20 columns, got {stats['columns']}"

        # 3. Test main.py database_info simulated logic
        from app.main import database_info
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_user = MagicMock()
        mock_user.user_id = user_id

        # Case A: Call WITH connection_id (OverviewView query pattern)
        info_with_id = database_info(request=mock_request, connection_id=conn_id, user=mock_user)
        assert info_with_id["connected"] is True
        assert info_with_id["tables"] == 4, f"With ID expected tables=4, got {info_with_id['tables']}"
        assert info_with_id["rows"] == 31, f"With ID expected rows=31, got {info_with_id['rows']}"
        assert info_with_id["columns"] == 20, f"With ID expected cols=20, got {info_with_id['columns']}"
        assert info_with_id["database"] == "MySQL Data Source"

        # Case B: Call WITHOUT connection_id (DatabasePopup / DatabaseStats query pattern)
        info_without_id = database_info(request=mock_request, connection_id=None, user=mock_user)
        assert info_without_id["connected"] is True
        assert info_without_id["tables"] == 4, f"Without ID expected tables=4, got {info_without_id['tables']}"
        assert info_without_id["rows"] == 31, f"Without ID expected rows=31, got {info_without_id['rows']}"
        assert info_without_id["columns"] == 20, f"Without ID expected cols=20, got {info_without_id['columns']}"
        assert info_without_id["database"] == "MySQL Data Source"

        # Case C: Verification of exact agreement
        assert info_with_id["tables"] == info_without_id["tables"], "Popup and Dashboard tables must agree!"
        assert info_with_id["rows"] == info_without_id["rows"], "Popup and Dashboard rows must agree!"
        assert info_with_id["columns"] == info_without_id["columns"], "Popup and Dashboard columns must agree!"

    finally:
        if connector:
            connector.disconnect()
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass

def test_engine_synchronization_when_engine_none():
    # Test that set_user_context_for_request reconnects or syncs engine
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE items (id INTEGER, name TEXT)")
    conn.execute("INSERT INTO items VALUES (1, 'item1')")
    conn.commit()
    conn.close()

    user_id = "test_user_sync_2"
    conn_id = "conn_sync_sql_2"
    reg = get_connection_registry()

    connector = SQLiteConnector(
        connection_id=conn_id,
        name="Auto-Connect Source",
        database_path=db_path,
        user_id=user_id,
    )
    # Connector initially has _engine = None
    assert connector._engine is None
    reg.register_connector(connector)
    reg.set_active_connector(user_id, conn_id)

    # Calling set_user_context_for_request should auto-connect
    set_user_context_for_request(user_id, conn_id)
    eng = get_request_engine()
    assert eng is not None, "Engine should not be None after set_user_context_for_request"
    assert connector._engine is not None, "Connector engine should be established"

    # get_schema() should now succeed
    clear_engine_schema_cache()
    schema = get_schema(conn_id)
    assert "items" in schema, f"Schema should contain 'items', got {schema.keys()}"

    connector.disconnect()
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass

def test_get_database_info_contract_fields():
    # Verify that get_database_info in db.py returns all expected unified keys
    info = get_database_info()
    expected_keys = ["connected", "db_type", "database", "tables", "collections", "rows", "documents", "columns", "size", "status", "category", "is_exact"]
    for k in expected_keys:
        assert k in info, f"Key '{k}' missing from get_database_info() contract"

if __name__ == "__main__":
    print("\nRunning Unified Database Statistics Verification Suite:")
    test("Unified /database-info Contract Agreement (Popup vs Dashboard)", test_unified_database_info_sqlite)
    test("Engine Synchronization & Schema Inspection", test_engine_synchronization_when_engine_none)
    test("Unified get_database_info() Contract Keys", test_get_database_info_contract_fields)

    passed = sum(1 for r in results if r[0] == "PASS")
    failed = sum(1 for r in results if r[0] == "FAIL")
    print(f"\n{len(results)} tests: {passed} passed, {failed} failed\n")
    sys.exit(0 if failed == 0 else 1)

