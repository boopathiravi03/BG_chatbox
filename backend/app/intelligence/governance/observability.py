"""backend/app/intelligence/governance/observability.py

Observability & Telemetry Aggregator for Phase 9.3: Enterprise Governance & Observability.
Aggregates factual operational metrics derived from recorded audit logs and agent traces.
Strictly non-evaluative: reports operational measurements without subjective rankings.
"""

from __future__ import annotations

import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta

from app.intelligence.governance.models import (
    GovernanceSummary,
    AgentObservabilityMetric,
)
from app.intelligence.governance.audit_store import (
    _get_connection,
    _init_db,
    _DB_LOCK,
    verify_audit_chain,
)
from app.intelligence.orchestration.agent_registry import list_registered_agents


class GovernanceObservability:
    """
    Computes aggregated operational metrics from factual database telemetry.
    """

    @classmethod
    def get_governance_summary(
        cls,
        user_id: str,
        database_identity: str = "none",
        days: int = 7,
    ) -> GovernanceSummary:
        """
        Synthesizes operational health metrics for the specified time window.
        """
        now = datetime.now(timezone.utc)
        start_cutoff = (now - timedelta(days=days)).isoformat()
        is_chain_valid, verified_count, _ = verify_audit_chain(user_id)

        with _DB_LOCK:
            conn = _get_connection()
            try:
                _init_db(conn)
                cur = conn.cursor()

                # 1. Total audit events
                cur.execute(
                    "SELECT COUNT(*) FROM governance_audit_events WHERE user_id = ? AND timestamp >= ?",
                    (user_id, start_cutoff),
                )
                total_audits = cur.fetchone()[0]

                # 2. Security events count & high/critical count
                cur.execute(
                    "SELECT COUNT(*) FROM security_events WHERE user_id = ? AND timestamp >= ?",
                    (user_id, start_cutoff),
                )
                total_sec = cur.fetchone()[0]

                cur.execute(
                    """
                    SELECT COUNT(*) FROM security_events 
                    WHERE user_id = ? AND timestamp >= ? AND severity IN ('HIGH', 'CRITICAL')
                    """,
                    (user_id, start_cutoff),
                )
                high_crit_sec = cur.fetchone()[0]

                # 3. Policy evaluations and blocks
                cur.execute(
                    """
                    SELECT COUNT(*) FROM governance_audit_events
                    WHERE user_id = ? AND timestamp >= ? AND event_type IN ('POLICY_CHECK', 'POLICY_BLOCK')
                    """,
                    (user_id, start_cutoff),
                )
                policy_evals = cur.fetchone()[0]

                cur.execute(
                    """
                    SELECT COUNT(*) FROM governance_audit_events
                    WHERE user_id = ? AND timestamp >= ? AND (event_type = 'POLICY_BLOCK' OR result IN ('BLOCKED', 'DENIED'))
                    """,
                    (user_id, start_cutoff),
                )
                policy_blocks = cur.fetchone()[0]

                # 4. Agent executions & duration
                cur.execute(
                    """
                    SELECT COUNT(*), AVG(duration_ms), SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END)
                    FROM agent_traces
                    WHERE user_id = ? AND started_at >= ?
                    """,
                    (user_id, start_cutoff),
                )
                agent_row = cur.fetchone()
                total_agent_execs = agent_row[0] or 0
                avg_agent_duration = round(agent_row[1] or 0.0, 2)
                agent_failures = agent_row[2] or 0

                # 5. Business actions counts
                cur.execute(
                    """
                    SELECT COUNT(*) FROM governance_audit_events
                    WHERE user_id = ? AND timestamp >= ? AND event_type = 'ACTION_PROPOSED'
                    """,
                    (user_id, start_cutoff),
                )
                actions_proposed = cur.fetchone()[0]

                cur.execute(
                    """
                    SELECT COUNT(*) FROM governance_audit_events
                    WHERE user_id = ? AND timestamp >= ? AND event_type = 'ACTION_CONFIRMED'
                    """,
                    (user_id, start_cutoff),
                )
                actions_confirmed = cur.fetchone()[0]

                cur.execute(
                    """
                    SELECT COUNT(*) FROM governance_audit_events
                    WHERE user_id = ? AND timestamp >= ? AND event_type = 'ACTION_EXECUTED'
                    """,
                    (user_id, start_cutoff),
                )
                actions_executed = cur.fetchone()[0]

                # 6. Data access queries
                cur.execute(
                    "SELECT COUNT(*) FROM data_access_events WHERE user_id = ? AND timestamp >= ?",
                    (user_id, start_cutoff),
                )
                data_queries = cur.fetchone()[0]

                # 7. Orchestrations count
                cur.execute(
                    """
                    SELECT COUNT(*) FROM governance_audit_events
                    WHERE user_id = ? AND timestamp >= ? AND event_type = 'ORCHESTRATION_STARTED'
                    """,
                    (user_id, start_cutoff),
                )
                total_orch = cur.fetchone()[0]

                cur.execute(
                    """
                    SELECT COUNT(*) FROM governance_audit_events
                    WHERE user_id = ? AND timestamp >= ? AND event_type = 'ORCHESTRATION_COMPLETED'
                    """,
                    (user_id, start_cutoff),
                )
                succ_orch = cur.fetchone()[0]

                cur.execute(
                    """
                    SELECT COUNT(*) FROM governance_audit_events
                    WHERE user_id = ? AND timestamp >= ? AND event_type = 'ORCHESTRATION_FAILED'
                    """,
                    (user_id, start_cutoff),
                )
                fail_orch = cur.fetchone()[0]

                return GovernanceSummary(
                    user_id=user_id,
                    database_identity=database_identity,
                    time_window=f"Past {days} days",
                    total_audit_events=total_audits,
                    total_orchestrations=total_orch,
                    successful_orchestrations=succ_orch,
                    failed_orchestrations=fail_orch,
                    total_agent_executions=total_agent_execs,
                    agent_failures=agent_failures,
                    average_agent_duration_ms=avg_agent_duration,
                    policy_evaluations_count=policy_evals,
                    policy_blocks_count=policy_blocks,
                    security_events_count=total_sec,
                    high_critical_security_count=high_crit_sec,
                    actions_proposed_count=actions_proposed,
                    actions_confirmed_count=actions_confirmed,
                    actions_executed_count=actions_executed,
                    data_access_queries_count=data_queries,
                    hash_chain_verified=is_chain_valid,
                )
            finally:
                conn.close()

    @classmethod
    def get_agent_metrics(cls, user_id: str) -> List[AgentObservabilityMetric]:
        """
        Computes operational measurements for all registered specialist agents.
        """
        registered = list_registered_agents()
        metrics: List[AgentObservabilityMetric] = []

        with _DB_LOCK:
            conn = _get_connection()
            try:
                _init_db(conn)
                cur = conn.cursor()

                for agent in registered:
                    cur.execute(
                        """
                        SELECT 
                            COUNT(*),
                            SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END),
                            SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END),
                            SUM(CASE WHEN status = 'BLOCKED' THEN 1 ELSE 0 END),
                            AVG(duration_ms),
                            MAX(started_at)
                        FROM agent_traces
                        WHERE user_id = ? AND agent_id = ?
                        """,
                        (user_id, agent.agent_id),
                    )
                    row = cur.fetchone()
                    total = row[0] or 0
                    succ = row[1] or 0
                    failed = row[2] or 0
                    blocked = row[3] or 0
                    avg_dur = round(row[4] or 0.0, 2)
                    last_exec = row[5]

                    metrics.append(
                        AgentObservabilityMetric(
                            agent_id=agent.agent_id,
                            name=agent.name,
                            total_executions=total,
                            successful_executions=succ,
                            failed_executions=failed,
                            blocked_executions=blocked,
                            average_duration_ms=avg_dur,
                            last_execution_at=last_exec,
                            error_count=failed,
                        )
                    )
                return metrics
            finally:
                conn.close()


def get_governance_summary(
    user_id: str,
    database_identity: str = "none",
    days: int = 7,
    time_window: Optional[str] = None,
) -> GovernanceSummary:
    """Return unified governance summary."""
    return GovernanceObservability.get_governance_summary(
        user_id=user_id,
        database_identity=database_identity,
        days=days,
    )


def get_agent_observability_metrics(
    user_id: str,
    database_identity: str = "none",
) -> List[AgentObservabilityMetric]:
    """Return observability metrics for all registered agents."""
    return GovernanceObservability.get_agent_metrics(user_id=user_id)
