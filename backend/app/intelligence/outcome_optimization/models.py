"""
backend/app/intelligence/outcome_optimization/models.py

Phase 8.9: Closed-Loop Outcome Optimization & Adaptive Recommendations
Defines typed models for action outcome measurement, baseline comparison,
effectiveness classification, attribution safety, and adaptive recommendations.

Epistemic Rules:
- NEVER claim causation. Use: associated_with, observed_after, measured_change.
- Effectiveness classification is deterministic, not AI-scored.
- Confidence levels are evidence-based, not arbitrary.
- Attribution always distinguishes OBSERVED OUTCOME from CAUSAL EFFECT.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Optional


# ── Classification Constants ──────────────────────────────────────────────────

class EffectivenessLabel:
    POSITIVE = "POSITIVE"           # Measurable improvement observed after action
    NEGATIVE = "NEGATIVE"           # Measurable deterioration observed after action
    NEUTRAL = "NEUTRAL"             # No meaningful change observed
    INCONCLUSIVE = "INCONCLUSIVE"   # Change observed but within noise/variance
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"  # Not enough data points to classify

    ALL = {POSITIVE, NEGATIVE, NEUTRAL, INCONCLUSIVE, INSUFFICIENT_DATA}


class ConfidenceLevel:
    HIGH = "HIGH"         # Large sample, strong signal, low variance
    MODERATE = "MODERATE" # Adequate sample, moderate signal
    LIMITED = "LIMITED"   # Small sample, weak or noisy signal

    ALL = {HIGH, MODERATE, LIMITED}


class AttributionStatus:
    OBSERVED_OUTCOME = "OBSERVED_OUTCOME"       # Change measured but causation not claimed
    CONFOUNDERS_PRESENT = "CONFOUNDERS_PRESENT" # Other factors detected that may explain change
    INSUFFICIENT_WINDOW = "INSUFFICIENT_WINDOW" # Not enough time has passed to measure
    NO_BASELINE = "NO_BASELINE"                 # No baseline data available

    ALL = {OBSERVED_OUTCOME, CONFOUNDERS_PRESENT, INSUFFICIENT_WINDOW, NO_BASELINE}


class MeasurementWindow:
    H24 = "24h"
    D7 = "7d"
    D14 = "14d"
    D30 = "30d"

    ALL = {"24h", "7d", "14d", "30d"}
    HOURS = {"24h": 24, "7d": 168, "14d": 336, "30d": 720}


class RecommendationSource:
    HISTORICAL_OUTCOMES = "HISTORICAL_OUTCOMES"  # Based on past execution results
    FEEDBACK_SIGNALS = "FEEDBACK_SIGNALS"        # Based on user feedback patterns
    PATTERN_MATCH = "PATTERN_MATCH"              # Based on action type success patterns
    COLD_START = "COLD_START"                    # Insufficient history for personalization

    ALL = {HISTORICAL_OUTCOMES, FEEDBACK_SIGNALS, PATTERN_MATCH, COLD_START}


# ── Data Models ───────────────────────────────────────────────────────────────

@dataclass
class OutcomeMeasurement:
    """
    A measurement of a specific metric taken at a specific window after an action.
    Links to a Phase 8.8 action_id for traceability.
    """
    measurement_id: str = field(default_factory=lambda: f"meas_{uuid.uuid4().hex[:10]}")
    user_id: str = ""
    action_id: Optional[str] = None
    metric_name: str = ""
    source_table: str = ""
    source_column: str = ""
    measurement_sql: str = ""
    baseline_value: Optional[float] = None
    baseline_period: Optional[str] = None   # e.g. "previous_24h", "rolling_7d"
    observed_value: Optional[float] = None
    delta: Optional[float] = None            # observed_value - baseline_value
    delta_pct: Optional[float] = None        # (delta / baseline_value) * 100
    window: str = MeasurementWindow.D7
    effectiveness: str = EffectivenessLabel.INSUFFICIENT_DATA
    confidence: str = ConfidenceLevel.LIMITED
    attribution: str = AttributionStatus.OBSERVED_OUTCOME
    confounders: list[str] = field(default_factory=list)
    sample_size: int = 0
    baseline_sample_size: int = 0
    measured_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    action_executed_at: Optional[str] = None
    epistemic_note: str = (
        "Change is observed after the action. Causation is not claimed. "
        "Other factors may have contributed."
    )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OutcomeMeasurement":
        return cls(
            measurement_id=data.get("measurement_id", f"meas_{uuid.uuid4().hex[:10]}"),
            user_id=data.get("user_id", ""),
            action_id=data.get("action_id"),
            metric_name=data.get("metric_name", ""),
            source_table=data.get("source_table", ""),
            source_column=data.get("source_column", ""),
            measurement_sql=data.get("measurement_sql", ""),
            baseline_value=data.get("baseline_value"),
            baseline_period=data.get("baseline_period"),
            observed_value=data.get("observed_value"),
            delta=data.get("delta"),
            delta_pct=data.get("delta_pct"),
            window=data.get("window", MeasurementWindow.D7),
            effectiveness=data.get("effectiveness", EffectivenessLabel.INSUFFICIENT_DATA),
            confidence=data.get("confidence", ConfidenceLevel.LIMITED),
            attribution=data.get("attribution", AttributionStatus.OBSERVED_OUTCOME),
            confounders=list(data.get("confounders") or []),
            sample_size=int(data.get("sample_size") or 0),
            baseline_sample_size=int(data.get("baseline_sample_size") or 0),
            measured_at=data.get("measured_at", datetime.utcnow().isoformat()),
            action_executed_at=data.get("action_executed_at"),
            epistemic_note=data.get(
                "epistemic_note",
                "Change is observed after the action. Causation is not claimed.",
            ),
        )


@dataclass
class OutcomeAnalysis:
    """
    Full analysis of an action's observed outcomes across one or more metrics.
    """
    analysis_id: str = field(default_factory=lambda: f"ana_{uuid.uuid4().hex[:10]}")
    action_id: str = ""
    user_id: str = ""
    action_type: str = ""
    target_table: str = ""
    measurements: list[OutcomeMeasurement] = field(default_factory=list)
    overall_effectiveness: str = EffectivenessLabel.INSUFFICIENT_DATA
    overall_confidence: str = ConfidenceLevel.LIMITED
    attribution_summary: str = AttributionStatus.OBSERVED_OUTCOME
    summary: str = ""
    data_gaps: list[str] = field(default_factory=list)
    analyzed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    disclaimer: str = (
        "This analysis describes observed associations, not causal effects. "
        "Other factors may explain the measured changes."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "action_id": self.action_id,
            "user_id": self.user_id,
            "action_type": self.action_type,
            "target_table": self.target_table,
            "measurements": [m.to_dict() for m in self.measurements],
            "overall_effectiveness": self.overall_effectiveness,
            "overall_confidence": self.overall_confidence,
            "attribution_summary": self.attribution_summary,
            "summary": self.summary,
            "data_gaps": self.data_gaps,
            "analyzed_at": self.analyzed_at,
            "disclaimer": self.disclaimer,
        }


@dataclass
class AdaptiveRecommendation:
    """
    A recommendation informed by real historical outcome data.
    Never auto-executes. Always requires human confirmation via Phase 8.8.
    """
    recommendation_id: str = field(default_factory=lambda: f"rec_{uuid.uuid4().hex[:10]}")
    user_id: str = ""
    title: str = ""
    description: str = ""
    action_type: str = ""
    target_table: str = ""
    rationale: str = ""
    source: str = RecommendationSource.COLD_START
    historical_success_rate: Optional[float] = None
    historical_sample_size: int = 0
    confidence: str = ConfidenceLevel.LIMITED
    supporting_outcome_ids: list[str] = field(default_factory=list)
    requires_human_confirmation: bool = True   # Always True — never auto-executes
    execution_path: str = "Phase 8.8 Action Proposal → Preview → Confirmation → Execution"
    caveat: str = (
        "This recommendation is based on observed historical patterns. "
        "Past outcomes do not guarantee future results. Human review is required."
    )
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AdaptiveRecommendation":
        return cls(
            recommendation_id=data.get("recommendation_id", f"rec_{uuid.uuid4().hex[:10]}"),
            user_id=data.get("user_id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            action_type=data.get("action_type", ""),
            target_table=data.get("target_table", ""),
            rationale=data.get("rationale", ""),
            source=data.get("source", RecommendationSource.COLD_START),
            historical_success_rate=data.get("historical_success_rate"),
            historical_sample_size=int(data.get("historical_sample_size") or 0),
            confidence=data.get("confidence", ConfidenceLevel.LIMITED),
            supporting_outcome_ids=list(data.get("supporting_outcome_ids") or []),
            requires_human_confirmation=True,
            execution_path=data.get(
                "execution_path",
                "Phase 8.8 Action Proposal → Preview → Confirmation → Execution",
            ),
            caveat=data.get(
                "caveat",
                "This recommendation is based on observed historical patterns.",
            ),
            generated_at=data.get("generated_at", datetime.utcnow().isoformat()),
        )


@dataclass
class RecommendationExplanation:
    """
    Structured explanation of why a recommendation was generated.
    """
    recommendation_id: str = ""
    user_id: str = ""
    explanation_points: list[str] = field(default_factory=list)
    evidence_references: list[dict[str, Any]] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
