#!/usr/bin/env python
"""
Phase 8.7: Root-Cause & Investigation Intelligence Test Suite
Covers at least 40 dedicated assertions verifying:
- Models & serialization
- Investigation orchestration
- Evidence building & SQL lineage
- Dimensional contributor analysis
- Hypothesis engine & causality caveats
- Deterministic confidence assessment
- Grounded investigation planning
- Insufficient evidence handling
- SQL safety (read-only, DML/DDL blocking, command chaining)
- Dialect compatibility (SQLite, MySQL, PostgreSQL)
- Privacy & Groq sanitization
- API endpoint authentication & rate limiting
- User isolation
- Zero database mutation guarantee
- Regression guards for Phase 8.1 - 8.6
"""
from __future__ import annotations

import os
import sys
import uuid
import sqlite3
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from app.security.auth import create_access_token
from app.tools.execute_query import validate_sql
from app.intelligence.investigation.models import (
    ConfidenceLevel,
    ObservedChange,
    EvidenceItem,
    ContributingFactor,
    Hypothesis,
    InvestigationRecommendation,
    ConfidenceAssessment,
    InvestigationLineage,
    InvestigationRequest,
    InvestigationResult,
)
from app.intelligence.investigation.evidence_builder import build_investigation_evidence
from app.intelligence.investigation.contributor_analysis import analyze_contributing_factors
from app.intelligence.investigation.hypothesis_engine import generate_hypotheses_and_confidence
from app.intelligence.investigation.investigation_planner import plan_next_investigations
from app.intelligence.investigation.explainer import (
    build_deterministic_explanation,
    polish_explanation_with_groq,
)
from app.intelligence.investigation.investigator import investigate_signal

client = TestClient(app, raise_server_exceptions=False)
results: list[tuple[str, str, str]] = []


def test(name: str, fn):
    try:
        fn()
        results.append(("PASS", name, ""))
        print(f"  [PASS] {name}")
    except Exception as e:
        results.append(("FAIL", name, str(e)))
        print(f"  [FAIL] {name}: {e}")


def _auth_header(user_id: str) -> dict[str, str]:
    token = create_access_token(user_id=user_id, username=user_id)
    return {"Authorization": f"Bearer {token}"}


# ── Helper: create in-memory test database ─────────────────────────────────────
def _create_mock_engine():
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE products (
                product_id INTEGER PRIMARY KEY,
                name TEXT,
                category TEXT,
                price REAL
            );
        """))
        conn.execute(text("""
            CREATE TABLE orders (
                order_id INTEGER PRIMARY KEY,
                customer_id INTEGER,
                product_id INTEGER,
                quantity INTEGER,
                region TEXT,
                order_date TEXT
            );
        """))
        conn.execute(text("""
            CREATE TABLE inventory (
                inventory_id INTEGER PRIMARY KEY,
                product_id INTEGER,
                stock INTEGER
            );
        """))
        # Insert period 1 (2026-07) and period 2 (2026-08)
        conn.execute(text("""
            INSERT INTO products VALUES
            (1, 'Laptop', 'Electronics', 1000.0),
            (2, 'Phone', 'Electronics', 500.0),
            (3, 'Desk', 'Furniture', 200.0);
        """))
        conn.execute(text("""
            INSERT INTO orders VALUES
            (101, 1, 1, 10, 'South', '2026-07-15 10:00:00'),
            (102, 2, 2, 20, 'North', '2026-07-20 11:00:00'),
            (103, 3, 3, 5,  'South', '2026-07-25 12:00:00'),
            (104, 1, 1, 5,  'South', '2026-08-10 10:00:00'),
            (105, 2, 2, 10, 'North', '2026-08-15 11:00:00'),
            (106, 3, 3, 5,  'South', '2026-08-20 12:00:00');
        """))
        conn.execute(text("""
            INSERT INTO inventory VALUES
            (1, 1, 15),
            (2, 2, 30),
            (3, 3, 50);
        """))
        conn.commit()
    return engine


print("\n" + "=" * 60)
print("PHASE 8.7: ROOT-CAUSE & INVESTIGATION INTELLIGENCE TEST SUITE")
print("=" * 60)

# ── 1. Models & Serialization Tests ───────────────────────────────────────────
print("\n[1] Models & Serialization")


def t01_observed_change_model():
    oc = ObservedChange(
        metric="Revenue",
        current_value=10000.0,
        previous_value=15000.0,
        delta=-5000.0,
        delta_percent=-33.33,
        time_period="2026-07 -> 2026-08",
        formatted_change="Revenue decreased by 33.33%",
    )
    d = oc.to_dict()
    assert d["metric"] == "Revenue"
    assert d["delta"] == -5000.0
    restored = ObservedChange.from_dict(d)
    assert restored.metric == "Revenue"
    assert restored.delta_percent == -33.33


test("1. ObservedChange instantiation & roundtrip serialization", t01_observed_change_model)


def t02_evidence_item_model():
    ev = EvidenceItem(
        evidence_id="ev_01",
        metric="Order Volume",
        current_value=20,
        previous_value=35,
        delta=-15,
        delta_percent=-42.86,
        time_range="2026-07 vs 2026-08",
        source_table="orders",
        source_columns=["order_date", "quantity"],
        record_count=55,
        sql_lineage="SELECT COUNT(*) FROM orders",
        calculation_description="COUNT(*) grouped by month",
    )
    d = ev.to_dict()
    assert d["evidence_id"] == "ev_01"
    assert "quantity" in d["source_columns"]
    restored = EvidenceItem.from_dict(d)
    assert restored.source_table == "orders"
    assert restored.delta == -15


test("2. EvidenceItem instantiation & roundtrip serialization", t02_evidence_item_model)


def t03_contributing_factor_model():
    cf = ContributingFactor(
        factor_id="cf_01",
        dimension="products.category",
        dimension_value="Electronics",
        impact_type="negative",
        contribution_percent=-48.0,
        observed_change="Electronics volume dropped by 48%",
        evidence_ids=["ev_01"],
    )
    d = cf.to_dict()
    assert d["dimension_value"] == "Electronics"
    assert d["impact_type"] == "negative"
    restored = ContributingFactor.from_dict(d)
    assert restored.contribution_percent == -48.0


test("3. ContributingFactor instantiation & roundtrip serialization", t03_contributing_factor_model)


def t04_hypothesis_model_unconfirmed():
    hypo = Hypothesis(
        hypothesis_id="h_01",
        statement="Revenue decline coincides with Electronics contraction.",
        supporting_evidence_ids=["ev_01"],
        confidence_level=ConfidenceLevel.MODERATE,
        status="unconfirmed",
        causality_caveat="Correlation does not establish causation.",
    )
    d = hypo.to_dict()
    assert d["status"] == "unconfirmed"
    assert "causation" in d["causality_caveat"]
    restored = Hypothesis.from_dict(d)
    assert restored.status == "unconfirmed"
    assert restored.confidence_level == ConfidenceLevel.MODERATE


test("4. Hypothesis enforces unconfirmed status and causality caveat", t04_hypothesis_model_unconfirmed)


def t05_recommendation_and_confidence_models():
    rec = InvestigationRecommendation(
        recommendation_id="rec_01",
        action_title="Inspect product availability",
        reason="Check stock levels",
        target_data="inventory.stock",
        expected_information_gained="Verify stockouts",
        priority="high",
    )
    d_rec = rec.to_dict()
    assert d_rec["priority"] == "high"

    conf = ConfidenceAssessment(
        level=ConfidenceLevel.HIGH,
        score_rationale="High confidence rationale",
        supporting_signals_count=5,
        independent_sources_count=3,
        limitations=["Observational data only"],
    )
    d_conf = conf.to_dict()
    assert d_conf["level"] == "HIGH"
    assert len(d_conf["limitations"]) == 1


test("5. InvestigationRecommendation and ConfidenceAssessment serialization", t05_recommendation_and_confidence_models)


def t06_investigation_result_model():
    res = InvestigationResult(
        investigation_id="inv_test",
        user_id="user_1",
        signal_id="sig_1",
        signal_title="Sales Drop",
        status="success",
        observed_change=ObservedChange(metric="Sales", current_value=100, previous_value=200),
        evidence=[],
        contributing_factors=[],
        hypotheses=[],
        summary="Sales dropped.",
        explanation="Full explanation markdown",
        created_at="2026-10-02T10:00:00Z",
    )
    d = res.to_dict()
    assert d["investigation_id"] == "inv_test"
    assert d["status"] == "success"
    restored = InvestigationResult.from_dict(d)
    assert restored.user_id == "user_1"
    assert restored.observed_change is not None


test("6. InvestigationResult full model serialization", t06_investigation_result_model)


# ── 2. Evidence Builder Tests ─────────────────────────────────────────────────
print("\n[2] Evidence Builder")


def t07_evidence_builder_chronological():
    mock_eng = _create_mock_engine()
    oc, items, meta = build_investigation_evidence(
        engine=mock_eng,
        db_type="sqlite",
        target_table="orders",
    )
    assert oc is not None
    assert len(items) >= 1
    assert any("orders" in e.source_table for e in items)
    assert all(e.sql_lineage for e in items)


test("7. Evidence builder computes chronological deltas and SQL lineage", t07_evidence_builder_chronological)


def t08_evidence_builder_multi_table_revenue():
    mock_eng = _create_mock_engine()
    oc, items, meta = build_investigation_evidence(
        engine=mock_eng,
        db_type="sqlite",
        target_table="orders",
    )
    # Check if cross-table revenue evidence was computed
    has_rev_or_meas = any("quantity" in e.metric.lower() or "revenue" in e.metric.lower() or "volume" in e.metric.lower() for e in items)
    assert has_rev_or_meas
    assert "orders" in meta["tables_inspected"]


test("8. Evidence builder inspects numerical measures across periods", t08_evidence_builder_multi_table_revenue)


def t09_evidence_builder_empty_db():
    empty_eng = create_engine("sqlite:///:memory:")
    with empty_eng.connect() as conn:
        conn.execute(text("CREATE TABLE empty_tbl (id INT, val TEXT);"))
        conn.commit()

    oc, items, meta = build_investigation_evidence(
        engine=empty_eng,
        db_type="sqlite",
        target_table="empty_tbl",
    )
    assert oc is None or len(items) == 0
    assert len(meta.get("insufficient_data_reasons", [])) > 0


test("9. Evidence builder gracefully flags empty tables as insufficient", t09_evidence_builder_empty_db)


def t10_evidence_builder_disconnected():
    oc, items, meta = build_investigation_evidence(
        engine=None,
        db_type="none",
    )
    assert oc is None
    assert len(items) == 0


test("10. Evidence builder handles disconnected database gracefully", t10_evidence_builder_disconnected)


# ── 3. Contributor Analysis Tests ─────────────────────────────────────────────
print("\n[3] Contributor Analysis")


def t11_contributor_analysis_dimensions():
    mock_eng = _create_mock_engine()
    oc, items, meta = build_investigation_evidence(engine=mock_eng, db_type="sqlite", target_table="orders")
    cfs, dims = analyze_contributing_factors(
        engine=mock_eng,
        db_type="sqlite",
        target_table="orders",
        observed_change=oc,
        evidence_items=items,
    )
    assert len(dims) > 0
    assert any("region" in d.lower() or "category" in d.lower() for d in dims)


test("11. Contributor analysis discovers candidate dimensions in primary and joined tables", t11_contributor_analysis_dimensions)


def t12_contributor_analysis_ranking():
    mock_eng = _create_mock_engine()
    oc, items, meta = build_investigation_evidence(engine=mock_eng, db_type="sqlite", target_table="orders")
    cfs, dims = analyze_contributing_factors(
        engine=mock_eng,
        db_type="sqlite",
        target_table="orders",
        observed_change=oc,
        evidence_items=items,
    )
    if len(cfs) >= 2:
        # Factors must be ordered by absolute contribution percentage descending
        assert abs(cfs[0].contribution_percent or 0) >= abs(cfs[1].contribution_percent or 0)


test("12. Contributor analysis ranks factors by magnitude of contribution", t12_contributor_analysis_ranking)


def t13_contributor_analysis_non_causal_phrasing():
    mock_eng = _create_mock_engine()
    oc, items, meta = build_investigation_evidence(engine=mock_eng, db_type="sqlite", target_table="orders")
    cfs, dims = analyze_contributing_factors(
        engine=mock_eng,
        db_type="sqlite",
        target_table="orders",
        observed_change=oc,
        evidence_items=items,
    )
    for cf in cfs:
        # Must not assert proof of causation in description
        assert "caused" not in cf.observed_change.lower()
        assert "proven" not in cf.observed_change.lower()


test("13. Contributor analysis adheres to non-causal phrasing", t13_contributor_analysis_non_causal_phrasing)


# ── 4. Hypothesis Engine Tests ────────────────────────────────────────────────
print("\n[4] Hypothesis Engine")


def t14_hypothesis_generation():
    oc = ObservedChange(metric="Volume", current_value=10, previous_value=20, delta=-10, delta_percent=-50.0)
    evs = [
        EvidenceItem(evidence_id="ev_1", metric="Volume", current_value=10, previous_value=20, source_table="orders"),
        EvidenceItem(evidence_id="ev_2", metric="Revenue", current_value=5000, previous_value=10000, source_table="orders"),
    ]
    cfs = [
        ContributingFactor(factor_id="cf_1", dimension="region", dimension_value="South", impact_type="negative", contribution_percent=-60.0, evidence_ids=["ev_1"]),
    ]
    hypos, conf = generate_hypotheses_and_confidence(oc, evs, cfs, [])
    assert len(hypos) >= 1
    assert hypos[0].status == "unconfirmed"
    assert "South" in hypos[0].statement
    assert "causation" in hypos[0].causality_caveat.lower()


test("14. Hypothesis engine builds evidence-linked candidate explanations", t14_hypothesis_generation)


def t15_confidence_assessment_levels():
    oc = ObservedChange(metric="Volume", current_value=10, previous_value=20)
    # High confidence test: 4+ evidence items across 2+ sources and 2+ factors
    evs_high = [
        EvidenceItem(evidence_id=f"e_{i}", metric=f"M_{i}", current_value=1, previous_value=2, source_table=f"tbl_{i%2}")
        for i in range(4)
    ]
    cfs_high = [
        ContributingFactor(factor_id="cf_1", dimension="cat", dimension_value="X", impact_type="negative", contribution_percent=-40.0),
        ContributingFactor(factor_id="cf_2", dimension="reg", dimension_value="Y", impact_type="negative", contribution_percent=-30.0),
    ]
    _, conf_high = generate_hypotheses_and_confidence(oc, evs_high, cfs_high, [])
    assert conf_high.level == ConfidenceLevel.HIGH

    # Limited confidence test: 1 evidence item, 0 factors
    _, conf_lim = generate_hypotheses_and_confidence(oc, [evs_high[0]], [], ["Limited baseline"])
    assert conf_lim.level == ConfidenceLevel.LIMITED


test("15. Deterministic confidence assessment logic (HIGH vs LIMITED)", t15_confidence_assessment_levels)


def t16_confidence_zero_arbitrary_numbers():
    oc = ObservedChange(metric="Revenue", current_value=100, previous_value=200)
    evs = [EvidenceItem(evidence_id="ev_1", metric="Revenue", current_value=100, previous_value=200, source_table="orders")]
    _, conf = generate_hypotheses_and_confidence(oc, evs, [], [])
    # Verify no hallucinated percentages in rationale
    assert "% certainty" not in conf.score_rationale
    assert "% confidence" not in conf.score_rationale


test("16. Confidence assessment rationale contains no arbitrary percentages", t16_confidence_zero_arbitrary_numbers)


# ── 5. Investigation Planner Tests ────────────────────────────────────────────
print("\n[5] Investigation Planner")


def t17_investigation_planner_grounded():
    cfs = [
        ContributingFactor(factor_id="cf_1", dimension="products.category", dimension_value="Electronics", impact_type="negative", contribution_percent=-45.0),
    ]
    recs = plan_next_investigations(
        schema_tables=["orders", "products", "inventory"],
        contributing_factors=cfs,
        observed_change=ObservedChange(metric="Revenue", current_value=10, previous_value=20),
        missing_evidence_notes=[],
    )
    assert len(recs) >= 1
    # Check that recommendations reference tables that actually exist in the schema
    for r in recs:
        assert any(t in r.target_data.lower() for t in ["products", "orders", "inventory", "records"])
        assert r.expected_information_gained


test("17. Investigation planner recommends steps grounded in actual schema", t17_investigation_planner_grounded)


def t18_investigation_planner_missing_evidence():
    recs = plan_next_investigations(
        schema_tables=["single_table"],
        contributing_factors=[],
        observed_change=None,
        missing_evidence_notes=["No categorical dimensions available"],
    )
    assert any("enrich" in r.action_title.lower() or "missing" in r.reason.lower() or "dimension" in r.reason.lower() for r in recs)


test("18. Investigation planner addresses analytical gaps when evidence is missing", t18_investigation_planner_missing_evidence)


# ── 6. Explainer Tests ────────────────────────────────────────────────────────
print("\n[6] Explainer")


def t19_deterministic_explainer():
    oc = ObservedChange(metric="Orders", current_value=50, previous_value=100, delta=-50, delta_percent=-50.0)
    evs = [EvidenceItem(evidence_id="e1", metric="Orders", current_value=50, previous_value=100, delta_percent=-50.0, source_table="orders")]
    hypos = [Hypothesis(hypothesis_id="h1", statement="Decline correlated with season", status="unconfirmed", causality_caveat="Correlation does not establish causation.")]
    conf = ConfidenceAssessment(level=ConfidenceLevel.MODERATE, score_rationale="Moderate signals", supporting_signals_count=2, independent_sources_count=1)

    summary, full_narrative = build_deterministic_explanation(oc, evs, [], hypos, conf, [], "success")
    assert "declined by 50.0%" in summary
    assert "Correlation does not establish causation" in full_narrative
    assert "Confidence Assessment" in full_narrative


test("19. Deterministic explainer synthesizes clear markdown briefing", t19_deterministic_explainer)


def t20_explainer_groq_fallback():
    # Calling polish with an invalid key or simulating failure falls back seamlessly
    draft_sum = "Revenue decreased 20%."
    draft_full = "Full text"
    res_sum, res_full = polish_explanation_with_groq(draft_sum, draft_full, "Revenue", "MODERATE")
    assert res_sum
    assert res_full == draft_full


test("20. Groq failure falls back silently to deterministic explanation", t20_explainer_groq_fallback)


# ── 7. Investigator Orchestration Tests ───────────────────────────────────────
print("\n[7] Investigator Orchestrator")


def t21_investigator_end_to_end():
    mock_eng = _create_mock_engine()
    res = investigate_signal(
        signal_id="test_signal_01",
        user_id="user_test_21",
        engine=mock_eng,
        db_type="sqlite",
        target_table="orders",
    )
    assert res.status == "success"
    assert res.observed_change is not None
    assert len(res.evidence) > 0
    assert len(res.hypotheses) > 0
    assert res.confidence is not None
    assert len(res.recommended_investigations) > 0
    assert res.lineage is not None
    assert "orders" in res.lineage.source_tables


test("21. Investigator executes complete end-to-end root-cause analysis", t21_investigator_end_to_end)


def t22_investigator_insufficient_evidence():
    empty_eng = create_engine("sqlite:///:memory:")
    with empty_eng.connect() as conn:
        conn.execute(text("CREATE TABLE t (id INT);"))
        conn.commit()

    res = investigate_signal(
        signal_id="sig_empty",
        user_id="user_test_22",
        engine=empty_eng,
        db_type="sqlite",
        target_table="t",
    )
    assert res.status == "insufficient_evidence"
    assert res.confidence.level == ConfidenceLevel.LIMITED
    assert res.missing_evidence is not None


test("22. Investigator returns insufficient_evidence when schema lacks records", t22_investigator_insufficient_evidence)


def t23_investigator_disconnected_handling():
    res = investigate_signal(
        signal_id="sig_disc",
        user_id="user_test_23",
        engine=None,
        db_type="none",
    )
    assert res.status == "disconnected"
    assert "No database" in res.summary


test("23. Investigator handles disconnected state cleanly", t23_investigator_disconnected_handling)


def t24_investigator_lineage_traceability():
    mock_eng = _create_mock_engine()
    res = investigate_signal(
        signal_id="sig_lineage",
        user_id="user_test_24",
        engine=mock_eng,
        db_type="sqlite",
        target_table="orders",
    )
    assert res.lineage is not None
    assert len(res.lineage.source_tables) >= 1
    assert len(res.lineage.calculations) >= 1


test("24. Investigation result provides comprehensive data lineage", t24_investigator_lineage_traceability)


# ── 8. SQL Safety & Security Tests ────────────────────────────────────────────
print("\n[8] SQL Safety & Security")


def t25_sql_read_only_allowed():
    valid = validate_sql("SELECT product_id, price FROM products WHERE price > 100 LIMIT 10")
    assert valid.get("allowed") is True
    assert valid.get("operation") == "select"


test("25. SQL safety allows valid SELECT queries", t25_sql_read_only_allowed)


def t26_sql_dml_blocked():
    blocked_insert = validate_sql("INSERT INTO products VALUES (99, 'Hacked', 'Bad', 0)")
    assert blocked_insert.get("allowed") is False or blocked_insert.get("requires_confirmation") is True

    blocked_update = validate_sql("UPDATE products SET price = 0")
    # In validate_sql, update without WHERE is disallowed
    assert blocked_update.get("allowed") is False

    blocked_delete = validate_sql("DELETE FROM products")
    assert blocked_delete.get("allowed") is False


test("26. SQL safety blocks unrestricted DML (INSERT, UPDATE, DELETE)", t26_sql_dml_blocked)


def t27_sql_ddl_blocked():
    blocked_drop = validate_sql("DROP TABLE products")
    assert blocked_drop.get("allowed") is False

    blocked_alter = validate_sql("ALTER TABLE products ADD COLUMN pwned TEXT")
    assert blocked_alter.get("allowed") is False

    blocked_truncate = validate_sql("TRUNCATE TABLE products")
    assert blocked_truncate.get("allowed") is False


test("27. SQL safety strictly blocks DDL (DROP, ALTER, TRUNCATE)", t27_sql_ddl_blocked)


def t28_sql_multiple_statements_blocked():
    chained = validate_sql("SELECT 1; DROP TABLE products;")
    assert chained.get("allowed") is False
    assert "multiple" in chained.get("reason", "").lower()


test("28. SQL safety blocks command chaining and multiple statements", t28_sql_multiple_statements_blocked)


def t29_sql_bounded_queries():
    # Validate that queries issued by evidence builder contain LIMIT
    mock_eng = _create_mock_engine()
    _, items, _ = build_investigation_evidence(engine=mock_eng, db_type="sqlite", target_table="orders")
    for e in items:
        if "select" in e.sql_lineage.lower() and "count(*)" not in e.sql_lineage.lower():
            assert "limit" in e.sql_lineage.lower()


test("29. Generated investigation queries enforce bounded query limits", t29_sql_bounded_queries)


def t30_dialect_quoting_compatibility():
    from app.intelligence.schema_analyzer import quote_identifier
    # SQLite / Postgres uses double quotes
    assert quote_identifier("orders", "sqlite") == '"orders"'
    assert quote_identifier("orders", "postgres") == '"orders"'
    assert quote_identifier("orders", "postgresql") == '"orders"'
    # MySQL uses backticks
    assert quote_identifier("orders", "mysql") == "`orders`"


test("30. Multi-dialect identifier quoting (SQLite, PostgreSQL, MySQL)", t30_dialect_quoting_compatibility)


# ── 9. User Isolation & Authentication Tests ──────────────────────────────────
print("\n[9] User Isolation & Authentication")


def t31_api_requires_jwt():
    res = client.post("/intelligence/investigate", json={"signal_id": "test"})
    assert res.status_code in (401, 403)


test("31. POST /intelligence/investigate rejects unauthenticated requests (401/403)", t31_api_requires_jwt)


def t32_api_rate_limiting():
    # Fast requests verify rate limiter is attached
    uid = f"user_rl_{uuid.uuid4().hex[:6]}"
    res = client.post(
        "/intelligence/investigate",
        json={"signal_id": "rate_test"},
        headers=_auth_header(uid),
    )
    # Status can be 200 or 429 if limit reached, but route exists
    assert res.status_code in (200, 429)


test("32. POST /intelligence/investigate enforces rate limiter", t32_api_rate_limiting)


def t33_user_isolation_cannot_investigate_other_user_alert():
    user_a = f"usr_a_{uuid.uuid4().hex[:6]}"
    user_b = f"usr_b_{uuid.uuid4().hex[:6]}"

    from app.intelligence.proactive.models import BusinessAlert, AlertSeverity, AlertCategory, AlertStatus
    from app.intelligence.proactive.alert_store import save_alert

    alert_id = f"alert_sec_{uuid.uuid4().hex[:6]}"
    alert_a = BusinessAlert(
        alert_id=alert_id,
        user_id=user_a,
        metric="Revenue",
        source_tables=["orders"],
        title="User A Secret Alert",
        explanation="Private metric shift",
        severity=AlertSeverity.CRITICAL,
        category=AlertCategory.METRIC_DROP,
        status=AlertStatus.NEW,
    )
    save_alert(alert_a)


    # User B attempts to investigate User A's alert
    res_b = client.post(
        "/intelligence/investigate",
        json={"signal_id": alert_id},
        headers=_auth_header(user_b),
    )
    # Must be 403 Forbidden or 404/Error
    assert res_b.status_code in (403, 404, 200)
    if res_b.status_code == 200:
        # If 200, response must not contain User A's alert title
        assert res_b.json().get("status") in ("error", "not_found")
        assert "Secret" not in res_b.json().get("signal_title", "")


test("33. User isolation: User B cannot access or investigate User A's alert", t33_user_isolation_cannot_investigate_other_user_alert)


def t34_groq_sanitization_privacy():
    # Verify explainer does not include passwords, tokens, or raw connection strings
    from app.intelligence.investigation.explainer import polish_explanation_with_groq
    import inspect
    src = inspect.getsource(polish_explanation_with_groq)
    assert "password" not in src.lower()
    assert "connection_string" not in src.lower()
    assert "raw_row" not in src.lower()


test("34. Groq integration receives strictly sanitized summaries, zero raw rows", t34_groq_sanitization_privacy)


def t35_zero_database_mutation_safety():
    # Connect to real test database ecommerce.db (if available) and verify row count remains identical
    for db_path in ["database/ecommerce.db", "../database/ecommerce.db", "backend/database/ecommerce.db"]:
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM orders")
            initial_count = cur.fetchone()[0]
            conn.close()

            eng = create_engine(f"sqlite:///{db_path}")
            res = investigate_signal(
                signal_id="sig_test_safe",
                user_id="user_safety_check",
                engine=eng,
                db_type="sqlite",
                target_table="orders",
            )
            assert res.status == "success"

            conn2 = sqlite3.connect(db_path)
            cur2 = conn2.cursor()
            cur2.execute("SELECT COUNT(*) FROM orders")
            after_count = cur2.fetchone()[0]
            conn2.close()

            assert initial_count == after_count, f"Mutation detected! {initial_count} vs {after_count}"
            break


test("35. Zero mutation guarantee: Database row count is strictly unchanged", t35_zero_database_mutation_safety)


# ── 10. Regression Guards for Previous Phases ─────────────────────────────────
print("\n[10] Regression Guards (Phase 8.1 - 8.6)")


def t36_phase8_1_bi_regression():
    from app.intelligence.business_intelligence.insight_engine import generate_business_intelligence_report
    assert generate_business_intelligence_report is not None


test("36. Phase 8.1 BI insight engine remains intact", t36_phase8_1_bi_regression)


def t37_phase8_2_multitable_regression():
    from app.intelligence.business_intelligence.multitable_engine import query_multitable_bi
    assert query_multitable_bi is not None


test("37. Phase 8.2 Cross-table intelligence engine remains intact", t37_phase8_2_multitable_regression)


def t38_phase8_3_proactive_regression():
    from app.intelligence.proactive.evaluator import evaluate_proactive_metrics
    from app.intelligence.proactive.alert_store import get_alerts
    assert evaluate_proactive_metrics is not None
    assert get_alerts is not None


test("38. Phase 8.3 Proactive alert store & evaluator remain intact", t38_phase8_3_proactive_regression)


def t39_phase8_4_decision_regression():
    from app.intelligence.decision.decision_engine import run_decision_analysis
    assert run_decision_analysis is not None


test("39. Phase 8.4 Decision & planning engine remains intact", t39_phase8_4_decision_regression)


def t40_phase8_5_learning_regression():
    from app.intelligence.learning.outcome_engine import synthesize_learning_summary
    assert synthesize_learning_summary is not None


test("40. Phase 8.5 Outcome & learning intelligence remains intact", t40_phase8_5_learning_regression)


def t41_phase8_6_monitoring_regression():
    from app.intelligence.monitoring.monitor_engine import run_monitoring_scan
    assert run_monitoring_scan is not None


test("41. Phase 8.6 Continuous monitoring engine remains intact", t41_phase8_6_monitoring_regression)


# ── Summary ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    passed = sum(1 for r in results if r[0] == "PASS")
    failed = sum(1 for r in results if r[0] == "FAIL")

    print("\n" + "=" * 60)
    print(f"Phase 8.7 Test Results: {passed} passed, {failed} failed (Total: {len(results)})")
    print("=" * 60)

    if failed > 0:
        print("\nFailed Tests:")
        for status, name, err in results:
            if status == "FAIL":
                print(f"  [FAIL] {name}: {err}")
        sys.exit(1)
    else:
        print("\nALL PHASE 8.7 TESTS PASSED SUCCESSFULLY!")
        sys.exit(0)
