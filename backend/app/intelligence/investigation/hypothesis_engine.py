"""
backend/app/intelligence/investigation/hypothesis_engine.py

Phase 8.7: Evidence-Backed Hypothesis Generation
Synthesizes candidate explanations from verified database evidence and contributing dimensions.

Strict Epistemic Hygiene:
- Hypotheses are explicitly unconfirmed candidate explanations.
- Never asserts causation; always appends "Correlation does not establish causation."
- Evaluates confidence deterministically (HIGH / MODERATE / LIMITED) based on signal count and breadth.
- Zero arbitrary confidence percentages.
"""
from __future__ import annotations

import uuid
from typing import Optional
from app.intelligence.investigation.models import (
    Hypothesis,
    ConfidenceAssessment,
    ConfidenceLevel,
    EvidenceItem,
    ContributingFactor,
    ObservedChange,
)


def generate_hypotheses_and_confidence(
    observed_change: Optional[ObservedChange],
    evidence_items: list[EvidenceItem],
    contributing_factors: list[ContributingFactor],
    missing_evidence_notes: list[str],
) -> tuple[list[Hypothesis], ConfidenceAssessment]:
    """
    Formulates evidence-backed hypotheses and a transparent confidence assessment.
    """
    hypotheses: list[Hypothesis] = []
    limitations: list[str] = list(missing_evidence_notes)

    signal_count = len(evidence_items)
    factor_count = len(contributing_factors)

    # Collect unique tables involved
    unique_tables = {e.source_table for e in evidence_items if e.source_table}
    for cf in contributing_factors:
        if "." in cf.dimension:
            unique_tables.add(cf.dimension.split(".")[0])

    independent_sources = len(unique_tables)

    # ── A. Insufficient Evidence Scenario ──────────────────────────────────────
    if not evidence_items or not observed_change:
        hypo = Hypothesis(
            hypothesis_id=f"hypo_insuf_{uuid.uuid4().hex[:6]}",
            statement=(
                "The connected database does not contain sufficient chronological or dimensional records "
                "to formulate an evidence-backed hypothesis."
            ),
            supporting_evidence_ids=[],
            confidence_level=ConfidenceLevel.LIMITED,
            status="unconfirmed",
            causality_caveat="Correlation does not establish causation.",
        )
        hypotheses.append(hypo)

        confidence = ConfidenceAssessment(
            level=ConfidenceLevel.LIMITED,
            score_rationale="Insufficient evidence: Lack of multi-period records or dimensional attributes.",
            supporting_signals_count=0,
            independent_sources_count=0,
            limitations=limitations or ["Database lacks chronological time series or categorical dimensions."],
        )
        return hypotheses, confidence

    # ── B. Sufficient Evidence: Derive Hypotheses from Top Contributors ────────
    if contributing_factors:
        # Group factors by impact type (negative vs positive)
        negative_factors = [f for f in contributing_factors if f.impact_type == "negative"]
        positive_factors = [f for f in contributing_factors if f.impact_type == "positive"]

        metric_name = observed_change.metric

        if negative_factors and (observed_change.delta or 0) <= 0:
            top_factors = negative_factors[:3]
            factor_summaries = [f"{f.dimension} '{f.dimension_value}' ({f.contribution_percent:+.1f}%)" for f in top_factors]
            supp_ev = []
            for f in top_factors:
                supp_ev.extend(f.evidence_ids)

            # Deduplicate evidence IDs while preserving order
            supp_ev_dedup = list(dict.fromkeys(supp_ev or [e.evidence_id for e in evidence_items]))

            stmt = (
                f"The observed decline in {metric_name} strongly coincides with contraction in "
                f"{', '.join(factor_summaries)}. These dimensional contractions represent the primary associated shifts."
            )

            # Determine confidence for this hypothesis
            h_conf = ConfidenceLevel.HIGH if len(supp_ev_dedup) >= 3 and len(top_factors) >= 2 else ConfidenceLevel.MODERATE
            hypotheses.append(Hypothesis(
                hypothesis_id=f"hypo_dim_{uuid.uuid4().hex[:6]}",
                statement=stmt,
                supporting_evidence_ids=supp_ev_dedup,
                confidence_level=h_conf,
                status="unconfirmed",
                causality_caveat="Correlation does not establish causation.",
            ))

        elif positive_factors and (observed_change.delta or 0) >= 0:
            top_factors = positive_factors[:3]
            factor_summaries = [f"{f.dimension} '{f.dimension_value}' ({f.contribution_percent:+.1f}%)" for f in top_factors]
            supp_ev = []
            for f in top_factors:
                supp_ev.extend(f.evidence_ids)

            supp_ev_dedup = list(dict.fromkeys(supp_ev or [e.evidence_id for e in evidence_items]))

            stmt = (
                f"The observed increase in {metric_name} is accompanied by growth in "
                f"{', '.join(factor_summaries)}."
            )
            h_conf = ConfidenceLevel.HIGH if len(supp_ev_dedup) >= 3 and len(top_factors) >= 2 else ConfidenceLevel.MODERATE
            hypotheses.append(Hypothesis(
                hypothesis_id=f"hypo_dim_{uuid.uuid4().hex[:6]}",
                statement=stmt,
                supporting_evidence_ids=supp_ev_dedup,
                confidence_level=h_conf,
                status="unconfirmed",
                causality_caveat="Correlation does not establish causation.",
            ))
        else:
            # Neutral / mixed distribution hypothesis
            top_f = contributing_factors[0]
            stmt = (
                f"Variations in {metric_name} correlate with the concentration of {top_f.dimension} "
                f"('{top_f.dimension_value}'), which represents a significant portion of active volume."
            )
            hypotheses.append(Hypothesis(
                hypothesis_id=f"hypo_dist_{uuid.uuid4().hex[:6]}",
                statement=stmt,
                supporting_evidence_ids=[e.evidence_id for e in evidence_items],
                confidence_level=ConfidenceLevel.MODERATE,
                status="unconfirmed",
                causality_caveat="Correlation does not establish causation.",
            ))

    # Fallback hypothesis if no dimensional factors were extracted
    if not hypotheses:
        hypotheses.append(Hypothesis(
            hypothesis_id=f"hypo_base_{uuid.uuid4().hex[:6]}",
            statement=(
                f"The observed metric shift in {observed_change.metric} is verified by chronological records, "
                "but no granular dimensional contributors were detected in the immediate schema."
            ),
            supporting_evidence_ids=[e.evidence_id for e in evidence_items],
            confidence_level=ConfidenceLevel.LIMITED,
            status="unconfirmed",
            causality_caveat="Correlation does not establish causation.",
        ))

    # ── C. Deterministic Confidence Assessment ────────────────────────────────
    if signal_count >= 4 and independent_sources >= 2 and factor_count >= 2:
        level = ConfidenceLevel.HIGH
        rationale = (
            f"HIGH confidence: Supported by {signal_count} quantitative measurements and {factor_count} "
            f"dimensional contributor signals corroborated across {independent_sources} distinct tables."
        )
    elif signal_count >= 2 or factor_count >= 1:
        level = ConfidenceLevel.MODERATE
        rationale = (
            f"MODERATE confidence: Supported by {signal_count} database measurements and {factor_count} "
            "dimensional shift signals. Causal confirmation requires independent domain verification."
        )
    else:
        level = ConfidenceLevel.LIMITED
        rationale = (
            f"LIMITED confidence: Only {signal_count} quantitative signal(s) available. "
            "Evidence is preliminary and warrants broader investigation."
        )

    if not limitations:
        limitations.append("Causal mechanism cannot be established solely from observational database queries.")

    confidence = ConfidenceAssessment(
        level=level,
        score_rationale=rationale,
        supporting_signals_count=signal_count + factor_count,
        independent_sources_count=independent_sources,
        limitations=limitations,
    )

    return hypotheses, confidence

