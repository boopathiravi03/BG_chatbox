"""
backend/app/intelligence/orchestration/orchestrator.py

Main coordinator for Phase 9.2: Advanced Agent Orchestration.
Orchestrates multi-agent execution pipeline:
Goal -> Plan DAG -> Validate -> Context -> Execute Steps -> Aggregate Evidence ->
Resolve Conflicts -> Safety Gate -> Explanation -> Persist Run.
"""

from __future__ import annotations

import time
import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from app.intelligence.orchestration.models import (
    OrchestrationRun,
    OrchestrationStatus,
    ConfidenceTier,
    TaskStepStatus,
    ProposedActionSummary,
)
from app.intelligence.orchestration.planner import OrchestrationPlanner
from app.intelligence.orchestration.task_graph import validate_task_graph
from app.intelligence.orchestration.context_manager import OrchestrationContextManager
from app.intelligence.orchestration.executor import OrchestrationExecutor
from app.intelligence.orchestration.conflict_resolver import OrchestrationConflictResolver
from app.intelligence.orchestration.safety_gate import OrchestrationSafetyGate
from app.intelligence.orchestration.explainer import OrchestrationExplainer
from app.intelligence.orchestration.store import save_orchestration_run

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """
    Primary orchestrator coordinating specialist intelligence capabilities.
    """

    def __init__(self):
        self.planner = OrchestrationPlanner()

    def orchestrate(
        self,
        goal: str,
        user_id: str,
        database_identity: str,
        engine: Optional[Any] = None,
        db_type: str = "sqlite",
    ) -> OrchestrationRun:
        """
        Coordinates full multi-agent orchestration for a given goal.
        """
        start_time = time.time()
        orchestration_id = f"orch_{uuid.uuid4().hex[:10]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        # 1. Sanitize user goal via Safety Gate
        sanitized_goal, is_clean = OrchestrationSafetyGate.sanitize_user_goal(goal)

        run = OrchestrationRun(
            orchestration_id=orchestration_id,
            user_id=user_id,
            database_identity=database_identity,
            goal=sanitized_goal,
            status=OrchestrationStatus.PLANNING,
            created_at=timestamp,
            updated_at=timestamp,
        )

        try:
            # 2. Plan TaskGraph
            task_graph = self.planner.plan(sanitized_goal)
            run.task_graph = task_graph
            run.status = OrchestrationStatus.VALIDATING

            # 3. Validate TaskGraph DAG
            is_valid, validation_errors = validate_task_graph(task_graph)
            if not is_valid:
                run.status = OrchestrationStatus.FAILED
                run.executive_summary = f"Task planning failed validation: {'; '.join(validation_errors)}"
                run.duration_ms = round((time.time() - start_time) * 1000, 2)
                save_orchestration_run(run)
                return run

            # 4. Build Context
            context = OrchestrationContextManager.build_context(
                user_id=user_id,
                database_identity=database_identity,
                goal=sanitized_goal,
                engine=engine,
                db_type=db_type,
            )

            # 5. Execute TaskGraph
            run.status = OrchestrationStatus.EXECUTING
            evidence_ledger = []
            executed_graph = OrchestrationExecutor.execute_graph(task_graph, context, evidence_ledger)
            run.task_graph = executed_graph
            run.evidence_ledger = evidence_ledger

            # 6. Detect and Resolve Conflicts
            conflicts = OrchestrationConflictResolver.detect_and_resolve_conflicts(evidence_ledger, context)
            run.conflicts = conflicts

            # 7. Check for Proposed Actions
            for step in executed_graph.steps:
                if step.agent_id == "action_agent" and step.output and step.output.get("action_proposal"):
                    prop_data = step.output["action_proposal"]
                    run.proposed_action = ProposedActionSummary.from_dict(prop_data)
                    break

            # 8. Evaluate Completion Status
            completed_steps = [s for s in executed_graph.steps if s.status == TaskStepStatus.COMPLETED]
            failed_steps = [s for s in executed_graph.steps if s.status == TaskStepStatus.FAILED]

            if run.proposed_action:
                run.status = OrchestrationStatus.WAITING_FOR_CONFIRMATION
            elif not failed_steps:
                run.status = OrchestrationStatus.COMPLETED
            elif completed_steps and failed_steps:
                run.status = OrchestrationStatus.PARTIALLY_COMPLETED
            else:
                run.status = OrchestrationStatus.FAILED

            # 9. Set Confidence Tier
            if not run.evidence_ledger:
                run.confidence_tier = ConfidenceTier.LIMITED
            elif any(c for c in conflicts if not c.resolved):
                run.confidence_tier = ConfidenceTier.MODERATE
            else:
                run.confidence_tier = ConfidenceTier.HIGH

            # 10. Generate Explanations
            run.completed_at = datetime.now(timezone.utc).isoformat()
            run.duration_ms = round((time.time() - start_time) * 1000, 2)
            explanation = OrchestrationExplainer.explain(run)
            run.explanation = explanation
            run.executive_summary = explanation.get("executive_summary", "")

            # 11. Persist Run
            save_orchestration_run(run)
            return run

        except Exception as e:
            logger.error(f"Orchestration pipeline exception: {e}", exc_info=True)
            run.status = OrchestrationStatus.FAILED
            run.executive_summary = f"Orchestration encountered fatal error: {e}"
            run.duration_ms = round((time.time() - start_time) * 1000, 2)
            save_orchestration_run(run)
            return run


# Singleton instance
_default_orchestrator = AgentOrchestrator()


def orchestrate_goal(
    goal: str,
    user_id: str,
    database_identity: str,
    engine: Optional[Any] = None,
    db_type: str = "sqlite",
) -> OrchestrationRun:
    """Convenience helper to run orchestration."""
    return _default_orchestrator.orchestrate(
        goal=goal,
        user_id=user_id,
        database_identity=database_identity,
        engine=engine,
        db_type=db_type,
    )
