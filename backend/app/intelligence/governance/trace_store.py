"""backend/app/intelligence/governance/trace_store.py

Agent execution trace management and request correlation for Phase 9.3: Enterprise Governance.
Connects request_id -> orchestration_id -> step_id -> agent_id -> telemetry.
"""

from __future__ import annotations

import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from app.intelligence.governance.models import (
    AgentTraceRecord,
    RiskLevel,
    PolicyDecision,
)
from app.intelligence.governance.audit_store import (
    save_agent_trace,
    get_agent_trace,
    list_agent_traces_for_orchestration,
)


class GovernanceTraceStore:
    """
    Manages structured trace lifecycles for specialist agents.
    """

    @classmethod
    def start_trace(
        cls,
        user_id: str,
        database_identity: str,
        agent_id: str,
        tool_or_capability: str,
        request_id: Optional[str] = None,
        orchestration_id: Optional[str] = None,
        step_id: Optional[str] = None,
        risk_level: RiskLevel = RiskLevel.LOW,
        policy_decision: PolicyDecision = PolicyDecision.ALLOW,
    ) -> AgentTraceRecord:
        """
        Initializes an execution trace for an agent.
        """
        trace_id = f"trc_{uuid.uuid4().hex[:10]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        req_id = request_id or f"req_{uuid.uuid4().hex[:8]}"

        trace = AgentTraceRecord(
            trace_id=trace_id,
            request_id=req_id,
            agent_id=agent_id,
            user_id=user_id,
            database_identity=database_identity,
            tool_or_capability=tool_or_capability,
            started_at=now_iso,
            duration_ms=0.0,
            status="RUNNING",
            risk_level=risk_level,
            policy_decision=policy_decision,
            evidence_count=0,
            orchestration_id=orchestration_id,
            step_id=step_id,
        )
        return save_agent_trace(trace)

    @classmethod
    def complete_trace(
        cls,
        trace_id: str,
        user_id: str,
        status: str = "SUCCESS",
        duration_ms: float = 0.0,
        evidence_count: int = 0,
        error_message: Optional[str] = None,
    ) -> Optional[AgentTraceRecord]:
        """
        Finalizes an execution trace.
        """
        trace = get_agent_trace(trace_id, user_id=user_id)
        if not trace:
            return None

        trace.completed_at = datetime.now(timezone.utc).isoformat()
        trace.duration_ms = round(duration_ms, 2)
        trace.status = status
        trace.evidence_count = evidence_count
        trace.error_message = error_message

        return save_agent_trace(trace)

    @classmethod
    def get_traces_for_orchestration(
        cls, orchestration_id: str, user_id: str
    ) -> List[AgentTraceRecord]:
        return list_agent_traces_for_orchestration(orchestration_id, user_id)


AgentTraceStore = GovernanceTraceStore
