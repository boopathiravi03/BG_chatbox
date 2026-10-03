"""
backend/app/intelligence/orchestration/executor.py

In-process DAG executor for Phase 9.2: Advanced Agent Orchestration.
Executes steps in topological batches with step-level isolation, timeouts, retries,
and permission enforcement via the SafetyGate.
"""

from __future__ import annotations

import time
import logging
import concurrent.futures
from typing import Dict, Any, List, Optional

from app.intelligence.orchestration.models import (
    TaskGraph,
    PlanStep,
    TaskStepStatus,
    OrchestrationStatus,
    EvidenceItem,
)
from app.intelligence.orchestration.agent_registry import (
    get_agent_handler,
    get_registered_agent,
)
from app.intelligence.orchestration.task_graph import get_execution_batches
from app.intelligence.orchestration.safety_gate import OrchestrationSafetyGate
from app.intelligence.orchestration.evidence_aggregator import EvidenceAggregator

logger = logging.getLogger(__name__)

STEP_TIMEOUT_SECONDS = 15.0
MAX_STEP_RETRIES = 2


class OrchestrationExecutor:
    """
    Coordinates the robust, in-process execution of a validated TaskGraph.
    """

    @classmethod
    def execute_graph(
        cls,
        graph: TaskGraph,
        context: Dict[str, Any],
        evidence_ledger: List[EvidenceItem],
    ) -> TaskGraph:
        """
        Executes all steps in a TaskGraph according to topological batches.
        """
        batches = get_execution_batches(graph)
        step_results: Dict[str, Dict[str, Any]] = {}

        for batch in batches:
            # Check if any dependencies for steps in this batch failed
            runnable_steps: List[PlanStep] = []
            for step in batch:
                failed_deps = [
                    dep for dep in step.dependencies
                    if step_results.get(dep, {}).get("status") in ("failed", "blocked")
                ]
                if failed_deps:
                    step.status = TaskStepStatus.BLOCKED
                    step.error = f"Blocked by failed dependencies: {', '.join(failed_deps)}"
                    step_results[step.step_id] = {"status": "blocked", "error": step.error}
                else:
                    runnable_steps.append(step)

            if not runnable_steps:
                continue

            # Execute batch: run read-only steps in parallel if multiple exist
            if len(runnable_steps) > 1 and all(
                get_registered_agent(s.agent_id) and get_registered_agent(s.agent_id).is_read_only
                for s in runnable_steps
            ):
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(3, len(runnable_steps))) as pool:
                    futures = {
                        pool.submit(cls._execute_single_step, s, context, step_results): s
                        for s in runnable_steps
                    }
                    for fut in concurrent.futures.as_completed(futures):
                        step = futures[fut]
                        try:
                            output = fut.result()
                            step_results[step.step_id] = output
                            # Aggregate evidence
                            if step.status == TaskStepStatus.COMPLETED and output:
                                new_ev = EvidenceAggregator.aggregate_step_output(step, output, evidence_ledger)
                                evidence_ledger.extend(new_ev)
                        except Exception as e:
                            step.status = TaskStepStatus.FAILED
                            step.error = str(e)
                            step_results[step.step_id] = {"status": "failed", "error": str(e)}
            else:
                for step in runnable_steps:
                    try:
                        output = cls._execute_single_step(step, context, step_results)
                        step_results[step.step_id] = output
                        if step.status == TaskStepStatus.COMPLETED and output:
                            new_ev = EvidenceAggregator.aggregate_step_output(step, output, evidence_ledger)
                            evidence_ledger.extend(new_ev)
                    except Exception as e:
                        step.status = TaskStepStatus.FAILED
                        step.error = str(e)
                        step_results[step.step_id] = {"status": "failed", "error": str(e)}

        return graph

    @classmethod
    def _execute_single_step(
        cls,
        step: PlanStep,
        context: Dict[str, Any],
        prior_results: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Executes a single step with permission checking, timeout, and retry handling.
        """
        # 1. Safety Gate: validate step permissions
        is_allowed, perm_err = OrchestrationSafetyGate.validate_step_permissions(step)
        if not is_allowed:
            step.status = TaskStepStatus.BLOCKED
            step.error = perm_err
            return {"status": "blocked", "error": perm_err}

        handler = get_agent_handler(step.agent_id)
        if not handler:
            step.status = TaskStepStatus.FAILED
            step.error = f"No execution handler registered for agent '{step.agent_id}'."
            return {"status": "failed", "error": step.error}

        agent_desc = get_registered_agent(step.agent_id)
        max_retries = MAX_STEP_RETRIES if agent_desc and agent_desc.is_read_only else 0

        # Inject outputs from dependent steps into step inputs
        step_context = dict(context)
        step_context["prior_results"] = prior_results
        step_context["step_inputs"] = step.inputs

        step.status = TaskStepStatus.RUNNING
        start_time = time.time()
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                step.retry_count = attempt
                output = handler(step, step_context)

                # Validate step output via Safety Gate
                valid_output, output_err = OrchestrationSafetyGate.validate_step_output(step, output)
                if not valid_output:
                    step.status = TaskStepStatus.FAILED
                    step.error = f"Safety Gate rejected output: {output_err}"
                    step.duration_ms = round((time.time() - start_time) * 1000, 2)
                    return {"status": "failed", "error": step.error}

                step.status = TaskStepStatus.COMPLETED
                step.output = output
                step.duration_ms = round((time.time() - start_time) * 1000, 2)
                return output

            except Exception as e:
                last_error = e
                logger.warning(f"Step {step.step_id} ({step.agent_id}) attempt {attempt+1} failed: {e}")
                time.sleep(0.1)

        step.status = TaskStepStatus.FAILED
        step.error = str(last_error)
        step.duration_ms = round((time.time() - start_time) * 1000, 2)
        return {"status": "failed", "error": str(last_error)}
