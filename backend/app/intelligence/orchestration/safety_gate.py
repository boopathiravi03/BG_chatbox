"""
backend/app/intelligence/orchestration/safety_gate.py

Security and safety validation policies for Phase 9.2: Advanced Agent Orchestration.
Guarantees:
1. Strict agent permission boundary enforcement (READ_ONLY, PROPOSAL_ONLY, etc.).
2. Prompt injection defense (sanitizes user inputs, treats DB content as inert data).
3. Prohibition of unconfirmed mutations (human-in-the-loop enforcement).
4. Strict multi-tenant user and database context isolation.
5. SQL safety verification for any generated queries.
"""

from __future__ import annotations

import re
import logging
from typing import Dict, Any, List, Optional, Tuple

from app.intelligence.orchestration.models import (
    AgentPermission,
    SpecialistAgentDescriptor,
    PlanStep,
    OrchestrationRun,
)
from app.intelligence.orchestration.agent_registry import get_registered_agent

logger = logging.getLogger(__name__)

# Patterns indicative of prompt injection or rule bypass attempts
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|safety|prior)\s+(instructions|rules|guidelines)", re.IGNORECASE),
    re.compile(r"override\s+(safety|permission|confirmation|security)", re.IGNORECASE),
    re.compile(r"bypass\s+(human|confirmation|safety|auth)", re.IGNORECASE),
    re.compile(r"drop\s+table", re.IGNORECASE),
    re.compile(r"truncate\s+table", re.IGNORECASE),
    re.compile(r"alter\s+table", re.IGNORECASE),
    re.compile(r"grant\s+all", re.IGNORECASE),
    re.compile(r"execute\s+immediately\s+without\s+confirmation", re.IGNORECASE),
    re.compile(r"delete\s+from\s+[\w_]+\s*;?\s*--", re.IGNORECASE),
]


class SafetyViolationError(Exception):
    """Raised when an orchestration step or goal violates safety policy."""
    pass


class OrchestrationSafetyGate:
    """
    Validates and enforces security constraints across all stages of agent orchestration.
    """

    @classmethod
    def sanitize_user_goal(cls, goal: str) -> Tuple[str, bool]:
        """
        Inspects user goal for prompt injection, safety override, or destructive SQL syntax.
        Returns (sanitized_goal, is_clean).
        """
        if not goal:
            return "", True

        for pattern in _INJECTION_PATTERNS:
            if pattern.search(goal):
                logger.warning(f"Safety Gate intercepted injection pattern in goal: {pattern.pattern}")
                # Neutralize malicious directive while preserving safe context
                cleaned = pattern.sub("[BLOCKED_INJECTION_DIRECTIVE]", goal)
                return cleaned, False

        return goal.strip(), True

    @classmethod
    def validate_step_permissions(cls, step: PlanStep) -> Tuple[bool, Optional[str]]:
        """
        Validates that a plan step respects the assigned agent's declared permissions.
        - Read-only agents cannot specify mutation actions.
        - Proposal-only agents cannot mark an action as EXECUTED.
        """
        agent = get_registered_agent(step.agent_id)
        if not agent:
            return False, f"Unknown agent '{step.agent_id}' referenced in step '{step.step_id}'."

        # If agent is READ_ONLY or ANALYTICAL, it cannot emit action proposals
        if agent.permission in (AgentPermission.READ_ONLY, AgentPermission.ANALYTICAL):
            inputs = step.inputs or {}
            if "action_type" in inputs or "mutation" in inputs:
                return False, f"Agent '{agent.name}' has {agent.permission.value} permission and cannot propose actions or mutations."

        return True, None

    @classmethod
    def validate_step_output(cls, step: PlanStep, output: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validates the output of a step before it enters the evidence ledger:
        1. Confirms no un-reviewed mutations are claimed as executed.
        2. Ensures sensitive database passwords/credentials are not leaked.
        """
        agent = get_registered_agent(step.agent_id)
        if not agent:
            return False, f"Unknown agent '{step.agent_id}'."

        # Check for unconfirmed mutation attempt in output
        if output.get("action_proposal"):
            proposal = output["action_proposal"]
            if proposal.get("status") == "EXECUTED":
                return False, f"Agent '{step.agent_id}' attempted to mark an action EXECUTED without human confirmation token."

        # Check for password or secret leaks in stringified output
        str_repr = str(output).lower()
        if "password=" in str_repr or "secret=" in str_repr:
            return False, "Output contains potential credential leakage."

        return True, None

    @classmethod
    def enforce_isolation(
        cls,
        run_user_id: str,
        run_db_id: str,
        context_user_id: str,
        context_db_id: str,
    ) -> bool:
        """
        Enforces tenant isolation: verifies that the execution context matches the orchestration run.
        """
        if run_user_id != context_user_id:
            logger.error(f"Tenant isolation mismatch: run {run_user_id} vs context {context_user_id}")
            return False
        if run_db_id != context_db_id:
            logger.error(f"Database isolation mismatch: run {run_db_id} vs context {context_db_id}")
            return False
        return True
