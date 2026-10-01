#!/usr/bin/env python
"""
backend/scratch/test_phase8_2_multitable.py

Phase 8.2: Multi-Table Business Intelligence Automated Regression Suite
Tests all 29 required specifications:
1. FK relationship discovery
2. Multi-hop relationship discovery
3. Join path correctness
4. Circular path prevention
5. Maximum join depth
6. Invalid relationship rejection
7. Revenue metric
8. Revenue by product
9. Revenue by category
10. Revenue by customer
11. Units sold
12. Average order value
13. Grouped metric
14. Time-series cross-table metric
15. SQL lineage
16. Source table lineage
17. Read-only enforcement
18. SQL injection protection
19. User isolation
20. Cache isolation
21. Cache invalidation
22. Empty table handling
23. Missing FK handling
24. No relationship handling
25. SQLite compatibility
26. Groq unavailable fallback
27. No-write guarantee
28. Evidence completeness
29. Causality-safe explanation
"""
import sys
import os
import sqlite3
from sqlalchemy import create_engine, text

# Add backend directory to path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.intelligence.schema_analyzer import analyze_schema
from app.intelligence.business_intelligence.join_path import (
    build_relationship_graph,
    find_join_path,
    find_all_join_paths,
    format_join_sql,
    JoinEdge,
)
from app.intelligence.business_intelligence.business_context import discover_business_context
from app.intelligence.business_intelligence.multitable_engine import (
    discover_multitable_metrics,
    generate_multitable_insights,
    query_multitable_bi,
    _generate_multitable_summary,
    _explain_with_groq_or_fallback,
)
from app.tools.execute_query import validate_sql
from app.security.user_cache import (
    cache_set,
    cache_get,
    cache_clear_user,
    CACHE_JOIN_PATHS,
    CACHE_CROSS_TABLE_INSIGHTS,
)

results: list[tuple[str, str, str]] = []


def run_test(number: int, name: str, fn):
    try:
        fn()
        results.append(("PASS", f"{number}. {name}", ""))
        print(f"  [PASS] {number}. {name}")
    except Exception as e:
        results.append(("FAIL", f"{number}. {name}", str(e)))
        print(f"  [FAIL] {number}. {name}: {e}")


def create_disposable_test_db():
    """Creates a temporary in-memory SQLite schema with 5 related tables."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON;"))
        conn.execute(text("""
            CREATE TABLE categories (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            );
        """))
        conn.execute(text("""
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                category_id INTEGER,
                category TEXT,
                price REAL NOT NULL,
                FOREIGN KEY (category_id) REFERENCES categories(id)
            );
        """))
        conn.execute(text("""
            CREATE TABLE customers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                region TEXT NOT NULL
            );
        """))
        conn.execute(text("""
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                total_amount REAL NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            );
        """))
        conn.execute(text("""
            CREATE TABLE order_items (
                id INTEGER PRIMARY KEY,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            );
        """))

        # Populate test fixtures
        conn.execute(text("INSERT INTO categories (id, name) VALUES (1, 'Electronics'), (2, 'Apparel');"))
        conn.execute(text("""
            INSERT INTO products (id, name, category_id, category, price) VALUES
            (1, 'Laptop', 1, 'Electronics', 1200.0),
            (2, 'Mouse', 1, 'Electronics', 25.0),
            (3, 'Hoodie', 2, 'Apparel', 60.0),
            (4, 'Sneakers', 2, 'Apparel', 110.0);
        """))
        conn.execute(text("""
            INSERT INTO customers (id, name, region) VALUES
            (1, 'Alice Smith', 'North America'),
            (2, 'Bob Jones', 'Europe'),
            (3, 'Charlie Lee', 'Asia Pacific');
        """))
        conn.execute(text("""
            INSERT INTO orders (id, customer_id, total_amount, created_at) VALUES
            (1, 1, 1225.0, '2026-08-01 10:00:00'),
            (2, 1, 60.0, '2026-08-15 14:30:00'),
            (3, 2, 110.0, '2026-09-02 09:15:00'),
            (4, 3, 25.0, '2026-09-10 16:45:00');
        """))
        conn.execute(text("""
            INSERT INTO order_items (id, order_id, product_id, quantity) VALUES
            (1, 1, 1, 1),
            (2, 1, 2, 1),
            (3, 2, 3, 1),
            (4, 3, 4, 1),
            (5, 4, 2, 1);
        """))
        conn.commit()

    return engine


def main():
    print("\n" + "=" * 60)
    print("PHASE 8.2: MULTI-TABLE BUSINESS INTELLIGENCE REGRESSION SUITE")
    print("=" * 60 + "\n")

    engine = create_disposable_test_db()
    schema_info = analyze_schema(engine, "sqlite")
    graph = build_relationship_graph(schema_info)
    context = discover_business_context(engine, "sqlite", schema_info)

    # 1. FK relationship discovery
    def test_1():
        assert len(schema_info["relationships"]) >= 4, f"Expected at least 4 FKs, found {len(schema_info['relationships'])}"
        edges = graph.get("orders", [])
        has_cust_edge = any(e.target_table == "customers" and e.source_column == "customer_id" for e in edges)
        assert has_cust_edge, "Failed to discover orders -> customers FK relationship"
    run_test(1, "FK relationship discovery", test_1)

    # 2. Multi-hop relationship discovery
    def test_2():
        path = find_join_path(graph, "order_items", "categories", max_depth=3, db_type="sqlite")
        assert path is not None, "Failed to discover order_items -> products -> categories path"
        assert path.depth == 2, f"Expected depth 2 for order_items->categories, got {path.depth}"
    run_test(2, "Multi-hop relationship discovery", test_2)

    # 3. Join path correctness
    def test_3():
        path = find_join_path(graph, "orders", "customers", max_depth=2, db_type="sqlite")
        assert path is not None
        assert "LEFT JOIN \"customers\" ON \"orders\".\"customer_id\" = \"customers\".\"id\"" in path.generated_join_clause
    run_test(3, "Join path correctness", test_3)

    # 4. Circular path prevention
    def test_4():
        # Bidirectional graph contains cycles: orders -> customers -> orders
        # find_join_path must terminate cleanly without recursion error
        path = find_join_path(graph, "orders", "categories", max_depth=3, db_type="sqlite")
        # Should not crash
        assert path is None or isinstance(path.depth, int)
    run_test(4, "Circular path prevention", test_4)

    # 5. Maximum join depth
    def test_5():
        # Depth 1 should NOT find order_items -> categories (which requires 2 hops)
        path = find_join_path(graph, "order_items", "categories", max_depth=1, db_type="sqlite")
        assert path is None, "Should not return path exceeding max_depth=1"
    run_test(5, "Maximum join depth enforcement", test_5)

    # 6. Invalid relationship rejection
    def test_6():
        path = find_join_path(graph, "customers", "nonexistent_table", max_depth=3, db_type="sqlite")
        assert path is None, "Should reject nonexistent table"
    run_test(6, "Invalid relationship rejection", test_6)

    # 7. Revenue metric
    def test_7():
        metrics = discover_multitable_metrics(engine, "sqlite", context)
        rev_cust = next((m for m in metrics if m.name == "Revenue by Customer"), None)
        assert rev_cust is not None, "Missing Revenue by Customer metric"
        assert rev_cust.current_value > 0, "Revenue value must be > 0"
    run_test(7, "Revenue metric calculation", test_7)

    # 8. Revenue by product
    def test_8():
        res = query_multitable_bi("Which products generated the most revenue?", engine=engine, db_type="sqlite")
        assert res["status"] == "success"
        assert len(res["data"]) > 0
        assert res["data"][0]["product_name"] == "Laptop"
    run_test(8, "Revenue by product", test_8)

    # 9. Revenue by category
    def test_9():
        res = query_multitable_bi("Which category generated the highest revenue?", engine=engine, db_type="sqlite")
        assert res["status"] == "success"
        assert len(res["data"]) > 0
        assert res["data"][0]["category_name"] == "Electronics"
    run_test(9, "Revenue by category", test_9)

    # 10. Revenue by customer
    def test_10():
        res = query_multitable_bi("Which customers generated the highest revenue?", engine=engine, db_type="sqlite")
        assert res["status"] == "success"
        assert len(res["data"]) > 0
        assert res["data"][0]["customer_name"] == "Alice Smith"
    run_test(10, "Revenue by customer", test_10)

    # 11. Units sold
    def test_11():
        res = query_multitable_bi("Which products were sold the most?", engine=engine, db_type="sqlite")
        assert res["status"] == "success"
        assert len(res["data"]) > 0
        assert "units_sold" in res["data"][0]
    run_test(11, "Units sold", test_11)

    # 12. Average order value
    def test_12():
        res = query_multitable_bi("What is the average order value by customer?", engine=engine, db_type="sqlite")
        assert res["status"] == "success"
        assert len(res["data"]) > 0
        assert "average_order_value" in res["data"][0]
    run_test(12, "Average order value", test_12)

    # 13. Grouped metric
    def test_13():
        res = query_multitable_bi("Which region has the highest sales?", engine=engine, db_type="sqlite")
        assert res["status"] == "success"
        assert len(res["data"]) > 0
        assert res["data"][0]["region_name"] == "North America"
    run_test(13, "Grouped metric (regional performance)", test_13)

    # 14. Time-series cross-table metric
    def test_14():
        res = query_multitable_bi("Show monthly revenue by product category.", engine=engine, db_type="sqlite")
        assert res["status"] == "success"
        assert len(res["data"]) > 0
        assert "period" in res["data"][0]
    run_test(14, "Time-series cross-table metric", test_14)

    # 15. SQL lineage
    def test_15():
        res = query_multitable_bi("Which products generated the most revenue?", engine=engine, db_type="sqlite")
        assert res["sql"] is not None and len(res["sql"]) > 10
        assert "LEFT JOIN" in res["sql"]
    run_test(15, "SQL lineage generation", test_15)

    # 16. Source table lineage
    def test_16():
        res = query_multitable_bi("Which products generated the most revenue?", engine=engine, db_type="sqlite")
        assert "order_items" in res["source_tables"]
        assert "products" in res["source_tables"]
        assert len(res["lineage"]) > 0
    run_test(16, "Source table lineage", test_16)

    # 17. Read-only enforcement
    def test_17():
        bad_sqls = [
            "DROP TABLE orders;",
            "UPDATE customers SET name = 'Hacked';",
            "DELETE FROM products;",
            "INSERT INTO categories VALUES (99, 'Bad');",
            "TRUNCATE TABLE order_items;",
        ]
        for b_sql in bad_sqls:
            val_res = validate_sql(b_sql)
            # In Phase 8.2 read-only BI engine: only SELECT or WITH allowed without write
            is_allowed = val_res.get("allowed", False) and val_res.get("operation", "").lower() in ("select", "with")
            assert not is_allowed, f"Failed to block dangerous SQL: {b_sql}"
    run_test(17, "Read-only enforcement", test_17)

    # 18. SQL injection protection
    def test_18():
        injection = "SELECT * FROM orders WHERE 1=1; DROP TABLE products; --"
        val_res = validate_sql(injection)
        assert not val_res.get("allowed", False), "SQL injection with semicolon DROP was not blocked"
    run_test(18, "SQL injection protection", test_18)

    # 19. User isolation
    def test_19():
        from app.database.connection_context import set_user_context_for_request, get_user_context
        set_user_context_for_request("user_alpha")
        ctx_a = get_user_context("user_alpha")
        ctx_b = get_user_context("user_beta")
        assert ctx_a.user_id == "user_alpha"
        assert ctx_b.user_id == "user_beta"
    run_test(19, "User isolation via ContextVar", test_19)

    # 20. Cache isolation
    def test_20():
        cache_set("user_a", CACHE_CROSS_TABLE_INSIGHTS, {"val": "data_a"})
        cache_set("user_b", CACHE_CROSS_TABLE_INSIGHTS, {"val": "data_b"})
        assert cache_get("user_a", CACHE_CROSS_TABLE_INSIGHTS)["val"] == "data_a"
        assert cache_get("user_b", CACHE_CROSS_TABLE_INSIGHTS)["val"] == "data_b"
    run_test(20, "Cache isolation between users", test_20)

    # 21. Cache invalidation
    def test_21():
        cache_set("user_x", CACHE_JOIN_PATHS, ["path1"])
        cache_set("user_y", CACHE_JOIN_PATHS, ["path2"])
        cache_clear_user("user_x")
        assert cache_get("user_x", CACHE_JOIN_PATHS) is None
        assert cache_get("user_y", CACHE_JOIN_PATHS) == ["path2"]
    run_test(21, "Cache invalidation on disconnect", test_21)

    # 22. Empty table handling
    def test_22():
        empty_engine = create_engine("sqlite:///:memory:")
        with empty_engine.connect() as conn:
            conn.execute(text("CREATE TABLE t1 (id INT PRIMARY KEY, name TEXT);"))
            conn.execute(text("CREATE TABLE t2 (id INT PRIMARY KEY, t1_id INT, FOREIGN KEY (t1_id) REFERENCES t1(id));"))
        empty_ctx = discover_business_context(empty_engine, "sqlite")
        assert not empty_ctx.has_sufficient_data, "Empty tables must report insufficient data"
    run_test(22, "Empty table handling", test_22)

    # 23. Missing FK handling
    def test_23():
        nofk_engine = create_engine("sqlite:///:memory:")
        with nofk_engine.connect() as conn:
            conn.execute(text("CREATE TABLE users (id INT, val TEXT);"))
            conn.execute(text("CREATE TABLE logs (id INT, msg TEXT);"))
        nofk_schema = analyze_schema(nofk_engine, "sqlite")
        nofk_graph = build_relationship_graph(nofk_schema)
        path = find_join_path(nofk_graph, "users", "logs", max_depth=3, db_type="sqlite")
        assert path is None, "Tables without FK should have no join path"
    run_test(23, "Missing FK handling", test_23)

    # 24. No relationship handling
    def test_24():
        res = query_multitable_bi("Show users matching logs", engine=create_engine("sqlite:///:memory:"), db_type="sqlite")
        assert res["status"] in ("no_relationship", "error")
    run_test(24, "No relationship handling", test_24)

    # 25. SQLite compatibility
    def test_25():
        with engine.connect() as conn:
            res = conn.execute(text('SELECT "name" FROM "customers" LIMIT 1')).scalar()
            assert res is not None, "Double-quoted identifiers must succeed in SQLite"
    run_test(25, "SQLite compatibility & quoting", test_25)

    # 26. Groq unavailable fallback
    def test_26():
        explanation = _explain_with_groq_or_fallback(
            question="Which category has highest sales?",
            key_insight="Sales concentrated in Electronics",
            data_rows=[{"category": "Electronics", "sales": 1000}],
            lineage=["products.category_id -> categories.id"],
        )
        assert explanation is not None and len(explanation) > 10
        assert "Electronics" in explanation
    run_test(26, "Groq unavailable fallback", test_26)

    # 27. No-write guarantee
    def test_27():
        with engine.connect() as conn:
            cnt_before = conn.execute(text("SELECT COUNT(*) FROM orders")).scalar()
            query_multitable_bi("Which customers placed the most orders?", engine=engine, db_type="sqlite")
            query_multitable_bi("Which products generated the most revenue?", engine=engine, db_type="sqlite")
            cnt_after = conn.execute(text("SELECT COUNT(*) FROM orders")).scalar()
            assert cnt_before == cnt_after, "Row counts must be identical before and after queries"
    run_test(27, "No-write guarantee", test_27)

    # 28. Evidence completeness
    def test_28():
        res = query_multitable_bi("Which products generated the most revenue?", engine=engine, db_type="sqlite")
        assert "data" in res and res["data"] is not None
        assert "lineage" in res and len(res["lineage"]) > 0
        assert "sql" in res and len(res["sql"]) > 0
        assert "record_count" in res and res["record_count"] > 0
    run_test(28, "Evidence completeness", test_28)

    # 29. Causality-safe explanation
    def test_29():
        summary = _generate_multitable_summary(
            "Which category generated highest revenue?",
            [{"category": "Electronics", "revenue": 5000}],
            ["order_items.product_id -> products.id"],
        )
        s_low = summary.lower()
        assert "caused" not in s_low and "causation" not in s_low, "Explanation must not assert causation"
        assert "concentrated in" in s_low or "associated" in s_low or "indicated" in s_low
    run_test(29, "Causality-safe explanation phrasing", test_29)

    print("\n" + "=" * 60)
    passed = sum(1 for r in results if r[0] == "PASS")
    failed = sum(1 for r in results if r[0] == "FAIL")
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
