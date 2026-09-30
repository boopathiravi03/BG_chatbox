from __future__ import annotations

from typing import Any
from app.intelligence.scanner import get_cached_report, run_database_intelligence_scan


def analyze_health_findings() -> dict[str, Any]:
    """
    Returns structured evidence explaining database health findings and data quality.
    Derived directly from Phase 1 continuous intelligence audit.
    """
    report = get_cached_report()
    if report is None:
        report = run_database_intelligence_scan(force_refresh=False)

    findings = []
    dq = report.data_quality

    for orphan in dq.orphan_foreign_keys:
        findings.append({
            "category": "critical",
            "type": "Orphan Foreign Key",
            "table": orphan.source_table,
            "column": orphan.foreign_key_column,
            "details": f"{orphan.orphan_count} records in '{orphan.source_table}.{orphan.foreign_key_column}' reference non-existent records in '{orphan.target_table}'.",
        })

    for col in dq.null_heavy_columns:
        findings.append({
            "category": "warning",
            "type": "High Null Ratio",
            "table": col.get("table", ""),
            "column": col.get("column", ""),
            "details": f"Column '{col.get('column')}' in table '{col.get('table')}' has {col.get('null_percentage')}% missing values ({col.get('null_count')}/{col.get('total_rows')} rows).",
        })

    for empty_t in dq.empty_tables:
        findings.append({
            "category": "warning",
            "type": "Empty Table",
            "table": empty_t,
            "column": None,
            "details": f"Table '{empty_t}' contains 0 records.",
        })

    for perf in report.performance_findings:
        findings.append({
            "category": "performance",
            "type": perf.type.replace("_", " ").title(),
            "table": perf.table,
            "column": perf.column,
            "details": perf.description,
        })

    health_score = report.health_score

    if health_score >= 90:
        health_verdict = "Excellent database hygiene with minimal or no structural anomalies."
    elif health_score >= 75:
        health_verdict = "Good overall structure with minor performance or null density warnings."
    elif health_score >= 60:
        health_verdict = "Needs attention: several unindexed keys or high null ratios detected."
    else:
        health_verdict = "Critical integrity issues detected: referential orphans or missing primary keys present."

    return {
        "status": "success",
        "health_score": health_score,
        "health_verdict": health_verdict,
        "total_findings": len(findings),
        "findings": findings,
        "empty_tables_count": len(dq.empty_tables),
        "orphan_keys_count": len(dq.orphan_foreign_keys),
        "null_heavy_count": len(dq.null_heavy_columns),
    }
