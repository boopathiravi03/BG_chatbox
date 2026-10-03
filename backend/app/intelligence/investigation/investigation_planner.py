"""
backend/app/intelligence/investigation/investigation_planner.py

Phase 8.7: Grounded Investigation Planner
Formulates sequential, actionable next steps based strictly on discovered schema structure and evidence gaps.

Guarantees:
- Never recommends tables or columns that do not exist in the connected database.
- Explicitly addresses identified analytical gaps (e.g. missing dimensions).
- Prioritizes investigations based on contributor impact.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional
from app.intelligence.investigation.models import (
    InvestigationRecommendation,
    ContributingFactor,
    ObservedChange,
)


def plan_next_investigations(
    schema_tables: list[str],
    contributing_factors: list[ContributingFactor],
    observed_change: Optional[ObservedChange],
    missing_evidence_notes: list[str],
    entity_metadata: Optional[list[dict[str, Any]]] = None,
) -> list[InvestigationRecommendation]:
    """
    Generates prioritized next investigation steps grounded in the connected schema.
    """
    recommendations: list[InvestigationRecommendation] = []
    schema_tables_lower = {t.lower() for t in schema_tables}

    # ── 1. Contributor-Specific Deep Dives ─────────────────────────────────────
    for factor in contributing_factors[:2]:
        dim_name = factor.dimension
        val = factor.dimension_value
        rec_id = f"rec_f_{uuid.uuid4().hex[:6]}"

        if "category" in dim_name.lower():
            target = f"Table '{dim_name.split('.')[0] if '.' in dim_name else 'products'}' where category='{val}'"
            recommendations.append(InvestigationRecommendation(
                recommendation_id=rec_id,
                action_title=f"Inspect order volume and unit economics for category '{val}'",
                reason=f"Category '{val}' exhibited an associated shift of {factor.contribution_percent:+.1f}%.",
                target_data=target,
                expected_information_gained=f"Determines whether the shift in '{val}' is driven by unit volume loss or pricing changes.",
                priority="high",
            ))
        elif "city" in dim_name.lower() or "region" in dim_name.lower():
            target = f"Geographic records where {dim_name}='{val}'"
            recommendations.append(InvestigationRecommendation(
                recommendation_id=rec_id,
                action_title=f"Analyze local market and customer retention in '{val}'",
                reason=f"Region/City '{val}' shifted by {factor.contribution_percent:+.1f}%.",
                target_data=target,
                expected_information_gained="Identifies whether geographic contraction is isolated to specific regional accounts or widespread.",
                priority="high",
            ))
        elif "status" in dim_name.lower():
            target = f"Orders with status='{val}'"
            recommendations.append(InvestigationRecommendation(
                recommendation_id=rec_id,
                action_title=f"Review transaction lifecycle for status '{val}'",
                reason=f"Status '{val}' accounts for a significant portion of recent volume ({factor.contribution_percent:+.1f}%).",
                target_data=target,
                expected_information_gained="Surfaces whether operational bottlenecks, cancellations, or payment failures correlate with the change.",
                priority="high",
            ))

    # ── 2. Schema-Aware Cross-Table Recommendations ───────────────────────────
    # If inventory exists, check product availability
    if "inventory" in schema_tables_lower and len(recommendations) < 3:
        recommendations.append(InvestigationRecommendation(
            recommendation_id=f"rec_inv_{uuid.uuid4().hex[:6]}",
            action_title="Inspect product inventory and stockout events",
            reason="Connected schema contains an 'inventory' table which may reveal supply-side constraints.",
            target_data="inventory.stock, inventory.product_id",
            expected_information_gained="Confirms whether stockouts or backorders directly preceded sales contraction.",
            priority="medium",
        ))

    # If customers exists and not yet analyzed
    if "customers" in schema_tables_lower and len(recommendations) < 3 and not any("customer" in r.action_title.lower() for r in recommendations):
        recommendations.append(InvestigationRecommendation(
            recommendation_id=f"rec_cust_{uuid.uuid4().hex[:6]}",
            action_title="Analyze customer order frequency and repeat purchasing",
            reason="Connected database contains 'customers' table for cross-table cohort analysis.",
            target_data="customers, orders.customer_id",
            expected_information_gained="Differentiates between customer churn versus lower spend per existing customer.",
            priority="medium",
        ))

    # ── 3. Handling Missing Evidence & Analytical Gaps ─────────────────────────
    if missing_evidence_notes and len(recommendations) < 3:
        gap_desc = "; ".join(missing_evidence_notes)
        recommendations.append(InvestigationRecommendation(
            recommendation_id=f"rec_gap_{uuid.uuid4().hex[:6]}",
            action_title="Enrich dataset with missing dimensional attributes",
            reason=f"Current database is limited: {gap_desc}.",
            target_data="External customer, channel, or promotional datasets",
            expected_information_gained="Provides the categorical dimensions required for root-cause attribution.",
            priority="low",
        ))

    # Fallback generic recommendation if none triggered
    if not recommendations:
        recommendations.append(InvestigationRecommendation(
            recommendation_id=f"rec_gen_{uuid.uuid4().hex[:6]}",
            action_title="Conduct multi-period cohort comparison",
            reason="Establish granular historical baseline across active records.",
            target_data=", ".join(schema_tables[:3]),
            expected_information_gained="Discovers multi-month baseline volatility for connected entity tables.",
            priority="medium",
        ))

    return recommendations[:3]  # Bounded to top 3 prioritized recommendations

