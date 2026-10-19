"""backend/app/guardian/models.py

Data structures and domain models for BG AI's AI Database Guardian.
Enforces strict separation of:
1. Observed Facts (telemetry readings & system capabilities)
2. Rule-Based Detections (operational anomalies)
3. Likely Root Causes (probabilistic hypotheses with confidence levels)
4. AI Advisory (natural-language explanations & safe verification queries)
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class IncidentSeverity(str, enum.Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class IncidentStatus(str, enum.Enum):
    DETECTED = "detected"
    INVESTIGATING = "investigating"
    DIAGNOSED = "diagnosed"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class MetricAvailability(str, enum.Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    PERMISSION_DENIED = "permission_denied"
    UNSUPPORTED_ENGINE = "unsupported_engine"


@dataclass
class MetricItem:
    """Represents a single discrete operational metric reading with freshness and provenance."""
    name: str
    value: Optional[Any]
    unit: str
    status: MetricAvailability
    description: str
    freshness_seconds: float = 0.0
    collected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "status": self.status.value,
            "description": self.description,
            "freshness_seconds": round(self.freshness_seconds, 2),
            "collected_at": self.collected_at,
        }


@dataclass
class EngineTelemetrySnapshot:
    """Container holding multi-dimensional engine telemetry for a connected source."""
    database_type: str
    database_identity: str
    collected_at: str
    is_live: bool
    latency_ms: float
    metrics: Dict[str, MetricItem] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "database_type": self.database_type,
            "database_identity": self.database_identity,
            "collected_at": self.collected_at,
            "is_live": self.is_live,
            "latency_ms": round(self.latency_ms, 2),
            "metrics": {k: v.to_dict() for k, v in self.metrics.items()},
            "warnings": self.warnings,
        }


@dataclass
class GuardianIncident:
    """
    Operational issue detected by rule-based analysis or operational thresholds.
    Strictly isolates observed facts from deductions.
    """
    incident_id: str
    user_id: str
    database_identity: str
    database_type: str
    title: str
    severity: IncidentSeverity
    status: IncidentStatus
    category: str  # connection_pool, memory, lock_contention, cache_efficiency, storage, schema
    detected_at: str
    updated_at: str
    
    # 1. Observed facts: Raw numerical or state evidence
    observed_facts: Dict[str, Any]
    
    # 2. Rule explanation: Exact condition triggered
    trigger_rule: str
    
    # 3. Likely root cause (hypothesis with explicit uncertainty score)
    likely_root_cause: str
    confidence_score: float  # 0.0 to 1.0
    confidence_justification: str = ""
    limitations: List[str] = field(default_factory=list)
    
    # 4. Safe, non-destructive verification instructions & AI advisory
    verification_steps: List[str] = field(default_factory=list)
    ai_advisory: Optional[str] = None
    
    # Recovery & resolution details
    recovery_rule: Optional[str] = None
    recovered_at: Optional[str] = None
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[str] = None
    resolution_notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "user_id": self.user_id,
            "database_identity": self.database_identity,
            "database_type": self.database_type,
            "title": self.title,
            "severity": self.severity.value,
            "status": self.status.value,
            "category": self.category,
            "detected_at": self.detected_at,
            "updated_at": self.updated_at,
            "observed_facts": self.observed_facts,
            "trigger_rule": self.trigger_rule,
            "likely_root_cause": self.likely_root_cause,
            "confidence_score": round(self.confidence_score, 2),
            "confidence_justification": self.confidence_justification,
            "limitations": self.limitations,
            "verification_steps": self.verification_steps,
            "ai_advisory": self.ai_advisory,
            "recovery_rule": self.recovery_rule,
            "recovered_at": self.recovered_at,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at,
            "resolved_by": self.resolved_by,
            "resolved_at": self.resolved_at,
            "resolution_notes": self.resolution_notes,
        }


@dataclass
class DiagnosisReport:
    """Full operational health report returned to the user."""
    report_id: str
    database_type: str
    database_identity: str
    overall_health: str  # healthy, warning, critical, unknown
    health_score: int  # 0 - 100
    generated_at: str
    telemetry: EngineTelemetrySnapshot
    active_incidents: List[GuardianIncident]
    summary_advisory: str
    recommendations: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "database_type": self.database_type,
            "database_identity": self.database_identity,
            "overall_health": self.overall_health,
            "health_score": self.health_score,
            "generated_at": self.generated_at,
            "telemetry": self.telemetry.to_dict(),
            "active_incidents": [inc.to_dict() for inc in self.active_incidents],
            "summary_advisory": self.summary_advisory,
            "recommendations": self.recommendations,
        }

