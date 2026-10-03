"""
backend/app/intelligence/predictive/scenario_engine.py

Phase 9.0: What-If Scenario Simulation & Comparison Engine
Simulates statistical baseline forecasts under explicit parameterized conditions
(percentage change, absolute increment, growth, decline).

Strict Epistemic Principles:
- Distinguishes scenario arithmetic from empirical causality.
- Explicitly states: mathematical projection under hypothetical assumptions does not
  prove real-world market elasticity or causal effect.
- Validates and clamps extreme or invalid inputs.
- Never designates a subjective "winner" in scenario comparisons.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.intelligence.predictive.models import (
    ForecastPoint,
    PredictionResult,
    ScenarioComparison,
    ScenarioResult,
    ScenarioType,
)

logger = logging.getLogger("bgai.predictive.scenario_engine")

MAX_PERCENT_CHANGE = 1000.0  # +1000%
MIN_PERCENT_CHANGE = -100.0  # -100% (cannot drop below zero for non-negative metrics)


def simulate_what_if_scenario(
    baseline_result: PredictionResult,
    change_percent: Optional[float] = None,
    absolute_change: Optional[float] = None,
    scenario_name: Optional[str] = None,
    scenario_type: str = ScenarioType.CUSTOM.value,
) -> ScenarioResult:
    """
    Applies explicit mathematical transformation to a baseline forecast series.
    """
    # 1. Validation
    if change_percent is not None:
        if change_percent < MIN_PERCENT_CHANGE:
            raise ValueError(f"Change percent cannot be less than {MIN_PERCENT_CHANGE}%.")
        if change_percent > MAX_PERCENT_CHANGE:
            raise ValueError(f"Change percent cannot exceed +{MAX_PERCENT_CHANGE}%.")

    if change_percent is None and absolute_change is None:
        change_percent = 0.0
        scenario_type = ScenarioType.BASELINE.value

    # Determine scenario title
    if not scenario_name:
        if change_percent is not None and change_percent != 0.0:
            sign = "+" if change_percent > 0 else ""
            scenario_name = f"Scenario {sign}{change_percent}%"
        elif absolute_change is not None and absolute_change != 0.0:
            sign = "+" if absolute_change > 0 else ""
            scenario_name = f"Scenario {sign}{absolute_change}"
        else:
            scenario_name = "Baseline Scenario"

    # Separate forecast points from historical points
    forecast_points = [p for p in baseline_result.points if p.is_forecast]
    if not forecast_points:
        # If no forecast points exist, return empty scenario
        return ScenarioResult(
            prediction_id=baseline_result.prediction_id,
            scenario_name=scenario_name,
            scenario_type=scenario_type,
            change_percent=change_percent,
            absolute_change=absolute_change,
            baseline_projected_total=0.0,
            scenario_projected_total=0.0,
            delta_total=0.0,
            delta_percent=0.0,
            scenario_points=[],
            assumption_statement="No forecast points available to simulate.",
        )

    baseline_total = sum(p.value for p in forecast_points)

    scenario_points: list[ForecastPoint] = []
    for p in forecast_points:
        orig_val = p.value
        if change_percent is not None:
            new_val = orig_val * (1.0 + (change_percent / 100.0))
            ratio = 1.0 + (change_percent / 100.0)
            low = (p.lower_bound * ratio) if p.lower_bound is not None else None
            high = (p.upper_bound * ratio) if p.upper_bound is not None else None
        else:
            new_val = orig_val + (absolute_change or 0.0)
            low = (p.lower_bound + (absolute_change or 0.0)) if p.lower_bound is not None else None
            high = (p.upper_bound + (absolute_change or 0.0)) if p.upper_bound is not None else None

        # Clamp lower bound to 0 for non-negative metrics
        new_val = max(0.0, round(new_val, 2))
        low = max(0.0, round(low, 2)) if low is not None else None
        high = max(0.0, round(high, 2)) if high is not None else None

        uncertainty_w = (high - low) if (high is not None and low is not None) else None

        scenario_points.append(
            ForecastPoint(
                period=p.period,
                value=new_val,
                is_forecast=True,
                lower_bound=low,
                upper_bound=high,
                uncertainty_width=round(uncertainty_w, 2) if uncertainty_w is not None else None,
            )
        )

    scenario_total = sum(p.value for p in scenario_points)
    delta_total = scenario_total - baseline_total
    delta_percent = (delta_total / baseline_total * 100.0) if baseline_total > 1e-6 else 0.0

    # Build clear assumption description
    if change_percent is not None:
        sign = "+" if change_percent > 0 else ""
        assumption = (
            f"Assumes an explicit simulated parameter adjustment of {sign}{change_percent}% "
            f"applied uniformly across {len(forecast_points)} forecast periods."
        )
    else:
        sign = "+" if (absolute_change or 0) > 0 else ""
        assumption = (
            f"Assumes an explicit simulated increment of {sign}{absolute_change} "
            f"per period across {len(forecast_points)} forecast periods."
        )

    limitations = [
        "Scenario projection assumes linear elasticity; actual business response may deviate.",
        "External market dynamics, competitive actions, or capacity constraints are not modeled.",
    ]

    return ScenarioResult(
        prediction_id=baseline_result.prediction_id,
        scenario_name=scenario_name,
        scenario_type=scenario_type,
        change_percent=change_percent,
        absolute_change=absolute_change,
        baseline_projected_total=round(baseline_total, 2),
        scenario_projected_total=round(scenario_total, 2),
        delta_total=round(delta_total, 2),
        delta_percent=round(delta_percent, 2),
        scenario_points=scenario_points,
        assumption_statement=assumption,
        limitations=limitations,
    )


def compare_scenarios(
    baseline_result: PredictionResult, scenario_specs: list[dict[str, Any]]
) -> ScenarioComparison:
    """
    Executes multiple scenarios and builds a side-by-side comparative analysis.
    """
    scenarios: list[ScenarioResult] = []

    # Always include baseline as first scenario
    baseline_scen = simulate_what_if_scenario(
        baseline_result=baseline_result,
        change_percent=0.0,
        scenario_name="Baseline (Status Quo)",
        scenario_type=ScenarioType.BASELINE.value,
    )
    scenarios.append(baseline_scen)

    for spec in scenario_specs:
        try:
            scen = simulate_what_if_scenario(
                baseline_result=baseline_result,
                change_percent=spec.get("change_percent"),
                absolute_change=spec.get("absolute_change"),
                scenario_name=spec.get("scenario_name"),
                scenario_type=spec.get("scenario_type", ScenarioType.CUSTOM.value),
            )
            scenarios.append(scen)
        except Exception as e:
            logger.warning("Error simulating scenario %s: %s", spec.get("scenario_name"), str(e))

    forecast_points = [p for p in baseline_result.points if p.is_forecast]
    baseline_total = sum(p.value for p in forecast_points)

    summary_table = []
    for s in scenarios:
        summary_table.append({
            "scenario_name": s.scenario_name,
            "type": s.scenario_type,
            "projected_total": s.scenario_projected_total,
            "delta_from_baseline": s.delta_total,
            "delta_percent": s.delta_percent,
            "assumption": s.assumption_statement,
        })

    return ScenarioComparison(
        metric_name=baseline_result.metric_name,
        forecast_horizon_days=baseline_result.forecast_horizon_days,
        baseline_total=round(baseline_total, 2),
        scenarios=scenarios,
        summary_table=summary_table,
    )
