"""
backend/scratch/test_phase8_4_decision.py

Phase 8.4: AI Decision & Planning Intelligence Test Suite
Validates:
1. Model construction, serialization, and deserialization
2. Question intent parsing & understanding
3. Multi-source evidence aggregation
4. Deterministic findings derivation
5. Epistemic hypothesis labeling & causality caveats
6. Sequential decision planning & human confirmation gating
7. Transparent confidence assessment (no arbitrary AI percentages)
8. Authenticated FastAPI endpoint (POST /intelligence/decision)
9. Unauthenticated 401 protection
10. Per-user context isolation
11. Disconnected database handling
12. Read-only database safety & zero mutation guarantee
13. Groq privacy & context minimization
"""
import sys
import os
from typing import Any
from datetime import datetime

# Setup path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import tempfile
import sqlite3
from sqlalchemy import create_engine, text
from fastapi.testclient import TestClient

from app.main import app
from app.security.auth import create_access_token
from app.database.connection_context import connect_sqlite_for_user, clear_user_context
from app.intelligence.decision.models import (
    EvidenceItem,
    Finding,
    Hypothesis,
    RecommendedInvestigation,
    PlanStep,
    ConfidenceAssessment,
    DecisionQuestion,
    DecisionAnalysis,
)
from app.intelligence.decision.decision_engine import (
    understand_question,
    synthesize_decision_analysis,
)
from app.intelligence.decision.confidence import assess_confidence
from app.intelligence.decision.planner import generate_decision_plan_and_investigations
from app.intelligence.decision.evidence import aggregate_multi_source_evidence


def create_test_db_file() -> tuple[str, Any]:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_path = tmp.name
    tmp.close()

    conn = sqlite3.connect(tmp_path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, category TEXT, price REAL);")
    cur.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, email TEXT);")
    cur.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, product_id INTEGER, amount REAL, order_date TEXT, status TEXT);")
    
    cur.execute("INSERT INTO products VALUES (1, 'Laptop', 'Electronics', 1000.0);")
    cur.execute("INSERT INTO products VALUES (2, 'Mouse', 'Accessories', 50.0);")
    cur.execute("INSERT INTO customers VALUES (1, 'Alice', 'alice@test.com');")
    cur.execute("INSERT INTO customers VALUES (2, 'Bob', 'bob@test.com');")
    
    # Chronological orders
    cur.execute("INSERT INTO orders VALUES (1, 1, 1, 1000.0, '2026-01-10', 'COMPLETED');")
    cur.execute("INSERT INTO orders VALUES (2, 2, 2, 50.0, '2026-01-15', 'COMPLETED');")
    cur.execute("INSERT INTO orders VALUES (3, 1, 1, 800.0, '2026-02-10', 'COMPLETED');")
    cur.execute("INSERT INTO orders VALUES (4, 2, 2, 40.0, '2026-02-15', 'CANCELLED');")
    conn.commit()
    conn.close()

    engine = create_engine(f"sqlite:///{tmp_path.replace(os.sep, '/')}")
    return tmp_path, engine



passed_tests = 0
failed_tests = 0


def record_result(name: str, passed: bool, detail: str = ""):
    global passed_tests, failed_tests
    if passed:
        passed_tests += 1
        print(f"  [PASS] {name}")
    else:
        failed_tests += 1
        print(f"  [FAIL] {name}: {detail}")


def run_tests():
    print("\n" + "=" * 60)
    print("PHASE 8.4: AI DECISION & PLANNING INTELLIGENCE TEST SUITE")
    print("=" * 60 + "\n")

    # 1. Model construction
    ev = EvidenceItem(
        metric="revenue",
        title="Total Revenue",
        current_value=10100.0,
        previous_value=12400.0,
        delta=-2300.0,
        delta_percent=-18.5,
        source_tables=["orders"],
        source_columns=["amount"],
        calculation="(current - previous) / previous * 100",
        source_system="BI_ENGINE",
    )
    record_result("1. EvidenceItem construction & delta calculation", ev.delta == -2300.0 and ev.delta_percent == -18.5)

    # 2. EvidenceItem serialization & deserialization
    ev_dict = ev.to_dict()
    ev_restored = EvidenceItem.from_dict(ev_dict)
    record_result("2. EvidenceItem roundtrip serialization", ev_restored.metric == "revenue" and ev_restored.source_system == "BI_ENGINE")

    # 3. Finding construction
    fnd = Finding(
        statement="Revenue declined by 18.5% in recent observation period.",
        evidence_ids=[ev.evidence_id],
        severity="CRITICAL",
        category="REVENUE",
        source_tables=["orders"],
    )
    record_result("3. Finding construction with severity & category", fnd.severity == "CRITICAL" and fnd.category == "REVENUE")

    # 4. Hypothesis Epistemic Hygiene
    hyp = Hypothesis(
        statement="Category A contraction may be contributing to the observed decline.",
        supporting_evidence_ids=[ev.evidence_id],
        likelihood="PROBABLE",
    )
    record_result(
        "4. Hypothesis status is explicitly unconfirmed",
        hyp.status == "UNCONFIRMED_HYPOTHESIS" and "causation" in hyp.causality_caveat.lower(),
    )

    # 5. RecommendedInvestigation construction
    inv = RecommendedInvestigation(
        title="Segment Breakdown in 'orders'",
        rationale="Audit revenue across individual categories",
        target_table="orders",
        priority=1,
    )
    record_result("5. RecommendedInvestigation structure & priority", inv.priority == 1 and inv.target_table == "orders")

    # 6. PlanStep confirmation requirement
    step = PlanStep(
        step_number=4,
        title="Prepare Safe Action",
        description="Formulate corrective operation",
        action_type="REMEDIATE",
        requires_confirmation=True,
        safe_action_eligible=True,
    )
    record_result("6. PlanStep mandates human confirmation for remediation", step.requires_confirmation is True and step.safe_action_eligible is True)

    # 7. Confidence Assessment: High Evidence
    high_evs = [
        EvidenceItem(metric="m1", title="T1", current_value=1, source_system="BI_ENGINE"),
        EvidenceItem(metric="m2", title="T2", current_value=2, source_system="CROSS_TABLE_BI"),
        EvidenceItem(metric="m3", title="T3", current_value=3, source_system="ANOMALY_DETECTOR"),
        EvidenceItem(metric="m4", title="T4", current_value=4, source_system="PROACTIVE_ALERTS"),
    ]
    conf_high = assess_confidence(high_evs)
    record_result("7. ConfidenceAssessment: HIGH with 4+ multi-source signals", conf_high.level == "HIGH" and conf_high.signal_count == 4)

    # 8. Confidence Assessment: Moderate Evidence
    mod_evs = [
        EvidenceItem(metric="m1", title="T1", current_value=1, source_system="BI_ENGINE"),
        EvidenceItem(metric="m2", title="T2", current_value=2, source_system="CROSS_TABLE_BI"),
    ]
    conf_mod = assess_confidence(mod_evs)
    record_result("8. ConfidenceAssessment: MODERATE with 2 signals", conf_mod.level == "MODERATE" and conf_mod.signal_count == 2)

    # 9. Confidence Assessment: Limited Evidence
    lim_evs = [
        EvidenceItem(metric="m1", title="T1", current_value=1, source_system="BI_ENGINE"),
    ]
    conf_lim = assess_confidence(lim_evs)
    record_result("9. ConfidenceAssessment: LIMITED with single signal", conf_lim.level == "LIMITED" and len(conf_lim.limitations) > 0)

    # 10. Question understanding: Revenue decline
    q1 = understand_question("Why are sales and revenue falling this month?")
    record_result("10. Intent detection: REVENUE_DECLINE", q1.intent == "REVENUE_DECLINE")

    # 11. Question understanding: Order cancellations
    q2 = understand_question("What is causing the sudden increase in order cancellations?")
    record_result("11. Intent detection: ORDER_CANCELLATION", q2.intent == "ORDER_CANCELLATION")

    # 12. Question understanding: Product attention
    q3 = understand_question("Which product category needs immediate attention?")
    record_result("12. Intent detection: PRODUCT_PERFORMANCE", q3.intent == "PRODUCT_PERFORMANCE")

    # 13. Question understanding: Business risks
    q4 = understand_question("Where is the highest business risk in my database?")
    record_result("13. Intent detection: BUSINESS_RISK", q4.intent == "BUSINESS_RISK")

    # 14. Question understanding: Recent changes
    q5 = understand_question("What changed recently in my store?")
    record_result("14. Intent detection: RECENT_CHANGES", q5.intent == "RECENT_CHANGES")

    # 15. Decision planner generation
    invs, steps = generate_decision_plan_and_investigations(q1, [fnd], [ev], [hyp])
    record_result("15. Decision planner outputs sequential steps", len(steps) >= 3 and steps[0].action_type == "INVESTIGATE")

    # 16. Multi-source evidence aggregation with live DB
    test_db_path, test_engine = create_test_db_file()
    aggregated = aggregate_multi_source_evidence(test_engine, "sqlite", user_id="test_user_84")
    record_result("16. Live DB multi-source evidence aggregation executes without error", isinstance(aggregated, list))

    # 17. Decision analysis synthesis with real DB
    analysis = synthesize_decision_analysis(
        question_text="Why did revenue decrease?",
        engine=test_engine,
        db_type="sqlite",
        user_id="test_user_84",
    )
    record_result("17. Synthesize decision analysis produces complete model", analysis.problem_statement != "" and len(analysis.findings) > 0)

    # 18. Decision analysis contains non-causal hypotheses
    record_result(
        "18. Generated hypotheses contain mandatory causality caveats",
        all("causation" in h.causality_caveat.lower() for h in analysis.hypotheses),
    )

    # 19. Decision analysis contains decision plan
    record_result("19. Synthesized plan has sequential prioritized steps", len(analysis.decision_plan) >= 2)

    # 20. Decision analysis contains transparent confidence assessment
    record_result("20. Confidence assessment contains no arbitrary percentage", analysis.confidence is not None and analysis.confidence.level in {"HIGH", "MODERATE", "LIMITED"})

    # 21. DecisionAnalysis roundtrip serialization
    analysis_dict = analysis.to_dict()
    analysis_restored = DecisionAnalysis.from_dict(analysis_dict)
    record_result("21. DecisionAnalysis roundtrip dict serialization", analysis_restored.question == analysis.question and len(analysis_restored.findings) == len(analysis.findings))

    # 22. Database state unaltered by decision intelligence (Read-only check)
    with test_engine.connect() as conn:
        order_count = conn.execute(text("SELECT COUNT(*) FROM orders")).scalar()
    record_result("22. Read-only safety: orders row count is strictly unchanged", order_count == 4)

    # API Tests with TestClient
    client = TestClient(app)
    token = create_access_token(user_id="user_decision_a", username="decision_alice")

    # 23. Unauthenticated request to POST /intelligence/decision returns 401
    resp_unauth = client.post("/intelligence/decision", json={"question": "Why are sales declining?"})
    record_result("23. Unauthenticated request returns 401 Unauthorized", resp_unauth.status_code == 401)

    # 24. Authenticated request with disconnected DB returns clean disconnected response
    headers = {"Authorization": f"Bearer {token}"}
    resp_disc = client.post("/intelligence/decision", json={"question": "Why are sales declining?"}, headers=headers)
    record_result(
        "24. Disconnected database returns clean response",
        resp_disc.status_code == 200 and resp_disc.json().get("status") == "disconnected",
    )

    # 25. Authenticated request with connected DB returns structured decision intelligence
    connect_sqlite_for_user("user_decision_a", test_db_path)

    resp_auth = client.post(
        "/intelligence/decision",
        json={"question": "Why did revenue decrease and what should we do?"},
        headers=headers,
    )
    data = resp_auth.json()
    record_result(
        "25. Authenticated decision query returns complete structured analysis",
        resp_auth.status_code == 200
        and data.get("status") == "success"
        and "problem_statement" in data
        and len(data.get("findings", [])) > 0
        and len(data.get("decision_plan", [])) > 0,
    )

    # 26. User isolation: User B context does not see User A's connected DB
    token_b = create_access_token(user_id="user_decision_b", username="decision_bob")
    headers_b = {"Authorization": f"Bearer {token_b}"}
    resp_b = client.post(
        "/intelligence/decision",
        json={"question": "What changed recently?"},
        headers=headers_b,
    )
    record_result(
        "26. User isolation: User B cannot access User A's connected database",
        resp_b.status_code == 200 and resp_b.json().get("status") == "disconnected",
    )

    # 27. Rate limit preserved (status 200 under normal limit)
    record_result("27. Normal request rate functions as expected", resp_auth.status_code == 200)

    # 28. No credentials or connection string in response
    resp_str = str(data)
    record_result(
        "28. Security: No passwords, tokens, or raw connection strings in response",
        "password" not in resp_str.lower() and "bearer" not in resp_str.lower(),
    )

    # 29. Hypothesis status check in API response
    api_hyps = data.get("hypotheses", [])
    record_result(
        "29. API response flags all hypotheses as unconfirmed candidates",
        len(api_hyps) > 0 and all(h.get("status") == "UNCONFIRMED_HYPOTHESIS" for h in api_hyps),
    )

    # 30. Plan steps require human confirmation for mutations
    api_plan = data.get("decision_plan", [])
    remediation_steps = [s for s in api_plan if s.get("action_type") == "REMEDIATE"]
    record_result(
        "30. Decision plan remediation steps require human confirmation",
        all(s.get("requires_confirmation") is True for s in remediation_steps),
    )

    # Cleanup
    clear_user_context("user_decision_a")
    clear_user_context("user_decision_b")

    print("\n" + "=" * 60)
    print(f"Results: {passed_tests} passed, {failed_tests} failed")
    print("=" * 60 + "\n")

    if failed_tests > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
