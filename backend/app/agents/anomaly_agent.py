from __future__ import annotations

from typing import Any

from app.agents.base_agent import BaseAgent
from app.agents.models import AgentFinding, AgentResult, AgentTask
from app.intelligence.anomaly.detector import detect_anomalies


class AnomalyAgent(BaseAgent):
    name = "anomaly_agent"
    role = "Anomaly Investigator"
    description = (
        "Detects statistical outliers, period-over-period surges or drops, and unexpected "
        "distribution patterns with explainable baselines and deviation metrics."
    )
    is_read_only = True
    capabilities = [
        "Detect numeric statistical outliers via IQR profiling",
        "Identify sudden chronological volume or measure shifts (drops >= 50%, surges >= 200%)",
        "Correlate data quality anomalies with operational patterns",
        "Provide explainable baseline vs observed comparisons",
    ]
    allowed_tools = ["anomaly_detector", "iqr_scanner", "trend_change_detector"]

    def execute(self, task: AgentTask, context: dict[str, Any]) -> AgentResult:
        steps = ["Running anomaly detection scan across connected tables..."]

        report = detect_anomalies(force_refresh=False)
        steps.append(
            f"Detected {report.total_anomalies} total anomaly finding(s) "
            f"({report.critical_count} CRITICAL, {report.warning_count} WARNING, {report.info_count} INFO)."
        )

        findings: list[AgentFinding] = []
        recommendations: list[str] = []

        for a in report.anomalies:
            findings.append(
                AgentFinding(
                    id=a.id,
                    severity=a.severity,
                    title=f"{a.metric}: {a.table}{f'.{a.column}' if a.column else ''}",
                    description=a.explanation,
                    table=a.table,
                    column=a.column,
                    evidence={
                        "observed_value": a.observed_value,
                        "expected_value": a.expected_value,
                        "deviation_str": a.deviation_str,
                        "detection_method": a.detection_method,
                        "time_period": a.time_period,
                        "suggested_action": a.suggested_action,
                    },
                )
            )
            if a.severity == "CRITICAL":
                recommendations.append(
                    f"Immediate review recommended: '{a.metric}' in table '{a.table}'. {a.explanation}"
                )
            elif a.severity == "WARNING" and len(recommendations) < 4:
                recommendations.append(
                    f"Investigate '{a.table}': {a.deviation_str} detected."
                )

        if not recommendations:
            recommendations = ["No severe operational anomalies detected. Continue routine monitoring."]

        summary = (
            f"Anomaly investigation completed. Found {report.total_anomalies} finding(s) "
            f"across active tables ({report.critical_count} critical, {report.warning_count} warning, "
            f"{report.info_count} informational). Baseline comparisons and deviation factors are documented in evidence."
        )

        steps.append("Anomaly classification and evidence synthesis complete.")

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            status="COMPLETED",
            summary=summary,
            findings=findings,
            evidence={
                "total_anomalies": report.total_anomalies,
                "critical_count": report.critical_count,
                "warning_count": report.warning_count,
                "info_count": report.info_count,
            },
            recommendations=recommendations,
            proposed_action=None,
            limitations=[
                "Read-only anomaly detector: cannot alter underlying records.",
                "Non-causal: identifies statistical deviations without asserting underlying real-world cause.",
            ],
            execution_steps=steps,
        )
