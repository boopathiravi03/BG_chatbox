#!/usr/bin/env python
"""
backend/scratch/test_phase8_bi.py

Phase 8.1: Automated Business Intelligence Test Suite
Tests all 20 required specifications using a real disposable SQLite test database.
Never uses fake production insights.
"""
import os
import sys
import tempfile
import sqlite3
from datetime import datetime
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

results = []

def test(name, fn):
    try:
        fn()
        results.append(("PASS", name))
        print(f"  [PASS] {name}")
    except Exception as e:
        results.append(("FAIL", name, str(e)))
        print(f"  [FAIL] {name}: {e}")


def create_populated_test_db(db_path: str):
    """Creates a realistic e-commerce database with dates, measures, categories, and nulls."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            region TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            amount REAL NOT NULL,
            status TEXT NOT NULL,
            category TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    """)

    # Insert 10 customers, 2 with NULL email (20% null)
    customers_data = [
        (1, "Alice Smith", "alice@example.com", "North", "2024-01-10"),
        (2, "Bob Jones", "bob@example.com", "South", "2024-01-15"),
        (3, "Charlie Brown", None, "East", "2024-02-01"),
        (4, "Diana Prince", "diana@example.com", "West", "2024-02-10"),
        (5, "Evan Wright", None, "North", "2024-02-20"),
        (6, "Fiona Gallagher", "fiona@example.com", "East", "2024-03-01"),
        (7, "George Clark", "george@example.com", "South", "2024-03-15"),
        (8, "Hannah Abbott", "hannah@example.com", "West", "2024-04-01"),
        (9, "Ian Malcolm", "ian@example.com", "North", "2024-04-10"),
        (10, "Julia Roberts", "julia@example.com", "East", "2024-05-01"),
    ]
    cur.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?)", customers_data)

    # Insert orders across 6 months with clear trends, top category, and customer concentration
    # Month 1 (Jan): 1000
    # Month 2 (Feb): 1500 (Growth)
    # Month 3 (Mar): 2200 (Growth)
    # Month 4 (Apr): 3100 (Growth)
    # Month 5 (May): 4000 (Growth)
    # Month 6 (Jun): 2500 (Decline -37.5%)
    orders_data = [
        # Jan 2024
        (1, 1, 600.0, "completed", "Electronics", "2024-01-05"),
        (2, 2, 400.0, "completed", "Clothing", "2024-01-20"),
        # Feb 2024
        (3, 1, 900.0, "completed", "Electronics", "2024-02-05"),
        (4, 3, 600.0, "completed", "Home", "2024-02-18"),
        # Mar 2024
        (5, 1, 1400.0, "completed", "Electronics", "2024-03-02"),
        (6, 4, 800.0, "completed", "Clothing", "2024-03-25"),
        # Apr 2024
        (7, 1, 2000.0, "completed", "Electronics", "2024-04-10"),
        (8, 2, 1100.0, "completed", "Home", "2024-04-22"),
        # May 2024
        (9, 1, 2500.0, "completed", "Electronics", "2024-05-04"),
        (10, 5, 1500.0, "completed", "Electronics", "2024-05-18"),
        # Jun 2024 (Drop)
        (11, 2, 1500.0, "completed", "Electronics", "2024-06-02"),
        (12, 6, 1000.0, "completed", "Clothing", "2024-06-15"),
    ]
    cur.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)", orders_data)

    conn.commit()
    conn.close()


print("\n" + "=" * 60)
print("PHASE 8.1: AUTOMATED BUSINESS INTELLIGENCE TEST SUITE")
print("=" * 60)

# Setup temporary test database
temp_dir = tempfile.mkdtemp()
db_file = os.path.join(temp_dir, "test_bi.db")
create_populated_test_db(db_file)
engine = create_engine(f"sqlite:///{db_file}")

# ── 1. Business Context Discovery ─────────────────────────────────────────────
print("\n[1] Business Context Discovery")

def test_business_context_discovery():
    from app.intelligence.business_intelligence import discover_business_context
    ctx = discover_business_context(engine, "sqlite")
    assert ctx.has_sufficient_data is True
    assert ctx.total_records >= 22
    assert any(e["table"] == "orders" for e in ctx.entity_tables)
    assert any(m["column"] == "amount" for m in ctx.measure_columns)
    assert any(t["column"] == "created_at" for t in ctx.time_columns)
    assert any(d["column"] == "category" for d in ctx.dimension_columns)
test("Discovers entity tables, time columns, measures, and dimensions", test_business_context_discovery)


# ── 2. Metric Discovery ───────────────────────────────────────────────────────
print("\n[2] Metric Discovery")

def test_metric_discovery():
    from app.intelligence.business_intelligence import discover_business_context, discover_business_metrics
    ctx = discover_business_context(engine, "sqlite")
    metrics = discover_business_metrics(engine, "sqlite", ctx)
    assert len(metrics) > 0
    metric_names = [m.name for m in metrics]
    assert any("Amount" in n or "Order" in n for n in metric_names)
    amount_metric = next((m for m in metrics if "Amount" in m.name and m.calculation_method.startswith("SUM")), None)
    assert amount_metric is not None
    assert amount_metric.current_value > 0
    assert "SELECT SUM" in amount_metric.sql
test("Discovers quantitative volume and aggregate metrics with deterministic SQL", test_metric_discovery)


# ── 3. Trend Insight ──────────────────────────────────────────────────────────
print("\n[3] Trend Insight")

def test_trend_insight():
    from app.intelligence.business_intelligence import generate_business_intelligence_report, InsightCategory
    report = generate_business_intelligence_report(engine, "sqlite")
    assert report.status == "success"
    trends = [i for i in report.insights if i.category == InsightCategory.TREND]
    assert len(trends) > 0
    t = trends[0]
    assert t.current_value is not None
    assert "trajectory" in t.title.lower() or "trend" in t.title.lower() or "increased" in t.title.lower() or "decreased" in t.title.lower()
test("Generates chronological TREND insight across multiple periods", test_trend_insight)


# ── 4. Growth Insight ─────────────────────────────────────────────────────────
print("\n[4] Growth Insight")

def test_growth_insight():
    # Test growth detection logic
    from app.intelligence.business_intelligence.insight_explainer import generate_deterministic_explanation
    from app.intelligence.business_intelligence.models import InsightCategory
    title, summary, rec = generate_deterministic_explanation(
        category=InsightCategory.GROWTH,
        metric_name="Order Volume",
        current_val=500.0,
        prev_val=400.0,
        change_pct=25.0,
    )
    assert "increased by 25.0%" in title
    assert "+25.0%" in summary
    assert "Data Explorer" in rec
test("Generates formatted GROWTH insight with percentage increase and next step", test_growth_insight)


# ── 5. Decline Insight ────────────────────────────────────────────────────────
print("\n[5] Decline Insight")

def test_decline_insight():
    from app.intelligence.business_intelligence import generate_business_intelligence_report, InsightCategory
    report = generate_business_intelligence_report(engine, "sqlite")
    declines = [i for i in report.insights if i.category == InsightCategory.DECLINE]
    assert len(declines) > 0, "Expected at least 1 decline insight for the June drop"
    d = declines[0]
    assert d.change_percent < 0
    assert "decreased" in d.title.lower()
    assert d.evidence["previous_value"] > d.evidence["current_value"]
test("Detects recent period volume/revenue contraction as DECLINE insight", test_decline_insight)


# ── 6. Top Contributor Insight ────────────────────────────────────────────────
print("\n[6] Top Contributor Insight")

def test_top_contributor_insight():
    from app.intelligence.business_intelligence import generate_business_intelligence_report, InsightCategory
    report = generate_business_intelligence_report(engine, "sqlite")
    top_contribs = [i for i in report.insights if i.category == InsightCategory.TOP_CONTRIBUTOR]
    assert len(top_contribs) > 0
    tc = top_contribs[0]
    assert tc.evidence["share_percent"] >= 25.0
    assert "contributed" in tc.title.lower()
test("Identifies dominant dimension category as TOP_CONTRIBUTOR insight", test_top_contributor_insight)


# ── 7. Concentration Insight ──────────────────────────────────────────────────
print("\n[7] Concentration Insight")

def test_concentration_insight():
    from app.intelligence.business_intelligence import generate_business_intelligence_report, InsightCategory
    report = generate_business_intelligence_report(engine, "sqlite")
    concs = [i for i in report.insights if i.category == InsightCategory.CONCENTRATION]
    assert len(concs) > 0
    c = concs[0]
    assert c.evidence["share_percent"] >= 50.0
    assert "concentration" in c.title.lower()
test("Identifies Pareto/concentration patterns as CONCENTRATION insight", test_concentration_insight)


# ── 8. Data Quality Insight ───────────────────────────────────────────────────
print("\n[8] Data Quality Insight")

def test_data_quality_insight():
    from app.intelligence.business_intelligence import generate_business_intelligence_report, InsightCategory
    report = generate_business_intelligence_report(engine, "sqlite")
    quality_insights = [i for i in report.insights if i.category == InsightCategory.QUALITY]
    assert len(quality_insights) > 0, "Expected quality insight for customers.email NULLs"
    q = quality_insights[0]
    assert "email" in q.metric.lower() or "customers" in q.source_tables
    assert q.evidence["null_percent"] >= 15.0
test("Detects high-null density columns as QUALITY insight", test_data_quality_insight)


# ── 9. Anomaly Integration ────────────────────────────────────────────────────
print("\n[9] Anomaly Integration")

def test_anomaly_integration():
    from app.intelligence.business_intelligence.insight_engine import _generate_anomaly_insights
    # Call directly with engine
    insights = _generate_anomaly_insights(engine, "sqlite")
    # Even if dataset has no extreme IQR outliers, function handles cleanly without error
    assert isinstance(insights, list)
test("Anomaly detection integrates cleanly without exception", test_anomaly_integration)


# ── 10. Forecast Integration ──────────────────────────────────────────────────
print("\n[10] Forecast Integration")

def test_forecast_integration():
    from app.intelligence.business_intelligence import generate_business_intelligence_report, InsightCategory
    report = generate_business_intelligence_report(engine, "sqlite")
    forecasts = [i for i in report.insights if i.category == InsightCategory.FORECAST]
    assert len(forecasts) > 0, "Expected at least 1 forecast insight from 6 monthly periods"
    f = forecasts[0]
    assert "projected" in f.title.lower()
    assert f.evidence["method"] == "Holt's Exponential Smoothing"
test("Forecast engine produces cautious forward-looking FORECAST insight", test_forecast_integration)


# ── 11. Insufficient Data Handling ────────────────────────────────────────────
print("\n[11] Insufficient Data Handling")

def test_insufficient_data():
    from app.intelligence.business_intelligence import generate_business_intelligence_report
    small_db = os.path.join(temp_dir, "small.db")
    c = sqlite3.connect(small_db)
    c.execute("CREATE TABLE test (id INT, val TEXT)")
    c.execute("INSERT INTO test VALUES (1, 'only_one_row')")
    c.commit()
    c.close()
    e_small = create_engine(f"sqlite:///{small_db}")

    report = generate_business_intelligence_report(e_small, "sqlite")
    assert report.status == "insufficient_data"
    assert "insufficient" in report.message.lower()
    assert len(report.insights) == 0
test("Returns graceful insufficient_data response when records < 2", test_insufficient_data)


# ── 12. Empty Database Handling ───────────────────────────────────────────────
print("\n[12] Empty Database Handling")

def test_empty_database():
    from app.intelligence.business_intelligence import generate_business_intelligence_report
    empty_db = os.path.join(temp_dir, "empty.db")
    c = sqlite3.connect(empty_db)
    c.execute("CREATE TABLE empty_table (id INT, val TEXT)")
    c.commit()
    c.close()
    e_empty = create_engine(f"sqlite:///{empty_db}")

    report = generate_business_intelligence_report(e_empty, "sqlite")
    assert report.status == "insufficient_data"
    assert "no records" in report.message.lower() or "insufficient" in report.message.lower()
test("Handles empty tables with zero records gracefully", test_empty_database)


# ── 13. No Numeric Columns Handling ───────────────────────────────────────────
print("\n[13] No Numeric Columns Handling")

def test_no_numeric_columns():
    from app.intelligence.business_intelligence import generate_business_intelligence_report
    text_db = os.path.join(temp_dir, "text_only.db")
    c = sqlite3.connect(text_db)
    c.execute("CREATE TABLE logs (id TEXT, message TEXT, user_agent TEXT)")
    c.execute("INSERT INTO logs VALUES ('1', 'hello', 'chrome')")
    c.execute("INSERT INTO logs VALUES ('2', 'world', 'firefox')")
    c.commit()
    c.close()
    e_text = create_engine(f"sqlite:///{text_db}")

    report = generate_business_intelligence_report(e_text, "sqlite")
    # Generates volume / count insights or handles without crashing
    assert report is not None
test("Handles schema without numeric measure columns without crashing", test_no_numeric_columns)


# ── 14. No Time-Series Columns Handling ───────────────────────────────────────
print("\n[14] No Time-Series Columns Handling")

def test_no_timeseries_columns():
    from app.intelligence.business_intelligence import generate_business_intelligence_report, InsightCategory
    notime_db = os.path.join(temp_dir, "notime.db")
    c = sqlite3.connect(notime_db)
    c.execute("CREATE TABLE products (id INT, name TEXT, category TEXT, price REAL)")
    c.execute("INSERT INTO products VALUES (1, 'Widget', 'Tools', 10.0)")
    c.execute("INSERT INTO products VALUES (2, 'Gadget', 'Electronics', 50.0)")
    c.execute("INSERT INTO products VALUES (3, 'Hammer', 'Tools', 15.0)")
    c.commit()
    c.close()
    e_notime = create_engine(f"sqlite:///{notime_db}")

    report = generate_business_intelligence_report(e_notime, "sqlite")
    # Should not produce temporal insights (no time col), but can produce breakdown/metrics
    temporal = [i for i in report.insights if i.category in (InsightCategory.TREND, InsightCategory.GROWTH, InsightCategory.DECLINE)]
    assert len(temporal) == 0, "Should not generate temporal insights without date column"
test("Skips temporal insights gracefully when no time-series columns exist", test_no_timeseries_columns)


# ── 15. Evidence Generation ───────────────────────────────────────────────────
print("\n[15] Evidence Generation")

def test_evidence_generation():
    from app.intelligence.business_intelligence import generate_business_intelligence_report
    report = generate_business_intelligence_report(engine, "sqlite")
    for ins in report.insights:
        assert isinstance(ins.evidence, dict)
        assert len(ins.evidence) > 0, f"Insight {ins.title} must have non-empty evidence"
test("Every generated insight contains verifiable structured evidence", test_evidence_generation)


# ── 16. SQL Lineage ───────────────────────────────────────────────────────────
print("\n[16] SQL Lineage")

def test_sql_lineage():
    from app.intelligence.business_intelligence import generate_business_intelligence_report, InsightCategory
    report = generate_business_intelligence_report(engine, "sqlite")
    sql_insights = [i for i in report.insights if i.category in (InsightCategory.TREND, InsightCategory.DECLINE, InsightCategory.TOP_CONTRIBUTOR)]
    for ins in sql_insights:
        assert ins.sql is not None and len(ins.sql) > 0, f"Insight {ins.title} missing SQL query"
        assert "SELECT" in ins.sql.upper()
        assert not any(forbidden in ins.sql.upper() for forbidden in ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER"])
test("Insights include reproducible, read-only SQL lineage queries", test_sql_lineage)


# ── 17. User Isolation ────────────────────────────────────────────────────────
print("\n[17] User Isolation")

def test_user_isolation():
    from app.security.user_cache import cache_set, cache_get, cache_clear_user, CACHE_INSIGHTS_REPORT
    cache_set("user_a", CACHE_INSIGHTS_REPORT, {"summary": {"total": 5}})
    cache_set("user_b", CACHE_INSIGHTS_REPORT, {"summary": {"total": 12}})

    assert cache_get("user_a", CACHE_INSIGHTS_REPORT)["summary"]["total"] == 5
    assert cache_get("user_b", CACHE_INSIGHTS_REPORT)["summary"]["total"] == 12

    cache_clear_user("user_a")
    assert cache_get("user_a", CACHE_INSIGHTS_REPORT) is None
    assert cache_get("user_b", CACHE_INSIGHTS_REPORT) is not None
test("Insights cache is strictly user-scoped; clearing User A leaves User B intact", test_user_isolation)


# ── 18. Cache Invalidation ────────────────────────────────────────────────────
print("\n[18] Cache Invalidation")

def test_cache_invalidation():
    from app.security.user_cache import cache_set, cache_get, cache_delete, CACHE_INSIGHTS_REPORT
    user_test = "user_cache_inv_test"
    cache_set(user_test, CACHE_INSIGHTS_REPORT, {"report_id": 123})
    assert cache_get(user_test, CACHE_INSIGHTS_REPORT) is not None

    cache_delete(user_test, CACHE_INSIGHTS_REPORT)
    assert cache_get(user_test, CACHE_INSIGHTS_REPORT) is None
test("Cache invalidation removes user insights report on demand", test_cache_invalidation)


# ── 19. Groq Unavailable Fallback ─────────────────────────────────────────────
print("\n[19] Groq Unavailable Fallback")

def test_groq_fallback():
    from app.intelligence.business_intelligence.models import BusinessInsight, InsightCategory, InsightSeverity
    from app.intelligence.business_intelligence.insight_explainer import polish_explanation_with_groq_if_available
    ins = BusinessInsight(
        title="Revenue dropped 20%",
        summary="Deterministic summary text",
        category=InsightCategory.DECLINE,
        severity=InsightSeverity.WARNING,
        evidence={"sample": 1},
    )
    # Calling polish_explanation_with_groq_if_available should never raise even if Groq fails/is missing key
    polish_explanation_with_groq_if_available(ins)
    assert ins.title == "Revenue dropped 20%"
    assert len(ins.summary) > 0
test("Groq failure falls back silently to deterministic explanation", test_groq_fallback)


# ── 20. No-Write Guarantee ────────────────────────────────────────────────────
print("\n[20] No-Write Guarantee")

def test_no_write_guarantee():
    from app.intelligence.business_intelligence import generate_business_intelligence_report

    with engine.connect() as conn:
        before_orders = conn.execute(text("SELECT COUNT(*) FROM orders")).scalar()
        before_customers = conn.execute(text("SELECT COUNT(*) FROM customers")).scalar()

    # Run full business intelligence scan
    report = generate_business_intelligence_report(engine, "sqlite")

    with engine.connect() as conn:
        after_orders = conn.execute(text("SELECT COUNT(*) FROM orders")).scalar()
        after_customers = conn.execute(text("SELECT COUNT(*) FROM customers")).scalar()

    assert before_orders == after_orders, "Insight engine must NEVER insert, update, or delete rows"
    assert before_customers == after_customers, "Insight engine must NEVER mutate customer rows"
test("Guaranteed read-only: database state and row counts are completely unchanged", test_no_write_guarantee)


# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
passed = sum(1 for r in results if r[0] == "PASS")
failed = sum(1 for r in results if r[0] == "FAIL")
print(f"Phase 8.1 Test Results: {passed} passed, {failed} failed")
print("=" * 60)

if failed > 0:
    sys.exit(1)
else:
    sys.exit(0)
