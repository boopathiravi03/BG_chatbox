from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from app.database.database_manager import get_engine, get_current_db_type
from app.intelligence.models import (
    DatabaseIntelligenceReport,
    DataQualitySummary,
)
from app.intelligence.schema_analyzer import analyze_schema
from app.intelligence.data_quality import audit_data_quality
from app.intelligence.performance_analyzer import analyze_performance
from app.intelligence.business_analyzer import discover_business_metrics
from app.intelligence.anomaly_detector import synthesize_attention_items


_cached_intelligence_report: DatabaseIntelligenceReport | None = None


def get_cached_report() -> DatabaseIntelligenceReport | None:
    return _cached_intelligence_report


def clear_cached_report() -> None:
    global _cached_intelligence_report
    _cached_intelligence_report = None


def calculate_health_score(
    data_quality: DataQualitySummary,
    performance_findings: list[Any],
    total_tables: int,
) -> int:
    """
    Computes a deterministic health score from 0 to 100 based on actual detected issues:
    - Base: 100
    - Missing PK: -10 each
    - Orphan FK: -15 each
    - High Null Columns: -4 each
    - Empty Tables: -3 each
    - Unindexed FKs: -2 each
    """
    if total_tables == 0:
        return 100

    score = 100
    score -= len(data_quality.orphan_foreign_keys) * 15

    missing_pks = [f for f in performance_findings if getattr(f, "type", "") == "missing_primary_key"]
    score -= len(missing_pks) * 10

    score -= len(data_quality.null_heavy_columns) * 4
    score -= len(data_quality.empty_tables) * 3

    unindexed_fks = [f for f in performance_findings if getattr(f, "type", "") == "unindexed_foreign_key"]
    score -= len(unindexed_fks) * 2

    # Clamp between 20 and 100
    return max(20, min(100, score))


def run_database_intelligence_scan(force_refresh: bool = False) -> DatabaseIntelligenceReport:
    """
    Executes a comprehensive, non-destructive, strictly READ-ONLY Database Intelligence Scan.
    Gathers schema topology, real row counts, null densities, referential integrity,
    performance signals, and business aggregates.
    Caches the resulting DatabaseIntelligenceReport.
    """
    global _cached_intelligence_report

    if not force_refresh and _cached_intelligence_report is not None:
        return _cached_intelligence_report

    engine = get_engine()
    db_type = get_current_db_type()

    if engine is None or db_type == "none":
        empty_report = DatabaseIntelligenceReport(
            database_type="none",
            database_name="Disconnected",
            total_tables=0,
            total_rows=0,
            total_columns=0,
            total_relationships=0,
            health_score=100,
            schema_summary={},
            data_quality=DataQualitySummary(),
            performance_findings=[],
            business_metrics=[],
            attention_items=[],
            scan_timestamp=datetime.now(timezone.utc).isoformat(),
            scan_duration_ms=0,
            is_partial=False,
            error_message="No active database is currently connected.",
        )
        _cached_intelligence_report = empty_report
        return empty_report

    start_time = time.perf_counter()
    is_partial = False
    error_msg = None

    # Determine database name safely
    db_name = "Connected Database"
    try:
        if engine.url.database:
            db_name = str(engine.url.database)
    except Exception:
        pass

    try:
        # 1. Structural schema discovery
        schema_info = analyze_schema(engine, db_type)

        # 2. Safe data quality & row count inspection
        data_quality, table_row_counts, total_rows = audit_data_quality(engine, db_type, schema_info)

        # 3. Performance signals
        performance_findings = analyze_performance(schema_info, table_row_counts)

        # 4. Detect business metrics
        business_metrics = discover_business_metrics(engine, db_type, schema_info, table_row_counts)

        # 5. Synthesize attention center items
        attention_items = synthesize_attention_items(
            schema_info=schema_info,
            data_quality=data_quality,
            performance_findings=performance_findings,
            business_metrics=business_metrics,
            table_row_counts=table_row_counts,
        )

        # 6. Compute health score
        health_score = calculate_health_score(
            data_quality=data_quality,
            performance_findings=performance_findings,
            total_tables=schema_info.get("total_tables", 0),
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        is_partial = True
        error_msg = f"Scan completed with warnings: {str(e)}"
        schema_info = {"tables": {}, "total_tables": 0, "total_columns": 0, "total_relationships": 0}
        data_quality = DataQualitySummary()
        performance_findings = []
        business_metrics = []
        attention_items = []
        total_rows = 0
        health_score = 80

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    report = DatabaseIntelligenceReport(
        database_type=db_type,
        database_name=db_name,
        total_tables=schema_info.get("total_tables", 0),
        total_rows=total_rows,
        total_columns=schema_info.get("total_columns", 0),
        total_relationships=schema_info.get("total_relationships", 0),
        health_score=health_score,
        schema_summary=schema_info.get("tables", {}),
        data_quality=data_quality,
        performance_findings=performance_findings,
        business_metrics=business_metrics,
        attention_items=attention_items,
        scan_timestamp=datetime.now(timezone.utc).isoformat(),
        scan_duration_ms=elapsed_ms,
        is_partial=is_partial,
        error_message=error_msg,
    )

    _cached_intelligence_report = report
    return report
