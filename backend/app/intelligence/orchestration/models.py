"""
backend/app/intelligence/orchestration/models.py

Data structures, enums, and dataclasses for Phase 9.2: Advanced Agent Orchestration.
Maintains strict permissions, evidence provenance, conflict tracking, and safety gates.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone


class AgentPermission(str, Enum):
    READ_ONLY = "READ_ONLY"
    ANALYTICAL = "ANALYTICAL"
    PROPOSAL_ONLY = "PROPOSAL_ONLY"
    CONTROLLED_MUTATION = "CONTROLLED_MUTATION"


class OrchestrationStatus(str, Enum):
    PLANNING = "PLANNING"
    VALIDATING = "VALIDATING"
    EXECUTING = "EXECUTING"
    WAITING_FOR_INPUT = "WAITING_FOR_INPUT"
    WAITING_FOR_CONFIRMATION = "WAITING_FOR_CONFIRMATION"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


class TaskStepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


class EvidenceType(str, Enum):
    DATABASE_FACT = "DATABASE_FACT"
    METRIC_RESULT = "METRIC_RESULT"
    BUSINESS_CONTEXT = "BUSINESS_CONTEXT"
    TREND = "TREND"
    ANOMALY = "ANOMALY"
    INVESTIGATION_FINDING = "INVESTIGATION_FINDING"
    FORECAST = "FORECAST"
    DECISION_FINDING = "DECISION_FINDING"
    OUTCOME = "OUTCOME"
    USER_CONTEXT = "USER_CONTEXT"
    ACTION_STATUS = "ACTION_STATUS"


class ConflictType(str, Enum):
    TIME_WINDOW_CONFLICT = "TIME_WINDOW_CONFLICT"
    METRIC_DEFINITION_CONFLICT = "METRIC_DEFINITION_CONFLICT"
    DATA_SCOPE_CONFLICT = "DATA_SCOPE_CONFLICT"
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"
    KNOWLEDGE_CONFLICT = "KNOWLEDGE_CONFLICT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ConfidenceTier(str, Enum):
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LIMITED = "LIMITED"


@dataclass
class SpecialistAgentDescriptor:
    agent_id: str
    name: str
    description: str
    permission: AgentPermission
    capabilities: List[str] = field(default_factory=list)
    supported_inputs: List[str] = field(default_factory=list)
    supported_outputs: List[str] = field(default_factory=list)
    is_read_only: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "permission": self.permission.value,
            "capabilities": self.capabilities,
            "supported_inputs": self.supported_inputs,
            "supported_outputs": self.supported_outputs,
            "is_read_only": self.is_read_only,
        }


@dataclass
class PlanStep:
    step_id: str
    agent_id: str
    name: str
    purpose: str
    dependencies: List[str] = field(default_factory=list)
    inputs: Dict[str, Any] = field(default_factory=dict)
    status: TaskStepStatus = TaskStepStatus.PENDING
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "agent_id": self.agent_id,
            "name": self.name,
            "purpose": self.purpose,
            "dependencies": self.dependencies,
            "inputs": self.inputs,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "retry_count": self.retry_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PlanStep:
        return cls(
            step_id=data["step_id"],
            agent_id=data["agent_id"],
            name=data["name"],
            purpose=data.get("purpose", ""),
            dependencies=data.get("dependencies", []),
            inputs=data.get("inputs", {}),
            status=TaskStepStatus(data.get("status", TaskStepStatus.PENDING.value)),
            output=data.get("output"),
            error=data.get("error"),
            duration_ms=data.get("duration_ms", 0.0),
            retry_count=data.get("retry_count", 0),
        )


@dataclass
class TaskGraph:
    graph_id: str
    steps: List[PlanStep] = field(default_factory=list)
    entry_steps: List[str] = field(default_factory=list)
    exit_steps: List[str] = field(default_factory=list)
    max_depth: int = 5
    total_steps: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "steps": [s.to_dict() for s in self.steps],
            "entry_steps": self.entry_steps,
            "exit_steps": self.exit_steps,
            "max_depth": self.max_depth,
            "total_steps": len(self.steps),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskGraph:
        steps = [PlanStep.from_dict(s) for s in data.get("steps", [])]
        return cls(
            graph_id=data.get("graph_id", str(uuid.uuid4())),
            steps=steps,
            entry_steps=data.get("entry_steps", []),
            exit_steps=data.get("exit_steps", []),
            max_depth=data.get("max_depth", 5),
            total_steps=len(steps),
        )


@dataclass
class EvidenceItem:
    evidence_id: str
    evidence_type: EvidenceType
    title: str
    summary: str
    source_agent: str
    step_id: str
    data_facts: Dict[str, Any] = field(default_factory=dict)
    confidence: ConfidenceTier = ConfidenceTier.HIGH
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    lineage: List[str] = field(default_factory=list)
    table_references: List[str] = field(default_factory=list)
    metric_references: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "evidence_type": self.evidence_type.value,
            "title": self.title,
            "summary": self.summary,
            "source_agent": self.source_agent,
            "step_id": self.step_id,
            "data_facts": self.data_facts,
            "confidence": self.confidence.value,
            "created_at": self.created_at,
            "lineage": self.lineage,
            "table_references": self.table_references,
            "metric_references": self.metric_references,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EvidenceItem:
        return cls(
            evidence_id=data["evidence_id"],
            evidence_type=EvidenceType(data["evidence_type"]),
            title=data["title"],
            summary=data.get("summary", ""),
            source_agent=data.get("source_agent", "unknown"),
            step_id=data.get("step_id", ""),
            data_facts=data.get("data_facts", {}),
            confidence=ConfidenceTier(data.get("confidence", ConfidenceTier.HIGH.value)),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            lineage=data.get("lineage", []),
            table_references=data.get("table_references", []),
            metric_references=data.get("metric_references", []),
        )


@dataclass
class OrchestrationConflict:
    conflict_id: str
    conflict_type: ConflictType
    description: str
    involved_agents: List[str] = field(default_factory=list)
    involved_steps: List[str] = field(default_factory=list)
    resolution_strategy: str = "EXPLICIT_NOTE"
    resolved: bool = True
    resolution_details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type.value,
            "description": self.description,
            "involved_agents": self.involved_agents,
            "involved_steps": self.involved_steps,
            "resolution_strategy": self.resolution_strategy,
            "resolved": self.resolved,
            "resolution_details": self.resolution_details,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OrchestrationConflict:
        return cls(
            conflict_id=data["conflict_id"],
            conflict_type=ConflictType(data["conflict_type"]),
            description=data["description"],
            involved_agents=data.get("involved_agents", []),
            involved_steps=data.get("involved_steps", []),
            resolution_strategy=data.get("resolution_strategy", "EXPLICIT_NOTE"),
            resolved=data.get("resolved", True),
            resolution_details=data.get("resolution_details", ""),
        )


@dataclass
class ProposedActionSummary:
    action_type: str
    title: str
    description: str
    preview: Dict[str, Any] = field(default_factory=dict)
    impact: Dict[str, Any] = field(default_factory=dict)
    confirmation_required: bool = True
    action_plan_id: Optional[str] = None
    status: str = "PROPOSED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type,
            "title": self.title,
            "description": self.description,
            "preview": self.preview,
            "impact": self.impact,
            "confirmation_required": self.confirmation_required,
            "action_plan_id": self.action_plan_id,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProposedActionSummary:
        return cls(
            action_type=data.get("action_type", "GENERAL"),
            title=data.get("title", ""),
            description=data.get("description", ""),
            preview=data.get("preview", {}),
            impact=data.get("impact", {}),
            confirmation_required=data.get("confirmation_required", True),
            action_plan_id=data.get("action_plan_id"),
            status=data.get("status", "PROPOSED"),
        )


@dataclass
class OrchestrationRun:
    orchestration_id: str
    user_id: str
    database_identity: str
    goal: str
    status: OrchestrationStatus = OrchestrationStatus.PLANNING
    task_graph: Optional[TaskGraph] = None
    evidence_ledger: List[EvidenceItem] = field(default_factory=list)
    conflicts: List[OrchestrationConflict] = field(default_factory=list)
    proposed_action: Optional[ProposedActionSummary] = None
    executive_summary: str = ""
    explanation: Dict[str, Any] = field(default_factory=dict)
    confidence_tier: ConfidenceTier = ConfidenceTier.HIGH
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: Optional[str] = None
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "orchestration_id": self.orchestration_id,
            "user_id": self.user_id,
            "database_identity": self.database_identity,
            "goal": self.goal,
            "status": self.status.value,
            "task_graph": self.task_graph.to_dict() if self.task_graph else None,
            "evidence_ledger": [e.to_dict() for e in self.evidence_ledger],
            "conflicts": [c.to_dict() for c in self.conflicts],
            "proposed_action": self.proposed_action.to_dict() if self.proposed_action else None,
            "executive_summary": self.executive_summary,
            "explanation": self.explanation,
            "confidence_tier": self.confidence_tier.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OrchestrationRun:
        task_graph = TaskGraph.from_dict(data["task_graph"]) if data.get("task_graph") else None
        evidence = [EvidenceItem.from_dict(e) for e in data.get("evidence_ledger", [])]
        conflicts = [OrchestrationConflict.from_dict(c) for c in data.get("conflicts", [])]
        proposed_action = ProposedActionSummary.from_dict(data["proposed_action"]) if data.get("proposed_action") else None

        return cls(
            orchestration_id=data["orchestration_id"],
            user_id=data["user_id"],
            database_identity=data["database_identity"],
            goal=data["goal"],
            status=OrchestrationStatus(data.get("status", OrchestrationStatus.PLANNING.value)),
            task_graph=task_graph,
            evidence_ledger=evidence,
            conflicts=conflicts,
            proposed_action=proposed_action,
            executive_summary=data.get("executive_summary", ""),
            explanation=data.get("explanation", {}),
            confidence_tier=ConfidenceTier(data.get("confidence_tier", ConfidenceTier.HIGH.value)),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
            completed_at=data.get("completed_at"),
            duration_ms=data.get("duration_ms", 0.0),
            metadata=data.get("metadata", {}),
        )
