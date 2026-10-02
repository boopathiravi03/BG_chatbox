"""
backend/app/intelligence/learning/models.py

Phase 8.5: Outcome & Learning Intelligence Data Models
Defines strongly typed models for recorded outcomes, explicit user feedback,
and synthesized learning summaries.

Strict Epistemic & Learning Principles:
- Grounded strictly in real historical outcomes and user feedback.
- Zero fake/demo learning data.
- Defensible thresholds for "learned" patterns (never claims pattern learning with insufficient data).
- Disclaims future guarantees (correlation does not imply causation or future certainty).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Optional


class OutcomeStatus:
    SUCCESSFUL = "SUCCESSFUL"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"

    ALL = {SUCCESSFUL, PARTIAL, FAILED, UNKNOWN}


class FeedbackTargetType:
    DECISION = "DECISION"
    PLAN = "PLAN"
    ALERT = "ALERT"
    RECOMMENDATION = "RECOMMENDATION"
    INVESTIGATION = "INVESTIGATION"

    ALL = {DECISION, PLAN, ALERT, RECOMMENDATION, INVESTIGATION}


@dataclass
class OutcomeRecord:
    """
    A recorded result from executing or completing a planned action or decision.
    """
    user_id: str
    action_type: str
    expected_outcome: str
    actual_outcome: str
    status: str = OutcomeStatus.UNKNOWN
    outcome_id: str = field(default_factory=lambda: f"out_{uuid.uuid4().hex[:8]}")
    decision_id: Optional[str] = None
    question: Optional[str] = None
    action_id: Optional[str] = None
    plan_step: Optional[int] = None
    evidence: Any = None
    notes: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutcomeRecord:
        raw_status = (data.get("status") or OutcomeStatus.UNKNOWN).upper()
        norm_status = raw_status if raw_status in OutcomeStatus.ALL else OutcomeStatus.UNKNOWN
        return cls(
            outcome_id=data.get("outcome_id", f"out_{uuid.uuid4().hex[:8]}"),
            user_id=data["user_id"],
            decision_id=data.get("decision_id"),
            question=data.get("question"),
            action_id=data.get("action_id"),
            plan_step=data.get("plan_step"),
            action_type=data.get("action_type", "GENERAL"),
            expected_outcome=data.get("expected_outcome", ""),
            actual_outcome=data.get("actual_outcome", ""),
            status=norm_status,
            evidence=data.get("evidence"),
            notes=data.get("notes"),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
        )


@dataclass
class FeedbackRecord:
    """
    Explicit user feedback on a decision, plan step, alert, or recommendation.
    """
    user_id: str
    target_type: str = FeedbackTargetType.DECISION
    feedback_id: str = field(default_factory=lambda: f"fb_{uuid.uuid4().hex[:8]}")
    target_id: Optional[str] = None
    question: Optional[str] = None
    useful: Optional[bool] = None
    accepted: Optional[bool] = None
    comment: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeedbackRecord:
        raw_target = (data.get("target_type") or FeedbackTargetType.DECISION).upper()
        norm_target = raw_target if raw_target in FeedbackTargetType.ALL else FeedbackTargetType.DECISION
        return cls(
            feedback_id=data.get("feedback_id", f"fb_{uuid.uuid4().hex[:8]}"),
            user_id=data["user_id"],
            target_type=norm_target,
            target_id=data.get("target_id"),
            question=data.get("question"),
            useful=data.get("useful"),
            accepted=data.get("accepted"),
            comment=data.get("comment"),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
        )


@dataclass
class LearningPattern:
    """
    A recognized empirical pattern synthesized across historical user outcomes.
    """
    pattern_id: str
    pattern_type: str  # "SUCCESSFUL_ACTION", "REJECTED_ACTION", "HIGH_EFFICACY_DECISION"
    description: str
    occurrence_count: int
    success_rate: float
    corroborating_actions: list[str] = field(default_factory=list)
    caveat: str = "Empirical pattern from historical observations; not a guarantee of future outcomes."

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LearningSummary:
    """
    Comprehensive, transparent summary of historical outcomes and feedback for a user.
    """
    user_id: str
    total_outcomes: int
    successful_count: int
    partial_count: int
    failed_count: int
    unknown_count: int
    total_feedbacks: int
    useful_count: int
    not_useful_count: int
    accepted_count: int
    rejected_count: int
    successful_patterns: list[dict[str, Any]] = field(default_factory=list)
    rejected_patterns: list[dict[str, Any]] = field(default_factory=list)
    frequently_accepted_actions: list[dict[str, Any]] = field(default_factory=list)
    frequently_rejected_actions: list[dict[str, Any]] = field(default_factory=list)
    evidence_coverage: dict[str, Any] = field(default_factory=dict)
    areas_with_insufficient_data: list[str] = field(default_factory=list)
    insufficient_data: bool = True
    disclaimer: str = (
        "Learning signals reflect past user-confirmed outcomes only. "
        "Historical correlation does not establish deterministic causation."
    )
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
