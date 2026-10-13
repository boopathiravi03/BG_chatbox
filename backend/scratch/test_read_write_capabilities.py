#!/usr/bin/env python
"""
Read/Write Capabilities & Permission Verification Tests for BG AI
"""
import sys
import os
import tempfile
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.connectors.base import BaseConnector, ConnectorCapabilities
from app.connectors.relational import SQLiteConnector, MySQLConnector, PostgreSQLConnector
from app.connectors.mongodb import MongoDBConnector
from app.connectors.redis_connector import RedisConnector
from app.connectors.vector import QdrantConnector, ChromaConnector
from app.connectors.file_connectors import CSVConnector, ExcelConnector, JSONConnector
from app.tools.execute_query import validate_sql, execute_query


def test_capabilities_defaults():
    print("Testing Connector Capabilities Defaults...")
    
    # SQLite
    sqlite_conn = SQLiteConnector("test-sq", "SQLite Test", "test.db", is_read_only=False)
    caps = sqlite_conn.get_capabilities()
    assert caps.can_read_data is True
    assert caps.can_insert_records is True
    assert caps.can_update_records is True
    assert caps.can_delete_records is True
    assert caps.can_create_entities is True
    assert caps.can_manage_indexes is True
    assert caps.can_execute_raw_queries is True
    assert caps.read_only_reason is None
    print("  [OK] SQLite default Read/Write capabilities verified")

    # Read-Only SQLite
    ro_sqlite = SQLiteConnector("test-sq-ro", "SQLite RO", "test.db", is_read_only=True)
    ro_caps = ro_sqlite.get_capabilities()
    assert ro_caps.can_read_data is True
    assert ro_caps.can_insert_records is False
    assert ro_caps.can_update_records is False
    assert ro_caps.can_delete_records is False
    assert ro_caps.can_create_entities is False
    assert ro_caps.can_manage_indexes is False
    assert ro_caps.read_only_reason is not None
    print("  [OK] SQLite Read-Only enforcement verified")

    # MongoDB
    mongo_conn = MongoDBConnector("test-mg", "Mongo Test", host="localhost", database="testdb", is_read_only=False)
    mg_caps = mongo_conn.get_capabilities()
    assert mg_caps.can_read_data is True
    assert mg_caps.can_insert_records is True
    assert mg_caps.can_update_records is True
    assert mg_caps.can_delete_records is True
    assert mg_caps.can_create_entities is True
    assert mg_caps.can_manage_indexes is True
    print("  [OK] MongoDB Read/Write capabilities verified")

    # Redis
    redis_conn = RedisConnector("test-rd", "Redis Test", host="localhost", is_read_only=False)
    rd_caps = redis_conn.get_capabilities()
    assert rd_caps.can_read_data is True
    assert rd_caps.can_insert_records is True
    assert rd_caps.can_update_records is True
    assert rd_caps.can_delete_records is True
    print("  [OK] Redis Read/Write capabilities verified")

    # Vector
    qdrant_conn = QdrantConnector("test-qd", "Qdrant Test", host="localhost", is_read_only=False)
    qd_caps = qdrant_conn.get_capabilities()
    assert qd_caps.can_read_data is True
    assert qd_caps.can_insert_records is True
    assert qd_caps.can_create_entities is True
    print("  [OK] Qdrant Read/Write capabilities verified")

    # Files
    csv_conn = CSVConnector("test-csv", "CSV Test", file_path="test.csv", is_read_only=False)
    csv_caps = csv_conn.get_capabilities()
    assert csv_caps.can_read_data is True
    assert csv_caps.can_insert_records is True
    print("  [OK] CSV Read/Write capabilities verified")


def test_sql_validation():
    print("\nTesting SQL Validation for CRUD & DDL...")

    # Reads
    res = validate_sql("SELECT * FROM users")
    assert res["allowed"] is True
    assert res["requires_confirmation"] is False
    print("  [OK] SELECT allowed without confirmation")

    # Writes
    res = validate_sql("INSERT INTO users (name) VALUES ('Alice')")
    assert res["allowed"] is True
    assert res["requires_confirmation"] is True
    print("  [OK] INSERT allowed with confirmation")

    res = validate_sql("UPDATE users SET name = 'Bob' WHERE id = 1")
    assert res["allowed"] is True
    assert res["requires_confirmation"] is True
    print("  [OK] UPDATE with WHERE allowed with confirmation")

    # UPDATE without WHERE blocked
    res = validate_sql("UPDATE users SET name = 'Bob'")
    assert res["allowed"] is False
    print("  [OK] UPDATE without WHERE blocked")

    # CREATE TABLE
    res = validate_sql("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT)")
    assert res["allowed"] is True
    assert res["requires_confirmation"] is True
    print("  [OK] CREATE TABLE allowed with confirmation")

    # CREATE INDEX
    res = validate_sql("CREATE INDEX idx_user_name ON users(name)")
    assert res["allowed"] is True
    assert res["requires_confirmation"] is True
    print("  [OK] CREATE INDEX allowed with confirmation")

    # Destructive DROP / TRUNCATE
    res = validate_sql("DROP TABLE users")
    assert res["allowed"] is False
    assert res.get("dangerous") is True
    print("  [OK] DROP TABLE blocked for safety")

    res = validate_sql("TRUNCATE TABLE users")
    assert res["allowed"] is False
    assert res.get("dangerous") is True
    print("  [OK] TRUNCATE blocked for safety")


def test_real_database_operations():
    print("\nTesting Real Database CRUD and Index Operations...")
    
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, name TEXT)")
        cur.execute("INSERT INTO users (email, name) VALUES ('alice@example.com', 'Alice')")
        conn.commit()
        conn.close()

        connector = SQLiteConnector(
            connection_id="test-sqlite-live",
            name="Live SQLite Test",
            database_path=db_path,
            is_read_only=False,
        )
        assert connector.connect() is True

        # Test index creation
        res = connector.create_index("users", ["email"], "idx_users_email", unique=True)
        assert res["success"] is True
        print("  [OK] Real index creation succeeded")

        # Test index drop
        res = connector.drop_index("users", "idx_users_email")
        assert res["success"] is True
        print("  [OK] Real index drop succeeded")

        # Test record insertion
        res = connector.create_record("users", {"email": "bob@example.com", "name": "Bob"})
        assert res["success"] is True
        print("  [OK] Real record insertion succeeded")

        # Test record update
        res = connector.update_record("users", {"id": 1}, {"name": "Alice Wonderland"})
        assert res["success"] is True
        print("  [OK] Real record update succeeded")

        # Test record read
        records = connector.get_records("users")
        assert records["total_count"] == 2
        assert records["is_read_only"] is False
        print("  [OK] Real record fetch confirms Read/Write status")

        # Test read-only switch blocks write
        connector.is_read_only = True
        try:
            connector.create_record("users", {"email": "charlie@example.com", "name": "Charlie"})
            assert False, "Should have raised PermissionError"
        except PermissionError as e:
            assert "READ-ONLY" in str(e)
            print("  [OK] Read-only switch successfully blocked record creation with PermissionError")

        connector.disconnect()
    finally:
        try:
            connector.disconnect()
        except Exception:
            pass
        try:
            if os.path.exists(db_path):
                os.remove(db_path)
        except Exception:
            pass


if __name__ == "__main__":
    test_capabilities_defaults()
    test_sql_validation()
    test_real_database_operations()
    print("\n==================================================")
    print("All Read/Write and Capabilities tests PASSED! [OK]")
    print("==================================================")
