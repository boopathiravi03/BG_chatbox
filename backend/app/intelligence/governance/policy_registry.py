"""backend/app/intelligence/governance/policy_registry.py

Policy definition and registry management for Phase 9.3: Enterprise Governance & Observability.
Houses immutable system policies that can NEVER be disabled or overridden by LLMs or users.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional
from datetime import datetime, timezone

from app.intelligence.governance.models import (
    GovernancePolicy,
    PolicyCategory,
    PolicyScope,
    PolicyDecision,
    RiskLevel,
)

_POLICY_LOCK = threading.RLock()


class PolicyModificationError(Exception):
    """Raised when an illegal modification to a protected system policy is attempted."""
    pass


# Registry stores
_SYSTEM_POLICIES: Dict[str, GovernancePolicy] = {}
_USER_POLICIES: Dict[str, Dict[str, GovernancePolicy]] = {}  # user_id -> {policy_id -> GovernancePolicy}


def initialize_default_policies() -> None:
    """Registers default immutable system policies."""
    with _POLICY_LOCK:
        if _SYSTEM_POLICIES:
            return

        # 1. SQL DDL Safety (Prohibits destructive DDL)
        _SYSTEM_POLICIES["sys_sql_ddl_safety"] = GovernancePolicy(
            policy_id="sys_sql_ddl_safety",
            name="SQL DDL Safety Policy",
            description="Strictly prohibits all DROP, ALTER, TRUNCATE, and GRANT operations.",
            category=PolicyCategory.SECURITY,
            scope=PolicyScope.SYSTEM_POLICY,
            enabled=True,
            decision=PolicyDecision.DENY,
            rule_spec={"disallowed_statements": ["DROP", "ALTER", "TRUNCATE", "CREATE", "GRANT", "REVOKE"]},
            severity=RiskLevel.BLOCKED,
        )

        # 2. Prompt Injection Guard (Prohibits instruction overrides)
        _SYSTEM_POLICIES["sys_prompt_injection_guard"] = GovernancePolicy(
            policy_id="sys_prompt_injection_guard",
            name="Prompt Injection Guard",
            description="Blocks requests containing instruction override or prompt jailbreak directives.",
            category=PolicyCategory.SECURITY,
            scope=PolicyScope.SYSTEM_POLICY,
            enabled=True,
            decision=PolicyDecision.DENY,
            rule_spec={"blocked_patterns": ["ignore all previous", "override safety", "bypass confirmation"]},
            severity=RiskLevel.HIGH,
        )

        # 3. Mandatory Human Confirmation for Mutations
        _SYSTEM_POLICIES["sys_action_human_confirmation"] = GovernancePolicy(
            policy_id="sys_action_human_confirmation",
            name="Mandatory Human Confirmation for Business Mutations",
            description="Requires explicit cryptographic HMAC token confirmation for any database write.",
            category=PolicyCategory.ACTION_EXECUTION,
            scope=PolicyScope.SYSTEM_POLICY,
            enabled=True,
            decision=PolicyDecision.REQUIRE_CONFIRMATION,
            rule_spec={"mutation_types": ["INSERT", "UPDATE", "DELETE"]},
            severity=RiskLevel.HIGH,
        )

        # 4. Read-Only Agent Boundary Enforcement
        _SYSTEM_POLICIES["sys_read_only_agent_boundary"] = GovernancePolicy(
            policy_id="sys_read_only_agent_boundary",
            name="Read-Only Agent Boundary Enforcement",
            description="Prevents non-action analytical agents from initiating or proposing state modifications.",
            category=PolicyCategory.AGENT_ACCESS,
            scope=PolicyScope.SYSTEM_POLICY,
            enabled=True,
            decision=PolicyDecision.DENY,
            rule_spec={"read_only_agents": ["analyst", "health", "anomaly", "performance", "bi"]},
            severity=RiskLevel.HIGH,
        )

        # 5. Credential Leak Prevention
        _SYSTEM_POLICIES["sys_credential_leak_guard"] = GovernancePolicy(
            policy_id="sys_credential_leak_guard",
            name="Credential Leak Prevention",
            description="Prevents database passwords, tokens, and secret connection strings from appearing in prompts.",
            category=PolicyCategory.SECURITY,
            scope=PolicyScope.SYSTEM_POLICY,
            enabled=True,
            decision=PolicyDecision.DENY,
            rule_spec={"redact_keys": ["password", "token", "secret", "private_key"]},
            severity=RiskLevel.CRITICAL,
        )

        # 6. Tenant and Database Isolation Policy
        _SYSTEM_POLICIES["sys_cross_tenant_isolation"] = GovernancePolicy(
            policy_id="sys_cross_tenant_isolation",
            name="Multi-Tenant Isolation Guard",
            description="Prevents cross-user data access, query execution on foreign databases, or tenant spoofing.",
            category=PolicyCategory.SECURITY,
            scope=PolicyScope.SYSTEM_POLICY,
            enabled=True,
            decision=PolicyDecision.DENY,
            rule_spec={"enforce_user_scope": True, "enforce_db_identity": True},
            severity=RiskLevel.CRITICAL,
        )


def list_policies(user_id: Optional[str] = None) -> List[GovernancePolicy]:
    """Lists all active system policies plus user-defined policies for the tenant."""
    initialize_default_policies()
    with _POLICY_LOCK:
        result = list(_SYSTEM_POLICIES.values())
        if user_id and user_id in _USER_POLICIES:
            result.extend(_USER_POLICIES[user_id].values())
        return result


def get_policy(policy_id: str, user_id: Optional[str] = None) -> Optional[GovernancePolicy]:
    """Retrieves a policy by ID."""
    initialize_default_policies()
    with _POLICY_LOCK:
        if policy_id in _SYSTEM_POLICIES:
            return _SYSTEM_POLICIES[policy_id]
        if user_id and user_id in _USER_POLICIES and policy_id in _USER_POLICIES[user_id]:
            return _USER_POLICIES[user_id][policy_id]
        return None


def register_user_policy(user_id: str, policy: GovernancePolicy) -> GovernancePolicy:
    """Registers or updates a user-defined policy."""
    with _POLICY_LOCK:
        if policy.policy_id in _SYSTEM_POLICIES or policy.scope == PolicyScope.SYSTEM_POLICY:
            raise PolicyModificationError("Cannot overwrite or create system-level security policies.")
        policy.scope = PolicyScope.USER_POLICY
        if user_id not in _USER_POLICIES:
            _USER_POLICIES[user_id] = {}
        _USER_POLICIES[user_id][policy.policy_id] = policy
        return policy


def set_policy_status(policy_id: str, enabled: bool, user_id: str) -> bool:
    """
    Enables or disables a policy.
    SYSTEM policies are protected: attempting to disable them raises PolicyModificationError.
    """
    initialize_default_policies()
    with _POLICY_LOCK:
        if policy_id in _SYSTEM_POLICIES:
            raise PolicyModificationError(
                f"Policy '{policy_id}' is a protected SYSTEM policy and cannot be disabled or modified."
            )
        if user_id in _USER_POLICIES and policy_id in _USER_POLICIES[user_id]:
            _USER_POLICIES[user_id][policy_id].enabled = enabled
            return True
        return False


register_policy = register_user_policy

# Seed on module import
initialize_default_policies()
