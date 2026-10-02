"""
backend/app/intelligence/proactive/models.py

Phase 8.3: Proactive Data Intelligence Data Models
Defines strongly typed models for metric snapshots, business alerts, threshold rules,
and alert statuses.

Zero LLM mathematical calculations. Never stores credentials, tokens, or raw PII records.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Optional


class AlertStatus:
    """Lifecycle statuses for proactive business alerts."""
    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"

    ALL = {NEW, ACKNOWLEDGED, INVESTIGATING, RESOLVED}
    ACTIVE_STATUSES = {NEW, ACKNOWLEDGED, INVESTIGATING}


class AlertSeverity:
    """Severity classification for proactive alerts."""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

    ALL = {INFO, WARNING, CRITICAL}


class AlertCategory:
    """Business categories of detected metric movements."""
    METRIC_SPIKE = "METRIC_SPIKE"
    METRIC_DROP = "METRIC_DROP"
    ANOMALY_DETECTED = "ANOMALY_DETECTED"
    DATA_QUALITY_DEGRADATION = "DATA_QUALITY_DEGRADATION"
    INVENTORY_RISK = "INVENTORY_RISK"
    FORECAST_DEVIATION = "FORECAST_DEVIATION"

    ALL = {
        METRIC_SPIKE,
        METRIC_DROP,
        ANOMALY_DETECTED,
        DATA_QUALITY_DEGRADATION,
        INVENTORY_RISK,
        FORECAST_DEVIATION,
    }


@dataclass
class MetricSnapshot:
    """
    Represents an observed, verifiable measurement from the connected database.
    Contains strictly computed database metrics; never contains LLM calculations.
    """
    metric: str
    user_id: str
    value: float
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    snapshot_id: str = field(default_factory=lambda: f"snp_{uuid.uuid4().hex[:8]}")
    period: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    source_tables: list[str] = field(default_factory=list)
    source_columns: list[str] = field(default_factory=list)
    sql: Optional[str] = None
    calculation_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MetricSnapshot:
        return cls(
            metric=data["metric"],
            user_id=data["user_id"],
            value=float(data["value"]),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            snapshot_id=data.get("snapshot_id", f"snp_{uuid.uuid4().hex[:8]}"),
            period=data.get("period"),
            period_start=data.get("period_start"),
            period_end=data.get("period_end"),
            source_tables=list(data.get("source_tables") or []),
            source_columns=list(data.get("source_columns") or []),
            sql=data.get("sql"),
            calculation_metadata=dict(data.get("calculation_metadata") or {}),
        )


@dataclass
class AlertRule:
    """
    Database-independent rule defining thresholds for proactive alert generation.
    Supports relative percentages, standard deviation bounds, and sample constraints.
    """
    name: str
    category: str
    rule_id: str = field(default_factory=lambda: f"rule_{uuid.uuid4().hex[:8]}")
    metric_pattern: str = "*"
    severity: str = AlertSeverity.WARNING
    drop_threshold_percent: Optional[float] = None
    spike_threshold_percent: Optional[float] = None
    absolute_delta_threshold: Optional[float] = None
    zscore_threshold: Optional[float] = None
    min_sample_size: int = 3
    is_enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AlertRule:
        return cls(
            name=data["name"],
            category=data["category"],
            rule_id=data.get("rule_id", f"rule_{uuid.uuid4().hex[:8]}"),
            metric_pattern=data.get("metric_pattern", "*"),
            severity=data.get("severity", AlertSeverity.WARNING),
            drop_threshold_percent=(
                float(data["drop_threshold_percent"])
                if data.get("drop_threshold_percent") is not None
                else None
            ),
            spike_threshold_percent=(
                float(data["spike_threshold_percent"])
                if data.get("spike_threshold_percent") is not None
                else None
            ),
            absolute_delta_threshold=(
                float(data["absolute_delta_threshold"])
                if data.get("absolute_delta_threshold") is not None
                else None
            ),
            zscore_threshold=(
                float(data["zscore_threshold"])
                if data.get("zscore_threshold") is not None
                else None
            ),
            min_sample_size=int(data.get("min_sample_size", 3)),
            is_enabled=bool(data.get("is_enabled", True)),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class BusinessAlert:
    """
    A proactive business alert generated when an observed metric breaches a threshold.
    Fully traceable with source tables, reproducible SQL, and structured evidence.
    """
    title: str
    category: str
    severity: str
    metric: str
    user_id: str
    alert_id: str = field(default_factory=lambda: f"alt_{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    previous_value: Optional[float] = None
    current_value: Optional[float] = None
    delta: Optional[float] = None
    delta_percent: Optional[float] = None
    threshold_applied: Optional[str] = None
    source_tables: list[str] = field(default_factory=list)
    source_columns: list[str] = field(default_factory=list)
    lineage_steps: list[str] = field(default_factory=list)
    sql: Optional[str] = None
    evidence: dict[str, Any] = field(default_factory=dict)
    explanation: str = ""
    recommendation: str = ""
    action_suggestion: Optional[dict[str, Any]] = None
    status: str = AlertStatus.NEW
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    resolved_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BusinessAlert:
        return cls(
            title=data["title"],
            category=data["category"],
            severity=data["severity"],
            metric=data["metric"],
            user_id=data["user_id"],
            alert_id=data.get("alert_id", f"alt_{uuid.uuid4().hex[:8]}"),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            previous_value=(
                float(data["previous_value"])
                if data.get("previous_value") is not None
                else None
            ),
            current_value=(
                float(data["current_value"])
                if data.get("current_value") is not None
                else None
            ),
            delta=(
                float(data["delta"])
                if data.get("delta") is not None
                else None
            ),
            delta_percent=(
                float(data["delta_percent"])
                if data.get("delta_percent") is not None
                else None
            ),
            threshold_applied=data.get("threshold_applied"),
            source_tables=list(data.get("source_tables") or []),
            source_columns=list(data.get("source_columns") or []),
            lineage_steps=list(data.get("lineage_steps") or []),
            sql=data.get("sql"),
            evidence=dict(data.get("evidence") or {}),
            explanation=data.get("explanation", ""),
            recommendation=data.get("recommendation", ""),
            action_suggestion=data.get("action_suggestion"),
            status=data.get("status", AlertStatus.NEW),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
            updated_at=data.get("updated_at", datetime.utcnow().isoformat()),
            resolved_at=data.get("resolved_at"),
        )
