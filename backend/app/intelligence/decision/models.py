"""
backend/app/intelligence/decision/models.py

Phase 8.4: AI Decision & Planning Intelligence Data Models
Defines strongly typed models for decision questions, multi-source evidence,
findings, hypotheses, decision plan steps, confidence assessments, and the
overall decision analysis.

Strict Epistemic Hygiene:
- Distinguishes observed facts from unconfirmed hypotheses.
- Transparent confidence levels without arbitrary AI percentages.
- Zero raw row PII, credentials, or tokens stored.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Optional


@dataclass
class EvidenceItem:
    """
    A verifiable, deterministic measurement collected from connected database sources
    (BI Engine, Cross-Table BI, Anomalies, Forecasts, Proactive Alerts).
    """
    metric: str
    title: str
    current_value: Any
    evidence_id: str = field(default_factory=lambda: f"evi_{uuid.uuid4().hex[:8]}")
    previous_value: Optional[Any] = None
    delta: Optional[float] = None
    delta_percent: Optional[float] = None
    source_tables: list[str] = field(default_factory=list)
    source_columns: list[str] = field(default_factory=list)
    sql: Optional[str] = None
    calculation: str = ""
    source_system: str = "DATABASE"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceItem:
        return cls(
            metric=data["metric"],
            title=data.get("title", data["metric"]),
            current_value=data.get("current_value"),
            evidence_id=data.get("evidence_id", f"evi_{uuid.uuid4().hex[:8]}"),
            previous_value=data.get("previous_value"),
            delta=float(data["delta"]) if data.get("delta") is not None else None,
            delta_percent=float(data["delta_percent"]) if data.get("delta_percent") is not None else None,
            source_tables=list(data.get("source_tables") or []),
            source_columns=list(data.get("source_columns") or []),
            sql=data.get("sql"),
            calculation=data.get("calculation", ""),
            source_system=data.get("source_system", "DATABASE"),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class Finding:
    """
    An observed factual conclusion derived directly from supporting evidence items.
    """
    statement: str
    finding_id: str = field(default_factory=lambda: f"fnd_{uuid.uuid4().hex[:8]}")
    evidence_ids: list[str] = field(default_factory=list)
    severity: str = "INFO"  # "CRITICAL", "WARNING", "INFO"
    category: str = "GENERAL"  # "REVENUE", "ORDERS", "QUALITY", "ANOMALY", "INVENTORY", "GENERAL"
    source_tables: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Finding:
        return cls(
            statement=data["statement"],
            finding_id=data.get("finding_id", f"fnd_{uuid.uuid4().hex[:8]}"),
            evidence_ids=list(data.get("evidence_ids") or []),
            severity=data.get("severity", "INFO"),
            category=data.get("category", "GENERAL"),
            source_tables=list(data.get("source_tables") or []),
        )


@dataclass
class Hypothesis:
    """
    A plausible contributing factor or explanation for observed findings.
    Strict Epistemic Principle: A hypothesis is an unconfirmed candidate factor,
    never asserted as a definitive cause without causal proof.
    """
    statement: str
    hypothesis_id: str = field(default_factory=lambda: f"hyp_{uuid.uuid4().hex[:8]}")
    status: str = "UNCONFIRMED_HYPOTHESIS"
    supporting_evidence_ids: list[str] = field(default_factory=list)
    likelihood: str = "POSSIBLE"  # "PROBABLE", "POSSIBLE", "UNCERTAIN"
    causality_caveat: str = (
        "Hypothesis requires targeted empirical verification. "
        "Observed correlation does not establish direct causation."
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Hypothesis:
        return cls(
            statement=data["statement"],
            hypothesis_id=data.get("hypothesis_id", f"hyp_{uuid.uuid4().hex[:8]}"),
            status=data.get("status", "UNCONFIRMED_HYPOTHESIS"),
            supporting_evidence_ids=list(data.get("supporting_evidence_ids") or []),
            likelihood=data.get("likelihood", "POSSIBLE"),
            causality_caveat=data.get(
                "causality_caveat",
                "Hypothesis requires targeted empirical verification. "
                "Observed correlation does not establish direct causation.",
            ),
        )


@dataclass
class RecommendedInvestigation:
    """
    A targeted, non-destructive exploratory investigation to test hypotheses.
    """
    title: str
    rationale: str
    investigation_id: str = field(default_factory=lambda: f"inv_{uuid.uuid4().hex[:8]}")
    target_table: Optional[str] = None
    suggested_focus: Optional[str] = None
    priority: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecommendedInvestigation:
        return cls(
            title=data["title"],
            rationale=data.get("rationale", ""),
            investigation_id=data.get("investigation_id", f"inv_{uuid.uuid4().hex[:8]}"),
            target_table=data.get("target_table"),
            suggested_focus=data.get("suggested_focus"),
            priority=int(data.get("priority", 1)),
        )


@dataclass
class PlanStep:
    """
    A sequential, prioritized step in the generated decision plan.
    Preserves human confirmation for any actionable remediation.
    """
    step_number: int
    title: str
    description: str
    action_type: str = "INVESTIGATE"  # "INVESTIGATE", "AUDIT", "COMPARE", "REMEDIATE"
    target_table: Optional[str] = None
    requires_confirmation: bool = True
    safe_action_eligible: bool = False
    suggested_action_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlanStep:
        return cls(
            step_number=int(data["step_number"]),
            title=data["title"],
            description=data["description"],
            action_type=data.get("action_type", "INVESTIGATE"),
            target_table=data.get("target_table"),
            requires_confirmation=bool(data.get("requires_confirmation", True)),
            safe_action_eligible=bool(data.get("safe_action_eligible", False)),
            suggested_action_id=data.get("suggested_action_id"),
        )


@dataclass
class ConfidenceAssessment:
    """
    Transparent, verifiable confidence scoring.
    Derived strictly from verified signal counts and independent source diversity.
    """
    level: str  # "HIGH", "MODERATE", "LIMITED"
    signal_count: int
    corroborating_sources: list[str]
    rationale: str
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConfidenceAssessment:
        return cls(
            level=data["level"],
            signal_count=int(data["signal_count"]),
            corroborating_sources=list(data.get("corroborating_sources") or []),
            rationale=data["rationale"],
            limitations=list(data.get("limitations") or []),
        )


@dataclass
class DecisionQuestion:
    """
    Parsed representation of the user's strategic decision question.
    """
    raw_question: str
    intent: str  # "REVENUE_DECLINE", "ORDER_CANCELLATION", "PRODUCT_PERFORMANCE", "RECENT_CHANGES", "BUSINESS_RISK", "GENERAL_DECISION"
    target_entities: list[str] = field(default_factory=list)
    focus_metric: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DecisionAnalysis:
    """
    Complete evidence-backed decision intelligence analysis.
    """
    question: str
    intent: str
    problem_statement: str
    analysis_id: str = field(default_factory=lambda: f"dec_{uuid.uuid4().hex[:8]}")
    findings: list[Finding] = field(default_factory=list)
    evidence: list[EvidenceItem] = field(default_factory=list)
    hypotheses: list[Hypothesis] = field(default_factory=list)
    recommended_investigations: list[RecommendedInvestigation] = field(default_factory=list)
    decision_plan: list[PlanStep] = field(default_factory=list)
    confidence: Optional[ConfidenceAssessment] = None
    source_tables: list[str] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    database_name: str = "none"
    database_type: str = "none"
    status: str = "success"

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        if self.confidence:
            res["confidence"] = self.confidence.to_dict()
        res["status"] = self.status
        return res

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DecisionAnalysis:
        conf_data = data.get("confidence")
        conf_obj = ConfidenceAssessment.from_dict(conf_data) if conf_data else None
        return cls(
            question=data["question"],
            intent=data["intent"],
            problem_statement=data["problem_statement"],
            analysis_id=data.get("analysis_id", f"dec_{uuid.uuid4().hex[:8]}"),
            findings=[Finding.from_dict(f) for f in data.get("findings", [])],
            evidence=[EvidenceItem.from_dict(e) for e in data.get("evidence", [])],
            hypotheses=[Hypothesis.from_dict(h) for h in data.get("hypotheses", [])],
            recommended_investigations=[
                RecommendedInvestigation.from_dict(r) for r in data.get("recommended_investigations", [])
            ],
            decision_plan=[PlanStep.from_dict(p) for p in data.get("decision_plan", [])],
            confidence=conf_obj,
            source_tables=list(data.get("source_tables") or []),
            generated_at=data.get("generated_at", datetime.utcnow().isoformat()),
            database_name=data.get("database_name", "none"),
            database_type=data.get("database_type", "none"),
            status=data.get("status", "success"),
        )

