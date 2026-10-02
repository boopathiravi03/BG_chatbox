"""
backend/app/intelligence/decision/decision_engine.py

Phase 8.4: AI Decision & Planning Intelligence Engine
Synthesizes multi-source database intelligence into an evidence-backed
decision analysis and actionable decision plan.

Strict Epistemic Hygiene:
- Separates observed database facts from candidate hypotheses.
- Prohibits unfounded causal claims (correlation does not imply causation).
- Zero LLM-calculated mathematics; 100% deterministic Python metrics.
- Groq integration is strictly read-only and narrative-summarizing with local fallback.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from app.intelligence.decision.models import (
    DecisionQuestion,
    DecisionAnalysis,
    Finding,
    Hypothesis,
    EvidenceItem,
)
from app.intelligence.decision.evidence import aggregate_multi_source_evidence
from app.intelligence.decision.confidence import assess_confidence
from app.intelligence.decision.planner import generate_decision_plan_and_investigations
from app.database.database_manager import get_database_connection_info
from app.agent.groq_agent import ask_groq

logger = logging.getLogger("bgai.decision.engine")


def understand_question(question_text: str) -> DecisionQuestion:
    """
    Parses natural language strategic question to determine analytical intent
    and candidate target entities.
    """
    q_clean = (question_text or "").strip()
    q_lower = q_clean.lower()

    intent = "GENERAL_DECISION"
    focus_metric: Optional[str] = None
    target_entities: list[str] = []

    # Detect Intent
    if any(k in q_lower for k in ["revenue", "sales", "decline", "drop", "decrease", "down", "falling", "slump"]):
        intent = "REVENUE_DECLINE"
        focus_metric = "revenue"
    elif any(k in q_lower for k in ["cancel", "cancellation", "refund", "return", "churn"]):
        intent = "ORDER_CANCELLATION"
        focus_metric = "status"
    elif any(k in q_lower for k in ["product", "sku", "item", "category", "inventory", "stock"]):
        intent = "PRODUCT_PERFORMANCE"
        focus_metric = "products"
    elif any(k in q_lower for k in ["recent", "recently", "what changed", "latest", "month", "shift"]):
        intent = "RECENT_CHANGES"
    elif any(k in q_lower for k in ["risk", "danger", "threat", "critical", "issue", "attention"]):
        intent = "BUSINESS_RISK"

    # Detect Entities
    for ent in ["orders", "products", "customers", "inventory", "order_items", "payments", "transactions"]:
        if ent in q_lower or ent[:-1] in q_lower:
            target_entities.append(ent)

    return DecisionQuestion(
        raw_question=q_clean,
        intent=intent,
        target_entities=target_entities,
        focus_metric=focus_metric,
    )


def synthesize_decision_analysis(
    question_text: str = "",
    engine: Any = None,
    db_type: str = "none",
    user_id: str = "default_user",
    question: Optional[str] = None,
) -> DecisionAnalysis:
    """
    Core entrypoint: Evaluates connected database data across all intelligence
    subsystems to construct an evidence-grounded decision analysis.
    """
    effective_question = question if question is not None else question_text
    # 1. Parse question intent
    parsed_q = understand_question(effective_question)


    # 2. Multi-source evidence aggregation
    evidence_items = aggregate_multi_source_evidence(
        engine=engine,
        db_type=db_type,
        user_id=user_id,
        intent=parsed_q.intent,
        target_tables=parsed_q.target_entities,
    )

    db_info = get_database_connection_info()
    db_name = db_info.get("database") or "database"

    # Identify all involved tables across evidence
    source_tables = sorted(list({t for e in evidence_items for t in e.source_tables if t}))

    # 3. Derive deterministic findings from evidence
    findings: list[Finding] = []
    hypotheses: list[Hypothesis] = []

    # Analyze primary metrics from evidence
    primary_metric_ev = next(
        (e for e in evidence_items if e.delta_percent is not None and abs(e.delta_percent) > 0),
        None,
    )

    if primary_metric_ev:
        delta_str = f"{'+' if (primary_metric_ev.delta_percent or 0) > 0 else ''}{primary_metric_ev.delta_percent:.1f}%"
        stmt = f"{primary_metric_ev.title} experienced a {delta_str} movement in recent data."
        findings.append(
            Finding(
                statement=stmt,
                evidence_ids=[primary_metric_ev.evidence_id],
                severity="CRITICAL" if (primary_metric_ev.delta_percent or 0) <= -20 else "WARNING",
                category="REVENUE" if "revenue" in primary_metric_ev.metric.lower() else "ORDERS",
                source_tables=primary_metric_ev.source_tables,
            )
        )

        # Formulate non-causal hypothesis
        hypotheses.append(
            Hypothesis(
                statement=(
                    f"Observed shifts in '{primary_metric_ev.metric}' may be driven by category-level "
                    "demand variance or changes in order volume."
                ),
                status="UNCONFIRMED_HYPOTHESIS",
                supporting_evidence_ids=[primary_metric_ev.evidence_id],
                likelihood="PROBABLE" if abs(primary_metric_ev.delta_percent or 0) > 15 else "POSSIBLE",
                causality_caveat=(
                    "Hypothesis requires empirical validation. "
                    "Observed correlation does not establish definitive causation."
                ),
            )
        )

    # Incorporate Cross-Table / Concentration Evidence
    ct_ev = next((e for e in evidence_items if e.source_system == "CROSS_TABLE_BI"), None)
    if ct_ev:
        findings.append(
            Finding(
                statement=f"Cross-table multi-hop analysis identified: {ct_ev.title}.",
                evidence_ids=[ct_ev.evidence_id],
                severity="INFO",
                category="REVENUE",
                source_tables=ct_ev.source_tables,
            )
        )
        hypotheses.append(
            Hypothesis(
                statement=(
                    "Product or category concentration imbalances across related tables "
                    "could be influencing top-line aggregate outcomes."
                ),
                status="UNCONFIRMED_HYPOTHESIS",
                supporting_evidence_ids=[ct_ev.evidence_id],
                likelihood="POSSIBLE",
            )
        )

    # Incorporate Anomaly Evidence
    anom_ev = next((e for e in evidence_items if e.source_system == "ANOMALY_DETECTOR"), None)
    if anom_ev:
        findings.append(
            Finding(
                statement=f"Detected statistical anomaly in {anom_ev.title}.",
                evidence_ids=[anom_ev.evidence_id],
                severity="WARNING",
                category="ANOMALY",
                source_tables=anom_ev.source_tables,
            )
        )
        hypotheses.append(
            Hypothesis(
                statement=(
                    f"Statistical outliers observed in '{', '.join(anom_ev.source_tables)}' "
                    "might indicate pipeline ingestion anomalies or isolated transaction spikes."
                ),
                status="UNCONFIRMED_HYPOTHESIS",
                supporting_evidence_ids=[anom_ev.evidence_id],
                likelihood="POSSIBLE",
            )
        )

    # Incorporate Proactive Alert Evidence
    alt_ev = next((e for e in evidence_items if e.source_system == "PROACTIVE_ALERTS"), None)
    if alt_ev:
        findings.append(
            Finding(
                statement=f"Active Proactive Alert: {alt_ev.title}.",
                evidence_ids=[alt_ev.evidence_id],
                severity=alt_ev.metadata.get("severity", "WARNING"),
                category="QUALITY",
                source_tables=alt_ev.source_tables,
            )
        )

    # Fallback finding if database has minimal records
    if not findings:
        findings.append(
            Finding(
                statement=(
                    f"Evaluated connected tables ({', '.join(source_tables) if source_tables else 'database'}). "
                    "Metrics remain within expected baseline variations with no anomalous breaches."
                ),
                evidence_ids=[],
                severity="INFO",
                category="GENERAL",
                source_tables=source_tables,
            )
        )
        hypotheses.append(
            Hypothesis(
                statement="Current performance trends are stable and consistent with historical baselines.",
                status="UNCONFIRMED_HYPOTHESIS",
                supporting_evidence_ids=[],
                likelihood="POSSIBLE",
            )
        )

    # 4. Formulate Problem Statement
    if primary_metric_ev and (primary_metric_ev.delta_percent or 0) < 0:
        problem_statement = (
            f"Observed contraction of {abs(primary_metric_ev.delta_percent or 0):.1f}% in "
            f"'{primary_metric_ev.metric}' during the latest available observation period."
        )
    elif primary_metric_ev:
        problem_statement = (
            f"Observed metric shift of {primary_metric_ev.delta_percent:+.1f}% in "
            f"'{primary_metric_ev.metric}' across connected database records."
        )
    elif anom_ev:
        problem_statement = f"Identified statistical outlier behavior in '{anom_ev.title}'."
    else:
        problem_statement = (
            f"Business query regarding '{parsed_q.raw_question}' evaluated against "
            f"{len(source_tables)} connected table(s)."
        )

    # 5. Generate Recommended Investigations & Sequential Decision Plan
    investigations, plan_steps = generate_decision_plan_and_investigations(
        question=parsed_q,
        findings=findings,
        evidence_items=evidence_items,
        hypotheses=hypotheses,
    )

    # 6. Assess Confidence
    confidence_assessment = assess_confidence(
        evidence_items=evidence_items,
        findings_count=len(findings),
        has_historical_data=len(evidence_items) >= 2,
    )

    # 7. Optional Groq Narrative Refinement (Privacy Guarded)
    problem_narrative = problem_statement
    try:
        # Pass only anonymized aggregates; NEVER pass raw database rows or credentials
        prompt_summary = (
            f"Question: {parsed_q.raw_question}\n"
            f"Observed Findings: {'; '.join(f.statement for f in findings[:3])}\n"
            f"Formulate a concise 1-2 sentence executive problem statement summarizing the core observed fact."
        )
        enriched = ask_groq(prompt_summary)
        if enriched and len(enriched.strip()) > 10:
            problem_narrative = enriched.strip()
    except Exception as e:
        logger.debug("Groq narrative refinement skipped: %s", str(e))

    return DecisionAnalysis(
        question=parsed_q.raw_question,
        intent=parsed_q.intent,
        problem_statement=problem_narrative,
        findings=findings,
        evidence=evidence_items,
        hypotheses=hypotheses,
        recommended_investigations=investigations,
        decision_plan=plan_steps,
        confidence=confidence_assessment,
        source_tables=source_tables,
        database_name=db_name,
        database_type=db_type,
    )


# Convenience alias
run_decision_analysis = synthesize_decision_analysis

