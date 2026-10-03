"""
backend/app/intelligence/outcome_optimization/effectiveness.py

Phase 8.9: Deterministic Effectiveness Classification
Classifies observed metric changes as POSITIVE, NEGATIVE, NEUTRAL,
INCONCLUSIVE, or INSUFFICIENT_DATA using only rule-based thresholds.

No AI scoring. No arbitrary weights. All thresholds are explicit and auditable.

Classification rules (applied in order):
1. INSUFFICIENT_DATA: sample_size < MIN_SAMPLES or no baseline
2. NEUTRAL: |delta_pct| < NOISE_THRESHOLD_PCT
3. INCONCLUSIVE: MIN_SIGNIFICANT_PCT <= |delta_pct| < SIGNIFICANCE_THRESHOLD_PCT
4. POSITIVE: delta > 0 and |delta_pct| >= SIGNIFICANCE_THRESHOLD_PCT
5. NEGATIVE: delta < 0 and |delta_pct| >= SIGNIFICANCE_THRESHOLD_PCT
"""
from __future__ import annotations

from typing import Optional
from app.intelligence.outcome_optimization.models import EffectivenessLabel

# Explicit deterministic thresholds (auditable, not arbitrary ML weights)
MIN_SAMPLES = 3               # Minimum observations needed for classification
NOISE_THRESHOLD_PCT = 1.0    # Changes < 1% treated as noise / NEUTRAL
INCONCLUSIVE_THRESHOLD_PCT = 5.0   # 1-5% changes: weak signal → INCONCLUSIVE
SIGNIFICANCE_THRESHOLD_PCT = 5.0  # ≥ 5% → classifiable as POSITIVE or NEGATIVE


def classify_effectiveness(
    delta: Optional[float],
    delta_pct: Optional[float],
    baseline_value: Optional[float],
    observed_value: Optional[float],
    sample_size: int = 0,
    baseline_sample_size: int = 0,
) -> str:
    """
    Deterministic classification of observed metric change.

    Returns one of: POSITIVE, NEGATIVE, NEUTRAL, INCONCLUSIVE, INSUFFICIENT_DATA
    """
    # Rule 1: Insufficient data
    if (
        delta is None
        or observed_value is None
        or baseline_value is None
        or sample_size < MIN_SAMPLES
    ):
        return EffectivenessLabel.INSUFFICIENT_DATA

    # Rule 2: No percentage change available (baseline was 0, or delta_pct unavailable)
    if delta_pct is None:
        # Fall back to raw delta classification
        if abs(delta) < 1e-9:
            return EffectivenessLabel.NEUTRAL
        return EffectivenessLabel.POSITIVE if delta > 0 else EffectivenessLabel.NEGATIVE

    abs_pct = abs(delta_pct)

    # Rule 3: Below noise floor → NEUTRAL
    if abs_pct < NOISE_THRESHOLD_PCT:
        return EffectivenessLabel.NEUTRAL

    # Rule 4: Weak signal → INCONCLUSIVE
    if abs_pct < INCONCLUSIVE_THRESHOLD_PCT:
        return EffectivenessLabel.INCONCLUSIVE

    # Rule 5: Significant change → POSITIVE or NEGATIVE
    if delta > 0:
        return EffectivenessLabel.POSITIVE
    return EffectivenessLabel.NEGATIVE


def describe_effectiveness(label: str) -> str:
    """Return a human-readable description of an effectiveness label."""
    descriptions = {
        EffectivenessLabel.POSITIVE: (
            "A measurable improvement was observed after the action. "
            "The metric moved in a favorable direction."
        ),
        EffectivenessLabel.NEGATIVE: (
            "A measurable deterioration was observed after the action. "
            "The metric moved in an unfavorable direction."
        ),
        EffectivenessLabel.NEUTRAL: (
            "No meaningful change was observed. "
            "The metric remained within the expected noise range."
        ),
        EffectivenessLabel.INCONCLUSIVE: (
            "A small change was observed, but it falls within the range of "
            "normal variation. The signal is too weak to classify as positive or negative."
        ),
        EffectivenessLabel.INSUFFICIENT_DATA: (
            "There is not enough data to classify the outcome. "
            "More observations are needed."
        ),
    }
    return descriptions.get(label, "Unknown effectiveness label.")
