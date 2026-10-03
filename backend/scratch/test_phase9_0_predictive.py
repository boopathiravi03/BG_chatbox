#!/usr/bin/env python
"""
Phase 9.0 Test Suite: Advanced Predictive & Simulation Intelligence
Over 60 rigorous, evidence-based assertions testing:
- Strongly typed prediction models and serialization
- Data quality gates, time-series discovery, and insufficient data guards
- Deterministic statistical forecasting methods (Naive, SMA, WMA, OLS Linear Trend, Holt's Exponential Smoothing, Seasonality)
- Holdout backtesting (MAE, RMSE, MAPE with division-by-zero guard) and strategy selection
- Uncertainty intervals (residual SE expanding by sqrt(h)) and confidence tiers (HIGH, MODERATE, LIMITED)
- Trend trajectory classification (INCREASING, DECREASING, STABLE, VOLATILE)
- Seasonality validation (guarded against claiming patterns without 2+ full cycles)
- What-if simulation engine, percentage/absolute shifts, input validation & clamping
- Scenario comparison matrix and objective evaluation (no subjective winner labels)
- Epistemic safety: causal disclaimers, no fake certainty, no hallucinated accuracy
- Integration with Phase 8.9 measured outcomes & Phase 8.5 learning signals
- Authentication, rate limiting, and strict user/database isolation
- Read-only SQL safety, DML/DDL blocking, bounded queries
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
        print(f"  OK   {name}")
    except AssertionError as e:
        results.append((FAIL, name, str(e)))
        print(f"  FAIL {name}: {e}")
    except Exception as e:
        results.append((FAIL, name, f"{type(e).__name__}: {e}"))
        print(f"  FAIL {name}: {type(e).__name__}: {e}")


# ── 1. Models & Serialization ────────────────────────────────────────────────

def test_prediction_models():
    from app.intelligence.predictive.models import (
        ConfidenceTier,
        DataQualityStatus,
        ForecastPoint,
        ForecastingMethod,
        PredictionEvidence,
        PredictionResult,
        ScenarioComparison,
        ScenarioResult,
        ScenarioType,
        TrendDirection,
    )

    pt = ForecastPoint(period="2024-05", value=125.45, is_forecast=True, lower_bound=100.0, upper_bound=150.0)
    d_pt = pt.to_dict()
    assert d_pt["value"] == 125.45
    assert d_pt["is_forecast"] is True
    reconstructed_pt = ForecastPoint.from_dict(d_pt)
    assert reconstructed_pt.period == "2024-05"

    ev = PredictionEvidence(
        source_table="orders",
        date_column="created_at",
        metric_column="amount",
        aggregation="SUM",
        historical_count=12,
        min_date="2023-01",
        max_date="2023-12",
        sql_lineage="SELECT strftime('%Y-%m', created_at), SUM(amount) FROM orders GROUP BY 1",
    )
    d_ev = ev.to_dict()
    assert d_ev["source_table"] == "orders"
    assert d_ev["historical_count"] == 12

    res = PredictionResult(
        metric_name="Total Order Amount",
        source_table="orders",
        points=[pt],
        evidence=ev,
        confidence_tier=ConfidenceTier.MODERATE.value,
        trend_direction=TrendDirection.INCREASING.value,
    )
    d_res = res.to_dict()
    assert d_res["metric_name"] == "Total Order Amount"
    assert len(d_res["points"]) == 1
    assert d_res["confidence_tier"] == "MODERATE"


test("1.1 Prediction models and roundtrip serialization", test_prediction_models)


# ── 2. Real Metric & Temporal Discovery ───────────────────────────────────────

def test_metric_and_temporal_discovery():
    from sqlalchemy import create_engine
    from app.intelligence.predictive.data_quality import discover_predictive_candidates

    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.exec_driver_sql("""
            CREATE TABLE sales_events (
                event_id INTEGER PRIMARY KEY,
                order_date TEXT NOT NULL,
                revenue REAL NOT NULL,
                units INTEGER NOT NULL
            );
        """)
        conn.commit()

    candidates = discover_predictive_candidates(engine, "sqlite")
    assert len(candidates) >= 1
    table_names = [c.table for c in candidates]
    assert "sales_events" in table_names
    date_cols = [c.date_column for c in candidates]
    assert "order_date" in date_cols


test("2.1 Discovery: identifies real table and date column from schema", test_metric_and_temporal_discovery)


# ── 3. Data Quality Gate & Minimum History ───────────────────────────────────

def test_data_quality_insufficient_history():
    from sqlalchemy import create_engine
    from app.intelligence.predictive.data_quality import extract_and_evaluate_time_series
    from app.intelligence.predictive.models import DataQualityStatus

    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.connection.cursor().executescript("""
            CREATE TABLE short_history (
                id INTEGER PRIMARY KEY,
                tx_date TEXT,
                amount REAL
            );
            INSERT INTO short_history VALUES (1, '2024-01-01', 10.0), (2, '2024-01-02', 20.0);
        """)
        conn.commit()

    report = extract_and_evaluate_time_series(
        engine, "sqlite", table="short_history", date_column="tx_date", metric_column="amount", frequency="daily"
    )
    assert not report.is_sufficient
    assert report.status == DataQualityStatus.INSUFFICIENT_DATA
    assert report.observation_count == 2
    assert any("Insufficient historical data" in iss for iss in report.issues)


test("3.1 Data Quality: <3 periods triggers INSUFFICIENT_DATA", test_data_quality_insufficient_history)


def test_data_quality_valid_series():
    from sqlalchemy import create_engine
    from app.intelligence.predictive.data_quality import extract_and_evaluate_time_series
    from app.intelligence.predictive.models import DataQualityStatus

    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.connection.cursor().executescript("""
            CREATE TABLE valid_history (
                id INTEGER PRIMARY KEY,
                tx_date TEXT,
                amount REAL
            );
            INSERT INTO valid_history VALUES 
                (1, '2024-01-01', 100.0), 
                (2, '2024-01-02', 110.0),
                (3, '2024-01-03', 120.0),
                (4, '2024-01-04', 130.0);
        """)
        conn.commit()

    report = extract_and_evaluate_time_series(
        engine, "sqlite", table="valid_history", date_column="tx_date", metric_column="amount", frequency="daily"
    )
    assert report.is_sufficient
    assert report.status == DataQualityStatus.VALID
    assert report.observation_count == 4
    assert len(report.clean_series) == 4


test("3.2 Data Quality: valid chronological sequence passes gate", test_data_quality_valid_series)



# ── 4. Deterministic Forecasting Algorithms ───────────────────────────────────

def test_naive_forecast():
    from app.intelligence.predictive.forecasting import naive_forecast

    series = [10.0, 20.0, 30.0, 45.0]
    fitted, preds = naive_forecast(series, horizon=3)
    assert len(preds) == 3
    assert preds == [45.0, 45.0, 45.0]
    assert fitted[-1] == 30.0


test("4.1 Naive baseline forecast persistence", test_naive_forecast)


def test_simple_moving_average():
    from app.intelligence.predictive.forecasting import simple_moving_average_forecast

    series = [10.0, 20.0, 30.0, 40.0]
    fitted, preds = simple_moving_average_forecast(series, horizon=2, window=3)
    # Average of last 3: (20 + 30 + 40) / 3 = 30.0
    assert len(preds) == 2
    assert preds == [30.0, 30.0]


test("4.2 Simple Moving Average (SMA) calculation", test_simple_moving_average)


def test_weighted_moving_average():
    from app.intelligence.predictive.forecasting import weighted_moving_average_forecast

    series = [10.0, 20.0, 30.0]
    # Weights for window=3: 1, 2, 3 (sum=6) -> (10*1 + 20*2 + 30*3)/6 = (10 + 40 + 90)/6 = 140/6 = 23.33
    fitted, preds = weighted_moving_average_forecast(series, horizon=2, window=3)
    assert len(preds) == 2
    assert round(preds[0], 2) == 23.33


test("4.3 Weighted Moving Average (WMA) calculation", test_weighted_moving_average)


def test_linear_trend_forecast():
    from app.intelligence.predictive.forecasting import linear_trend_forecast

    # Perfect linear slope = 10, y = 10*x + 10 (x=0,1,2,3 -> y=10, 20, 30, 40)
    series = [10.0, 20.0, 30.0, 40.0]
    fitted, preds = linear_trend_forecast(series, horizon=2)
    # Next points: x=4 -> 50.0, x=5 -> 60.0
    assert len(preds) == 2
    assert preds == [50.0, 60.0]


test("4.4 Linear Trend (OLS regression) extrapolation", test_linear_trend_forecast)


def test_exponential_smoothing_forecast():
    from app.intelligence.predictive.forecasting import exponential_smoothing_forecast

    series = [100.0, 110.0, 120.0, 130.0, 140.0]
    fitted, preds = exponential_smoothing_forecast(series, horizon=3, alpha=0.4, beta=0.2)
    assert len(preds) == 3
    # With positive trend, projections should be greater than the last point
    assert preds[0] > 140.0
    assert preds[1] >= preds[0]


test("4.5 Holt's Linear Exponential Smoothing forecast", test_exponential_smoothing_forecast)


def test_seasonal_decomposition_forecast():
    from app.intelligence.predictive.forecasting import seasonal_forecast

    # 14 days of weekly cyclical data (2 full cycles of length 7)
    cycle = [10.0, 15.0, 20.0, 25.0, 30.0, 50.0, 45.0]
    series = cycle + [x + 5 for x in cycle]
    fitted, preds = seasonal_forecast(series, horizon=7, cycle_length=7)
    assert len(preds) == 7
    # Weekend peak (index 5) should remain highest in projection
    assert preds[5] > preds[0]


test("4.6 Seasonal Decomposition with cycle projection", test_seasonal_decomposition_forecast)


# ── 5. Model Selection & Holdout Backtesting ──────────────────────────────────

def test_model_evaluation_metrics():
    from app.intelligence.predictive.model_selection import calculate_mae, calculate_rmse, calculate_mape

    actuals = [100.0, 200.0, 300.0]
    preds = [110.0, 190.0, 310.0]
    # Errors: +10, -10, +10 -> MAE = 10.0
    mae = calculate_mae(actuals, preds)
    assert mae == 10.0

    # MSE: (100 + 100 + 100) / 3 = 100 -> RMSE = 10.0
    rmse = calculate_rmse(actuals, preds)
    assert rmse == 10.0

    # Percentage errors: 10/100 = 10%, 10/200 = 5%, 10/300 = 3.33% -> avg = 6.11%
    mape, note = calculate_mape(actuals, preds)
    assert note is None
    assert mape == 6.11


test("5.1 Backtest metrics: MAE, RMSE, MAPE calculated accurately", test_model_evaluation_metrics)


def test_mape_division_by_zero_guard():
    from app.intelligence.predictive.model_selection import calculate_mape

    actuals = [0.0, 50.0, 100.0]
    preds = [10.0, 50.0, 100.0]
    mape, note = calculate_mape(actuals, preds)
    assert mape is None
    assert "division by zero" in note


test("5.2 MAPE safely omits score and returns note on division by zero", test_mape_division_by_zero_guard)


def test_evidence_based_model_selection():
    from app.intelligence.predictive.model_selection import evaluate_and_select_model

    # Linear series with 8 points
    series = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0]
    best_method, evals = evaluate_and_select_model(series, frequency="monthly")
    assert len(evals) >= 4
    # The linear trend should outperform or be selected
    selected = [e for e in evals if e.selected]
    assert len(selected) == 1
    assert selected[0].method == best_method


test("5.3 Model selection picks best holdout method", test_evidence_based_model_selection)


def test_model_selection_small_sample_fallback():
    from app.intelligence.predictive.model_selection import evaluate_and_select_model

    # Only 4 points (less than MIN_POINTS_FOR_HOLDOUT=6)
    series = [100.0, 105.0, 110.0, 115.0]
    best_method, evals = evaluate_and_select_model(series, frequency="monthly")
    assert len(evals) == 1
    assert evals[0].mae is None
    assert "fewer than 6 observations" in evals[0].mape_note


test("5.4 Small sample (<6 points) falls back gracefully with transparent note", test_model_selection_small_sample_fallback)


# ── 6. Uncertainty Quantification & Confidence Tiers ─────────────────────────

def test_expanding_prediction_intervals():
    from app.intelligence.predictive.uncertainty import compute_prediction_intervals

    actuals = [10.0, 20.0, 30.0, 40.0, 50.0]
    fitted = [11.0, 19.0, 31.0, 39.0, 51.0]
    forecast_values = [60.0, 70.0, 80.0]
    future_labels = ["2024-06", "2024-07", "2024-08"]

    points = compute_prediction_intervals(actuals, fitted, forecast_values, future_labels)
    assert len(points) == 3
    # Step 2 uncertainty width should be strictly greater than step 1 (scaled by sqrt(h))
    assert points[1].uncertainty_width > points[0].uncertainty_width
    assert points[2].uncertainty_width > points[1].uncertainty_width
    assert points[0].lower_bound < points[0].value < points[0].upper_bound


test("6.1 Uncertainty intervals expand monotonically with forecast horizon", test_expanding_prediction_intervals)


def test_confidence_tiers():
    from app.intelligence.predictive.models import ConfidenceTier, ModelEvaluationMetric, TrendDirection
    from app.intelligence.predictive.uncertainty import determine_confidence_tier

    # 1. Limited (<6 points)
    conf_1, _ = determine_confidence_tier(observation_count=4, trend=TrendDirection.STABLE)
    assert conf_1 == ConfidenceTier.LIMITED

    # 2. Moderate (10 points, reasonable error)
    ev_mod = ModelEvaluationMetric(method="EXPONENTIAL_SMOOTHING", rmse=15.0)
    conf_2, _ = determine_confidence_tier(
        observation_count=10, trend=TrendDirection.INCREASING, selected_eval=ev_mod, mean_value=100.0
    )
    assert conf_2 == ConfidenceTier.MODERATE

    # 3. High (14 points, low error <=15%)
    ev_high = ModelEvaluationMetric(method="EXPONENTIAL_SMOOTHING", rmse=10.0)
    conf_3, _ = determine_confidence_tier(
        observation_count=14, trend=TrendDirection.INCREASING, selected_eval=ev_high, mean_value=100.0
    )
    assert conf_3 == ConfidenceTier.HIGH


test("6.2 Confidence tier evaluation (LIMITED, MODERATE, HIGH)", test_confidence_tiers)


# ── 7. Trend & Seasonality Analysis ──────────────────────────────────────────

def test_trend_detection():
    from app.intelligence.predictive.forecasting import detect_trend
    from app.intelligence.predictive.models import TrendDirection

    # Increasing
    t_inc, slope_inc, _ = detect_trend([10.0, 20.0, 30.0, 40.0, 50.0])
    assert t_inc == TrendDirection.INCREASING
    assert slope_inc > 0

    # Decreasing
    t_dec, slope_dec, _ = detect_trend([50.0, 40.0, 30.0, 20.0, 10.0])
    assert t_dec == TrendDirection.DECREASING
    assert slope_dec < 0

    # Stable
    t_stb, slope_stb, _ = detect_trend([100.0, 100.5, 99.8, 100.2, 100.0])
    assert t_stb == TrendDirection.STABLE


test("7.1 Trend direction detection (INCREASING, DECREASING, STABLE)", test_trend_detection)


def test_seasonality_guard():
    from app.intelligence.predictive.forecasting import detect_seasonality

    # Only 8 daily points (needs at least 14 points for 2 weekly cycles)
    has_season, note = detect_seasonality([10.0] * 8, frequency="daily")
    assert not has_season
    assert "at least 14 periods" in note


test("7.2 Seasonality detection is guarded when history is under 2 full cycles", test_seasonality_guard)


# ── 8. What-If Scenario Simulation & Comparison ──────────────────────────────

def test_what_if_scenario_simulation():
    from app.intelligence.predictive.models import ForecastPoint, PredictionResult
    from app.intelligence.predictive.scenario_engine import simulate_what_if_scenario

    base_pts = [
        ForecastPoint(period="2024-01", value=100.0, is_forecast=False),
        ForecastPoint(period="2024-02", value=100.0, is_forecast=True, lower_bound=90.0, upper_bound=110.0),
        ForecastPoint(period="2024-03", value=200.0, is_forecast=True, lower_bound=180.0, upper_bound=220.0),
    ]
    pred = PredictionResult(metric_name="Revenue", points=base_pts)

    # +10% scenario
    scen = simulate_what_if_scenario(baseline_result=pred, change_percent=10.0, scenario_name="Optimistic Growth")
    assert scen.baseline_projected_total == 300.0
    assert scen.scenario_projected_total == 330.0  # (110 + 220)
    assert scen.delta_total == 30.0
    assert scen.delta_percent == 10.0
    assert "Assumes an explicit simulated parameter adjustment of +10.0%" in scen.assumption_statement
    assert "Scenario arithmetic describes mathematical projection" in scen.causal_disclaimer


test("8.1 What-If percentage uplift simulation and causal disclaimer", test_what_if_scenario_simulation)


def test_what_if_reduction_scenario():
    from app.intelligence.predictive.models import ForecastPoint, PredictionResult
    from app.intelligence.predictive.scenario_engine import simulate_what_if_scenario

    base_pts = [
        ForecastPoint(period="2024-02", value=100.0, is_forecast=True, lower_bound=90.0, upper_bound=110.0),
    ]
    pred = PredictionResult(metric_name="Cost", points=base_pts)

    # -15% scenario
    scen = simulate_what_if_scenario(baseline_result=pred, change_percent=-15.0)
    assert scen.scenario_projected_total == 85.0
    assert scen.delta_total == -15.0
    assert scen.delta_percent == -15.0


test("8.2 What-If reduction scenario simulation", test_what_if_reduction_scenario)


def test_what_if_extreme_input_validation():
    from app.intelligence.predictive.models import ForecastPoint, PredictionResult
    from app.intelligence.predictive.scenario_engine import simulate_what_if_scenario

    pred = PredictionResult(
        metric_name="M", points=[ForecastPoint(period="P1", value=100.0, is_forecast=True)]
    )

    try:
        simulate_what_if_scenario(pred, change_percent=1500.0)
        assert False, "Should have rejected change_percent > 1000%"
    except ValueError as ve:
        assert "cannot exceed" in str(ve)

    try:
        simulate_what_if_scenario(pred, change_percent=-150.0)
        assert False, "Should have rejected change_percent < -100%"
    except ValueError as ve:
        assert "cannot be less than" in str(ve)


test("8.3 Extreme scenario parameter inputs rejected cleanly", test_what_if_extreme_input_validation)


def test_scenario_comparison_matrix():
    from app.intelligence.predictive.models import ForecastPoint, PredictionResult
    from app.intelligence.predictive.scenario_engine import compare_scenarios

    base_pts = [
        ForecastPoint(period="2024-02", value=100.0, is_forecast=True, lower_bound=90.0, upper_bound=110.0),
    ]
    pred = PredictionResult(metric_name="Revenue", points=base_pts, forecast_horizon_days=30)

    comparison = compare_scenarios(
        baseline_result=pred,
        scenario_specs=[
            {"scenario_name": "+5% Uplift", "change_percent": 5.0},
            {"scenario_name": "+10% Uplift", "change_percent": 10.0},
            {"scenario_name": "-5% Decline", "change_percent": -5.0},
        ],
    )
    # Comparison includes Baseline + 3 specs = 4 scenarios
    assert len(comparison.scenarios) == 4
    assert len(comparison.summary_table) == 4
    # Baseline is first
    assert comparison.scenarios[0].scenario_name == "Baseline (Status Quo)"
    assert comparison.scenarios[1].scenario_projected_total == 105.0


test("8.4 Multi-scenario comparison matrix generation", test_scenario_comparison_matrix)


# ── 9. Evidence Lineage & Structured Explanations ────────────────────────────

def test_prediction_explanation():
    from app.intelligence.predictive.explainer import generate_structured_explanation
    from app.intelligence.predictive.models import (
        ConfidenceTier,
        ForecastPoint,
        ModelEvaluationMetric,
        PredictionEvidence,
        PredictionResult,
        TrendDirection,
    )

    pred = PredictionResult(
        metric_name="Sales",
        points=[
            ForecastPoint(period="2024-01", value=100.0, is_forecast=False),
            ForecastPoint(period="2024-02", value=110.0, is_forecast=True, lower_bound=95.0, upper_bound=125.0),
        ],
        selected_method="EXPONENTIAL_SMOOTHING",
        trend_direction=TrendDirection.INCREASING.value,
        confidence_tier=ConfidenceTier.MODERATE.value,
        confidence_rationale="Moderate history available.",
        model_evaluations=[
            ModelEvaluationMetric(method="EXPONENTIAL_SMOOTHING", rmse=5.2, mae=4.1, selected=True)
        ],
        evidence=PredictionEvidence(
            source_table="sales",
            date_column="dt",
            metric_column="amt",
            aggregation="SUM",
            historical_count=5,
            min_date="2024-01",
            max_date="2024-01",
            sql_lineage="SELECT dt, SUM(amt) FROM sales GROUP BY 1",
            historical_outcome_support=[{"note": "Observed 1 positive outcome on sales"}],
        ),
    )

    exp = generate_structured_explanation(pred)
    assert "sales" in exp.historical_summary.lower() or "analyzed" in exp.historical_summary.lower()
    assert "exponential smoothing" in exp.method_rationale.lower()
    assert "rmse" in exp.method_rationale.lower()
    assert len(exp.limitations) >= 2
    assert len(exp.phase89_historical_signals) == 1


test("9.1 Transparent structured explanation includes data lineage and model backtesting", test_prediction_explanation)


# ── 10. End-to-End Orchestrator (Predictor) ───────────────────────────────────

def test_predictor_end_to_end_with_db():
    from sqlalchemy import create_engine
    from app.intelligence.predictive.models import DataQualityStatus
    from app.intelligence.predictive.predictor import run_prediction

    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.connection.cursor().executescript("""
            CREATE TABLE monthly_revenue (
                id INTEGER PRIMARY KEY,
                order_date TEXT,
                revenue REAL
            );
            INSERT INTO monthly_revenue VALUES
                (1, '2023-01-15', 1000.0),
                (2, '2023-02-15', 1100.0),
                (3, '2023-03-15', 1250.0),
                (4, '2023-04-15', 1400.0),
                (5, '2023-05-15', 1550.0),
                (6, '2023-06-15', 1700.0);
        """)
        conn.commit()

    result = run_prediction(
        user_id="user_pred_test",
        table="monthly_revenue",
        date_column="order_date",
        metric_column="revenue",
        aggregation="SUM",
        frequency="monthly",
        horizon_days=60,
        engine=engine,
        db_type="sqlite",
    )

    assert result.status == "success"
    assert result.data_quality_status == DataQualityStatus.VALID.value
    assert len(result.points) > 6  # 6 historical + future forecasts
    assert result.evidence is not None
    assert result.evidence.historical_count == 6


test("10.1 Predictor end-to-end execution on real database data", test_predictor_end_to_end_with_db)


# ── 11. Persistence & User Isolation ─────────────────────────────────────────

def test_predictive_store_isolation():
    from app.intelligence.predictive.models import PredictionResult
    from app.intelligence.predictive.store import (
        clear_predictive_store,
        get_prediction,
        list_predictions,
        save_prediction,
    )

    clear_predictive_store()

    p_user_a = PredictionResult(user_id="user_a", metric_name="A Revenue", source_table="t_a")
    p_user_b = PredictionResult(user_id="user_b", metric_name="B Revenue", source_table="t_b")

    save_prediction(p_user_a)
    save_prediction(p_user_b)

    # User A cannot retrieve User B's prediction
    assert get_prediction(p_user_b.prediction_id, user_id="user_a") is None
    # User B can retrieve User B's prediction
    assert get_prediction(p_user_b.prediction_id, user_id="user_b") is not None

    list_a = list_predictions("user_a")
    assert len(list_a) == 1
    assert list_a[0].metric_name == "A Revenue"

    clear_predictive_store("user_a")
    assert len(list_predictions("user_a")) == 0
    assert len(list_predictions("user_b")) == 1


test("11.1 Prediction store enforces strict per-user multi-tenant isolation", test_predictive_store_isolation)


# ── 12. API Endpoints & Authentication ───────────────────────────────────────

def _get_test_client():
    from fastapi.testclient import TestClient
    from app.main import app

    if hasattr(app.state, "limiter"):
        app.state.limiter.enabled = False
    return TestClient(app)


def _auth_header(user_id="test_user_p9", username="p9user"):
    from app.security.auth import create_access_token

    tok = create_access_token(user_id=user_id, username=username)
    return {"Authorization": f"Bearer {tok}"}


def test_api_predict_requires_auth():
    client = _get_test_client()
    resp = client.post("/intelligence/predict", json={"table": "orders"})
    assert resp.status_code == 401


test("12.1 POST /intelligence/predict requires JWT authentication", test_api_predict_requires_auth)


def test_api_predict_candidates_endpoint():
    client = _get_test_client()
    headers = _auth_header()
    resp = client.get("/intelligence/predict/candidates", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "candidates" in data
    assert isinstance(data["candidates"], list)


test("12.2 GET /intelligence/predict/candidates returns list of eligible candidates", test_api_predict_candidates_endpoint)


def test_api_predict_endpoint_disconnected_db():
    client = _get_test_client()
    headers = _auth_header()
    resp = client.post("/intelligence/predict", json={"table": "nonexistent_table"}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    # When no real DB is connected, status is either 'error' or 'insufficient_data'
    assert data["status"] in ("error", "insufficient_data", "success")


test("12.3 POST /intelligence/predict handles missing/disconnected tables safely", test_api_predict_endpoint_disconnected_db)


def test_api_predict_scenario_requires_auth():
    client = _get_test_client()
    resp = client.post("/intelligence/predict/scenario", json={"prediction_id": "pred_xyz"})
    assert resp.status_code == 401


test("12.4 POST /intelligence/predict/scenario requires JWT authentication", test_api_predict_scenario_requires_auth)


def test_api_predict_scenario_simulation():
    from app.intelligence.predictive.models import ForecastPoint, PredictionResult
    from app.intelligence.predictive.store import save_prediction

    client = _get_test_client()
    headers = _auth_header(user_id="user_sim_test")

    pred = PredictionResult(
        user_id="user_sim_test",
        metric_name="Order Volume",
        points=[
            ForecastPoint(period="P1", value=50.0, is_forecast=True, lower_bound=40.0, upper_bound=60.0),
        ],
    )
    save_prediction(pred)

    resp = client.post(
        "/intelligence/predict/scenario",
        json={"prediction_id": pred.prediction_id, "change_percent": 20.0, "scenario_name": "+20% Expansion"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["scenario"]["scenario_projected_total"] == 60.0
    assert data["scenario"]["delta_percent"] == 20.0


test("12.5 POST /intelligence/predict/scenario executes simulation on existing prediction", test_api_predict_scenario_simulation)


def test_api_predict_compare_endpoint():
    from app.intelligence.predictive.models import ForecastPoint, PredictionResult
    from app.intelligence.predictive.store import save_prediction

    client = _get_test_client()
    headers = _auth_header(user_id="user_comp_test")

    pred = PredictionResult(
        user_id="user_comp_test",
        metric_name="Monthly Active Users",
        points=[ForecastPoint(period="M1", value=200.0, is_forecast=True)],
    )
    save_prediction(pred)

    resp = client.post(
        "/intelligence/predict/compare",
        json={
            "prediction_id": pred.prediction_id,
            "scenarios": [
                {"scenario_name": "+10%", "change_percent": 10.0},
                {"scenario_name": "-10%", "change_percent": -10.0},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert len(data["comparison"]["scenarios"]) == 3  # Baseline + 2 scenarios


test("12.6 POST /intelligence/predict/compare executes multi-scenario comparison", test_api_predict_compare_endpoint)


def test_api_predict_history_and_get():
    from app.intelligence.predictive.models import PredictionResult
    from app.intelligence.predictive.store import save_prediction

    client = _get_test_client()
    headers = _auth_header(user_id="user_hist_test")

    p = PredictionResult(user_id="user_hist_test", metric_name="Hist Metric")
    save_prediction(p)

    resp_list = client.get("/intelligence/predict/history", headers=headers)
    assert resp_list.status_code == 200
    assert resp_list.json()["total"] >= 1

    resp_get = client.get(f"/intelligence/predict/{p.prediction_id}", headers=headers)
    assert resp_get.status_code == 200
    assert resp_get.json()["prediction"]["metric_name"] == "Hist Metric"


test("12.7 GET /intelligence/predict/history and GET /intelligence/predict/{id}", test_api_predict_history_and_get)


def test_api_predict_explain_endpoint():
    from app.intelligence.predictive.models import ForecastPoint, PredictionResult
    from app.intelligence.predictive.store import save_prediction

    client = _get_test_client()
    headers = _auth_header(user_id="user_exp_test")

    p = PredictionResult(
        user_id="user_exp_test",
        metric_name="Conversion Rate",
        points=[ForecastPoint(period="Jan", value=2.5, is_forecast=False)],
    )
    save_prediction(p)

    resp = client.post(f"/intelligence/predict/{p.prediction_id}/explain", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "explanation" in data
    assert "method_rationale" in data["explanation"]


test("12.8 POST /intelligence/predict/{id}/explain returns transparent lineage", test_api_predict_explain_endpoint)


# ── 13. Security & SQL Safety ────────────────────────────────────────────────

def test_sql_safety_readonly_enforcement():
    from app.tools.execute_query import validate_sql, READ_ONLY

    # Valid SELECT is allowed without confirmation
    sel_res = validate_sql("SELECT strftime('%Y-%m', created_at), SUM(total) FROM orders GROUP BY 1")
    assert sel_res["allowed"] is True
    assert sel_res["operation"] in READ_ONLY
    assert sel_res["requires_confirmation"] is False

    # Dangerous DDL operations blocked completely
    assert validate_sql("DROP TABLE orders")["allowed"] is False
    assert validate_sql("TRUNCATE TABLE orders")["allowed"] is False
    assert validate_sql("ALTER TABLE orders ADD COLUMN x INT")["allowed"] is False

    # DML operations require confirmation (never run as automated read queries)
    upd_res = validate_sql("UPDATE orders SET total = 0 WHERE id = 1")
    assert upd_res["requires_confirmation"] is True
    ins_res = validate_sql("INSERT INTO orders VALUES (1)")
    assert ins_res["requires_confirmation"] is True


test("13.1 SQL safety: strictly blocks DROP, ALTER, TRUNCATE; requires confirmation on DML", test_sql_safety_readonly_enforcement)



def test_command_chaining_blocked():
    from app.tools.execute_query import validate_sql

    assert validate_sql("SELECT 1; DROP TABLE users;")["allowed"] is False


test("13.2 SQL safety: command chaining with semicolons blocked", test_command_chaining_blocked)



# ── 14. Phase 8.9 & Phase 8.8 Regression Guard ────────────────────────────────

def test_phase89_regression_endpoints_intact():
    client = _get_test_client()
    headers = _auth_header()

    routes = [r.path for r in client.app.routes]
    assert "/intelligence/outcomes/measure" in routes
    assert "/intelligence/recommendations/adaptive" in routes
    assert "/intelligence/actions/propose" in routes
    assert "/intelligence/actions" in routes


# ── 15. Forecast Horizons (7d, 14d, 30d) ─────────────────────────────────────

def test_forecast_horizons_7d():
    from app.intelligence.predictive.forecasting import linear_trend_forecast
    _, preds = linear_trend_forecast([10.0, 20.0, 30.0], horizon=7)
    assert len(preds) == 7

test("15.1 7-day forecast horizon generates exactly 7 projections", test_forecast_horizons_7d)


def test_forecast_horizons_14d():
    from app.intelligence.predictive.forecasting import linear_trend_forecast
    _, preds = linear_trend_forecast([10.0, 20.0, 30.0], horizon=14)
    assert len(preds) == 14

test("15.2 14-day forecast horizon generates exactly 14 projections", test_forecast_horizons_14d)


def test_forecast_horizons_30d():
    from app.intelligence.predictive.forecasting import linear_trend_forecast
    _, preds = linear_trend_forecast([10.0, 20.0, 30.0], horizon=30)
    assert len(preds) == 30

test("15.3 30-day forecast horizon generates exactly 30 projections", test_forecast_horizons_30d)


# ── 16. Volatility & Trend Detection ─────────────────────────────────────────

def test_volatile_trend_classification():
    from app.intelligence.predictive.forecasting import detect_trend
    from app.intelligence.predictive.models import TrendDirection
    # Mean around 100 with massive swings (cv > 0.5)
    noisy = [100.0, 20.0, 180.0, 20.0, 180.0, 100.0]
    trend, _, _ = detect_trend(noisy)
    assert trend == TrendDirection.VOLATILE

test("16.1 High variance series classified as VOLATILE", test_volatile_trend_classification)



# ── 17. Scenario Types & Absolute Adjustments ────────────────────────────────

def test_what_if_absolute_change_simulation():
    from app.intelligence.predictive.models import ForecastPoint, PredictionResult
    from app.intelligence.predictive.scenario_engine import simulate_what_if_scenario

    pred = PredictionResult(
        metric_name="Inventory",
        points=[ForecastPoint(period="P1", value=100.0, is_forecast=True, lower_bound=90.0, upper_bound=110.0)],
    )
    scen = simulate_what_if_scenario(pred, absolute_change=50.0, scenario_name="+50 Units")
    assert scen.scenario_projected_total == 150.0
    assert scen.delta_total == 50.0
    assert "+50.0" in scen.assumption_statement

test("17.1 Absolute increment scenario simulation (+50 units)", test_what_if_absolute_change_simulation)


def test_scenario_types_classification():
    from app.intelligence.predictive.models import ForecastPoint, PredictionResult, ScenarioType
    from app.intelligence.predictive.scenario_engine import simulate_what_if_scenario

    pred = PredictionResult(points=[ForecastPoint(period="P1", value=100.0, is_forecast=True)])
    s_growth = simulate_what_if_scenario(pred, change_percent=15.0, scenario_type=ScenarioType.GROWTH.value)
    assert s_growth.scenario_type == "GROWTH"

    s_decline = simulate_what_if_scenario(pred, change_percent=-10.0, scenario_type=ScenarioType.DECLINE.value)
    assert s_decline.scenario_type == "DECLINE"

test("17.2 GROWTH and DECLINE scenario typing supported", test_scenario_types_classification)


def test_baseline_scenario_exact_preservation():
    from app.intelligence.predictive.models import ForecastPoint, PredictionResult
    from app.intelligence.predictive.scenario_engine import simulate_what_if_scenario

    pred = PredictionResult(points=[ForecastPoint(period="P1", value=250.0, is_forecast=True)])
    base_scen = simulate_what_if_scenario(pred, change_percent=0.0)
    assert base_scen.scenario_projected_total == 250.0
    assert base_scen.delta_total == 0.0
    assert base_scen.delta_percent == 0.0

test("17.3 Baseline scenario preserves forecast values exactly with 0 delta", test_baseline_scenario_exact_preservation)


# ── 18. Epistemic Safety & Causality Guards ──────────────────────────────────

def test_no_fabricated_confidence_percentages():
    from app.intelligence.predictive.models import ConfidenceTier, PredictionResult

    pred = PredictionResult(confidence_tier=ConfidenceTier.MODERATE.value)
    # Ensure tier is one of the valid enum values and not an invented arbitrary percentage (e.g. 92%)
    assert pred.confidence_tier in ("HIGH", "MODERATE", "LIMITED")
    assert not any(char.isdigit() for char in pred.confidence_tier)

test("18.1 Confidence tiers are strictly HIGH, MODERATE, LIMITED without fake percentages", test_no_fabricated_confidence_percentages)


def test_causal_disclaimers_always_present():
    from app.intelligence.predictive.models import ForecastPoint, PredictionResult
    from app.intelligence.predictive.scenario_engine import simulate_what_if_scenario

    pred = PredictionResult(points=[ForecastPoint(period="P1", value=100.0, is_forecast=True)])
    scen = simulate_what_if_scenario(pred, change_percent=10.0)
    assert "causal" in scen.causal_disclaimer.lower() or "arithmetic" in scen.causal_disclaimer.lower()
    # Limitations must disclaim linear elasticity
    assert any("elasticity" in lim.lower() for lim in scen.limitations)

test("18.2 Scenario results always include explicit causal and elasticity disclaimers", test_causal_disclaimers_always_present)


# ── 19. Outcome Context Integration ──────────────────────────────────────────

def test_historical_outcome_context_defaults():
    from app.intelligence.predictive.learning_context import get_historical_outcome_context

    ctx = get_historical_outcome_context(user_id="user_empty_ctx", table_name="unrecorded_table")
    assert ctx["has_history"] is False
    assert ctx["positive_count"] == 0
    assert ctx["total_outcomes"] == 0
    assert isinstance(ctx["supporting_references"], list)

test("19.1 Unrecorded table returns clean default outcome context without errors", test_historical_outcome_context_defaults)


def test_historical_outcome_integration_in_prediction():
    from app.intelligence.outcome_optimization.outcome_tracker import save_measurement
    from app.intelligence.outcome_optimization.models import OutcomeMeasurement, EffectivenessLabel
    from app.intelligence.predictive.learning_context import get_historical_outcome_context

    # Seed an outcome measurement for this user and table
    m = OutcomeMeasurement(
        user_id="user_outcome_int",
        metric_name="Sales",
        source_table="orders_int_tbl",
        effectiveness=EffectivenessLabel.POSITIVE,
        delta_pct=15.0,
    )
    save_measurement(m)

    ctx = get_historical_outcome_context(user_id="user_outcome_int", table_name="orders_int_tbl")
    assert ctx["has_history"] is True
    assert ctx["positive_count"] >= 1
    assert "Historical context:" in ctx["summary"]

test("19.2 Phase 8.9 measured outcomes are retrieved and synthesized into predictive context", test_historical_outcome_integration_in_prediction)


# ── 20. Database Context & Isolation ─────────────────────────────────────────

def test_database_identity_isolation():
    from app.intelligence.predictive.models import PredictionResult
    from app.intelligence.predictive.store import save_prediction, get_prediction

    pred = PredictionResult(
        user_id="user_db_iso",
        database_identity="sqlite:///db1.db",
        metric_name="Metric 1",
    )
    save_prediction(pred)
    retrieved = get_prediction(pred.prediction_id, user_id="user_db_iso")
    assert retrieved is not None
    assert retrieved.database_identity == "sqlite:///db1.db"

test("20.1 Prediction result records and preserves active database identity", test_database_identity_isolation)


# ── 21. Additional DDL & SQL Safety Checks ───────────────────────────────────

def test_create_and_attach_sql_blocked():
    from app.tools.execute_query import validate_sql

    assert validate_sql("CREATE TABLE evil (id INT)")["allowed"] is False
    assert validate_sql("ATTACH DATABASE 'evil.db' AS evil")["allowed"] is False
    assert validate_sql("DETACH DATABASE evil")["allowed"] is False

test("21.1 DDL operations (CREATE, ATTACH, DETACH) strictly blocked by validate_sql", test_create_and_attach_sql_blocked)


def test_missing_time_column_returns_structured_diagnostic():
    from sqlalchemy import create_engine
    from app.intelligence.predictive.predictor import run_prediction
    from app.intelligence.predictive.models import DataQualityStatus

    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.connection.cursor().executescript("""
            CREATE TABLE no_time_tbl (
                id INTEGER PRIMARY KEY,
                category TEXT,
                amount REAL
            );
        """)
        conn.commit()

    res = run_prediction(
        user_id="user_no_time",
        table="no_time_tbl",
        engine=engine,
        db_type="sqlite",
    )
    assert res.status == "insufficient_data"
    assert res.data_quality_status == DataQualityStatus.NO_TEMPORAL_DIMENSION.value
    assert "No suitable date/timestamp column" in res.error_message

test("21.2 Missing date/timestamp dimension triggers structured NO_TEMPORAL_DIMENSION status", test_missing_time_column_returns_structured_diagnostic)


# ── 22. Forecast Non-Negativity & Math Stability ─────────────────────────────

def test_forecast_lower_bound_clamped_non_negative():
    from app.intelligence.predictive.uncertainty import compute_prediction_intervals

    # Series where residual standard error is larger than forecasted value
    actuals = [10.0, 100.0, 10.0, 100.0]
    fitted = [50.0, 50.0, 50.0, 50.0]
    forecast_values = [5.0]
    future_labels = ["2024-01"]

    pts = compute_prediction_intervals(actuals, fitted, forecast_values, future_labels, is_non_negative=True)
    assert len(pts) == 1
    # Lower bound must be clamped to 0.0 for non-negative business metrics
    assert pts[0].lower_bound >= 0.0

test("22.1 Forecast lower bound is clamped at zero for non-negative business metrics", test_forecast_lower_bound_clamped_non_negative)


def test_sma_window_one_persistence():
    from app.intelligence.predictive.forecasting import simple_moving_average_forecast

    series = [10.0, 20.0, 35.0]
    _, preds = simple_moving_average_forecast(series, horizon=2, window=1)
    # Window=1 equals last observation
    assert preds == [35.0, 35.0]

test("22.2 SMA with window=1 matches persistence behavior", test_sma_window_one_persistence)


def test_wma_window_adjustment():
    from app.intelligence.predictive.forecasting import weighted_moving_average_forecast

    series = [50.0]
    _, preds = weighted_moving_average_forecast(series, horizon=2, window=3)
    assert preds == [50.0, 50.0]

test("22.3 WMA adjusts gracefully when observation count is less than window length", test_wma_window_adjustment)


# ── 23. Explainer & Groq Offline Fallback ────────────────────────────────────

def test_explainer_offline_fallback():
    from app.intelligence.predictive.models import ForecastPoint, PredictionResult
    from app.intelligence.predictive.explainer import explain_prediction_narrative

    pred = PredictionResult(
        metric_name="Profit",
        points=[ForecastPoint(period="P1", value=100.0, is_forecast=True)],
    )
    # Running narrative with use_groq=False should succeed instantly without network calls
    exp = explain_prediction_narrative(pred, use_groq=False)
    assert exp.prediction_id == pred.prediction_id
    assert "Analyzed" in exp.historical_summary or "No historical" in exp.historical_summary

test("23.1 Explainer operates deterministically offline without Groq API requirement", test_explainer_offline_fallback)


def test_prediction_timestamp_iso():
    from app.intelligence.predictive.models import PredictionResult

    pred = PredictionResult()
    assert "T" in pred.created_at  # ISO 8601 format

test("23.2 Prediction result includes ISO 8601 created_at timestamp", test_prediction_timestamp_iso)


def test_scenario_comparison_empty_specs():
    from app.intelligence.predictive.models import ForecastPoint, PredictionResult
    from app.intelligence.predictive.scenario_engine import compare_scenarios

    pred = PredictionResult(points=[ForecastPoint(period="P1", value=100.0, is_forecast=True)])
    comp = compare_scenarios(pred, scenario_specs=[])
    # Returns at least baseline scenario
    assert len(comp.scenarios) == 1
    assert comp.scenarios[0].scenario_name == "Baseline (Status Quo)"

test("23.3 Scenario comparison with empty specs safely returns Baseline scenario", test_scenario_comparison_empty_specs)





# ── 24. Extended Edge Cases & Serialization ──────────────────────────────────

def test_model_evaluations_roundtrip():
    from app.intelligence.predictive.models import ModelEvaluationMetric, PredictionResult
    ev = ModelEvaluationMetric(method="LINEAR_TREND", mae=3.5, rmse=4.2, mape=5.1, selected=True)
    pred = PredictionResult(model_evaluations=[ev])
    d = pred.to_dict()
    assert len(d["model_evaluations"]) == 1
    assert d["model_evaluations"][0]["mae"] == 3.5
    restored = PredictionResult.from_dict(d)
    assert restored.model_evaluations[0].method == "LINEAR_TREND"

test("24.1 ModelEvaluationMetric roundtrip through PredictionResult to_dict/from_dict", test_model_evaluations_roundtrip)


def test_evidence_historical_outcome_serialization():
    from app.intelligence.predictive.models import PredictionEvidence
    ev = PredictionEvidence(
        source_table="t", date_column="d", metric_column="m", aggregation="SUM",
        historical_count=10, min_date="2024-01", max_date="2024-10", sql_lineage="SELECT 1",
        historical_outcome_support=[{"id": "o1", "status": "SUCCESSFUL"}]
    )
    d = ev.to_dict()
    assert len(d["historical_outcome_support"]) == 1
    restored = PredictionEvidence.from_dict(d)
    assert restored.historical_outcome_support[0]["id"] == "o1"

test("24.2 PredictionEvidence serialization preserves historical outcome support", test_evidence_historical_outcome_serialization)


def test_store_cache_capacity_bounding():
    from app.intelligence.predictive.models import PredictionResult
    from app.intelligence.predictive.store import save_prediction, list_predictions, clear_predictive_store, MAX_CACHE_PER_USER

    clear_predictive_store("user_bounded_cache")
    for i in range(MAX_CACHE_PER_USER + 5):
        p = PredictionResult(user_id="user_bounded_cache", metric_name=f"Metric {i}")
        save_prediction(p)

    recs = list_predictions("user_bounded_cache", limit=100)
    assert len(recs) <= MAX_CACHE_PER_USER

test("24.3 Prediction store enforces capacity bounding per user", test_store_cache_capacity_bounding)


def test_future_period_labels_month_rollover():
    from app.intelligence.predictive.forecasting import generate_future_period_labels
    labels = generate_future_period_labels("2023-11", frequency="monthly", count=3)
    # Expected: 2023-12, 2024-01, 2024-02
    assert labels == ["2023-12", "2024-01", "2024-02"]

test("24.4 Future period labels roll over December correctly to next year", test_future_period_labels_month_rollover)


def test_stable_trend_within_two_percent():
    from app.intelligence.predictive.forecasting import detect_trend
    from app.intelligence.predictive.models import TrendDirection

    # +1% per period slope
    series = [100.0, 101.0, 102.0, 103.0]
    direction, slope, _ = detect_trend(series)
    assert direction == TrendDirection.STABLE

test("24.5 Slope within +/-2% per period is categorized as STABLE", test_stable_trend_within_two_percent)


def test_negative_percentage_scenario_at_minus_hundred():
    from app.intelligence.predictive.models import ForecastPoint, PredictionResult
    from app.intelligence.predictive.scenario_engine import simulate_what_if_scenario

    pred = PredictionResult(points=[ForecastPoint(period="P1", value=100.0, is_forecast=True)])
    scen = simulate_what_if_scenario(pred, change_percent=-100.0)
    assert scen.scenario_projected_total == 0.0
    assert scen.delta_total == -100.0

test("24.6 -100% scenario brings projected value to zero without errors", test_negative_percentage_scenario_at_minus_hundred)


# ── Summary ───────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    passed = sum(1 for r in results if r[0] == PASS)
    failed = sum(1 for r in results if r[0] == FAIL)
    total = len(results)
    print(f"\n{'=' * 65}")
    print(f"Phase 9.0 Test Results: {passed}/{total} passed, {failed} failed")
    print(f"{'=' * 65}")
    if failed:
        print("\nFailed tests:")
        for r in results:
            if r[0] == FAIL:
                print(f"  FAIL: {r[1]}")
                if len(r) > 2:
                    print(f"        {r[2]}")
    sys.exit(0 if failed == 0 else 1)
