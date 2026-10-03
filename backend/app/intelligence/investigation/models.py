"""
backend/app/intelligence/investigation/models.py

Phase 8.7: Root-Cause & Investigation Intelligence Data Models
Defines structured, strongly typed data contracts for root-cause investigations.

Distinguishes:
OBSERVED FACT -> EVIDENCE -> CONTRIBUTING FACTOR -> HYPOTHESIS -> RECOMMENDED INVESTIGATION
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LIMITED = "LIMITED"


@dataclass
class ObservedChange:
    """The headline quantitative change or anomaly being investigated."""
    metric: str
    current_value: Any
    previous_value: Any
    delta: Optional[float] = None
    delta_percent: Optional[float] = None
    time_period: str = ""
    formatted_change: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "current_value": self.current_value,
            "previous_value": self.previous_value,
            "delta": self.delta,
            "delta_percent": self.delta_percent,
            "time_period": self.time_period,
            "formatted_change": self.formatted_change,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ObservedChange":
        return cls(
            metric=d.get("metric", ""),
            current_value=d.get("current_value"),
            previous_value=d.get("previous_value"),
            delta=d.get("delta"),
            delta_percent=d.get("delta_percent"),
            time_period=d.get("time_period", ""),
            formatted_change=d.get("formatted_change", ""),
        )


@dataclass
class EvidenceItem:
    """A single verifiable database measurement with lineage and calculation description."""
    evidence_id: str
    metric: str
    current_value: Any
    previous_value: Any
    delta: Optional[float] = None
    delta_percent: Optional[float] = None
    time_range: str = ""
    source_table: str = ""
    source_columns: list[str] = field(default_factory=list)
    record_count: Optional[int] = None
    sql_lineage: str = ""
    calculation_description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "metric": self.metric,
            "current_value": self.current_value,
            "previous_value": self.previous_value,
            "delta": self.delta,
            "delta_percent": self.delta_percent,
            "time_range": self.time_range,
            "source_table": self.source_table,
            "source_columns": list(self.source_columns),
            "record_count": self.record_count,
            "sql_lineage": self.sql_lineage,
            "calculation_description": self.calculation_description,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EvidenceItem":
        return cls(
            evidence_id=d.get("evidence_id", ""),
            metric=d.get("metric", ""),
            current_value=d.get("current_value"),
            previous_value=d.get("previous_value"),
            delta=d.get("delta"),
            delta_percent=d.get("delta_percent"),
            time_range=d.get("time_range", ""),
            source_table=d.get("source_table", ""),
            source_columns=d.get("source_columns", []),
            record_count=d.get("record_count"),
            sql_lineage=d.get("sql_lineage", ""),
            calculation_description=d.get("calculation_description", ""),
        )


@dataclass
class ContributingFactor:
    """An observed dimensional shift or concentration factor associated with the change."""
    factor_id: str
    dimension: str
    dimension_value: str
    impact_type: str  # "negative" | "positive" | "neutral"
    contribution_percent: Optional[float] = None
    observed_change: str = ""
    evidence_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "factor_id": self.factor_id,
            "dimension": self.dimension,
            "dimension_value": self.dimension_value,
            "impact_type": self.impact_type,
            "contribution_percent": self.contribution_percent,
            "observed_change": self.observed_change,
            "evidence_ids": list(self.evidence_ids),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ContributingFactor":
        return cls(
            factor_id=d.get("factor_id", ""),
            dimension=d.get("dimension", ""),
            dimension_value=d.get("dimension_value", ""),
            impact_type=d.get("impact_type", "neutral"),
            contribution_percent=d.get("contribution_percent"),
            observed_change=d.get("observed_change", ""),
            evidence_ids=d.get("evidence_ids", []),
        )


@dataclass
class Hypothesis:
    """An evidence-backed explanation candidate. Always flagged unconfirmed."""
    hypothesis_id: str
    statement: str
    supporting_evidence_ids: list[str] = field(default_factory=list)
    contradicting_evidence_ids: list[str] = field(default_factory=list)
    confidence_level: ConfidenceLevel = ConfidenceLevel.MODERATE
    status: str = "unconfirmed"  # Always unconfirmed; correlation != causation
    causality_caveat: str = "Correlation does not establish causation."

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "statement": self.statement,
            "supporting_evidence_ids": list(self.supporting_evidence_ids),
            "contradicting_evidence_ids": list(self.contradicting_evidence_ids),
            "confidence_level": self.confidence_level.value if isinstance(self.confidence_level, ConfidenceLevel) else self.confidence_level,
            "status": self.status,
            "causality_caveat": self.causality_caveat,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Hypothesis":
        conf_raw = d.get("confidence_level", "MODERATE")
        try:
            conf = ConfidenceLevel(conf_raw)
        except ValueError:
            conf = ConfidenceLevel.MODERATE

        return cls(
            hypothesis_id=d.get("hypothesis_id", ""),
            statement=d.get("statement", ""),
            supporting_evidence_ids=d.get("supporting_evidence_ids", []),
            contradicting_evidence_ids=d.get("contradicting_evidence_ids", []),
            confidence_level=conf,
            status=d.get("status", "unconfirmed"),
            causality_caveat=d.get("causality_caveat", "Correlation does not establish causation."),
        )


@dataclass
class InvestigationRecommendation:
    """A recommended next investigation step grounded in real schema structure."""
    recommendation_id: str
    action_title: str
    reason: str
    target_data: str
    expected_information_gained: str
    priority: str = "medium"  # "high" | "medium" | "low"

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "action_title": self.action_title,
            "reason": self.reason,
            "target_data": self.target_data,
            "expected_information_gained": self.expected_information_gained,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "InvestigationRecommendation":
        return cls(
            recommendation_id=d.get("recommendation_id", ""),
            action_title=d.get("action_title", ""),
            reason=d.get("reason", ""),
            target_data=d.get("target_data", ""),
            expected_information_gained=d.get("expected_information_gained", ""),
            priority=d.get("priority", "medium"),
        )


@dataclass
class ConfidenceAssessment:
    """Non-arbitrary confidence evaluation based on signal counts and corroborating sources."""
    level: ConfidenceLevel
    score_rationale: str
    supporting_signals_count: int
    independent_sources_count: int
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level.value if isinstance(self.level, ConfidenceLevel) else self.level,
            "score_rationale": self.score_rationale,
            "supporting_signals_count": self.supporting_signals_count,
            "independent_sources_count": self.independent_sources_count,
            "limitations": list(self.limitations),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ConfidenceAssessment":
        lvl_raw = d.get("level", "MODERATE")
        try:
            lvl = ConfidenceLevel(lvl_raw)
        except ValueError:
            lvl = ConfidenceLevel.MODERATE

        return cls(
            level=lvl,
            score_rationale=d.get("score_rationale", ""),
            supporting_signals_count=d.get("supporting_signals_count", 0),
            independent_sources_count=d.get("independent_sources_count", 0),
            limitations=d.get("limitations", []),
        )


@dataclass
class InvestigationLineage:
    """Lineage tracing how evidence was computed from the connected database."""
    source_tables: list[str] = field(default_factory=list)
    join_path: str = ""
    columns_analyzed: list[str] = field(default_factory=list)
    calculations: list[str] = field(default_factory=list)
    comparison_periods: list[str] = field(default_factory=list)
    record_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_tables": list(self.source_tables),
            "join_path": self.join_path,
            "columns_analyzed": list(self.columns_analyzed),
            "calculations": list(self.calculations),
            "comparison_periods": list(self.comparison_periods),
            "record_counts": dict(self.record_counts),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "InvestigationLineage":
        return cls(
            source_tables=d.get("source_tables", []),
            join_path=d.get("join_path", ""),
            columns_analyzed=d.get("columns_analyzed", []),
            calculations=d.get("calculations", []),
            comparison_periods=d.get("comparison_periods", []),
            record_counts=d.get("record_counts", {}),
        )


@dataclass
class InvestigationRequest:
    """Payload to trigger an investigation on a detected or user-specified signal."""
    signal_id: Optional[str] = None
    metric: Optional[str] = None
    table: Optional[str] = None
    context: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "metric": self.metric,
            "table": self.table,
            "context": self.context or {},
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "InvestigationRequest":
        return cls(
            signal_id=d.get("signal_id"),
            metric=d.get("metric"),
            table=d.get("table"),
            context=d.get("context"),
        )


@dataclass
class InvestigationResult:
    """Complete root-cause investigation outcome grounded in real database measurements."""
    investigation_id: str
    user_id: str
    signal_id: str
    signal_title: str
    status: str  # "success" | "insufficient_evidence" | "disconnected" | "error"
    observed_change: Optional[ObservedChange] = None
    evidence: list[EvidenceItem] = field(default_factory=list)
    contributing_factors: list[ContributingFactor] = field(default_factory=list)
    hypotheses: list[Hypothesis] = field(default_factory=list)
    confidence: Optional[ConfidenceAssessment] = None
    recommended_investigations: list[InvestigationRecommendation] = field(default_factory=list)
    lineage: Optional[InvestigationLineage] = None
    summary: str = ""
    explanation: str = ""
    missing_evidence: Optional[dict[str, Any]] = None
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "investigation_id": self.investigation_id,
            "user_id": self.user_id,
            "signal_id": self.signal_id,
            "signal_title": self.signal_title,
            "status": self.status,
            "observed_change": self.observed_change.to_dict() if self.observed_change else None,
            "evidence": [e.to_dict() for e in self.evidence],
            "contributing_factors": [c.to_dict() for c in self.contributing_factors],
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "confidence": self.confidence.to_dict() if self.confidence else None,
            "recommended_investigations": [r.to_dict() for r in self.recommended_investigations],
            "lineage": self.lineage.to_dict() if self.lineage else None,
            "summary": self.summary,
            "explanation": self.explanation,
            "missing_evidence": self.missing_evidence,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "InvestigationResult":
        oc = ObservedChange.from_dict(d["observed_change"]) if d.get("observed_change") else None
        ev = [EvidenceItem.from_dict(x) for x in d.get("evidence", [])]
        cf = [ContributingFactor.from_dict(x) for x in d.get("contributing_factors", [])]
        hy = [Hypothesis.from_dict(x) for x in d.get("hypotheses", [])]
        conf = ConfidenceAssessment.from_dict(d["confidence"]) if d.get("confidence") else None
        rec = [InvestigationRecommendation.from_dict(x) for x in d.get("recommended_investigations", [])]
        lin = InvestigationLineage.from_dict(d["lineage"]) if d.get("lineage") else None

        return cls(
            investigation_id=d.get("investigation_id", ""),
            user_id=d.get("user_id", ""),
            signal_id=d.get("signal_id", ""),
            signal_title=d.get("signal_title", ""),
            status=d.get("status", "success"),
            observed_change=oc,
            evidence=ev,
            contributing_factors=cf,
            hypotheses=hy,
            confidence=conf,
            recommended_investigations=rec,
            lineage=lin,
            summary=d.get("summary", ""),
            explanation=d.get("explanation", ""),
            missing_evidence=d.get("missing_evidence"),
            created_at=d.get("created_at", ""),
        )

