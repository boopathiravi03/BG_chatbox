"""Governance and Observability Models - Phase 9.3

Defines immutable system policy definitions, audit events, risk assessment tiers,
agent telemetry, security incident records, data access traces, and compliance models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class ActorType(str, Enum):
    USER = "USER"
    SYSTEM = "SYSTEM"
    AGENT = "AGENT"
    ORCHESTRATOR = "ORCHESTRATOR"


class GovernanceEventType(str, Enum):
    # Database Lifecycle
    DATABASE_CONNECT = "DATABASE_CONNECT"
    DATABASE_DISCONNECT = "DATABASE_DISCONNECT"
    DATABASE_SWITCH = "DATABASE_SWITCH"
    SCHEMA_ACCESS = "SCHEMA_ACCESS"
    DATA_QUERY = "DATA_QUERY"

    # Intelligence Subsystems
    BI_ANALYSIS = "BI_ANALYSIS"
    KNOWLEDGE_ACCESS = "KNOWLEDGE_ACCESS"
    KNOWLEDGE_CHANGE = "KNOWLEDGE_CHANGE"
    INVESTIGATION_RUN = "INVESTIGATION_RUN"
    PREDICTION_RUN = "PREDICTION_RUN"
    DECISION_RUN = "DECISION_RUN"

    # Orchestration & Agent Lifecycle
    ORCHESTRATION_STARTED = "ORCHESTRATION_STARTED"
    ORCHESTRATION_COMPLETED = "ORCHESTRATION_COMPLETED"
    ORCHESTRATION_FAILED = "ORCHESTRATION_FAILED"
    AGENT_STARTED = "AGENT_STARTED"
    AGENT_COMPLETED = "AGENT_COMPLETED"
    AGENT_FAILED = "AGENT_FAILED"

    # Policy & Governance
    POLICY_CHECK = "POLICY_CHECK"
    POLICY_BLOCK = "POLICY_BLOCK"

    # Action Lifecycle
    ACTION_PROPOSED = "ACTION_PROPOSED"
    ACTION_CONFIRMED = "ACTION_CONFIRMED"
    ACTION_EXECUTED = "ACTION_EXECUTED"
    ACTION_BLOCKED = "ACTION_BLOCKED"
    ACTION_VERIFIED = "ACTION_VERIFIED"

    # Security & Guardrails
    SECURITY_EVENT = "SECURITY_EVENT"
    RATE_LIMIT_EVENT = "RATE_LIMIT_EVENT"


class PolicyCategory(str, Enum):
    DATA_ACCESS = "DATA_ACCESS"
    AGENT_ACCESS = "AGENT_ACCESS"
    ACTION_EXECUTION = "ACTION_EXECUTION"
    KNOWLEDGE_CHANGE = "KNOWLEDGE_CHANGE"
    ORCHESTRATION = "ORCHESTRATION"
    RATE_LIMIT = "RATE_LIMIT"
    SECURITY = "SECURITY"


class PolicyScope(str, Enum):
    SYSTEM_POLICY = "SYSTEM_POLICY"
    USER_POLICY = "USER_POLICY"


class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"
    REQUIRE_ELEVATED_REVIEW = "REQUIRE_ELEVATED_REVIEW"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    BLOCKED = "BLOCKED"


class SecurityEventType(str, Enum):
    BLOCKED_REQUEST = "BLOCKED_REQUEST"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    AUTH_FAILURE = "AUTH_FAILURE"
    INJECTION_PATTERN_DETECTED = "INJECTION_PATTERN_DETECTED"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    UNAUTHORIZED_ACCESS = "UNAUTHORIZED_ACCESS"
    DDL_BLOCKED = "DDL_BLOCKED"
    DATA_LEAK_BLOCKED = "DATA_LEAK_BLOCKED"
    CROSS_TENANT_BLOCKED = "CROSS_TENANT_BLOCKED"
    INVALID_CONFIRMATION = "INVALID_CONFIRMATION"


class SecurityEventSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ── Audit Event Model ─────────────────────────────────────────────────────────

@dataclass
class GovernanceAuditEvent:
    event_id: str
    timestamp: str
    user_id: str
    database_identity: str
    event_type: GovernanceEventType
    resource_type: str
    resource_id: str
    actor_type: ActorType
    action: str
    result: str  # "SUCCESS", "FAILED", "BLOCKED", "DENIED", "AWAITING_CONFIRMATION"
    risk_level: RiskLevel
    agent_id: Optional[str] = None
    orchestration_id: Optional[str] = None
    policy_result: Optional[PolicyDecision] = None
    request_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    previous_event_hash: Optional[str] = None
    event_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "database_identity": self.database_identity,
            "event_type": self.event_type.value if hasattr(self.event_type, "value") else str(self.event_type),
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "actor_type": self.actor_type.value if hasattr(self.actor_type, "value") else str(self.actor_type),
            "agent_id": self.agent_id,
            "orchestration_id": self.orchestration_id,
            "action": self.action,
            "result": self.result,
            "risk_level": self.risk_level.value if hasattr(self.risk_level, "value") else str(self.risk_level),
            "policy_result": self.policy_result.value if hasattr(self.policy_result, "value") and self.policy_result else (str(self.policy_result) if self.policy_result else None),
            "request_id": self.request_id,
            "metadata": self.metadata,
            "previous_event_hash": self.previous_event_hash,
            "event_hash": self.event_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GovernanceAuditEvent:
        ev_type = GovernanceEventType(data["event_type"]) if isinstance(data["event_type"], str) else data["event_type"]
        actor = ActorType(data["actor_type"]) if isinstance(data["actor_type"], str) else data["actor_type"]
        risk = RiskLevel(data.get("risk_level", RiskLevel.LOW.value))
        pol = PolicyDecision(data["policy_result"]) if data.get("policy_result") else None

        return cls(
            event_id=data["event_id"],
            timestamp=data["timestamp"],
            user_id=data["user_id"],
            database_identity=data.get("database_identity", "none"),
            event_type=ev_type,
            resource_type=data.get("resource_type", "SYSTEM"),
            resource_id=data.get("resource_id", ""),
            actor_type=actor,
            agent_id=data.get("agent_id"),
            orchestration_id=data.get("orchestration_id"),
            action=data.get("action", ""),
            result=data.get("result", "SUCCESS"),
            risk_level=risk,
            policy_result=pol,
            request_id=data.get("request_id"),
            metadata=data.get("metadata", {}),
            previous_event_hash=data.get("previous_event_hash"),
            event_hash=data.get("event_hash"),
        )


# ── Security Event Model ─────────────────────────────────────────────────────

@dataclass
class SecurityEventRecord:
    event_id: str
    timestamp: str
    user_id: str
    database_identity: str
    event_type: SecurityEventType
    severity: SecurityEventSeverity
    source: str
    resource: str
    description: str
    status: str
    mitigation: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "database_identity": self.database_identity,
            "event_type": self.event_type.value if hasattr(self.event_type, "value") else str(self.event_type),
            "severity": self.severity.value if hasattr(self.severity, "value") else str(self.severity),
            "source": self.source,
            "resource": self.resource,
            "description": self.description,
            "status": self.status,
            "mitigation": self.mitigation,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SecurityEventRecord:
        return cls(
            event_id=data["event_id"],
            timestamp=data["timestamp"],
            user_id=data["user_id"],
            database_identity=data.get("database_identity", "none"),
            event_type=SecurityEventType(data["event_type"]) if isinstance(data["event_type"], str) else data["event_type"],
            severity=SecurityEventSeverity(data["severity"]) if isinstance(data["severity"], str) else data["severity"],
            source=data.get("source", "system"),
            resource=data.get("resource", "none"),
            description=data.get("description", ""),
            status=data.get("status", "BLOCKED"),
            mitigation=data.get("mitigation", ""),
            metadata=data.get("metadata", {}),
        )


# ── Policy Model ─────────────────────────────────────────────────────────────

@dataclass
class GovernancePolicy:
    policy_id: str
    name: str
    description: str
    category: PolicyCategory
    scope: PolicyScope
    enabled: bool
    decision: PolicyDecision
    rule_spec: Dict[str, Any] = field(default_factory=dict)
    severity: RiskLevel = RiskLevel.MEDIUM
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value if hasattr(self.category, "value") else str(self.category),
            "scope": self.scope.value if hasattr(self.scope, "value") else str(self.scope),
            "enabled": self.enabled,
            "decision": self.decision.value if hasattr(self.decision, "value") else str(self.decision),
            "rule_spec": self.rule_spec,
            "severity": self.severity.value if hasattr(self.severity, "value") else str(self.severity),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GovernancePolicy:
        return cls(
            policy_id=data["policy_id"],
            name=data["name"],
            description=data.get("description", ""),
            category=PolicyCategory(data["category"]),
            scope=PolicyScope(data.get("scope", PolicyScope.USER_POLICY.value)),
            enabled=data.get("enabled", True),
            decision=PolicyDecision(data.get("decision", PolicyDecision.ALLOW.value)),
            rule_spec=data.get("rule_spec", {}),
            severity=RiskLevel(data.get("severity", RiskLevel.MEDIUM.value)),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
        )


# ── Risk Assessment Model ────────────────────────────────────────────────────

@dataclass
class RiskAssessment:
    assessment_id: str
    risk_level: RiskLevel
    operation: str
    contributing_factors: List[str]
    applicable_policies: List[str]
    required_control: str
    explanation: str
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "risk_level": self.risk_level.value if hasattr(self.risk_level, "value") else str(self.risk_level),
            "operation": self.operation,
            "contributing_factors": self.contributing_factors,
            "applicable_policies": self.applicable_policies,
            "required_control": self.required_control,
            "explanation": self.explanation,
            "evaluated_at": self.evaluated_at,
        }


# ── Data Access Trace Model ──────────────────────────────────────────────────

@dataclass
class DataAccessEvent:
    access_id: str
    timestamp: str
    user_id: str
    database_identity: str
    operation: str
    query_fingerprint: str
    tables_referenced: List[str]
    is_write: bool
    duration_ms: float
    agent_id: Optional[str] = None
    row_count: Optional[int] = None
    status: str = "SUCCESS"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "access_id": self.access_id,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "database_identity": self.database_identity,
            "agent_id": self.agent_id,
            "operation": self.operation,
            "query_fingerprint": self.query_fingerprint,
            "tables_referenced": self.tables_referenced,
            "is_write": self.is_write,
            "duration_ms": self.duration_ms,
            "row_count": self.row_count,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DataAccessEvent:
        return cls(
            access_id=data["access_id"],
            timestamp=data["timestamp"],
            user_id=data["user_id"],
            database_identity=data.get("database_identity", "none"),
            agent_id=data.get("agent_id"),
            operation=data.get("operation", "SELECT"),
            query_fingerprint=data.get("query_fingerprint", ""),
            tables_referenced=data.get("tables_referenced", []),
            is_write=data.get("is_write", False),
            duration_ms=data.get("duration_ms", 0.0),
            row_count=data.get("row_count"),
            status=data.get("status", "SUCCESS"),
        )


# ── Agent Execution Trace Model ──────────────────────────────────────────────

@dataclass
class AgentTraceRecord:
    trace_id: str
    request_id: str
    agent_id: str
    user_id: str
    database_identity: str
    tool_or_capability: str
    started_at: str
    duration_ms: float
    status: str  # "SUCCESS", "FAILED", "BLOCKED", "RUNNING"
    risk_level: RiskLevel
    policy_decision: PolicyDecision
    evidence_count: int
    orchestration_id: Optional[str] = None
    step_id: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "orchestration_id": self.orchestration_id,
            "step_id": self.step_id,
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "database_identity": self.database_identity,
            "tool_or_capability": self.tool_or_capability,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "risk_level": self.risk_level.value if hasattr(self.risk_level, "value") else str(self.risk_level),
            "policy_decision": self.policy_decision.value if hasattr(self.policy_decision, "value") else str(self.policy_decision),
            "evidence_count": self.evidence_count,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentTraceRecord:
        return cls(
            trace_id=data["trace_id"],
            request_id=data.get("request_id", ""),
            orchestration_id=data.get("orchestration_id"),
            step_id=data.get("step_id"),
            agent_id=data["agent_id"],
            user_id=data["user_id"],
            database_identity=data.get("database_identity", "none"),
            tool_or_capability=data.get("tool_or_capability", ""),
            started_at=data["started_at"],
            completed_at=data.get("completed_at"),
            duration_ms=data.get("duration_ms", 0.0),
            status=data.get("status", "SUCCESS"),
            risk_level=RiskLevel(data.get("risk_level", RiskLevel.LOW.value)),
            policy_decision=PolicyDecision(data.get("policy_decision", PolicyDecision.ALLOW.value)),
            evidence_count=data.get("evidence_count", 0),
            error_message=data.get("error_message"),
        )


# ── Observability & Summary Models ───────────────────────────────────────────

@dataclass
class AgentObservabilityMetric:
    agent_id: str
    name: str
    total_executions: int
    successful_executions: int
    failed_executions: int
    blocked_executions: int
    average_duration_ms: float
    last_execution_at: Optional[str]
    error_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "blocked_executions": self.blocked_executions,
            "average_duration_ms": self.average_duration_ms,
            "last_execution_at": self.last_execution_at,
            "error_count": self.error_count,
        }


@dataclass
class GovernanceSummary:
    user_id: str
    database_identity: str
    time_window: str
    total_audit_events: int
    total_orchestrations: int
    successful_orchestrations: int
    failed_orchestrations: int
    total_agent_executions: int
    agent_failures: int
    average_agent_duration_ms: float
    policy_evaluations_count: int
    policy_blocks_count: int
    security_events_count: int
    high_critical_security_count: int
    actions_proposed_count: int
    actions_confirmed_count: int
    actions_executed_count: int
    data_access_queries_count: int
    hash_chain_verified: bool
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "database_identity": self.database_identity,
            "time_window": self.time_window,
            "total_audit_events": self.total_audit_events,
            "total_orchestrations": self.total_orchestrations,
            "successful_orchestrations": self.successful_orchestrations,
            "failed_orchestrations": self.failed_orchestrations,
            "total_agent_executions": self.total_agent_executions,
            "agent_failures": self.agent_failures,
            "average_agent_duration_ms": self.average_agent_duration_ms,
            "policy_evaluations_count": self.policy_evaluations_count,
            "policy_blocks_count": self.policy_blocks_count,
            "security_events_count": self.security_events_count,
            "high_critical_security_count": self.high_critical_security_count,
            "actions_proposed_count": self.actions_proposed_count,
            "actions_confirmed_count": self.actions_confirmed_count,
            "actions_executed_count": self.actions_executed_count,
            "data_access_queries_count": self.data_access_queries_count,
            "hash_chain_verified": self.hash_chain_verified,
            "generated_at": self.generated_at,
        }


@dataclass
class ComplianceReport:
    report_id: str
    user_id: str
    database_identity: str
    period_start: str
    period_end: str
    summary: GovernanceSummary
    factual_observations: List[str]
    governance_interpretations: List[str]
    risk_distribution: Dict[str, int]
    system_observations: List[str]
    persistence_disclosure: str = (
        "Note: Local SQLite audit storage is application-level and non-durable across environment "
        "redeployments or ephemeral filesystem resets. Real-time cryptographic hash-chaining verifies "
        "application-level append integrity during the lifecycle of the local database file."
    )
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "user_id": self.user_id,
            "database_identity": self.database_identity,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "summary": self.summary.to_dict(),
            "factual_observations": self.factual_observations,
            "governance_interpretations": self.governance_interpretations,
            "risk_distribution": self.risk_distribution,
            "system_observations": self.system_observations,
            "persistence_disclosure": self.persistence_disclosure,
            "generated_at": self.generated_at,
        }
