"""backend/app/intelligence/anomaly/business_anomaly.py

Explainable business anomaly detection for Sprint 2.
Analyzes verified business metrics, order volumes, revenue changes, and row count shifts
without fabricating data, trends, or causal assumptions.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import text

from app.agent.database_profile import DatabaseProfile


@dataclass
class BusinessAnomaly:
    """Represents a statistically detected, explainable business anomaly."""
    id: str
    title: str
    metric: str
    table: str
    severity: str  # critical, warning, info
    observed_value: float
    expected_value: float
    column: Optional[str] = None
    percentage_change: Optional[float] = None
    time_period: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    explanation: str = ""
    recommended_steps: List[str] = field(default_factory=list)
    is_root_cause_confirmed: bool = False  # Strictly False: anomaly != confirmed cause
    detection_method: str = "statistical_deviation"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "metric": self.metric,
            "table": self.table,
            "column": self.column,
            "severity": self.severity,
            "observed_value": round(self.observed_value, 2),
            "expected_value": round(self.expected_value, 2),
            "percentage_change": self.percentage_change,
            "time_period": self.time_period,
            "evidence": self.evidence,
            "explanation": self.explanation,
            "recommended_steps": self.recommended_steps,
            "is_root_cause_confirmed": self.is_root_cause_confirmed,
            "detection_method": self.detection_method,
        }


def _quote_ident(ident: str, db_type: str = "sqlite") -> str:
    escaped = ident.replace('"', '""').replace('`', '``')
    if db_type == "mysql":
        return f"`{escaped}`"
    return f'"{escaped}"'


def detect_business_anomalies(
    engine: Any,
    db_type: str,
    profile: DatabaseProfile,
    drop_threshold_pct: float = 30.0,
    critical_drop_threshold_pct: float = 50.0,
    spike_threshold_pct: float = 150.0,
) -> List[BusinessAnomaly]:
    """
    Detects business anomalies using verified queries on actual data.
    Inspects:
    1. Period-over-period metric declines or surges (e.g. monthly revenue/sales).
    2. Significant row count shifts across operational entities.
    3. Transactional numeric outliers (IQR).
    Guards strictly against zero division and insufficient history.
    """
    anomalies: List[BusinessAnomaly] = []

    if engine is None or not profile or not profile.tables:
        return anomalies

    with engine.connect() as conn:
        for table_name, table in profile.tables.items():
            if table.row_count == 0:
                continue

            # 1. Period-over-Period Time Series Changes
            if table.date_columns:
                date_col = table.date_columns[0]
                t_quoted = _quote_ident(table_name, db_type)
                d_quoted = _quote_ident(date_col, db_type)

                # Check metric columns (e.g. revenue, total_amount, price)
                metric_cols_to_check = table.metric_columns[:2] if table.metric_columns else [None]

                for metric_col in metric_cols_to_check:
                    if metric_col:
                        m_quoted = _quote_ident(metric_col, db_type)
                        val_expr = f"SUM({m_quoted})"
                        label_name = metric_col.replace("_", " ").title()
                    else:
                        val_expr = "COUNT(*)"
                        label_name = "Transaction Count"

                    # Formulate dialect-appropriate period grouping (monthly or daily)
                    if db_type == "sqlite":
                        period_expr = f"strftime('%Y-%m', {d_quoted})"
                    elif db_type == "mysql":
                        period_expr = f"DATE_FORMAT({d_quoted}, '%Y-%m')"
                    elif db_type == "postgres":
                        period_expr = f"to_char({d_quoted}, 'YYYY-MM')"
                    else:
                        period_expr = f"substr({d_quoted}, 1, 7)"

                    query_sql = f"""
                        SELECT {period_expr} as period, {val_expr} as val
                        FROM {t_quoted}
                        WHERE {d_quoted} IS NOT NULL
                        GROUP BY {period_expr}
                        ORDER BY period DESC
                        LIMIT 3
                    """

                    try:
                        rows = conn.execute(text(query_sql)).fetchall()
                    except Exception:
                        continue

                    # Insufficient history protection (< 2 periods)
                    if len(rows) < 2:
                        continue

                    curr_period, curr_val_raw = str(rows[0][0]), rows[0][1]
                    prev_period, prev_val_raw = str(rows[1][0]), rows[1][1]

                    if curr_val_raw is None or prev_val_raw is None:
                        continue

                    curr_val = float(curr_val_raw)
                    prev_val = float(prev_val_raw)

                    # Zero denominator protection
                    if prev_val <= 0:
                        continue

                    pct_change = round(((curr_val - prev_val) / prev_val) * 100, 1)

                    if pct_change <= -drop_threshold_pct:
                        sev = "critical" if pct_change <= -critical_drop_threshold_pct else "warning"
                        anomalies.append(
                            BusinessAnomaly(
                                id=f"anom_drop_{table_name}_{metric_col or 'count'}_{curr_period}",
                                title=f"Sudden {label_name} Decline in {curr_period}",
                                metric=label_name,
                                table=table_name,
                                column=metric_col,
                                severity=sev,
                                observed_value=curr_val,
                                expected_value=prev_val,
                                percentage_change=pct_change,
                                time_period=curr_period,
                                evidence={
                                    "current_period": curr_period,
                                    "current_value": curr_val,
                                    "previous_period": prev_period,
                                    "previous_value": prev_val,
                                    "delta": round(curr_val - prev_val, 2),
                                },
                                explanation=(
                                    f"{table_name} {label_name.lower()} dropped by {abs(pct_change)}% in {curr_period} "
                                    f"({curr_val:,.2f} vs {prev_val:,.2f} in {prev_period})."
                                ),
                                recommended_steps=[
                                    f"Compare product or regional sales breakdown for {curr_period} vs {prev_period}.",
                                    f"Verify if external transaction processing or tracking logging was interrupted.",
                                    f"Cross-reference customer activity to identify account churn vs macro drop.",
                                ],
                                is_root_cause_confirmed=False,
                                detection_method="Period-over-Period Delta",
                            )
                        )
                    elif pct_change >= spike_threshold_pct and prev_val > 5:
                        anomalies.append(
                            BusinessAnomaly(
                                id=f"anom_surge_{table_name}_{metric_col or 'count'}_{curr_period}",
                                title=f"Unusual {label_name} Volume Surge in {curr_period}",
                                metric=label_name,
                                table=table_name,
                                column=metric_col,
                                severity="warning",
                                observed_value=curr_val,
                                expected_value=prev_val,
                                percentage_change=pct_change,
                                time_period=curr_period,
                                evidence={
                                    "current_period": curr_period,
                                    "current_value": curr_val,
                                    "previous_period": prev_period,
                                    "previous_value": prev_val,
                                    "delta": round(curr_val - prev_val, 2),
                                },
                                explanation=(
                                    f"{table_name} {label_name.lower()} increased by +{pct_change}% in {curr_period} "
                                    f"({curr_val:,.2f} vs {prev_val:,.2f} in {prev_period})."
                                ),
                                recommended_steps=[
                                    f"Audit transactions in {curr_period} for duplicate bulk orders or test records.",
                                    f"Verify whether marketing campaigns or seasonal promotions occurred.",
                                ],
                                is_root_cause_confirmed=False,
                                detection_method="Period-over-Period Surge",
                            )
                        )

            # 2. Outlier Detection on Transactional/Metric Columns (IQR)
            for m_col in table.metric_columns[:1]:
                col_quoted = _quote_ident(m_col, db_type)
                t_quoted = _quote_ident(table_name, db_type)
                sql_samples = f"SELECT {col_quoted} FROM {t_quoted} WHERE {col_quoted} IS NOT NULL LIMIT 500"
                try:
                    s_rows = conn.execute(text(sql_samples)).fetchall()
                    vals = [float(r[0]) for r in s_rows if r[0] is not None]
                    # Minimum sample size guard
                    if len(vals) >= 8:
                        sorted_v = sorted(vals)
                        med = statistics.median(sorted_v)
                        q = statistics.quantiles(sorted_v, n=4, method="inclusive")
                        q1, q3 = q[0], q[2]
                        iqr = max(0.001, q3 - q1)
                        upper_bound = q3 + (3.0 * iqr)
                        lower_bound = q1 - (3.0 * iqr)

                        extreme_outliers = [v for v in vals if v > upper_bound or v < lower_bound]
                        if extreme_outliers:
                            max_extreme = max(extreme_outliers, key=lambda x: abs(x - med))
                            mult = round(abs(max_extreme - med) / iqr, 1)
                            anomalies.append(
                                BusinessAnomaly(
                                    id=f"anom_outlier_{table_name}_{m_col}",
                                    title=f"Extreme Value Outlier in {table_name}.{m_col}",
                                    metric=f"{table_name}.{m_col}",
                                    table=table_name,
                                    column=m_col,
                                    severity="warning",
                                    observed_value=max_extreme,
                                    expected_value=med,
                                    percentage_change=None,
                                    evidence={
                                        "median": round(med, 2),
                                        "q1": round(q1, 2),
                                        "q3": round(q3, 2),
                                        "iqr": round(iqr, 2),
                                        "extreme_val": round(max_extreme, 2),
                                        "iqr_distance": mult,
                                    },
                                    explanation=(
                                        f"Observed value {max_extreme:,.2f} in '{table_name}.{m_col}' is an extreme outlier "
                                        f"({mult}× IQR distance from median {med:,.2f})."
                                    ),
                                    recommended_steps=[
                                        f"Inspect record containing {m_col} = {max_extreme} in Data Explorer.",
                                        f"Verify whether currency or decimal input error occurred.",
                                    ],
                                    is_root_cause_confirmed=False,
                                    detection_method="IQR Extreme Outlier",
                                )
                            )
                except Exception:
                    continue

    return anomalies
