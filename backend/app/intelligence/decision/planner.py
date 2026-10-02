"""
backend/app/intelligence/decision/planner.py

Phase 8.4: Decision Planning & Recommended Investigations Generator
Converts observed evidence and candidate hypotheses into an actionable,
sequential decision plan and targeted investigation roadmap.

Human-in-the-Loop Safety:
- Every action step strictly mandates explicit human review (requires_confirmation = True).
- Integrates with Phase 5 / Phase 8.3 Safe Action architecture when remediation is eligible.
- Never schedules or performs unconfirmed database writes.
"""
from __future__ import annotations

from typing import Sequence, Optional
from app.intelligence.decision.models import (
    Finding,
    EvidenceItem,
    Hypothesis,
    RecommendedInvestigation,
    PlanStep,
    DecisionQuestion,
)


def generate_decision_plan_and_investigations(
    question: DecisionQuestion,
    findings: Sequence[Finding],
    evidence_items: Sequence[EvidenceItem],
    hypotheses: Sequence[Hypothesis],
) -> tuple[list[RecommendedInvestigation], list[PlanStep]]:
    """
    Builds structured, non-destructive investigation avenues and a prioritized
    decision plan tailored to the user's strategic intent.
    """
    investigations: list[RecommendedInvestigation] = []
    plan_steps: list[PlanStep] = []

    # Identify primary affected tables
    involved_tables: list[str] = []
    for f in findings:
        for t in f.source_tables:
            if t not in involved_tables:
                involved_tables.append(t)
    for e in evidence_items:
        for t in e.source_tables:
            if t not in involved_tables:
                involved_tables.append(t)

    primary_table = involved_tables[0] if involved_tables else "orders"
    secondary_table = involved_tables[1] if len(involved_tables) > 1 else None

    # ── 1. Recommended Investigations ──────────────────────────────────────────
    inv_idx = 1
    if question.intent in {"REVENUE_DECLINE", "RECENT_CHANGES"}:
        investigations.append(
            RecommendedInvestigation(
                title=f"Segment Breakdown in '{primary_table}'",
                rationale="Audit volume and aggregate metrics across individual dimensions to isolate contraction drivers.",
                target_table=primary_table,
                suggested_focus="Filter by category, status, and chronological month",
                priority=inv_idx,
            )
        )
        inv_idx += 1

        if secondary_table:
            investigations.append(
                RecommendedInvestigation(
                    title=f"Cross-Entity Correlation with '{secondary_table}'",
                    rationale=f"Trace join relationships between '{primary_table}' and '{secondary_table}' to detect customer or item churn.",
                    target_table=secondary_table,
                    suggested_focus=f"Join on foreign key reference between {primary_table} and {secondary_table}",
                    priority=inv_idx,
                )
            )
            inv_idx += 1

    elif question.intent == "PRODUCT_PERFORMANCE":
        investigations.append(
            RecommendedInvestigation(
                title="Product Contribution & Margin Audit",
                rationale="Identify top declining and top performing SKUs to detect concentration imbalances.",
                target_table="products" if "products" in involved_tables else primary_table,
                suggested_focus="Aggregate revenue and unit sales grouped by product_name or category",
                priority=inv_idx,
            )
        )
        inv_idx += 1

    elif question.intent == "ORDER_CANCELLATION":
        investigations.append(
            RecommendedInvestigation(
                title="Cancellation & Status Progression Audit",
                rationale="Evaluate status frequency and transition times for cancelled or returned orders.",
                target_table="orders" if "orders" in involved_tables else primary_table,
                suggested_focus="Group by order status and check temporal clustering",
                priority=inv_idx,
            )
        )
        inv_idx += 1

    # Add general data quality / anomaly investigation if anomalies or proactive alerts exist
    has_anomaly_evidence = any(e.source_system in {"ANOMALY_DETECTOR", "PROACTIVE_ALERTS"} for e in evidence_items)
    if has_anomaly_evidence:
        investigations.append(
            RecommendedInvestigation(
                title="Anomaly & Data Integrity Verification",
                rationale="Verify statistical outliers and null rates in connected tables to rule out data pipeline defects.",
                target_table=primary_table,
                suggested_focus="Inspect outliers, null densities, and orphan foreign key records",
                priority=inv_idx,
            )
        )
        inv_idx += 1

    if not investigations:
        investigations.append(
            RecommendedInvestigation(
                title=f"Baseline Health Audit of '{primary_table}'",
                rationale="Review primary table metrics, column distributions, and recent row updates.",
                target_table=primary_table,
                suggested_focus="Run descriptive statistics and frequency distributions",
                priority=1,
            )
        )

    # ── 2. Sequential Decision Plan ───────────────────────────────────────────
    step_num = 1

    # Step 1: In-depth Investigation
    plan_steps.append(
        PlanStep(
            step_number=step_num,
            title=f"Empirically Test Primary Hypothesis in '{primary_table}'",
            description=(
                f"Perform deep-dive dimensional slice on table '{primary_table}' "
                "to verify whether the observed shift is localized to specific categories or customer cohorts."
            ),
            action_type="INVESTIGATE",
            target_table=primary_table,
            requires_confirmation=False,  # Read-only exploration
            safe_action_eligible=False,
        )
    )
    step_num += 1

    # Step 2: Cross-Table Correlation
    if secondary_table:
        plan_steps.append(
            PlanStep(
                step_number=step_num,
                title=f"Cross-Reference Records with '{secondary_table}'",
                description=(
                    f"Evaluate cross-table linkage between '{primary_table}' and '{secondary_table}' "
                    "to determine external dependencies (e.g. supplier delays, inventory shortages, or customer tier shifts)."
                ),
                action_type="COMPARE",
                target_table=secondary_table,
                requires_confirmation=False,
                safe_action_eligible=False,
            )
        )
        step_num += 1

    # Step 3: Anomaly & Quality Review
    plan_steps.append(
        PlanStep(
            step_number=step_num,
            title="Audit Data Completeness and System Health",
            description=(
                "Review data pipeline integrity, null concentrations, and foreign key alignments "
                "to confirm reported shifts reflect genuine operational dynamics rather than ingestion lag."
            ),
            action_type="AUDIT",
            target_table=primary_table,
            requires_confirmation=False,
            safe_action_eligible=False,
        )
    )
    step_num += 1

    # Step 4: Remediation Plan / Safe Action Bridge
    # Check if any proactive alert or data quality item is eligible for safe action
    remediation_alert_id = None
    for e in evidence_items:
        if e.source_system == "PROACTIVE_ALERTS" and e.metadata.get("alert_id"):
            remediation_alert_id = e.metadata.get("alert_id")
            break

    plan_steps.append(
        PlanStep(
            step_number=step_num,
            title="Formulate Corrective Operational Strategy",
            description=(
                "Synthesize verified findings with business stakeholders. If actionable structural "
                "or database remediations are identified, prepare a human-gated Safe Action plan."
            ),
            action_type="REMEDIATE",
            target_table=primary_table,
            requires_confirmation=True,  # Mandatory human gate
            safe_action_eligible=remediation_alert_id is not None,
            suggested_action_id=remediation_alert_id,
        )
    )

    return investigations, plan_steps
