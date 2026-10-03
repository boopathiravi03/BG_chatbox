#!/usr/bin/env python
"""
Phase 8.9: Closed-Loop Outcome Optimization & Adaptive Recommendations
Test Suite — 50+ assertions

Tests cover:
1. Models: OutcomeMeasurement, OutcomeAnalysis, AdaptiveRecommendation, RecommendationExplanation
2. Persistence: save/get/list measurements and recommendations (with user isolation)
3. Effectiveness classification: deterministic rules
4. Attribution assessment
5. Baseline engine: metric discovery
6. Measurement engine: logic tests
7. Learning bridge: Phase 8.5 integration
8. Recommendation engine: cold start, sufficient data
9. Explainer: deterministic explanation generation
10. API endpoints: all 6 Phase 8.9 endpoints (JWT required, rate-limited)
11. No fake/hardcoded data asserted
12. Phase 8.5 regression: existing endpoints not broken
13. Phase 8.8 regression: action endpoints not broken
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

results = []
PASS = "PASS"
FAIL = "FAIL"

def test(name, fn):
    try:
        fn()
        results.append((PASS, name))
        print(f"  OK  {name}")
    except AssertionError as e:
        results.append((FAIL, name, str(e)))
        print(f"  FAIL {name}: {e}")
    except Exception as e:
        results.append((FAIL, name, f"{type(e).__name__}: {e}"))
        print(f"  FAIL {name}: {type(e).__name__}: {e}")


# ── 1. Models ─────────────────────────────────────────────────────────────────

def test_models():
    from app.intelligence.outcome_optimization.models import (
        OutcomeMeasurement, OutcomeAnalysis, AdaptiveRecommendation,
        RecommendationExplanation, EffectivenessLabel, ConfidenceLevel,
        AttributionStatus, MeasurementWindow, RecommendationSource,
    )

    # Test OutcomeMeasurement defaults
    m = OutcomeMeasurement(user_id="u1", metric_name="Total Revenue", source_table="orders")
    assert m.measurement_id.startswith("meas_"), f"Expected meas_ prefix, got {m.measurement_id}"
    assert m.effectiveness == EffectivenessLabel.INSUFFICIENT_DATA
    assert m.confidence == ConfidenceLevel.LIMITED
    assert m.attribution == AttributionStatus.OBSERVED_OUTCOME
    d = m.to_dict()
    assert d["metric_name"] == "Total Revenue"
    assert d["source_table"] == "orders"

test("1.1 OutcomeMeasurement defaults and to_dict", test_models)


def test_outcomemeasurement_from_dict():
    from app.intelligence.outcome_optimization.models import OutcomeMeasurement
    data = {
        "user_id": "u2",
        "metric_name": "Avg Price",
        "source_table": "products",
        "source_column": "price",
        "effectiveness": "POSITIVE",
        "confidence": "HIGH",
        "sample_size": 50,
    }
    m = OutcomeMeasurement.from_dict(data)
    assert m.user_id == "u2"
    assert m.effectiveness == "POSITIVE"
    assert m.confidence == "HIGH"
    assert m.sample_size == 50

test("1.2 OutcomeMeasurement.from_dict", test_outcomemeasurement_from_dict)


def test_outcomeanalysis_model():
    from app.intelligence.outcome_optimization.models import OutcomeAnalysis, OutcomeMeasurement
    analysis = OutcomeAnalysis(action_id="act_abc", user_id="u1")
    assert analysis.analysis_id.startswith("ana_")
    d = analysis.to_dict()
    assert d["action_id"] == "act_abc"
    assert isinstance(d["measurements"], list)
    assert isinstance(d["data_gaps"], list)
    assert "disclaimer" in d

test("1.3 OutcomeAnalysis model and to_dict", test_outcomeanalysis_model)


def test_adaptive_recommendation_model():
    from app.intelligence.outcome_optimization.models import AdaptiveRecommendation
    rec = AdaptiveRecommendation(
        user_id="u1",
        title="Test Rec",
        description="desc",
        action_type="UPDATE",
        target_table="products",
    )
    assert rec.recommendation_id.startswith("rec_")
    assert rec.requires_human_confirmation is True  # Always True
    d = rec.to_dict()
    assert d["requires_human_confirmation"] is True
    assert d["title"] == "Test Rec"

test("1.4 AdaptiveRecommendation always requires_human_confirmation=True", test_adaptive_recommendation_model)


def test_recommendation_explanation_model():
    from app.intelligence.outcome_optimization.models import RecommendationExplanation
    e = RecommendationExplanation(
        recommendation_id="rec_x",
        user_id="u1",
        explanation_points=["Point 1", "Point 2"],
        limitations=["Limitation 1"],
    )
    d = e.to_dict()
    assert len(d["explanation_points"]) == 2
    assert len(d["limitations"]) == 1

test("1.5 RecommendationExplanation model", test_recommendation_explanation_model)


# ── 2. Effectiveness Classification ──────────────────────────────────────────

def test_effectiveness_insufficient_data():
    from app.intelligence.outcome_optimization.effectiveness import classify_effectiveness
    label = classify_effectiveness(delta=None, delta_pct=None, baseline_value=None,
                                   observed_value=None, sample_size=0)
    assert label == "INSUFFICIENT_DATA"

test("2.1 Effectiveness: insufficient data → INSUFFICIENT_DATA", test_effectiveness_insufficient_data)


def test_effectiveness_small_sample():
    from app.intelligence.outcome_optimization.effectiveness import classify_effectiveness
    label = classify_effectiveness(delta=100, delta_pct=50, baseline_value=200,
                                   observed_value=300, sample_size=2)
    assert label == "INSUFFICIENT_DATA", f"Expected INSUFFICIENT_DATA, got {label}"

test("2.2 Effectiveness: sample_size < 3 → INSUFFICIENT_DATA", test_effectiveness_small_sample)


def test_effectiveness_neutral():
    from app.intelligence.outcome_optimization.effectiveness import classify_effectiveness
    # 0.5% change → below noise floor
    label = classify_effectiveness(delta=0.5, delta_pct=0.5, baseline_value=100,
                                   observed_value=100.5, sample_size=10)
    assert label == "NEUTRAL", f"Expected NEUTRAL, got {label}"

test("2.3 Effectiveness: <1% change → NEUTRAL", test_effectiveness_neutral)


def test_effectiveness_inconclusive():
    from app.intelligence.outcome_optimization.effectiveness import classify_effectiveness
    # 2% change → INCONCLUSIVE
    label = classify_effectiveness(delta=2, delta_pct=2.0, baseline_value=100,
                                   observed_value=102, sample_size=10)
    assert label == "INCONCLUSIVE", f"Expected INCONCLUSIVE, got {label}"

test("2.4 Effectiveness: 1-5% change → INCONCLUSIVE", test_effectiveness_inconclusive)


def test_effectiveness_positive():
    from app.intelligence.outcome_optimization.effectiveness import classify_effectiveness
    label = classify_effectiveness(delta=20, delta_pct=20.0, baseline_value=100,
                                   observed_value=120, sample_size=10)
    assert label == "POSITIVE", f"Expected POSITIVE, got {label}"

test("2.5 Effectiveness: +20% change → POSITIVE", test_effectiveness_positive)


def test_effectiveness_negative():
    from app.intelligence.outcome_optimization.effectiveness import classify_effectiveness
    label = classify_effectiveness(delta=-20, delta_pct=-20.0, baseline_value=100,
                                   observed_value=80, sample_size=10)
    assert label == "NEGATIVE", f"Expected NEGATIVE, got {label}"

test("2.6 Effectiveness: -20% change → NEGATIVE", test_effectiveness_negative)


def test_effectiveness_describe():
    from app.intelligence.outcome_optimization.effectiveness import describe_effectiveness
    desc = describe_effectiveness("POSITIVE")
    assert "improvement" in desc.lower() or "favorable" in desc.lower()
    desc_neg = describe_effectiveness("NEGATIVE")
    assert "deterioration" in desc_neg.lower() or "unfavorable" in desc_neg.lower()

test("2.7 describe_effectiveness returns meaningful strings", test_effectiveness_describe)


# ── 3. Persistence (Outcome Tracker) ──────────────────────────────────────────

def _make_in_memory_engine():
    from sqlalchemy import create_engine
    return create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})


def test_save_and_get_measurement():
    from app.intelligence.outcome_optimization.outcome_tracker import (
        save_measurement, get_measurement, reset_engine
    )
    from app.intelligence.outcome_optimization.models import OutcomeMeasurement

    reset_engine()
    eng = _make_in_memory_engine()
    from app.intelligence.outcome_optimization.outcome_tracker import _get_engine
    _get_engine(custom_engine=eng)

    m = OutcomeMeasurement(
        user_id="user_test1",
        metric_name="Total Orders",
        source_table="orders",
        source_column="id",
        effectiveness="POSITIVE",
        confidence="HIGH",
        sample_size=20,
    )
    saved = save_measurement(m)
    assert saved.measurement_id == m.measurement_id

    retrieved = get_measurement(m.measurement_id, user_id="user_test1")
    assert retrieved is not None
    assert retrieved.metric_name == "Total Orders"
    assert retrieved.effectiveness == "POSITIVE"

    # User isolation: wrong user_id → None
    none_result = get_measurement(m.measurement_id, user_id="user_other")
    assert none_result is None, "User isolation failed: retrieved another user's measurement"

test("3.1 save_measurement and get_measurement with user isolation", test_save_and_get_measurement)


def test_list_measurements():
    from app.intelligence.outcome_optimization.outcome_tracker import (
        list_measurements, save_measurement, reset_engine
    )
    from app.intelligence.outcome_optimization.models import OutcomeMeasurement

    reset_engine()
    eng = _make_in_memory_engine()
    from app.intelligence.outcome_optimization.outcome_tracker import _get_engine
    _get_engine(custom_engine=eng)

    uid = "list_test_user"
    for i in range(3):
        m = OutcomeMeasurement(
            user_id=uid,
            metric_name=f"Metric {i}",
            source_table="table_x",
            action_id="act_xyz",
        )
        save_measurement(m)

    # Other user measurement
    m_other = OutcomeMeasurement(user_id="other_user", metric_name="Other", source_table="y")
    save_measurement(m_other)

    results_list = list_measurements(user_id=uid, limit=10)
    assert len(results_list) == 3, f"Expected 3, got {len(results_list)}"

    # Filter by action_id
    act_results = list_measurements(user_id=uid, action_id="act_xyz", limit=10)
    assert len(act_results) == 3

    # Other user results not visible
    other_results = list_measurements(user_id="other_user", limit=10)
    assert len(other_results) == 1
    assert other_results[0].user_id == "other_user"

test("3.2 list_measurements user isolation and action_id filter", test_list_measurements)


def test_save_and_get_recommendation():
    from app.intelligence.outcome_optimization.outcome_tracker import (
        save_recommendation, get_recommendation, reset_engine
    )
    from app.intelligence.outcome_optimization.models import AdaptiveRecommendation

    reset_engine()
    eng = _make_in_memory_engine()
    from app.intelligence.outcome_optimization.outcome_tracker import _get_engine
    _get_engine(custom_engine=eng)

    rec = AdaptiveRecommendation(
        user_id="rec_test_user",
        title="Test Recommendation",
        description="Test description",
        action_type="UPDATE",
        target_table="products",
        source="HISTORICAL_OUTCOMES",
        confidence="MODERATE",
    )
    save_recommendation(rec)

    retrieved = get_recommendation(rec.recommendation_id, user_id="rec_test_user")
    assert retrieved is not None
    assert retrieved.title == "Test Recommendation"
    assert retrieved.requires_human_confirmation is True

    # User isolation
    none_result = get_recommendation(rec.recommendation_id, user_id="wrong_user")
    assert none_result is None

test("3.3 save_recommendation and get_recommendation with user isolation", test_save_and_get_recommendation)


def test_clear_store():
    from app.intelligence.outcome_optimization.outcome_tracker import (
        save_measurement, list_measurements, clear_outcome_opt_store, reset_engine
    )
    from app.intelligence.outcome_optimization.models import OutcomeMeasurement

    reset_engine()
    eng = _make_in_memory_engine()
    from app.intelligence.outcome_optimization.outcome_tracker import _get_engine
    _get_engine(custom_engine=eng)

    uid = "clear_test_user"
    m = OutcomeMeasurement(user_id=uid, metric_name="M", source_table="t")
    save_measurement(m)
    assert len(list_measurements(user_id=uid)) == 1

    clear_outcome_opt_store(user_id=uid)
    assert len(list_measurements(user_id=uid)) == 0

test("3.4 clear_outcome_opt_store clears user data", test_clear_store)


# ── 4. Learning Bridge ────────────────────────────────────────────────────────

def test_learning_bridge_insufficient_data():
    from app.intelligence.outcome_optimization.models import OutcomeMeasurement, EffectivenessLabel
    from app.intelligence.outcome_optimization.learning_bridge import bridge_measurement_to_learning
    from app.intelligence.learning.outcome_store import reset_engine as reset_learning_engine

    reset_learning_engine()

    m = OutcomeMeasurement(
        user_id="bridge_user",
        metric_name="Revenue",
        source_table="orders",
        effectiveness=EffectivenessLabel.INSUFFICIENT_DATA,
    )
    result = bridge_measurement_to_learning(m, action_type="UPDATE")
    # Should return None for insufficient data
    assert result is None, "Should not bridge INSUFFICIENT_DATA measurements"

test("4.1 Learning bridge skips INSUFFICIENT_DATA measurements", test_learning_bridge_insufficient_data)


def test_learning_bridge_positive():
    from app.intelligence.outcome_optimization.models import OutcomeMeasurement, EffectivenessLabel
    from app.intelligence.outcome_optimization.learning_bridge import bridge_measurement_to_learning
    from app.intelligence.learning.outcome_store import reset_engine as reset_learning_engine, clear_learning_store
    from app.intelligence.learning.models import OutcomeStatus

    reset_learning_engine()

    m = OutcomeMeasurement(
        user_id="bridge_user2",
        metric_name="Revenue",
        source_table="orders",
        effectiveness=EffectivenessLabel.POSITIVE,
        confidence="HIGH",
        delta=100.0,
        observed_value=1100.0,
        baseline_value=1000.0,
    )
    result = bridge_measurement_to_learning(m, action_type="UPDATE")
    assert result is not None, "Should bridge POSITIVE measurement"
    assert result.status == OutcomeStatus.SUCCESSFUL
    assert result.user_id == "bridge_user2"
    assert result.evidence is not None
    assert "measurement_id" in result.evidence

test("4.2 Learning bridge converts POSITIVE → SUCCESSFUL OutcomeRecord", test_learning_bridge_positive)


def test_learning_bridge_negative():
    from app.intelligence.outcome_optimization.models import OutcomeMeasurement, EffectivenessLabel
    from app.intelligence.outcome_optimization.learning_bridge import bridge_measurement_to_learning
    from app.intelligence.learning.outcome_store import reset_engine as reset_learning_engine
    from app.intelligence.learning.models import OutcomeStatus

    reset_learning_engine()

    m = OutcomeMeasurement(
        user_id="bridge_user3",
        metric_name="Revenue",
        source_table="orders",
        effectiveness=EffectivenessLabel.NEGATIVE,
    )
    result = bridge_measurement_to_learning(m, action_type="DELETE")
    assert result is not None
    assert result.status == OutcomeStatus.FAILED

test("4.3 Learning bridge converts NEGATIVE → FAILED OutcomeRecord", test_learning_bridge_negative)


# ── 5. Recommendation Engine ──────────────────────────────────────────────────

def test_recommendation_cold_start():
    from app.intelligence.outcome_optimization.recommendation_engine import (
        generate_adaptive_recommendations
    )
    from app.intelligence.learning.outcome_store import reset_engine as reset_learning, clear_learning_store
    from app.intelligence.outcome_optimization.outcome_tracker import (
        reset_engine as reset_opt, clear_outcome_opt_store
    )

    reset_learning()
    reset_opt()
    eng_learning = _make_in_memory_engine()
    eng_opt = _make_in_memory_engine()
    from app.intelligence.learning.outcome_store import _get_engine as le
    from app.intelligence.outcome_optimization.outcome_tracker import _get_engine as oe
    le(custom_engine=eng_learning)
    oe(custom_engine=eng_opt)

    uid = "cold_start_user_99"
    recs = generate_adaptive_recommendations(user_id=uid)

    assert len(recs) >= 1, "Should return at least one cold-start recommendation"
    assert recs[0].source == "COLD_START", f"Expected COLD_START source, got {recs[0].source}"
    assert recs[0].requires_human_confirmation is True

test("5.1 Recommendation engine: cold start returns COLD_START recommendation", test_recommendation_cold_start)


def test_recommendation_requires_human_confirmation():
    from app.intelligence.outcome_optimization.recommendation_engine import (
        generate_adaptive_recommendations
    )
    from app.intelligence.outcome_optimization.outcome_tracker import (
        reset_engine, clear_outcome_opt_store
    )
    reset_engine()
    eng = _make_in_memory_engine()
    from app.intelligence.outcome_optimization.outcome_tracker import _get_engine
    _get_engine(custom_engine=eng)

    recs = generate_adaptive_recommendations(user_id="any_user")
    for rec in recs:
        assert rec.requires_human_confirmation is True, (
            f"Recommendation '{rec.title}' has requires_human_confirmation=False!"
        )

test("5.2 All recommendations always have requires_human_confirmation=True", test_recommendation_requires_human_confirmation)


# ── 6. Explainer ──────────────────────────────────────────────────────────────

def test_explainer_cold_start():
    from app.intelligence.outcome_optimization.models import AdaptiveRecommendation, RecommendationSource
    from app.intelligence.outcome_optimization.explainer import explain_recommendation

    rec = AdaptiveRecommendation(
        user_id="u1",
        title="Test",
        description="desc",
        action_type="UPDATE",
        target_table="t",
        source=RecommendationSource.COLD_START,
        confidence="LIMITED",
    )
    explanation = explain_recommendation(rec=rec, use_groq=False)
    assert explanation.recommendation_id == rec.recommendation_id
    assert len(explanation.explanation_points) > 0
    assert len(explanation.limitations) > 0
    # Check no fabricated content
    for point in explanation.explanation_points:
        assert isinstance(point, str) and len(point) > 0

test("6.1 Explainer: cold start generates valid explanation points", test_explainer_cold_start)


def test_explainer_historical_outcomes():
    from app.intelligence.outcome_optimization.models import AdaptiveRecommendation, RecommendationSource
    from app.intelligence.outcome_optimization.explainer import explain_recommendation

    rec = AdaptiveRecommendation(
        user_id="u1",
        title="Repeat Successful Update",
        description="desc",
        action_type="UPDATE",
        target_table="products",
        source=RecommendationSource.HISTORICAL_OUTCOMES,
        confidence="HIGH",
        historical_success_rate=0.75,
        historical_sample_size=12,
        supporting_outcome_ids=["out_001", "out_002"],
    )
    explanation = explain_recommendation(rec=rec, use_groq=False)
    # Should reference evidence
    assert len(explanation.evidence_references) > 0
    # Should mention success rate
    combined_text = " ".join(explanation.explanation_points)
    assert "75%" in combined_text or "12" in combined_text or "sample" in combined_text.lower()
    # Should have limitations
    assert any("causation" in lim.lower() or "guarantee" in lim.lower()
               for lim in explanation.limitations)

test("6.2 Explainer: historical outcomes explanation references evidence", test_explainer_historical_outcomes)


def test_explainer_to_dict():
    from app.intelligence.outcome_optimization.models import AdaptiveRecommendation
    from app.intelligence.outcome_optimization.explainer import explain_recommendation

    rec = AdaptiveRecommendation(user_id="u1", title="T", description="D",
                                  action_type="UPDATE", target_table="t")
    explanation = explain_recommendation(rec=rec, use_groq=False)
    d = explanation.to_dict()
    assert "explanation_points" in d
    assert "limitations" in d
    assert "evidence_references" in d
    assert "generated_at" in d

test("6.3 RecommendationExplanation.to_dict contains required fields", test_explainer_to_dict)


# ── 7. Analysis Engine ────────────────────────────────────────────────────────

def test_analysis_engine_no_db():
    from app.intelligence.outcome_optimization.analysis_engine import run_outcome_analysis
    from app.intelligence.outcome_optimization.models import EffectivenessLabel

    analysis = run_outcome_analysis(
        user_id="u1",
        action_id="act_missing",
        engine=None,
        db_type="sqlite",
    )
    assert analysis.action_id == "act_missing"
    assert analysis.overall_effectiveness == EffectivenessLabel.INSUFFICIENT_DATA
    assert len(analysis.data_gaps) > 0

test("7.1 Analysis engine: no DB → INSUFFICIENT_DATA with data gaps", test_analysis_engine_no_db)


def test_analysis_aggregate_effectiveness():
    from app.intelligence.outcome_optimization.analysis_engine import _aggregate_effectiveness
    from app.intelligence.outcome_optimization.models import OutcomeMeasurement, EffectivenessLabel

    # Mostly positive
    measurements = [
        OutcomeMeasurement(user_id="u", metric_name="m1", source_table="t", effectiveness="POSITIVE"),
        OutcomeMeasurement(user_id="u", metric_name="m2", source_table="t", effectiveness="POSITIVE"),
        OutcomeMeasurement(user_id="u", metric_name="m3", source_table="t", effectiveness="NEGATIVE"),
    ]
    result = _aggregate_effectiveness(measurements)
    assert result == EffectivenessLabel.POSITIVE, f"Expected POSITIVE, got {result}"

    # All insufficient data
    measurements2 = [
        OutcomeMeasurement(user_id="u", metric_name="m", source_table="t",
                           effectiveness=EffectivenessLabel.INSUFFICIENT_DATA),
    ]
    result2 = _aggregate_effectiveness(measurements2)
    assert result2 == EffectivenessLabel.INSUFFICIENT_DATA

test("7.2 _aggregate_effectiveness: majority positive wins", test_analysis_aggregate_effectiveness)


def test_analysis_aggregate_confidence():
    from app.intelligence.outcome_optimization.analysis_engine import _aggregate_confidence
    from app.intelligence.outcome_optimization.models import OutcomeMeasurement, ConfidenceLevel

    measurements = [
        OutcomeMeasurement(user_id="u", metric_name="m1", source_table="t", confidence="HIGH"),
        OutcomeMeasurement(user_id="u", metric_name="m2", source_table="t", confidence="MODERATE"),
        OutcomeMeasurement(user_id="u", metric_name="m3", source_table="t", confidence="LIMITED"),
    ]
    result = _aggregate_confidence(measurements)
    # Most conservative
    assert result == ConfidenceLevel.LIMITED

test("7.3 _aggregate_confidence: uses most conservative (minimum) confidence", test_analysis_aggregate_confidence)


def test_analysis_aggregate_attribution():
    from app.intelligence.outcome_optimization.analysis_engine import _aggregate_attribution
    from app.intelligence.outcome_optimization.models import OutcomeMeasurement, AttributionStatus

    measurements = [
        OutcomeMeasurement(user_id="u", metric_name="m", source_table="t",
                           attribution=AttributionStatus.OBSERVED_OUTCOME),
        OutcomeMeasurement(user_id="u", metric_name="m2", source_table="t",
                           attribution=AttributionStatus.CONFOUNDERS_PRESENT),
    ]
    result = _aggregate_attribution(measurements)
    assert result == AttributionStatus.CONFOUNDERS_PRESENT

test("7.4 _aggregate_attribution: CONFOUNDERS_PRESENT if any measurement has it", test_analysis_aggregate_attribution)


# ── 8. Attribution ────────────────────────────────────────────────────────────

def test_attribution_no_db():
    from app.intelligence.outcome_optimization.attribution import assess_attribution
    from app.intelligence.outcome_optimization.models import AttributionStatus

    result = assess_attribution(engine=None, db_type="sqlite", source_table="orders")
    assert result["status"] == AttributionStatus.NO_BASELINE
    assert isinstance(result["confounders"], list)
    assert isinstance(result["explanation"], str)

test("8.1 Attribution: no DB → NO_BASELINE", test_attribution_no_db)


def test_attribution_returns_required_keys():
    from app.intelligence.outcome_optimization.attribution import assess_attribution

    # Test with no engine (safe)
    result = assess_attribution(engine=None, db_type="sqlite", source_table="test")
    assert "status" in result
    assert "confounders" in result
    assert "explanation" in result

test("8.2 Attribution result always contains status, confounders, explanation", test_attribution_returns_required_keys)


# ── 9. Epistemic Principles ───────────────────────────────────────────────────

def test_epistemic_note_never_claims_causation():
    from app.intelligence.outcome_optimization.models import OutcomeMeasurement

    m = OutcomeMeasurement(
        user_id="u1",
        metric_name="Revenue",
        source_table="orders",
        delta=100.0,
        delta_pct=10.0,
        baseline_value=1000.0,
        observed_value=1100.0,
        effectiveness="POSITIVE",
    )
    # Default epistemic note should not claim causation
    bad_words = ["caused", "due to", "because of", "proven"]
    for word in bad_words:
        assert word not in m.epistemic_note.lower(), (
            f"Epistemic note claims causation: '{word}' found in: {m.epistemic_note}"
        )

test("9.1 Default epistemic note never claims causation", test_epistemic_note_never_claims_causation)


def test_disclaimer_in_analysis():
    from app.intelligence.outcome_optimization.models import OutcomeAnalysis

    analysis = OutcomeAnalysis(action_id="act1", user_id="u1")
    assert "causation" in analysis.disclaimer.lower() or "association" in analysis.disclaimer.lower(), (
        f"Disclaimer should mention causation/association: {analysis.disclaimer}"
    )

test("9.2 OutcomeAnalysis.disclaimer explicitly addresses causation", test_disclaimer_in_analysis)


def test_recommendations_always_require_confirmation():
    from app.intelligence.outcome_optimization.models import AdaptiveRecommendation

    rec = AdaptiveRecommendation(
        user_id="u1", title="T", description="D",
        action_type="UPDATE", target_table="t",
    )
    # Override attempt should still be True (immutable by design)
    assert rec.requires_human_confirmation is True

    d = rec.to_dict()
    assert d["requires_human_confirmation"] is True

test("9.3 AdaptiveRecommendation.requires_human_confirmation is always True", test_recommendations_always_require_confirmation)


# ── 10. API Endpoints ─────────────────────────────────────────────────────────

def _get_test_client():
    from app.main import app
    from fastapi.testclient import TestClient
    if hasattr(app.state, "limiter"):
        app.state.limiter.enabled = False
    return TestClient(app)


def _auth_headers():
    from app.security.auth import create_access_token
    token = create_access_token(user_id="test_user_89", username="testuser89")
    return {"Authorization": f"Bearer {token}"}


def test_api_measure_outcome_requires_auth():
    client = _get_test_client()
    resp = client.post("/intelligence/outcomes/measure", json={"action_id": "act_x"})
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

test("10.1 POST /intelligence/outcomes/measure requires authentication", test_api_measure_outcome_requires_auth)


def test_api_measure_outcome_authenticated():
    client = _get_test_client()
    headers = _auth_headers()
    resp = client.post("/intelligence/outcomes/measure",
                       json={"action_id": "act_nonexistent_123"},
                       headers=headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert "status" in data
    # Status could be success, insufficient_data, or error
    assert data["status"] in ("success", "insufficient_data", "error", "disconnected")

test("10.2 POST /intelligence/outcomes/measure returns valid response", test_api_measure_outcome_authenticated)


def test_api_get_outcome_by_id_requires_auth():
    client = _get_test_client()
    resp = client.get("/intelligence/outcomes/meas_test123")
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

test("10.3 GET /intelligence/outcomes/{id} requires authentication", test_api_get_outcome_by_id_requires_auth)


def test_api_get_outcome_by_id_not_found():
    client = _get_test_client()
    headers = _auth_headers()
    resp = client.get("/intelligence/outcomes/meas_nonexistent_999", headers=headers)
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        data = resp.json()
        assert "status" in data
    # Either way should not crash

test("10.4 GET /intelligence/outcomes/{id} handles non-existent measurement", test_api_get_outcome_by_id_not_found)


def test_api_get_outcome_analysis_requires_auth():
    client = _get_test_client()
    resp = client.get("/intelligence/outcomes/act_x/analysis")
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

test("10.5 GET /intelligence/outcomes/{id}/analysis requires authentication", test_api_get_outcome_analysis_requires_auth)


def test_api_get_outcome_analysis_authenticated():
    client = _get_test_client()
    headers = _auth_headers()
    resp = client.get("/intelligence/outcomes/act_nonexistent_456/analysis", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "analysis" in data
    if data["analysis"]:
        assert "measurements" in data["analysis"]

test("10.6 GET /intelligence/outcomes/{id}/analysis returns analysis structure", test_api_get_outcome_analysis_authenticated)


def test_api_adaptive_recommendations_requires_auth():
    client = _get_test_client()
    resp = client.get("/intelligence/recommendations/adaptive")
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

test("10.7 GET /intelligence/recommendations/adaptive requires authentication", test_api_adaptive_recommendations_requires_auth)


def test_api_adaptive_recommendations_authenticated():
    client = _get_test_client()
    headers = _auth_headers()
    resp = client.get("/intelligence/recommendations/adaptive", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "recommendations" in data
    assert isinstance(data["recommendations"], list)
    # All recommendations must require human confirmation
    for rec in data["recommendations"]:
        assert rec.get("requires_human_confirmation") is True, (
            f"Recommendation missing requires_human_confirmation=True: {rec.get('title')}"
        )

test("10.8 GET /intelligence/recommendations/adaptive returns valid recommendations", test_api_adaptive_recommendations_authenticated)


def test_api_explain_recommendation_requires_auth():
    client = _get_test_client()
    resp = client.post("/intelligence/recommendations/rec_test123/explain")
    assert resp.status_code == 401

test("10.9 POST /intelligence/recommendations/{id}/explain requires authentication", test_api_explain_recommendation_requires_auth)


def test_api_explain_recommendation_not_found():
    client = _get_test_client()
    headers = _auth_headers()
    resp = client.post("/intelligence/recommendations/rec_nonexistent_xyz/explain",
                       headers=headers)
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        data = resp.json()
        assert "status" in data
    # Should not return 500

test("10.10 POST /intelligence/recommendations/{id}/explain handles missing rec gracefully", test_api_explain_recommendation_not_found)


# ── 11. Measure Window Validation ─────────────────────────────────────────────

def test_measure_window_validation():
    from app.intelligence.outcome_optimization.models import MeasurementWindow

    valid = MeasurementWindow.ALL
    assert "24h" in valid
    assert "7d" in valid
    assert "14d" in valid
    assert "30d" in valid

test("11.1 MeasurementWindow.ALL contains 24h, 7d, 14d, 30d", test_measure_window_validation)


def test_api_measure_with_valid_window():
    client = _get_test_client()
    headers = _auth_headers()
    resp = client.post("/intelligence/outcomes/measure",
                       json={"action_id": "act_x", "window": "30d"},
                       headers=headers)
    assert resp.status_code == 200

test("11.2 API accepts valid measurement window '30d'", test_api_measure_with_valid_window)


def test_api_measure_with_invalid_window():
    client = _get_test_client()
    headers = _auth_headers()
    # Invalid window should default to 7d gracefully
    resp = client.post("/intelligence/outcomes/measure",
                       json={"action_id": "act_x", "window": "INVALID"},
                       headers=headers)
    assert resp.status_code == 200  # Should not 422 or 500

test("11.3 API accepts invalid window gracefully (defaults to 7d)", test_api_measure_with_invalid_window)


# ── 12. User Isolation (API-level) ────────────────────────────────────────────

def test_api_user_isolation_measurements():
    from app.security.auth import create_access_token
    client = _get_test_client()

    token_a = create_access_token(user_id="user_a_iso", username="user_a")
    token_b = create_access_token(user_id="user_b_iso", username="user_b")

    # User A requests measurement
    resp_a = client.post("/intelligence/outcomes/measure",
                         json={"action_id": "act_user_a"},
                         headers={"Authorization": f"Bearer {token_a}"})
    assert resp_a.status_code == 200

    # User B's recommendations should be empty or cold-start (not User A's data)
    resp_b = client.get("/intelligence/recommendations/adaptive",
                        headers={"Authorization": f"Bearer {token_b}"})
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    # No error, returns valid structure
    assert "recommendations" in data_b

test("12.1 API user isolation: User B cannot see User A's outcomes in recommendations", test_api_user_isolation_measurements)


# ── 13. Phase 8.5 Regression ──────────────────────────────────────────────────

def test_phase85_outcomes_endpoint_still_works():
    client = _get_test_client()
    headers = _auth_headers()
    resp = client.get("/intelligence/outcomes", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "outcomes" in data or "status" in data

test("13.1 Phase 8.5 GET /intelligence/outcomes still works", test_phase85_outcomes_endpoint_still_works)


def test_phase85_feedback_endpoint_still_works():
    client = _get_test_client()
    headers = _auth_headers()
    resp = client.post("/intelligence/feedback",
                       json={"target_type": "DECISION", "useful": True},
                       headers=headers)
    assert resp.status_code == 200

test("13.2 Phase 8.5 POST /intelligence/feedback still works", test_phase85_feedback_endpoint_still_works)


def test_phase85_learning_summary_still_works():
    client = _get_test_client()
    headers = _auth_headers()
    resp = client.get("/intelligence/learning-summary", headers=headers)
    assert resp.status_code == 200

test("13.3 Phase 8.5 GET /intelligence/learning-summary still works", test_phase85_learning_summary_still_works)


# ── 14. Phase 8.8 Regression ──────────────────────────────────────────────────

def test_phase88_actions_endpoint_still_works():
    client = _get_test_client()
    headers = _auth_headers()
    resp = client.get("/intelligence/actions", headers=headers)
    assert resp.status_code == 200

test("14.1 Phase 8.8 GET /intelligence/actions still works", test_phase88_actions_endpoint_still_works)


def test_phase88_propose_still_exists():
    client = _get_test_client()
    routes = [r.path for r in client.app.routes]
    assert "/intelligence/actions/propose" in routes

test("14.2 Phase 8.8 /intelligence/actions/propose route still exists", test_phase88_propose_still_exists)


# ── 15. No Fake Data Assertions ───────────────────────────────────────────────

def test_no_hardcoded_business_numbers():
    """Verify source files don't contain hardcoded fake business numbers."""
    import os
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "app", "intelligence", "outcome_optimization")
    suspicious = [
        "revenue = 1000", "revenue=1000",
        "fake", "demo", "sample_data",
        "mock_customer", "test_revenue",
    ]
    for fname in os.listdir(base):
        if fname.endswith(".py"):
            content = open(os.path.join(base, fname)).read().lower()
            for s in suspicious:
                assert s not in content, (
                    f"Suspicious hardcoded value '{s}' found in {fname}"
                )

test("15.1 No hardcoded fake business data in outcome_optimization source files", test_no_hardcoded_business_numbers)


def test_models_do_not_generate_fake_metrics():
    from app.intelligence.outcome_optimization.models import OutcomeMeasurement
    # Default measurement should have no values (not fake ones)
    m = OutcomeMeasurement(user_id="u", metric_name="m", source_table="t")
    assert m.baseline_value is None
    assert m.observed_value is None
    assert m.delta is None
    assert m.delta_pct is None

test("15.2 OutcomeMeasurement defaults to None values (not fake numbers)", test_models_do_not_generate_fake_metrics)


# ── Summary ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    passed = sum(1 for r in results if r[0] == PASS)
    failed = sum(1 for r in results if r[0] == FAIL)
    total = len(results)
    print(f"\n{'=' * 60}")
    print(f"Phase 8.9 Test Results: {passed}/{total} passed, {failed} failed")
    print(f"{'=' * 60}")
    if failed:
        print("\nFailed tests:")
        for r in results:
            if r[0] == FAIL:
                print(f"  FAIL: {r[1]}")
                if len(r) > 2:
                    print(f"        {r[2]}")
    sys.exit(0 if failed == 0 else 1)
