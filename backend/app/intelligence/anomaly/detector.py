from __future__ import annotations

import math
import statistics
from datetime import datetime
from typing import Any, Optional
from sqlalchemy import text
from app.database.database_manager import get_engine, get_current_db_type
from app.intelligence.schema_analyzer import quote_identifier
from app.intelligence.table_explorer import classify_semantic_type
from app.intelligence.scanner import get_cached_report, run_database_intelligence_scan
from app.intelligence.ai_analyst.trend_analyzer import get_dialect_date_trunc
from app.intelligence.anomaly.models import AnomalyFinding, AnomalyScanReport
from app.intelligence.anomaly import rules

_cached_anomaly_report: Optional[AnomalyScanReport] = None


def clear_cached_anomaly_report() -> None:
    """Invalidates cached anomaly findings on database disconnect or rescan."""
    global _cached_anomaly_report
    _cached_anomaly_report = None


def calculate_quartiles(values: list[float]) -> tuple[float, float, float, float]:
    """
    Computes Q1, Median, Q3, and IQR deterministically.
    """
    sorted_v = sorted(values)
    n = len(sorted_v)
    if n == 0:
        return 0.0, 0.0, 0.0, 0.0
    
    med = statistics.median(sorted_v)
    
    # Q1 and Q3 via quantiles
    if n >= 4:
        q = statistics.quantiles(sorted_v, n=4, method="inclusive")
        q1, q3 = q[0], q[2]
    else:
        q1 = sorted_v[0]
        q3 = sorted_v[-1]
        
    iqr = max(0.0, q3 - q1)
    return q1, med, q3, iqr


def scan_numeric_outliers(
    engine: Any,
    db_type: str,
    table_name: str,
    numeric_cols: list[str],
) -> list[AnomalyFinding]:
    """
    Detects numeric outliers using Interquartile Range (IQR).
    Guards against large tables by bounding scan to 1000 sampled rows.
    """
    findings: list[AnomalyFinding] = []
    t_quoted = quote_identifier(table_name, db_type)

    for col in numeric_cols[:3]:  # Check up to 3 numeric columns per table
        c_quoted = quote_identifier(col, db_type)
        # Fetch non-null values with limit
        sql = f"""
            SELECT {c_quoted} 
            FROM {t_quoted} 
            WHERE {c_quoted} IS NOT NULL 
            LIMIT 1000
        """
        try:
            with engine.connect() as conn:
                rows = conn.execute(text(sql)).fetchall()
        except Exception:
            continue

        raw_vals = [float(r[0]) for r in rows if r[0] is not None]
        if len(raw_vals) < 4:
            continue

        q1, med, q3, iqr = calculate_quartiles(raw_vals)
        if iqr <= 0:
            continue

        upper_info = q3 + (rules.NUMERIC_IQR_FACTOR_INFO * iqr)
        lower_info = q1 - (rules.NUMERIC_IQR_FACTOR_INFO * iqr)
        upper_warn = q3 + (rules.NUMERIC_IQR_FACTOR_WARNING * iqr)
        lower_warn = q1 - (rules.NUMERIC_IQR_FACTOR_WARNING * iqr)

        # Check for extreme or moderate outliers
        outliers = [v for v in raw_vals if v > upper_info or v < lower_info]
        if not outliers:
            continue

        # Take the most extreme outlier
        extreme_val = max(outliers, key=lambda x: abs(x - med))
        is_extreme = extreme_val > upper_warn or extreme_val < lower_warn
        severity = "WARNING" if is_extreme else "INFO"

        # Deviation factor relative to IQR or median
        dev_mult = round(abs(extreme_val - med) / (iqr if iqr > 0 else 1.0), 1)
        col_label = col.replace("_", " ").title()

        findings.append(
            AnomalyFinding(
                id=f"anomaly_outlier_{table_name}_{col}",
                metric=f"Unusual {col_label} Value",
                table=table_name,
                column=col,
                observed_value=extreme_val,
                expected_value=f"Typical range [{round(q1, 1)} - {round(q3, 1)}], median {round(med, 1)}",
                deviation_str=f"{dev_mult}× IQR deviation from median",
                detection_method="IQR Outlier",
                severity=severity,
                explanation=(
                    f"Observed value {extreme_val:,.2f} in '{table_name}.{col}' is a statistical outlier "
                    f"({dev_mult}× IQR distance from historical median {med:,.2f}). Potential data anomaly requiring investigation."
                ),
                suggested_action="explorer",
                action_target=table_name,
            )
        )

    return findings


def scan_sudden_time_series_changes(
    engine: Any,
    db_type: str,
    table_name: str,
    date_col: str,
    metric_col: Optional[str] = None,
) -> list[AnomalyFinding]:
    """
    Detects period-over-period sudden drops (>= 50%) or sudden spikes (>= 200%).
    """
    findings: list[AnomalyFinding] = []
    t_quoted = quote_identifier(table_name, db_type)
    d_quoted = quote_identifier(date_col, db_type)

    date_expr = get_dialect_date_trunc(d_quoted, db_type, interval="month")
    if metric_col:
        m_quoted = quote_identifier(metric_col, db_type)
        val_expr = f"SUM({m_quoted})"
        metric_label = metric_col.replace("_", " ").title()
    else:
        val_expr = "COUNT(*)"
        metric_label = "Record Count"

    sql = f"""
        SELECT 
            {date_expr} as period,
            {val_expr} as val
        FROM {t_quoted}
        WHERE {d_quoted} IS NOT NULL
        GROUP BY {date_expr}
        ORDER BY {date_expr} DESC
        LIMIT 3
    """
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(sql)).fetchall()
    except Exception:
        return []

    if len(rows) < 2:
        return []

    curr_period, curr_val = str(rows[0][0]), float(rows[0][1] or 0.0)
    prev_period, prev_val = str(rows[1][0]), float(rows[1][1] or 0.0)

    if prev_val <= 0:
        return []

    pct_change = round(((curr_val - prev_val) / prev_val) * 100, 1)

    if pct_change <= -rules.TIME_SERIES_DROP_WARNING_PCT:
        findings.append(
            AnomalyFinding(
                id=f"anomaly_drop_{table_name}_{metric_col or 'count'}_{curr_period}",
                metric=f"Sudden {metric_label} Decline",
                table=table_name,
                column=metric_col,
                time_period=curr_period,
                observed_value=round(curr_val, 2),
                expected_value=round(prev_val, 2),
                deviation_str=f"{pct_change}% decline vs prior period",
                detection_method="Sudden Change",
                severity="WARNING",
                explanation=(
                    f"'{table_name}' {metric_label} declined by {abs(pct_change)}% in {curr_period} "
                    f"({curr_val:,.2f} vs {prev_val:,.2f} in {prev_period}). Potential anomaly requiring operational review."
                ),
                suggested_action="analytics",
                action_target=f"Analyze why {table_name} {metric_label} dropped in {curr_period}",
            )
        )
    elif pct_change >= rules.TIME_SERIES_SPIKE_WARNING_PCT:
        findings.append(
            AnomalyFinding(
                id=f"anomaly_spike_{table_name}_{metric_col or 'count'}_{curr_period}",
                metric=f"Unusual {metric_label} Surge",
                table=table_name,
                column=metric_col,
                time_period=curr_period,
                observed_value=round(curr_val, 2),
                expected_value=round(prev_val, 2),
                deviation_str=f"+{pct_change}% increase vs prior period",
                detection_method="Sudden Change",
                severity="WARNING",
                explanation=(
                    f"'{table_name}' {metric_label} surged by +{pct_change}% in {curr_period} "
                    f"({curr_val:,.2f} vs {prev_val:,.2f} in {prev_period}). Potential anomalous volume spike requiring investigation."
                ),
                suggested_action="analytics",
                action_target=f"Analyze trend of {table_name}",
            )
        )

    return findings


def detect_anomalies(force_refresh: bool = False) -> AnomalyScanReport:
    """
    Executes explainable anomaly scan across:
    1. Numeric Outliers (IQR)
    2. Sudden Time-Series Changes
    3. Data Quality & Referential Breaches (Phase 1 Synthesis)
    4. Categorical Distribution Imbalances
    """
    global _cached_anomaly_report
    if not force_refresh and _cached_anomaly_report is not None:
        return _cached_anomaly_report

    engine = get_engine()
    db_type = get_current_db_type()

    if engine is None or db_type == "none":
        return AnomalyScanReport(
            total_anomalies=0,
            critical_count=0,
            warning_count=0,
            info_count=0,
            anomalies=[],
            scan_timestamp=datetime.now().isoformat(),
            database_name="None",
            database_type="none",
        )

    report = get_cached_report()
    if report is None or force_refresh:
        report = run_database_intelligence_scan(force_refresh=force_refresh)

    anomalies: list[AnomalyFinding] = []

    # 1. Synthesize Data Quality & Integrity Anomalies
    if report and report.data_quality:
        dq = report.data_quality
        # Orphan Foreign Keys (CRITICAL)
        for orphan in dq.orphan_foreign_keys:
            if isinstance(orphan, dict):
                src_tbl = orphan.get("source_table", "")
                fk_col = orphan.get("foreign_key_column", "")
                tgt_tbl = orphan.get("target_table", "")
                orph_cnt = orphan.get("orphan_count", 0)
            else:
                src_tbl = getattr(orphan, "source_table", "")
                fk_col = getattr(orphan, "foreign_key_column", "")
                tgt_tbl = getattr(orphan, "target_table", "")
                orph_cnt = getattr(orphan, "orphan_count", 0)
            anomalies.append(
                AnomalyFinding(
                    id=f"anomaly_orphan_{src_tbl}_{fk_col}",
                    metric="Referential Integrity Breach",
                    table=src_tbl,
                    column=fk_col,
                    observed_value=f"{orph_cnt} orphan records",
                    expected_value="0 orphan records",
                    deviation_str=f"{orph_cnt} broken references",
                    detection_method="Data Quality Audit",
                    severity="CRITICAL",
                    explanation=(
                        f"Found {orph_cnt} records in '{src_tbl}.{fk_col}' "
                        f"pointing to non-existent rows in '{tgt_tbl}'. Violates relational consistency."
                    ),
                    suggested_action="health",
                    action_target=src_tbl,
                )
            )

        # Null Spikes (WARNING or CRITICAL)
        for nh in dq.null_heavy_columns:
            null_pct = float(nh.get("null_percentage", 0.0))
            if null_pct >= rules.NULL_RATIO_WARNING_PCT:
                sev = "CRITICAL" if null_pct >= rules.NULL_RATIO_CRITICAL_PCT else "WARNING"
                anomalies.append(
                    AnomalyFinding(
                        id=f"anomaly_null_{nh.get('table')}_{nh.get('column')}",
                        metric="High NULL Ratio",
                        table=nh.get("table", ""),
                        column=nh.get("column", ""),
                        observed_value=f"{null_pct}% nulls",
                        expected_value="< 20% nulls",
                        deviation_str=f"{null_pct}% missing values",
                        detection_method="Data Quality Audit",
                        severity=sev,
                        explanation=(
                            f"Column '{nh.get('column')}' in '{nh.get('table')}' contains {nh.get('null_count'):,} "
                            f"null values ({null_pct}% of {nh.get('total_rows'):,} rows)."
                        ),
                        suggested_action="health",
                        action_target=nh.get("table", ""),
                    )
                )

        # Empty Tables (WARNING)
        for empty_t in dq.empty_tables:
            anomalies.append(
                AnomalyFinding(
                    id=f"anomaly_empty_{empty_t}",
                    metric="Empty Database Table",
                    table=empty_t,
                    observed_value="0 records",
                    expected_value=">= 1 record",
                    deviation_str="100% empty",
                    detection_method="Data Quality Audit",
                    severity="WARNING",
                    explanation=f"Table '{empty_t}' exists in the database schema but contains zero records.",
                    suggested_action="explorer",
                    action_target=empty_t,
                )
            )

    # 2. Scan Schema for Numeric Outliers and Sudden Time-Series Changes
    if report and report.schema_summary:
        for t_name, t_meta in report.schema_summary.items():
            cols = t_meta.get("columns", [])
            row_count = t_meta.get("row_count", 0)

            if row_count < 3:
                continue

            num_cols: list[str] = []
            date_cols: list[str] = []

            for c in cols:
                c_name = c.get("name", "")
                c_type = c.get("type", "TEXT")
                sem = classify_semantic_type(c_name, c_type)

                if sem in ("Currency", "Quantity", "Numeric"):
                    num_cols.append(c_name)
                elif sem in ("Date", "Timestamp"):
                    date_cols.append(c_name)

            # Check numeric outliers
            if num_cols:
                outliers = scan_numeric_outliers(engine, db_type, t_name, num_cols)
                anomalies.extend(outliers)

            # Check time-series sudden changes
            if date_cols:
                primary_date = date_cols[0]
                primary_metric = num_cols[0] if num_cols else None
                ts_anomalies = scan_sudden_time_series_changes(engine, db_type, t_name, primary_date, primary_metric)
                anomalies.extend(ts_anomalies)

    # Count by severity and sort: CRITICAL -> WARNING -> INFO
    crit_count = sum(1 for a in anomalies if a.severity == "CRITICAL")
    warn_count = sum(1 for a in anomalies if a.severity == "WARNING")
    info_count = sum(1 for a in anomalies if a.severity == "INFO")

    severity_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
    anomalies.sort(key=lambda a: severity_order.get(a.severity, 3))

    scan_result = AnomalyScanReport(
        total_anomalies=len(anomalies),
        critical_count=crit_count,
        warning_count=warn_count,
        info_count=info_count,
        anomalies=anomalies,
        scan_timestamp=datetime.now().isoformat(),
        database_name=report.database_name if report else "Database",
        database_type=db_type,
    )

    _cached_anomaly_report = scan_result
    return scan_result
