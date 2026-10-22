"""backend/app/intelligence/governance/policy_engine.py

Deterministic Policy Evaluation Engine for Phase 9.3: Enterprise Governance & Observability.
Evaluates operations against immutable system security policies and tenant-scoped policies.
LLMs are never permitted to override policy decisions.
"""

from __future__ import annotations

import re
import logging
from typing import Dict, Any, List, Tuple, Optional

from app.intelligence.governance.models import (
    PolicyCategory,
    PolicyDecision,
    RiskLevel,
)
from app.intelligence.governance.policy_registry import list_policies, get_policy

logger = logging.getLogger(__name__)

# Core safety patterns
_DDL_PATTERN = re.compile(r"\b(drop\s+table|alter\s+table|truncate\s+table|create\s+table|grant\s+all|revoke\s+all)\b", re.IGNORECASE)
_INJECTION_PATTERN = re.compile(r"\b(ignore\s+(?:all\s+)?(?:previous|safety|prior|\s+)*(?:instructions|rules|safety|guidelines)|override\s+safety|bypass\s+confirmation)\b", re.IGNORECASE)


class PolicyEngine:
    """
    Evaluates system, agent, and user operations against registered governance policies.
    """

    @classmethod
    def evaluate(
        cls,
        category: PolicyCategory,
        operation: str,
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> Tuple[PolicyDecision, List[str], str]:
        """
        Evaluates an operation against active policies.
        Returns:
            (decision: PolicyDecision, applied_policy_ids: List[str], rationale: str)
        """
        ctx = context or {}
        policies = list_policies(user_id=user_id)
        applied_policies: List[str] = []
        op_text = f"{operation} {ctx.get('sql', '')} {ctx.get('goal', '')} {ctx.get('text', '')}"

        # 1. SQL DDL Safety Policy
        if _DDL_PATTERN.search(op_text):
            pol = get_policy("sys_sql_ddl_safety")
            if pol and pol.enabled:
                has_confirmation = bool(ctx.get("confirmed") or ctx.get("user_confirmed") or ctx.get("confirmation_token"))
                if not has_confirmation:
                    applied_policies.append(pol.policy_id)
                    return PolicyDecision.DENY, applied_policies, "Blocked by policy 'sys_sql_ddl_safety': Destructive schema DDL operations prohibited without explicit human confirmation."

        # 2. Prompt Injection Guard Policy
        if _INJECTION_PATTERN.search(op_text):
            pol = get_policy("sys_prompt_injection_guard")
            if pol and pol.enabled:
                applied_policies.append(pol.policy_id)
                return PolicyDecision.DENY, applied_policies, "Blocked by policy 'sys_prompt_injection_guard': Instruction override pattern detected."

        # 3. Agent Boundary Policy
        agent_perm = ctx.get("agent_permission")
        is_mutation_req = (
            ctx.get("is_mutation")
            or ctx.get("action_type") in ("UPDATE", "DELETE", "MUTATION")
            or any(operation.strip().upper().startswith(kw) for kw in ("UPDATE ", "DELETE ", "INSERT INTO "))
        )
        if agent_perm in ("READ_ONLY", "ANALYTICAL") and is_mutation_req:
            pol = get_policy("sys_read_only_agent_boundary")
            if pol and pol.enabled:
                applied_policies.append(pol.policy_id)
                return PolicyDecision.DENY, applied_policies, f"Blocked by policy 'sys_read_only_agent_boundary': Agent with {agent_perm} permission cannot perform mutations."

        # 4. Mandatory Human Confirmation Policy for mutations
        if is_mutation_req:
            has_hmac = bool(ctx.get("confirmation_token") or ctx.get("confirmed"))
            if not has_hmac:
                pol = get_policy("sys_action_human_confirmation")
                if pol and pol.enabled:
                    applied_policies.append(pol.policy_id)
                    return PolicyDecision.REQUIRE_CONFIRMATION, applied_policies, "Enforced policy 'sys_action_human_confirmation': Mutation proposal requires human confirmation."

        # 5. Credential Leak Guard Policy
        str_repr = str(ctx).lower()
        if "password=" in str_repr or "secret=" in str_repr:
            pol = get_policy("sys_credential_leak_guard")
            if pol and pol.enabled:
                applied_policies.append(pol.policy_id)
                return PolicyDecision.DENY, applied_policies, "Blocked by policy 'sys_credential_leak_guard': Potential credential leakage detected in payload."

        # 6. Tenant & DB Isolation Policy
        if ctx.get("tenant_mismatch") or ctx.get("db_mismatch"):
            pol = get_policy("sys_cross_tenant_isolation")
            if pol and pol.enabled:
                applied_policies.append(pol.policy_id)
                return PolicyDecision.DENY, applied_policies, "Blocked by policy 'sys_cross_tenant_isolation': Tenant or database boundary mismatch."

        # Default ALLOW
        return PolicyDecision.ALLOW, applied_policies, "Operation satisfies all active governance and safety policies."
