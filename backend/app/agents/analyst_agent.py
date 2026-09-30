from __future__ import annotations

from typing import Any

from app.agents.base_agent import BaseAgent
from app.agents.models import AgentFinding, AgentResult, AgentTask
from app.intelligence.ai_analyst.analyst import run_ai_analysis


class AnalystAgent(BaseAgent):
    name = "analyst_agent"
    role = "Business & Data Analyst"
    description = (
        "Performs in-depth business data analysis, identifies drivers of metric performance, "
        "and synthesizes analytical findings into clear executive insights."
    )
    is_read_only = True
    capabilities = [
        "Answer complex business intelligence inquiries",
        "Investigate metric movements and historical drivers",
        "Deconstruct dimensional breakdowns and distributions",
        "Produce actionable business recommendations",
    ]
    allowed_tools = ["ai_analyst", "query_executor", "chart_renderer"]

    def execute(self, task: AgentTask, context: dict[str, Any]) -> AgentResult:
        steps = [f"Analyzing analytical query: '{task.request}'"]

        analysis = run_ai_analysis(task.request)
        if (analysis.status or "").upper() != "SUCCESS":
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                status="FAILED",
                summary=analysis.error_message or "Analysis could not be completed.",
                findings=[],
                evidence={},
                recommendations=[],
                proposed_action=None,
                limitations=["Ensure database has valid numerical/time-series data."],
                execution_steps=steps,
            )

        steps.append(f"AI Analyst classified intent as '{analysis.analysis_type}' and executed analytical pipeline.")

        findings: list[AgentFinding] = []
        if analysis.key_insight:
            findings.append(
                AgentFinding(
                    id="analyst_key_insight",
                    severity="INFO",
                    title="Key Analytical Insight",
                    description=analysis.key_insight,
                    evidence={"key_insight": analysis.key_insight},
                )
            )

        # Breakdowns
        if analysis.breakdown:
            for idx, item in enumerate(analysis.breakdown):
                findings.append(
                    AgentFinding(
                        id=f"analyst_breakdown_{idx}",
                        severity="INFO",
                        title=f"Distribution Item: {item.get('dimension', idx)}",
                        description=f"Value: {item.get('value')} ({item.get('percentage', 0):.1f}%)",
                        evidence=item,
                    )
                )

        evidence = {
            "analysis_type": analysis.analysis_type,
            "evidence": analysis.evidence,
            "sql_query": analysis.sql_query,
            "has_chart": bool(analysis.chart),
        }

        steps.append("Synthesized observations and formulated executive recommendations.")

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            status="COMPLETED",
            summary=analysis.key_insight or "Analysis completed successfully.",
            findings=findings,
            evidence=evidence,
            recommendations=analysis.recommended_investigations or [
                "Track this metric across subsequent reporting periods.",
                "Review dimensional drivers for anomalous variances.",
            ],
            proposed_action=None,
            limitations=[
                "Read-only analyst: cannot modify underlying tables.",
                "Derived from historical data in connected database.",
            ],
            execution_steps=steps,
        )

