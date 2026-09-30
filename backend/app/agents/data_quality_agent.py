from __future__ import annotations

from typing import Any

from app.agents.base_agent import BaseAgent
from app.agents.models import AgentFinding, AgentResult, AgentTask
from app.intelligence.scanner import get_cached_report, run_database_intelligence_scan


class DataQualityAgent(BaseAgent):
    name = "data_quality_agent"
    role = "Data Quality Specialist"
    description = (
        "Investigates data hygiene issues including missing values, null ratios, "
        "orphan foreign key references, and schema anomalies with concrete statistical evidence."
    )
    is_read_only = True
    capabilities = [
        "Audit null-value distribution across tables",
        "Detect referential integrity violations and orphan records",
        "Identify high null ratios and empty relations",
        "Surface data quality improvement recommendations",
    ]
    allowed_tools = ["data_quality_auditor", "column_profiler", "sample_inspector"]

    def execute(self, task: AgentTask, context: dict[str, Any]) -> AgentResult:
        steps = ["Inspecting data quality metrics..."]

        report = get_cached_report()
        if report is None:
            steps.append("Running database intelligence scan for fresh quality metrics...")
            report = run_database_intelligence_scan(force_refresh=False)

        if report is None or report.data_quality is None:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                status="FAILED",
                summary="Unable to retrieve data quality profile.",
                findings=[],
                evidence={},
                recommendations=[],
                proposed_action=None,
                limitations=["Connected database required."],
                execution_steps=steps,
            )

        dq = report.data_quality
        steps.append(f"Scanned database quality: overall null ratio is {dq.null_percentage}%.")

        findings: list[AgentFinding] = []
        recommendations: list[str] = []

        # 1. Null-Heavy Columns
        if dq.null_heavy_columns:
            for nh in dq.null_heavy_columns:
                tbl = nh.get("table", "")
                col = nh.get("column", "")
                ratio = nh.get("null_percentage", 0.0)
                null_cnt = nh.get("null_count", 0)
                tot_rows = nh.get("total_rows", 0)

                findings.append(
                    AgentFinding(
                        id=f"dq_null_{tbl}_{col}",
                        severity="WARNING" if ratio >= 35.0 else "INFO",
                        title=f"Elevated NULL Ratio in '{tbl}.{col}'",
                        description=f"{ratio}% of values ({null_cnt:,} of {tot_rows:,} rows) are NULL.",
                        table=tbl,
                        column=col,
                        evidence=nh,
                    )
                )
                recommendations.append(f"Consider establishing NOT NULL constraint or default value for '{tbl}.{col}'.")

        # 2. Orphan Foreign Keys
        if dq.orphan_foreign_keys:
            for orphan in dq.orphan_foreign_keys:
                if isinstance(orphan, dict):
                    src_tbl = orphan.get("source_table", "")
                    fk_col = orphan.get("foreign_key_column", "")
                    tgt_tbl = orphan.get("target_table", "")
                    cnt = orphan.get("orphan_count", 0)
                else:
                    src_tbl = getattr(orphan, "source_table", "")
                    fk_col = getattr(orphan, "foreign_key_column", "")
                    tgt_tbl = getattr(orphan, "target_table", "")
                    cnt = getattr(orphan, "orphan_count", 0)

                findings.append(
                    AgentFinding(
                        id=f"dq_orphan_{src_tbl}_{fk_col}",
                        severity="CRITICAL",
                        title=f"Referential Integrity Breach: '{src_tbl}.{fk_col}'",
                        description=(
                            f"Found {cnt:,} record(s) referencing non-existent parent rows in '{tgt_tbl}'."
                        ),
                        table=src_tbl,
                        column=fk_col,
                        evidence=orphan,
                    )
                )
                recommendations.append(
                    f"Prepare corrective action with Safe Action Agent to reconcile orphan records in '{src_tbl}'."
                )

        # 3. Empty Tables
        for empty_tbl in dq.empty_tables:
            findings.append(
                AgentFinding(
                    id=f"dq_empty_{empty_tbl}",
                    severity="INFO",
                    title=f"Empty Table: '{empty_tbl}'",
                    description=f"Table exists in schema catalog but currently contains zero records.",
                    table=empty_tbl,
                    evidence={"table": empty_tbl, "row_count": 0},
                )
            )

        summary = (
            f"Data quality audit completed across {report.total_tables} tables. "
            f"Overall database null percentage is {dq.null_percentage}%. "
            f"Identified {len(findings)} data quality finding(s) requiring attention."
        )

        steps.append("Data quality audit completed successfully.")

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            status="COMPLETED",
            summary=summary,
            findings=findings,
            evidence={
                "null_percentage": dq.null_percentage,
                "null_heavy_columns_count": len(dq.null_heavy_columns),
                "orphan_foreign_keys_count": len(dq.orphan_foreign_keys),
                "empty_tables_count": len(dq.empty_tables),
            },
            recommendations=recommendations or ["Data quality is currently within healthy operational thresholds."],
            proposed_action=None,
            limitations=[
                "Read-only specialist agent: never writes or modifies rows.",
                "Quality metrics are calculated deterministically from active tables.",
            ],
            execution_steps=steps,
        )
