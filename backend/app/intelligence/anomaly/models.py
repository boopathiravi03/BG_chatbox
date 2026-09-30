from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional, Literal


@dataclass
class AnomalyFinding:
    id: str
    metric: str
    table: str
    column: Optional[str] = None
    time_period: Optional[str] = None
    observed_value: Any = None
    expected_value: Any = None
    deviation_str: str = ""
    detection_method: str = "IQR"  # "IQR Outlier" | "Sudden Change" | "Data Quality Breach" | "Distribution Shift"
    severity: Literal["CRITICAL", "WARNING", "INFO"] = "WARNING"
    explanation: str = ""
    suggested_action: Literal["explorer", "sqllab", "analytics"] = "explorer"
    action_target: Optional[str] = None  # Table name or SQL query
    chart: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "metric": self.metric,
            "table": self.table,
            "column": self.column,
            "time_period": self.time_period,
            "observed_value": self.observed_value,
            "expected_value": self.expected_value,
            "deviation_str": self.deviation_str,
            "detection_method": self.detection_method,
            "severity": self.severity,
            "explanation": self.explanation,
            "suggested_action": self.suggested_action,
            "action_target": self.action_target,
            "chart": self.chart,
        }


@dataclass
class AnomalyScanReport:
    total_anomalies: int
    critical_count: int
    warning_count: int
    info_count: int
    anomalies: list[AnomalyFinding]
    scan_timestamp: str
    database_name: str
    database_type: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_anomalies": self.total_anomalies,
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "anomalies": [a.to_dict() for a in self.anomalies],
            "scan_timestamp": self.scan_timestamp,
            "database_name": self.database_name,
            "database_type": self.database_type,
        }
