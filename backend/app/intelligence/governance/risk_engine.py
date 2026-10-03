"""backend/app/intelligence/governance/risk_engine.py

Deterministic Risk Classification & Explanation Engine for Phase 9.3: Enterprise Governance.
Evaluates operations based on mutation scope, affected rows, agent permissions,
and data sensitivity without arbitrary AI-generated hallucinated scores.
"""

from __future__ import annotations

import uuid
from typing import Dict, Any, List, Optional
from app.intelligence.governance.models import (
    RiskLevel,
    RiskAssessment,
)


class GovernanceRiskEngine:
    """
    Computes deterministic risk assessments and transparent rationales.
    """

    @classmethod
    def assess_risk(
        cls,
        operation: str,
        operation_type: str = "READ_ONLY",  # "READ_ONLY", "ANALYTICAL", "PROPOSAL", "MUTATION", "DDL"
        affected_rows: int = 0,
        agent_permission: str = "READ_ONLY",
        context: Optional[Dict[str, Any]] = None,
    ) -> RiskAssessment:
        """
        Classifies operational risk into deterministic tiers.
        """
        ctx = context or {}
        assessment_id = f"risk_{uuid.uuid4().hex[:8]}"
        contributing_factors: List[str] = []
        applicable_policies: List[str] = []

        # 1. Blocked DDL / Destructive
        if operation_type == "DDL" or any(kw in operation.upper() for kw in ("DROP TABLE", "TRUNCATE", "ALTER TABLE")):
            return RiskAssessment(
                assessment_id=assessment_id,
                risk_level=RiskLevel.BLOCKED,
                operation=operation,
                contributing_factors=["Attempted schema modification or structural table destruction."],
                applicable_policies=["sys_sql_ddl_safety"],
                required_control="Operation Prohibited",
                explanation="Operation violates database integrity rules and cannot be executed under any circumstance.",
            )

        # 2. Critical Mutation (Large blast radius or uncontrolled)
        if operation_type == "MUTATION" and affected_rows > 100:
            contributing_factors.append(f"High blast radius: {affected_rows} estimated affected records.")
            contributing_factors.append("Database state will be permanently altered.")
            applicable_policies.append("sys_action_human_confirmation")
            return RiskAssessment(
                assessment_id=assessment_id,
                risk_level=RiskLevel.CRITICAL,
                operation=operation,
                contributing_factors=contributing_factors,
                applicable_policies=applicable_policies,
                required_control="Mandatory Elevated Human Confirmation",
                explanation=f"Critical operational mutation impacting {affected_rows} rows. Permanent data change requires explicit human confirmation.",
            )

        # 3. High Risk Mutation (Standard mutation)
        if operation_type == "MUTATION" or ctx.get("is_mutation"):
            contributing_factors.append(f"State mutation affecting estimated {affected_rows} rows.")
            applicable_policies.append("sys_action_human_confirmation")
            return RiskAssessment(
                assessment_id=assessment_id,
                risk_level=RiskLevel.HIGH,
                operation=operation,
                contributing_factors=contributing_factors,
                applicable_policies=applicable_policies,
                required_control="Mandatory Human Confirmation",
                explanation="Database record write or modification. Requires cryptographic confirmation prior to execution.",
            )

        # 4. Medium Risk: Proposal or Analytical Modification
        if operation_type in ("PROPOSAL", "ANALYTICAL") or agent_permission in ("FULL_ACTION", "PROPOSE"):
            contributing_factors.append("Analytical or action planning step proposing potential future state changes.")
            return RiskAssessment(
                assessment_id=assessment_id,
                risk_level=RiskLevel.MEDIUM,
                operation=operation,
                contributing_factors=contributing_factors,
                applicable_policies=[],
                required_control="Policy Review & Preview",
                explanation="Operation prepares business proposals or complex analytics without altering database records.",
            )

        # 5. Low Risk: Standard Read-Only Queries
        contributing_factors.append("Read-only execution with bounded query parameters.")
        return RiskAssessment(
            assessment_id=assessment_id,
            risk_level=RiskLevel.LOW,
            operation=operation,
            contributing_factors=contributing_factors,
            applicable_policies=[],
            required_control="Audit Telemetry Logging",
            explanation="Safe read-only operation. Telemetry captured into audit log.",
        )
