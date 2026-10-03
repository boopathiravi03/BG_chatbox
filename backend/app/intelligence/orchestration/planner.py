"""
backend/app/intelligence/orchestration/planner.py

Deterministic goal intent decomposition and DAG plan generator for Phase 9.2.
Selects minimal sufficient specialist agents based on verified data requirements.
Prevents over-orchestration and enforces acyclic dependency topologies.
"""

from __future__ import annotations

import uuid
import re
from typing import Dict, Any, List, Optional
from app.intelligence.orchestration.models import (
    TaskGraph,
    PlanStep,
    TaskStepStatus,
)


class OrchestrationPlanner:
    """
    Analyzes user goals and plans minimal sufficient DAGs of specialist agents.
    """

    def plan(self, goal: str, context: Optional[Dict[str, Any]] = None) -> TaskGraph:
        """
        Decomposes user goal into a structured TaskGraph.
        """
        cleaned_goal = (goal or "").strip()
        lower_goal = cleaned_goal.lower()
        graph_id = f"graph_{uuid.uuid4().hex[:8]}"

        # Intent heuristic detection
        is_investigation = any(kw in lower_goal for kw in [
            "why", "root cause", "decrease", "drop", "spike", "investigate", "anomaly", "decline", "fall", "loss"
        ])
        is_predictive = any(kw in lower_goal for kw in [
            "predict", "forecast", "future", "simulate", "what if", "scenario", "next month", "trend"
        ])
        is_action = any(kw in lower_goal for kw in [
            "action", "fix", "mitigate", "optimize", "resolve", "update", "apply", "clean"
        ])
        is_monitoring = any(kw in lower_goal for kw in [
            "health", "monitor", "alert", "status", "system check", "overview"
        ])

        steps: List[PlanStep] = []

        if is_investigation:
            # Investigation Flow: Knowledge -> BI -> Investigation -> Decision
            s1 = PlanStep(
                step_id="step_1",
                agent_id="knowledge_agent",
                name="Resolve Business Context",
                purpose="Resolve metric definitions and business entity rules relevant to the signal.",
                dependencies=[],
                inputs={"query": cleaned_goal},
            )
            s2 = PlanStep(
                step_id="step_2",
                agent_id="bi_agent",
                name="Discover Correlated Insights",
                purpose="Compute single and multi-table business metrics related to the investigated anomaly.",
                dependencies=["step_1"],
                inputs={"query": cleaned_goal},
            )
            s3 = PlanStep(
                step_id="step_3",
                agent_id="investigation_agent",
                name="Decompose Root Causes",
                purpose="Formulate causal hypotheses and isolate primary contributing factors.",
                dependencies=["step_2"],
                inputs={"signal": cleaned_goal},
            )
            s4 = PlanStep(
                step_id="step_4",
                agent_id="decision_agent",
                name="Synthesize Findings",
                purpose="Evaluate strategic options and trade-offs based on the investigated evidence.",
                dependencies=["step_3"],
                inputs={"goal": cleaned_goal},
            )
            steps = [s1, s2, s3, s4]

        elif is_predictive:
            # Predictive Flow: Knowledge -> Prediction -> Decision
            s1 = PlanStep(
                step_id="step_1",
                agent_id="knowledge_agent",
                name="Verify Metric Semantics",
                purpose="Ensure target prediction metrics have verified database bindings.",
                dependencies=[],
                inputs={"query": cleaned_goal},
            )
            s2 = PlanStep(
                step_id="step_2",
                agent_id="prediction_agent",
                name="Compute Forecast & Scenarios",
                purpose="Project future metric values with uncertainty bands and scenario simulations.",
                dependencies=["step_1"],
                inputs={"metric": "revenue", "horizon_steps": 6},
            )
            s3 = PlanStep(
                step_id="step_3",
                agent_id="decision_agent",
                name="Evaluate Scenario Trade-offs",
                purpose="Assess confidence and risk trade-offs under simulated scenarios.",
                dependencies=["step_2"],
                inputs={"goal": cleaned_goal},
            )
            steps = [s1, s2, s3]

        elif is_action:
            # Action Flow: Knowledge -> Investigation -> Action Proposal
            s1 = PlanStep(
                step_id="step_1",
                agent_id="knowledge_agent",
                name="Validate Action Boundaries",
                purpose="Check entity constraints and confirmed business rules before proposing modifications.",
                dependencies=[],
                inputs={"query": cleaned_goal},
            )
            s2 = PlanStep(
                step_id="step_2",
                agent_id="investigation_agent",
                name="Isolate Scope & Factors",
                purpose="Identify affected tables, records, and specific root causes.",
                dependencies=["step_1"],
                inputs={"signal": cleaned_goal},
            )
            s3 = PlanStep(
                step_id="step_3",
                agent_id="action_agent",
                name="Generate Action Proposal & Preview",
                purpose="Draft a controlled business action with impact preview, awaiting confirmation.",
                dependencies=["step_2"],
                inputs={"title": cleaned_goal, "action_type": "OPERATIONAL_MITIGATION"},
            )
            steps = [s1, s2, s3]

        elif is_monitoring:
            # Monitoring Flow: Monitoring -> BI
            s1 = PlanStep(
                step_id="step_1",
                agent_id="monitoring_agent",
                name="Check Health & Active Alerts",
                purpose="Evaluate database health score and active anomaly alerts.",
                dependencies=[],
                inputs={},
            )
            s2 = PlanStep(
                step_id="step_2",
                agent_id="bi_agent",
                name="Assess Recent Metric Trends",
                purpose="Correlate active alerts with current business metric performance.",
                dependencies=["step_1"],
                inputs={"query": cleaned_goal},
            )
            steps = [s1, s2]

        else:
            # General Orchestration Flow: Knowledge -> (BI + Analyst in parallel) -> Decision
            s1 = PlanStep(
                step_id="step_1",
                agent_id="knowledge_agent",
                name="Resolve Business Context",
                purpose="Resolve business entities and metric definitions.",
                dependencies=[],
                inputs={"query": cleaned_goal},
            )
            s2 = PlanStep(
                step_id="step_2",
                agent_id="bi_agent",
                name="Analyze Business Metrics",
                purpose="Compute verified business insights across tables.",
                dependencies=["step_1"],
                inputs={"query": cleaned_goal},
            )
            s3 = PlanStep(
                step_id="step_3",
                agent_id="data_analyst_agent",
                name="Inspect Table Profiling",
                purpose="Perform schema exploration and row distribution analysis.",
                dependencies=["step_1"],
                inputs={},
            )
            s4 = PlanStep(
                step_id="step_4",
                agent_id="decision_agent",
                name="Synthesize Strategic Summary",
                purpose="Synthesize BI findings and table stats into clear strategic recommendations.",
                dependencies=["step_2", "step_3"],
                inputs={"goal": cleaned_goal},
            )
            steps = [s1, s2, s3, s4]

        # Populate entry/exit steps
        entry_steps = [s.step_id for s in steps if not s.dependencies]
        all_deps = set()
        for s in steps:
            all_deps.update(s.dependencies)
        exit_steps = [s.step_id for s in steps if s.step_id not in all_deps]

        return TaskGraph(
            graph_id=graph_id,
            steps=steps,
            entry_steps=entry_steps,
            exit_steps=exit_steps,
            max_depth=len(steps),
            total_steps=len(steps),
        )
