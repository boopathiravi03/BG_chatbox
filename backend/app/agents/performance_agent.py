from __future__ import annotations

from typing import Any

from app.agents.base_agent import BaseAgent
from app.agents.models import AgentFinding, AgentResult, AgentTask
from app.intelligence.scanner import get_cached_report, run_database_intelligence_scan


class PerformanceAgent(BaseAgent):
    name = "performance_agent"
    role = "Performance & Indexing Advisor"
    description = (
        "Identifies potential performance issues, unindexed foreign keys, missing primary keys, "
        "and expensive schema patterns without claiming unmeasured query latencies."
    )
    is_read_only = True
    capabilities = [
        "Audit indexing coverage across tables and foreign keys",
        "Detect tables lacking primary keys that may impact query performance",
        "Evaluate large table scans and indexing recommendations",
        "Surface schema design optimizations",
    ]
    allowed_tools = ["performance_analyzer", "schema_inspector", "index_auditor"]

    def execute(self, task: AgentTask, context: dict[str, Any]) -> AgentResult:
        steps = ["Auditing schema performance and indexing structure..."]

        report = get_cached_report()
        if report is None:
            steps.append("Refreshing database profile for performance analysis...")
            report = run_database_intelligence_scan(force_refresh=False)

        if report is None:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                status="FAILED",
                summary="Unable to retrieve database performance metadata.",
                findings=[],
                evidence={},
                recommendations=[],
                proposed_action=None,
                limitations=["Connected database required."],
                execution_steps=steps,
            )

        findings: list[AgentFinding] = []
        recommendations: list[str] = []

        # 1. Performance Findings from Intelligence Engine
        for pf in report.performance_findings:
            findings.append(
                AgentFinding(
                    id=f"perf_{pf.table}_{pf.column or 'general'}",
                    severity="WARNING",
                    title=f"Potential Performance Issue: {pf.table}",
                    description=pf.description,
                    table=pf.table,
                    column=pf.column,
                    evidence={"recommendation": pf.recommendation, "type": pf.type},
                )
            )
            recommendations.append(pf.recommendation)

        # 2. Check for missing PKs as potential performance bottlenecks
        if report.health_score:
            hs = report.health_score
            breakdown = getattr(hs, "breakdown", {}) if not isinstance(hs, int) else {}
            missing_pks = breakdown.get("missing_primary_keys", [])

            for tbl in missing_pks:
                findings.append(
                    AgentFinding(
                        id=f"perf_missing_pk_{tbl}",
                        severity="WARNING",
                        title=f"Potential Performance Issue: Missing Primary Key in '{tbl}'",
                        description=(
                            f"Table '{tbl}' lacks a clustered primary index. "
                            "Row lookups and relational joins may require sequential table scans."
                        ),
                        table=tbl,
                        evidence={"table": tbl, "issue": "Missing Primary Key"},
                    )
                )
                recommendations.append(f"Create a primary key on '{tbl}' to ensure indexed record lookups.")

        summary = (
            f"Performance audit identified {len(findings)} potential performance issue(s) "
            f"across {report.total_tables} tables. Findings focus on structural indexing efficiency and join paths."
        )

        steps.append("Performance and indexing review completed.")

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            status="COMPLETED",
            summary=summary,
            findings=findings,
            evidence={
                "total_findings": len(findings),
                "total_tables_checked": report.total_tables,
                "database_type": report.database_type,
            },
            recommendations=recommendations or ["Schema indexing structure is operating within optimal baseline parameters."],
            proposed_action=None,
            limitations=[
                "Read-only performance advisor: does not measure live network latency or runtime query execution times without active tracing.",
                "Identifies architectural bottlenecks based on indexing patterns.",
            ],
            execution_steps=steps,
        )
