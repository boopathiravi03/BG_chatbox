"""
backend/app/intelligence/decision/__init__.py

Phase 8.4: AI Decision & Planning Intelligence
Provides evidence-backed decision planning synthesizing multi-source database intelligence.
"""
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
    run_decision_analysis,
)
from app.intelligence.decision.evidence import aggregate_multi_source_evidence
from app.intelligence.decision.confidence import assess_confidence
from app.intelligence.decision.planner import generate_decision_plan_and_investigations

__all__ = [
    "EvidenceItem",
    "Finding",
    "Hypothesis",
    "RecommendedInvestigation",
    "PlanStep",
    "ConfidenceAssessment",
    "DecisionQuestion",
    "DecisionAnalysis",
    "understand_question",
    "synthesize_decision_analysis",
    "run_decision_analysis",

    "aggregate_multi_source_evidence",
    "assess_confidence",
    "generate_decision_plan_and_investigations",
]
