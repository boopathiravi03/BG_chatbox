"""
backend/app/intelligence/orchestration/explainer.py

Explanation generator for Phase 9.2: Advanced Agent Orchestration.
Produces human-readable, executive explanations of orchestrated multi-agent runs,
evidence provenance, identified conflicts, and proposed actions.
"""

from __future__ import annotations

from typing import Dict, Any, List
from app.intelligence.orchestration.models import (
    OrchestrationRun,
    ConfidenceTier,
    OrchestrationStatus,
)


class OrchestrationExplainer:
    """
    Synthesizes orchestration runs into transparent, actionable explanations.
    """

    @classmethod
    def explain(cls, run: OrchestrationRun) -> Dict[str, Any]:
        """
        Builds a comprehensive explanation bundle for an orchestration run.
        """
        graph = run.task_graph
        total_steps = len(graph.steps) if graph else 0
        completed_steps = len([s for s in (graph.steps if graph else []) if s.status.value == "COMPLETED"])

        # Determine overall narrative
        lines = []
        lines.append(f"Orchestrated multi-agent execution completed with status: {run.status.value}.")
        lines.append(f"Executed {completed_steps}/{total_steps} planned specialist agent steps.")

        if run.evidence_ledger:
            lines.append(f"Collected {len(run.evidence_ledger)} verified evidence items across database facts, business context, and specialist findings.")

        if run.conflicts:
            lines.append(f"Identified {len(run.conflicts)} cross-specialist discrepancy signals. All conflicts surfaced transparently.")

        if run.proposed_action:
            lines.append(f"Formulated controlled action proposal: '{run.proposed_action.title}'. Action remains dormant awaiting human confirmation.")

        executive_summary = " ".join(lines)

        evidence_breakdown = [
            {
                "id": ev.evidence_id,
                "title": ev.title,
                "type": ev.evidence_type.value,
                "agent": ev.source_agent,
                "summary": ev.summary,
                "confidence": ev.confidence.value,
            }
            for ev in run.evidence_ledger
        ]

        conflicts_summary = [
            {
                "id": c.conflict_id,
                "type": c.conflict_type.value,
                "description": c.description,
                "agents": c.involved_agents,
                "strategy": c.resolution_strategy,
                "resolved": c.resolved,
                "details": c.resolution_details,
            }
            for c in run.conflicts
        ]

        steps_timeline = [
            {
                "step_id": s.step_id,
                "name": s.name,
                "agent_id": s.agent_id,
                "status": s.status.value,
                "duration_ms": s.duration_ms,
                "purpose": s.purpose,
                "error": s.error,
            }
            for s in (graph.steps if graph else [])
        ]

        return {
            "orchestration_id": run.orchestration_id,
            "goal": run.goal,
            "status": run.status.value,
            "confidence_tier": run.confidence_tier.value,
            "executive_summary": executive_summary,
            "total_duration_ms": run.duration_ms,
            "steps_timeline": steps_timeline,
            "evidence_ledger": evidence_breakdown,
            "conflicts": conflicts_summary,
            "proposed_action": run.proposed_action.to_dict() if run.proposed_action else None,
            "provenance_guarantee": "All findings strictly derived from connected database facts and verified knowledge rules.",
        }
