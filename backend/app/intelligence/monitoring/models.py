"""Phase 8.6 — Monitoring data models."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class MonitoringSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class MonitoringItemType(str, Enum):
    ANOMALY = "anomaly"
    PROACTIVE_ALERT = "proactive_alert"
    BI_INSIGHT = "bi_insight"
    CROSS_TABLE = "cross_table"


@dataclass
class MonitoringItem:
    """One actionable signal surfaced during a monitoring scan."""

    item_id: str
    item_type: MonitoringItemType
    severity: MonitoringSeverity
    title: str
    observed_change: str
    business_impact: str
    possible_explanation: str
    recommended_next_step: str
    evidence: dict[str, Any] = field(default_factory=dict)
    source_component: str = ""  # which Phase provided this signal

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "item_type": self.item_type.value if isinstance(self.item_type, MonitoringItemType) else self.item_type,
            "severity": self.severity.value if isinstance(self.severity, MonitoringSeverity) else self.severity,
            "title": self.title,
            "observed_change": self.observed_change,
            "business_impact": self.business_impact,
            "possible_explanation": self.possible_explanation,
            "recommended_next_step": self.recommended_next_step,
            "evidence": self.evidence,
            "source_component": self.source_component,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MonitoringItem":
        return cls(
            item_id=d["item_id"],
            item_type=MonitoringItemType(d.get("item_type", "bi_insight")),
            severity=MonitoringSeverity(d.get("severity", "info")),
            title=d["title"],
            observed_change=d.get("observed_change", ""),
            business_impact=d.get("business_impact", ""),
            possible_explanation=d.get("possible_explanation", ""),
            recommended_next_step=d.get("recommended_next_step", ""),
            evidence=d.get("evidence", {}),
            source_component=d.get("source_component", ""),
        )


@dataclass
class ExecutiveSummary:
    """High-level executive view of a monitoring scan."""

    overall_status: str          # "healthy" | "attention_needed" | "critical"
    headline: str                # one-sentence summary
    critical_count: int
    warning_count: int
    info_count: int
    top_risks: list[str]         # up to 3 risk bullets
    top_opportunities: list[str] # up to 3 opportunity bullets
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "headline": self.headline,
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "top_risks": self.top_risks,
            "top_opportunities": self.top_opportunities,
            "generated_at": self.generated_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ExecutiveSummary":
        return cls(
            overall_status=d.get("overall_status", "healthy"),
            headline=d.get("headline", ""),
            critical_count=d.get("critical_count", 0),
            warning_count=d.get("warning_count", 0),
            info_count=d.get("info_count", 0),
            top_risks=d.get("top_risks", []),
            top_opportunities=d.get("top_opportunities", []),
            generated_at=d.get("generated_at", ""),
        )


@dataclass
class MonitoringReport:
    """Full result of a single on-demand monitoring scan for one user."""

    user_id: str
    db_type: str
    scanned_at: str
    items: list[MonitoringItem] = field(default_factory=list)
    executive_summary: ExecutiveSummary | None = None
    scan_duration_ms: int = 0
    status: str = "success"      # "success" | "disconnected" | "error"
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "db_type": self.db_type,
            "scanned_at": self.scanned_at,
            "items": [i.to_dict() for i in self.items],
            "executive_summary": self.executive_summary.to_dict() if self.executive_summary else None,
            "scan_duration_ms": self.scan_duration_ms,
            "status": self.status,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MonitoringReport":
        items = [MonitoringItem.from_dict(x) for x in d.get("items", [])]
        es = ExecutiveSummary.from_dict(d["executive_summary"]) if d.get("executive_summary") else None
        return cls(
            user_id=d.get("user_id", ""),
            db_type=d.get("db_type", ""),
            scanned_at=d.get("scanned_at", ""),
            items=items,
            executive_summary=es,
            scan_duration_ms=d.get("scan_duration_ms", 0),
            status=d.get("status", "success"),
            message=d.get("message", ""),
        )
