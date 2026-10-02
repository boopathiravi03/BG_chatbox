"""
backend/app/intelligence/decision/confidence.py

Phase 8.4: Transparent Evidence Confidence Assessment
Calculates defensible, non-arbitrary confidence levels based strictly on:
- Quantitative signal counts
- Number of independent corroborating intelligence sources
- Sample depth and data breadth

Zero Hallucinated AI Scores:
- Never outputs arbitrary percentages (e.g. "94% AI certainty").
- Distinguishes HIGH, MODERATE, and LIMITED confidence with verifiable rationales.
"""
from __future__ import annotations

from typing import Sequence
from app.intelligence.decision.models import EvidenceItem, ConfidenceAssessment


def assess_confidence(
    evidence_items: Sequence[EvidenceItem],
    findings_count: int = 0,
    has_historical_data: bool = True,
) -> ConfidenceAssessment:
    """
    Evaluates evidence strength deterministically.
    """
    signal_count = len(evidence_items)
    unique_sources = sorted(list({e.source_system for e in evidence_items if e.source_system}))

    limitations: list[str] = []
    if not has_historical_data:
        limitations.append("Insufficient historical time periods to establish long-term baseline.")
    if len(unique_sources) <= 1:
        limitations.append("Evidence is derived from a single intelligence subsystem without cross-validation.")
    if signal_count < 2:
        limitations.append("Limited quantitative measurements available in connected database.")

    # High Confidence: 4+ signals across at least 3 independent systems
    if signal_count >= 4 and len(unique_sources) >= 3:
        level = "HIGH"
        rationale = (
            f"High evidence strength: Supported by {signal_count} independent database signals "
            f"corroborated across {len(unique_sources)} distinct analytical subsystems "
            f"({', '.join(unique_sources)})."
        )
    # Moderate Confidence: At least 2 signals across 1 or more systems
    elif signal_count >= 2:
        level = "MODERATE"
        rationale = (
            f"Moderate evidence strength: Supported by {signal_count} database measurements "
            f"across {len(unique_sources)} subsystem(s) ({', '.join(unique_sources)})."
        )
    # Limited Confidence
    else:
        level = "LIMITED"
        rationale = (
            f"Limited evidence strength: Only {signal_count} signal(s) detected. "
            "Findings represent initial observations and warrant manual database exploration."
        )

    return ConfidenceAssessment(
        level=level,
        signal_count=signal_count,
        corroborating_sources=unique_sources,
        rationale=rationale,
        limitations=limitations,
    )
