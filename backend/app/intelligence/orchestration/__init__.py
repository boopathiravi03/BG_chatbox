"""
backend/app/intelligence/orchestration/__init__.py

Public package interface for Phase 9.2: Advanced Agent Orchestration.
"""

from app.intelligence.orchestration.models import (
    AgentPermission,
    OrchestrationStatus,
    TaskStepStatus,
    EvidenceType,
    ConflictType,
    ConfidenceTier,
    SpecialistAgentDescriptor,
    PlanStep,
    TaskGraph,
    EvidenceItem,
    OrchestrationConflict,
    ProposedActionSummary,
    OrchestrationRun,
)
from app.intelligence.orchestration.agent_registry import (
    register_specialist_agent,
    get_registered_agent,
    list_registered_agents,
    initialize_specialist_agents,
)
from app.intelligence.orchestration.task_graph import (
    validate_task_graph,
    get_execution_batches,
    get_step_by_id,
    GraphValidationError,
)
from app.intelligence.orchestration.planner import OrchestrationPlanner
from app.intelligence.orchestration.safety_gate import (
    OrchestrationSafetyGate,
    SafetyViolationError,
)
from app.intelligence.orchestration.evidence_aggregator import EvidenceAggregator
from app.intelligence.orchestration.conflict_resolver import OrchestrationConflictResolver
from app.intelligence.orchestration.context_manager import OrchestrationContextManager
from app.intelligence.orchestration.executor import OrchestrationExecutor
from app.intelligence.orchestration.explainer import OrchestrationExplainer
from app.intelligence.orchestration.store import (
    save_orchestration_run,
    get_orchestration_run,
    list_orchestration_runs,
    delete_orchestration_run,
    clear_user_orchestration_runs,
)
from app.intelligence.orchestration.orchestrator import (
    AgentOrchestrator,
    orchestrate_goal,
)

__all__ = [
    "AgentPermission",
    "OrchestrationStatus",
    "TaskStepStatus",
    "EvidenceType",
    "ConflictType",
    "ConfidenceTier",
    "SpecialistAgentDescriptor",
    "PlanStep",
    "TaskGraph",
    "EvidenceItem",
    "OrchestrationConflict",
    "ProposedActionSummary",
    "OrchestrationRun",
    "register_specialist_agent",
    "get_registered_agent",
    "list_registered_agents",
    "initialize_specialist_agents",
    "validate_task_graph",
    "get_execution_batches",
    "get_step_by_id",
    "GraphValidationError",
    "OrchestrationPlanner",
    "OrchestrationSafetyGate",
    "SafetyViolationError",
    "EvidenceAggregator",
    "OrchestrationConflictResolver",
    "OrchestrationContextManager",
    "OrchestrationExecutor",
    "OrchestrationExplainer",
    "save_orchestration_run",
    "get_orchestration_run",
    "list_orchestration_runs",
    "delete_orchestration_run",
    "clear_user_orchestration_runs",
    "AgentOrchestrator",
    "orchestrate_goal",
]
