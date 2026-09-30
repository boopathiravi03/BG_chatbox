from __future__ import annotations

from typing import Any

from app.agents.base_agent import BaseAgent
from app.agents.models import AgentFinding, AgentResult, AgentTask
from app.intelligence.scanner import get_cached_report, run_database_intelligence_scan


class DatabaseHealthAgent(BaseAgent):
    name = "database_health_agent"
    role = "Database Health Specialist"
    description = (
        "Diagnoses relational architecture, schema integrity, missing primary keys, "
        "orphan foreign keys, null ratios, and empty tables without executing any modifications."
    )
    is_read_only = True
    capabilities = [
        "Evaluate overall database health score",
        "Inspect schema integrity and missing primary keys",
        "Identify unindexed foreign key relationships",
        "Diagnose empty tables and null-heavy fields",
    ]
    allowed_tools = ["intelligence_report", "schema_analyzer", "health_scorer"]

    def execute(self, task: AgentTask, context: dict[str, Any]) -> AgentResult:
        steps = ["Querying database intelligence profile..."]

        report = get_cached_report()
        if report is None:
            steps.append("No cached report found. Running fresh intelligence scan...")
            report = run_database_intelligence_scan(force_refresh=False)

        if report is None or report.health_score is None:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                status="FAILED",
                summary="Unable to retrieve database health data. Please verify database connection.",
                findings=[],
                evidence={},
                recommendations=["Connect to a valid database instance to run health diagnosis."],
                proposed_action=None,
                limitations=["Database connection required."],
                execution_steps=steps,
            )

        hs = report.health_score
        if isinstance(hs, int):
            score = hs
            grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D" if score >= 40 else "F"
            breakdown = {}
        else:
            score = getattr(hs, "score", 0)
            grade = getattr(hs, "grade", "N/A")
            breakdown = getattr(hs, "breakdown", {}) or {}
        steps.append(f"Retrieved health assessment: {score}/100 (Grade {grade})")

        findings: list[AgentFinding] = []
        recommendations: list[str] = []

        # 1. Missing Primary Keys
        missing_pks = breakdown.get("missing_primary_keys", [])

        if missing_pks:
            findings.append(
                AgentFinding(
                    id=f"dh_missing_pks",
                    severity="WARNING",
                    title="Tables Missing Primary Keys",
                    description=f"{len(missing_pks)} table(s) lack a defined primary key: {', '.join(missing_pks)}",
                    table=missing_pks[0] if len(missing_pks) == 1 else None,
                    evidence={"missing_tables": missing_pks},
                )
            )
            recommendations.append(f"Define primary keys on {len(missing_pks)} table(s) to preserve entity integrity.")

        # 2. Orphan Foreign Keys
        dq = report.data_quality
        if dq and dq.orphan_foreign_keys:
            total_orphans = sum(
                o.get("orphan_count", 0) if isinstance(o, dict) else getattr(o, "orphan_count", 0)
                for o in dq.orphan_foreign_keys
            )
            findings.append(
                AgentFinding(
                    id="dh_orphan_fks",
                    severity="CRITICAL",
                    title="Broken Foreign Key References",
                    description=f"Identified {total_orphans} orphan record(s) across relational constraints.",
                    evidence=dq.orphan_foreign_keys,
                )
            )
            recommendations.append("Investigate orphan records in Data Quality Agent or prepare corrective action.")

        # 3. Empty Tables
        if dq and dq.empty_tables:
            findings.append(
                AgentFinding(
                    id="dh_empty_tables",
                    severity="INFO",
                    title="Empty Tables Present",
                    description=f"Found {len(dq.empty_tables)} empty table(s): {', '.join(dq.empty_tables)}",
                    evidence={"empty_tables": dq.empty_tables},
                )
            )

        # 4. Performance / Indexing Findings
        if report.performance_findings:
            for pf in report.performance_findings[:3]:
                findings.append(
                    AgentFinding(
                        id=f"dh_perf_{pf.table}_{pf.column or 'all'}",
                        severity="WARNING",
                        title=f"Potential Performance Finding: {pf.table}",
                        description=pf.description,
                        table=pf.table,
                        column=pf.column,
                        evidence={"recommendation": pf.recommendation},
                    )
                )
                recommendations.append(pf.recommendation)

        summary = (
            f"Database health is currently rated {score}/100 (Grade {grade}). "
            f"The architecture contains {report.total_tables} tables with {report.total_rows:,} total records. "
            f"Identified {len(findings)} structural/integrity finding(s)."
        )

        steps.append("Health diagnostic complete.")

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            status="COMPLETED",
            summary=summary,
            findings=findings,
            evidence={
                "health_score": score,
                "grade": grade,
                "total_tables": report.total_tables,
                "total_rows": report.total_rows,
                "database_type": report.database_type,
            },
            recommendations=recommendations or ["Maintain existing relational constraints and monitor performance."],
            proposed_action=None,
            limitations=[
                "Read-only diagnostic agent: cannot modify schema or data.",
                "Health scoring uses deterministic structural weights.",
            ],
            execution_steps=steps,
        )
