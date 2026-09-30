from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class AgentInfo:
    name: str
    role: str
    description: str
    is_read_only: bool
    capabilities: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentFinding:
    id: str
    severity: str  # "CRITICAL", "WARNING", "INFO"
    title: str
    description: str
    table: Optional[str] = None
    column: Optional[str] = None
    evidence: Any = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ActionPlan:
    action_id: str
    task_id: str
    agent_name: str
    table: str
    action_type: str  # "UPDATE", "DELETE", "INSERT"
    estimated_rows: int
    exact_sql: str
    verification_sql: str
    expected_verification_result: str = "0"
    risk_level: str = "MEDIUM"  # "LOW", "MEDIUM", "HIGH"
    potential_consequence: str = ""
    rollback_considerations: str = ""
    status: str = "AWAITING_CONFIRMATION"  # "PROPOSED", "AWAITING_CONFIRMATION", "EXECUTING", "EXECUTED", "VERIFIED", "VERIFICATION_FAILED", "FAILED", "CANCELLED"
    created_at: str = ""
    confirmed_at: Optional[str] = None
    executed_at: Optional[str] = None
    actual_rows_affected: Optional[int] = None
    verification_details: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    database_identity: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentTask:
    task_id: str
    agent_name: str
    request: str
    database_context: Optional[str] = None
    status: str = "ANALYZING"
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentResult:
    task_id: str
    agent_name: str
    status: str  # "COMPLETED", "ACTION_REQUIRED", "WAITING_CONFIRMATION", "FAILED"
    summary: str
    findings: list[AgentFinding] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    proposed_action: Optional[ActionPlan] = None
    limitations: list[str] = field(default_factory=list)
    execution_steps: list[str] = field(default_factory=list)
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.proposed_action:
            data["proposed_action"] = self.proposed_action.to_dict()
        data["findings"] = [f.to_dict() if hasattr(f, "to_dict") else f for f in self.findings]
        return data
