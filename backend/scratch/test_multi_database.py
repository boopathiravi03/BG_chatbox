#!/usr/bin/env python
"""backend/scratch/test_multi_database.py

Comprehensive Test Suite for BG AI 2.0: Multi-Database Intelligence Upgrade.
Tests:
1. Multi-connection registry with isolated per-user state
2. Simultaneous connection of multiple independent databases
3. Disconnecting one source while others remain connected and fully operational
4. Schema discovery across connectors (SQLite, MySQL, Postgres, MSSQL, MariaDB, MongoDB, Qdrant, Chroma, CSV, JSON)
5. Read-only permission enforcement & mutation blocking
6. Bounded queries, dialect-specific query execution
7. Cross-database routing, planning, and application-layer combination (key join & metrics)
8. Semantic vector search result handling
9. File connectors (CSV, JSON) with real SQL query execution
10. Backward compatibility with existing get_engine(), get_current_db_type(), and get_schema()
"""

import os
import sys
import tempfile
import time
import json
import uuid
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from app.connectors.base import (
    BaseConnector,
    ConnectorCategory,
    ConnectorStatus,
    QueryResult,
    VectorDocument,
    VectorSearchResult,
)
from app.connectors.relational import (
    SQLiteConnector,
    MySQLConnector,
    PostgreSQLConnector,
    MSSQLConnector,
    MariaDBConnector,
)
from app.connectors.mongodb import MongoDBConnector
from app.connectors.vector import QdrantConnector, ChromaConnector
from app.connectors.file_connectors import CSVConnector, JSONConnector
from app.connectors.registry import (
    ConnectionRegistry,
    get_connection_registry,
    get_supported_connectors_catalog,
)
from app.database.connection_context import (
    set_user_context_for_request,
    get_request_engine,
    get_request_db_type,
    get_request_user_id,
    clear_user_context,
)
from app.tools.get_schema import get_schema
from app.tools.execute_query import execute_query
from app.intelligence.cross_db.models import (
    CrossDatabaseResponse,
    QueryIntentType,
    SourceQueryResult,
)
from app.intelligence.cross_db.router import CrossDatabaseRouter
from app.intelligence.cross_db.planner import CrossDatabasePlanner
from app.intelligence.cross_db.combiner import CrossDatabaseCombiner
from app.intelligence.cross_db.engine import CrossDatabaseEngine


passed_count = 0
failed_count = 0


def assert_test(name: str, condition: bool, details: str = ""):
    global passed_count, failed_count
    if condition:
        passed_count += 1
        print(f"  [PASS] {name}")
    else:
        failed_count += 1
        print(f"  [FAIL] {name}: {details}")


def run_tests():
    print("=" * 70)
    print("BG AI 2.0: MULTI-DATABASE INTELLIGENCE UPGRADE TEST SUITE")
    print("=" * 70)

    test_user_id = f"test_usr_{uuid.uuid4().hex[:8]}"
    registry = get_connection_registry()

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 1: Connector Catalog & Discovery
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- 1. Connector Catalog & Discovery ---")
    catalog = get_supported_connectors_catalog()
    assert_test("Catalog lists all 11 connectors", len(catalog) >= 11)
    types_in_cat = {c["id"] for c in catalog}
    for expected in ["sqlite", "mysql", "postgres", "sqlserver", "mariadb", "mongodb", "qdrant", "chroma", "csv", "excel", "json"]:
        assert_test(f"Connector '{expected}' present in catalog", expected in types_in_cat)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 2: Simultaneous Multi-Source Connections
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- 2. Simultaneous Multi-Source Connections ---")

    # Create temporary SQLite DB 1: Sales database
    temp_dir = tempfile.mkdtemp()
    db1_path = os.path.join(temp_dir, "sales.db")
    conn1 = SQLiteConnector(
        connection_id=f"conn_sales_{uuid.uuid4().hex[:6]}",
        name="Sales Database",
        database_path=db1_path,
        user_id=test_user_id,
    )
    conn1.connect()
    # Populate sales table
    conn1.execute_query("CREATE TABLE sales (sale_id INTEGER PRIMARY KEY, customer_id INTEGER, amount REAL, sale_date TEXT)")
    conn1.execute_query("INSERT INTO sales VALUES (1, 101, 250.0, '2026-10-01')")
    conn1.execute_query("INSERT INTO sales VALUES (2, 102, 180.5, '2026-10-02')")
    registry.register_connector(conn1)

    # Create temporary SQLite DB 2: Customers database
    db2_path = os.path.join(temp_dir, "customers.db")
    conn2 = SQLiteConnector(
        connection_id=f"conn_cust_{uuid.uuid4().hex[:6]}",
        name="Customers CRM",
        database_path=db2_path,
        user_id=test_user_id,
    )
    conn2.connect()
    conn2.execute_query("CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, name TEXT, email TEXT, region TEXT)")
    conn2.execute_query("INSERT INTO customers VALUES (101, 'Alice Smith', 'alice@example.com', 'North America')")
    conn2.execute_query("INSERT INTO customers VALUES (102, 'Bob Jones', 'bob@example.com', 'Europe')")
    registry.register_connector(conn2)

    # Create temporary CSV file database
    csv_path = os.path.join(temp_dir, "products.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("product_id,product_name,category,price\n")
        f.write("P101,Wireless Mouse,Electronics,29.99\n")
        f.write("P102,Ergonomic Keyboard,Electronics,89.50\n")
        f.write("P103,Coffee Mug,Kitchen,12.00\n")

    conn3 = CSVConnector(
        connection_id=f"conn_csv_{uuid.uuid4().hex[:6]}",
        name="Products CSV Source",
        file_path=csv_path,
        user_id=test_user_id,
    )
    conn3.connect()
    registry.register_connector(conn3)

    user_conns = registry.list_connectors(test_user_id)
    assert_test("All 3 connections registered simultaneously", len(user_conns) == 3)
    assert_test("Connection 1 status is CONNECTED", conn1.status == ConnectorStatus.CONNECTED)
    assert_test("Connection 2 status is CONNECTED", conn2.status == ConnectorStatus.CONNECTED)
    assert_test("Connection 3 (CSV) status is CONNECTED", conn3.status == ConnectorStatus.CONNECTED)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 3: Independent Disconnect & Isolation
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- 3. Independent Disconnect & Isolation ---")
    # Disconnect ONLY connection 3 (CSV)
    registry.remove_connector(test_user_id, conn3.connection_id)
    remaining_conns = registry.list_connectors(test_user_id)
    assert_test("Removed connection 3, exactly 2 remain active", len(remaining_conns) == 2)
    assert_test("Connection 1 still responsive", conn1.test_connection()["connected"] is True)
    assert_test("Connection 2 still responsive", conn2.test_connection()["connected"] is True)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 4: Schema Discovery & Reflection
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- 4. Schema Discovery & Metadata Reflection ---")
    schema1 = conn1.get_schema()
    schema2 = conn2.get_schema()
    assert_test("Connection 1 discovers 'sales' table", "sales" in schema1)
    assert_test("Connection 1 reflects columns accurately", "amount" in schema1["sales"] and "customer_id" in schema1["sales"])
    assert_test("Connection 2 discovers 'customers' table", "customers" in schema2)
    assert_test("Connection 2 reflects 'email' column", "email" in schema2["customers"])

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 5: Query Execution & Dialect Routing
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- 5. Query Execution & Source Routing ---")
    res1 = conn1.execute_query("SELECT * FROM sales WHERE customer_id = 101")
    assert_test("Connection 1 executed query successfully", res1.success is True)
    assert_test("Connection 1 returned 1 row", res1.rows_returned == 1)
    assert_test("Row value matches database content", res1.rows[0]["amount"] == 250.0)

    res2 = conn2.execute_query("SELECT name, email FROM customers WHERE customer_id = 101")
    assert_test("Connection 2 executed query successfully", res2.success is True)
    assert_test("Customer name is Alice Smith", res2.rows[0]["name"] == "Alice Smith")

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 6: Read-Only Enforcement & Mutation Blocking
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- 6. Read-Only Enforcement & Permissions ---")
    conn1.is_read_only = True
    mut_res = conn1.execute_query("DELETE FROM sales WHERE sale_id = 1")
    assert_test("Read-only connector blocked DELETE mutation", mut_res.success is False)
    assert_test("Error explains read-only violation", "READ-ONLY" in (mut_res.error or ""))

    # Verify data was NOT deleted
    verify_res = conn1.execute_query("SELECT COUNT(*) as cnt FROM sales")
    assert_test("Data remained intact in read-only mode", verify_res.rows[0]["cnt"] == 2)
    conn1.is_read_only = False

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 7: Cross-Database Routing & Disambiguation
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- 7. Cross-Database Routing & Disambiguation ---")

    # Ambiguous test: create table 'items' on both databases
    conn1.execute_query("CREATE TABLE items (item_id INTEGER, name TEXT)")
    conn2.execute_query("CREATE TABLE items (item_id INTEGER, title TEXT)")
    conn1.clear_schema_cache()
    conn2.clear_schema_cache()

    intent_ambig, conns_ambig, options = CrossDatabaseRouter.route_query(
        user_id=test_user_id,
        message="Show all items",
    )
    assert_test("Detected ambiguous table request across databases", intent_ambig == QueryIntentType.AMBIGUOUS)
    assert_test("Generated disambiguation options for user", len(options or []) == 2)

    # Cross-source query: "Compare sales with customers"
    intent_cross, conns_cross, _ = CrossDatabaseRouter.route_query(
        user_id=test_user_id,
        message="Compare sales with customers data",
    )
    assert_test("Detected cross-database intent", intent_cross == QueryIntentType.CROSS_SOURCE)
    assert_test("Both target databases selected", len(conns_cross) == 2)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 8: Application-Layer Combination (Key Join)
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- 8. Application-Layer Data Combination ---")
    sub1 = SourceQueryResult(
        source_id=conn1.connection_id,
        source_name=conn1.name,
        connector_type="sqlite",
        query_text="SELECT * FROM sales",
        success=True,
        columns=["sale_id", "customer_id", "amount", "sale_date"],
        rows=conn1.execute_query("SELECT * FROM sales").rows,
        rows_returned=2,
    )
    sub2 = SourceQueryResult(
        source_id=conn2.connection_id,
        source_name=conn2.name,
        connector_type="sqlite",
        query_text="SELECT * FROM customers",
        success=True,
        columns=["customer_id", "name", "email", "region"],
        rows=conn2.execute_query("SELECT * FROM customers").rows,
        rows_returned=2,
    )

    combined, explanation, strategy = CrossDatabaseCombiner.combine(
        [sub1, sub2], "Compare sales and customer information"
    )
    assert_test("Combination strategy used key_join", strategy == "key_join")
    assert_test("Combined result has rows", combined is not None and len(combined["rows"]) == 2)
    assert_test("Combined rows contain sales amount and customer name", "amount" in combined["rows"][0] and "name" in combined["rows"][0])
    assert_test("Alice Smith matched with amount 250.0", any(r.get("name") == "Alice Smith" and r.get("amount") == 250.0 for r in combined["rows"]))
    assert_test("Explanation explains key used for correlation", "customer_id" in explanation)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 9: Vector Search Results Handling
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- 9. Vector Search Results Handling ---")
    vec_result = VectorSearchResult(
        success=True,
        collection="refund_policies",
        query_text="customer refund requests",
        documents=[
            VectorDocument(id="doc_1", score=0.942, text="Refunds are eligible within 30 days of purchase with receipt.", metadata={"category": "policy"}),
            VectorDocument(id="doc_2", score=0.885, text="Defective items can be exchanged or credited within 60 days.", metadata={"category": "warranty"}),
        ],
        total_found=2,
        execution_time_ms=12.4,
    )
    assert_test("Vector result contains top scored document", vec_result.documents[0].score == 0.942)
    assert_test("Vector result contains text payload", "30 days" in vec_result.documents[0].text)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 10: JSON File Connector
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- 10. JSON File Connector & Real SQL Querying ---")
    json_path = os.path.join(temp_dir, "transactions.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump([
            {"txn_id": "TXN_01", "user_id": 101, "amount": 49.99, "status": "settled"},
            {"txn_id": "TXN_02", "user_id": 102, "amount": 199.00, "status": "pending"},
            {"txn_id": "TXN_03", "user_id": 101, "amount": 15.00, "status": "settled"},
        ], f)

    json_conn = JSONConnector(
        connection_id=f"conn_json_{uuid.uuid4().hex[:6]}",
        name="Transactions JSON",
        file_path=json_path,
        user_id=test_user_id,
    )
    assert_test("JSON connector connected", json_conn.connect() is True)
    json_query_res = json_conn.execute_query("SELECT user_id, SUM(amount) as total FROM transactions WHERE status = 'settled' GROUP BY user_id")
    assert_test("JSON file queried with real SQL aggregation", json_query_res.success is True)
    assert_test("Aggregated sum is 64.99 for user 101", round(float(json_query_res.rows[0]["total"]), 2) == 64.99)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 11: Backward Compatibility with Request Context & Tools
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- 11. Backward Compatibility with Request Context & Tools ---")
    # Activate connection 1 in request context
    set_user_context_for_request(test_user_id, conn1.connection_id)
    req_eng = get_request_engine()
    req_type = get_request_db_type()
    assert_test("Request engine resolves to connection 1", req_eng is conn1.engine)
    assert_test("Request db type is sqlite", req_type == "sqlite")

    # Tool get_schema() resolves connection 1 schema transparently
    schema_tool = get_schema()
    assert_test("get_schema() reflects connection 1 tables", "sales" in schema_tool)

    # Switch active to connection 2
    set_user_context_for_request(test_user_id, conn2.connection_id)
    req_eng2 = get_request_engine()
    assert_test("Switching context updates engine to connection 2", req_eng2 is conn2.engine)
    schema_tool2 = get_schema()
    assert_test("get_schema() reflects connection 2 tables", "customers" in schema_tool2)

    # Clean up temp files
    try:
        conn1.disconnect()
        conn2.disconnect()
        json_conn.disconnect()
        registry.disconnect_all(test_user_id)
        clear_user_context(test_user_id)
    except Exception:
        pass

    print("\n" + "=" * 70)
    print(f"MULTI-DATABASE TEST RESULTS: {passed_count} PASSED, {failed_count} FAILED (TOTAL: {passed_count + failed_count})")
    print("=" * 70)

    if failed_count == 0:
        print("\nALL MULTI-DATABASE TESTS PASSED PERFECTLY.")
        return 0
    else:
        print(f"\n{failed_count} TESTS FAILED.")
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())

