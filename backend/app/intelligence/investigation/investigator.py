"""
backend/app/intelligence/investigation/investigator.py

Phase 8.7: Root-Cause & Investigation Intelligence Orchestrator
Coordinates evidence gathering, contributor analysis, hypothesis formation,
investigation planning, and explanation synthesis.

Guarantees:
- Strict user isolation: signals must belong to the authenticated user.
- Strictly read-only queries with SQL validation.
- Deterministic calculation first; Groq only polishes wording.
- Distinguishes OBSERVED FACT -> EVIDENCE -> CONTRIBUTING FACTOR -> HYPOTHESIS -> RECOMMENDED INVESTIGATION.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.database.database_manager import get_engine, get_current_db_type
from app.intelligence.business_intelligence.business_context import discover_business_context
from app.intelligence.investigation.models import (
    InvestigationResult,
    InvestigationLineage,
    ConfidenceAssessment,
    ConfidenceLevel,
)
from app.intelligence.investigation.evidence_builder import build_investigation_evidence
from app.intelligence.investigation.contributor_analysis import analyze_contributing_factors
from app.intelligence.investigation.hypothesis_engine import generate_hypotheses_and_confidence
from app.intelligence.investigation.investigation_planner import plan_next_investigations
from app.intelligence.investigation.explainer import (
    build_deterministic_explanation,
    polish_explanation_with_groq,
)

logger = logging.getLogger("bgai.investigation.investigator")


def investigate_signal(
    signal_id: Optional[str] = None,
    user_id: str = "default",
    engine: Any = None,
    db_type: Optional[str] = None,
    target_metric: Optional[str] = None,
    target_table: Optional[str] = None,
    context_data: Optional[dict[str, Any]] = None,
) -> InvestigationResult:
    """
    Main orchestration entry point for Phase 8.7 root-cause investigations.
    """
    investigation_id = f"inv_{uuid.uuid4().hex[:10]}"
    created_at = datetime.now(tz=timezone.utc).isoformat()

    # 1. Resolve Signal and Enforce Strict User Ownership
    resolved_title = "Detected Database Anomaly / Shift"
    target_tbl = target_table
    target_met = target_metric

    if signal_id and signal_id not in ("latest", "current_kpi", "auto"):
        signal_found = False

        # Check monitoring cache in main
        try:
            from app.main import _monitoring_cache, _monitoring_lock
            with _monitoring_lock:
                user_report = _monitoring_cache.get(user_id)
                if user_report and hasattr(user_report, "items"):
                    for item in user_report.items:
                        if item.item_id == signal_id:
                            signal_found = True
                            resolved_title = item.title
                            if "in " in item.title.lower():
                                parts = item.title.lower().split("in ")
                                if len(parts) > 1:
                                    target_tbl = parts[1].split()[0].strip("',\"")
                            break
        except Exception:
            pass

        # Check proactive alert store
        if not signal_found:
            try:
                from app.intelligence.proactive.alert_store import _get_session, AlertRecord, _entity_to_model
                session = _get_session()
                try:
                    raw_rec = session.query(AlertRecord).filter(AlertRecord.alert_id == signal_id).first()
                    if raw_rec:
                        if raw_rec.user_id != user_id:
                            raise PermissionError("Access denied: Signal belongs to another user.")
                        alert = _entity_to_model(raw_rec)
                        signal_found = True
                        resolved_title = alert.title
                        target_tbl = alert.source_tables[0] if getattr(alert, "source_tables", None) else target_tbl
                        target_met = getattr(alert, "metric", target_met)
                finally:
                    session.close()
            except PermissionError:
                raise
            except Exception:
                pass

        # Check if context_data supplies signal details
        if not signal_found and context_data and context_data.get("title"):
            signal_found = True
            resolved_title = context_data.get("title", resolved_title)
            target_tbl = context_data.get("table", target_tbl)
            target_met = context_data.get("metric", target_met)

        # If an explicit subsystem signal ID was requested but not found or not accessible
        if not signal_found and signal_id.startswith(("alt_", "alert-", "anom-", "bi-", "alt-", "alert_")):
            return InvestigationResult(
                investigation_id=investigation_id,
                user_id=user_id,
                signal_id=signal_id,
                signal_title="Signal Not Found",
                status="error",
                summary=f"Signal '{signal_id}' was not found in active monitoring cache or alert store.",
                explanation="The requested signal may have expired, or belongs to a different session.",
                created_at=created_at,
            )

    # 2. Resolve database engine
    if engine is None:
        engine = get_engine()
        db_type = get_current_db_type()

    if engine is None or db_type == "none":
        return InvestigationResult(
            investigation_id=investigation_id,
            user_id=user_id,
            signal_id=signal_id or "unspecified",
            signal_title=resolved_title if resolved_title != "Detected Database Anomaly / Shift" else "Database Disconnected",
            status="disconnected",
            summary="No database is currently connected.",
            explanation="Please connect a database to perform root-cause investigations.",
            created_at=created_at,
        )

    # 3. Discover Business Context & Schema
    b_context = discover_business_context(engine, db_type)
    schema_tables = [e.get("table", "") for e in b_context.entity_tables] if b_context.entity_tables else []

    # 4. Gather Quantitative Evidence
    observed_change, evidence_items, meta = build_investigation_evidence(
        engine=engine,
        db_type=db_type,
        target_table=target_tbl,
        target_metric=target_met,
    )

    missing_notes = list(meta.get("insufficient_data_reasons", []))

    # 5. Handle Insufficient Evidence
    if not observed_change or not evidence_items:
        summary, full_exp = build_deterministic_explanation(
            observed_change=None,
            evidence_items=[],
            contributing_factors=[],
            hypotheses=[],
            confidence=None,
            recommendations=[],
            status="insufficient_evidence",
        )
        return InvestigationResult(
            investigation_id=investigation_id,
            user_id=user_id,
            signal_id=signal_id or "detected_signal",
            signal_title=resolved_title,
            status="insufficient_evidence",
            observed_change=observed_change,
            evidence=[],
            contributing_factors=[],
            hypotheses=[],
            confidence=ConfidenceAssessment(
                level=ConfidenceLevel.LIMITED,
                score_rationale="Insufficient evidence: Lack of historical multi-period records.",
                supporting_signals_count=0,
                independent_sources_count=0,
                limitations=missing_notes or ["Database lacks historical chronological records."],
            ),
            recommended_investigations=plan_next_investigations(
                schema_tables=schema_tables,
                contributing_factors=[],
                observed_change=None,
                missing_evidence_notes=missing_notes or ["Need multi-period timestamped records"],
            ),
            lineage=InvestigationLineage(
                source_tables=meta.get("tables_inspected", []),
                join_path="None",
                columns_analyzed=[],
                calculations=[],
                comparison_periods=[],
                record_counts={},
            ),
            summary=summary,
            explanation=full_exp,
            missing_evidence={
                "has_temporal_data": meta.get("has_temporal_data", False),
                "has_measure_data": meta.get("has_measure_data", False),
                "reasons": missing_notes,
            },
            created_at=created_at,
        )

    # 6. Analyze Dimensional Contributors
    primary_tbl = meta.get("tables_inspected", [schema_tables[0] if schema_tables else ""])[0]
    contributing_factors, dims_analyzed = analyze_contributing_factors(
        engine=engine,
        db_type=db_type,
        target_table=primary_tbl,
        observed_change=observed_change,
        evidence_items=evidence_items,
    )

    if not contributing_factors:
        missing_notes.append("No categorical dimensions found in connected table or related schemas.")

    # 7. Formulate Hypotheses and Confidence
    hypotheses, confidence = generate_hypotheses_and_confidence(
        observed_change=observed_change,
        evidence_items=evidence_items,
        contributing_factors=contributing_factors,
        missing_evidence_notes=missing_notes,
    )

    # 8. Plan Recommended Investigations
    recommendations = plan_next_investigations(
        schema_tables=schema_tables,
        contributing_factors=contributing_factors,
        observed_change=observed_change,
        missing_evidence_notes=missing_notes,
    )

    # 9. Synthesize Explanations (Deterministic + Optional Groq Polish)
    det_summary, det_explanation = build_deterministic_explanation(
        observed_change=observed_change,
        evidence_items=evidence_items,
        contributing_factors=contributing_factors,
        hypotheses=hypotheses,
        confidence=confidence,
        recommendations=recommendations,
        status="success",
    )

    final_summary, final_explanation = polish_explanation_with_groq(
        summary=det_summary,
        full_narrative=det_explanation,
        observed_metric=observed_change.metric,
        confidence_level=confidence.level.value,
    )

    # 10. Assemble Lineage
    all_source_tables = list(dict.fromkeys(meta.get("tables_inspected", []) + [e.source_table for e in evidence_items if e.source_table]))
    join_str = " -> ".join(all_source_tables) if len(all_source_tables) > 1 else all_source_tables[0] if all_source_tables else ""

    lineage = InvestigationLineage(
        source_tables=all_source_tables,
        join_path=join_str,
        columns_analyzed=list(dict.fromkeys(sum([e.source_columns for e in evidence_items], []) + dims_analyzed)),
        calculations=[e.calculation_description for e in evidence_items if e.calculation_description],
        comparison_periods=[e.time_range for e in evidence_items if e.time_range],
        record_counts={e.source_table: e.record_count for e in evidence_items if e.record_count is not None},
    )

    return InvestigationResult(
        investigation_id=investigation_id,
        user_id=user_id,
        signal_id=signal_id or "detected_kpi",
        signal_title=resolved_title,
        status="success",
        observed_change=observed_change,
        evidence=evidence_items,
        contributing_factors=contributing_factors,
        hypotheses=hypotheses,
        confidence=confidence,
        recommended_investigations=recommendations,
        lineage=lineage,
        summary=final_summary,
        explanation=final_explanation,
        missing_evidence={"reasons": missing_notes} if missing_notes else None,
        created_at=created_at,
    )
