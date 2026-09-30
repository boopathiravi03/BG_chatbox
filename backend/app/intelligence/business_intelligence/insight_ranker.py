"""
backend/app/intelligence/business_intelligence/insight_ranker.py

Phase 8.1: Deterministic Insight Ranking System
Ranks insights using objective, explainable factors:
- Severity (CRITICAL > WARNING > INFO)
- Magnitude of change (percentage delta)
- Category significance (DECLINE / ANOMALY / QUALITY prioritized)
- Record impact / sample size
Never uses an LLM to decide importance.
"""
from __future__ import annotations

import math
from app.intelligence.business_intelligence.models import BusinessInsight, InsightCategory, InsightSeverity

SEVERITY_WEIGHTS = {
    InsightSeverity.CRITICAL: 100.0,
    InsightSeverity.WARNING: 50.0,
    InsightSeverity.INFO: 10.0,
}

CATEGORY_WEIGHTS = {
    InsightCategory.DECLINE: 25.0,
    InsightCategory.ANOMALY: 20.0,
    InsightCategory.QUALITY: 15.0,
    InsightCategory.PERFORMANCE: 12.0,
    InsightCategory.CONCENTRATION: 10.0,
    InsightCategory.TOP_CONTRIBUTOR: 8.0,
    InsightCategory.GROWTH: 7.0,
    InsightCategory.TREND: 5.0,
    InsightCategory.FORECAST: 4.0,
    InsightCategory.DATA_COMPLETENESS: 3.0,
}


def calculate_insight_priority(insight: BusinessInsight) -> float:
    """
    Computes an objective, explainable priority score for a business insight.
    
    Formula:
        Priority = BaseSeverityWeight + CategoryWeight + MagnitudeAdjustment + ImpactAdjustment
        
    - BaseSeverity: CRITICAL (100), WARNING (50), INFO (10)
    - CategoryWeight: 3.0 to 25.0 based on operational urgency
    - MagnitudeAdjustment: Up to +30.0 based on percentage change or anomaly severity
    - ImpactAdjustment: Up to +15.0 based on affected record volume
    """
    base_severity = SEVERITY_WEIGHTS.get(insight.severity, 10.0)
    category_bonus = CATEGORY_WEIGHTS.get(insight.category, 5.0)

    # Magnitude calculation
    magnitude_score = 0.0
    if insight.change_percent is not None:
        magnitude_score = min(30.0, abs(insight.change_percent) * 0.5)
    elif "severity_score" in insight.evidence:
        try:
            magnitude_score = min(30.0, float(insight.evidence["severity_score"]) * 0.3)
        except Exception:
            pass

    # Record / sample volume calculation
    impact_score = 0.0
    evidence = insight.evidence or {}
    record_count = evidence.get("affected_records") or evidence.get("record_count") or evidence.get("sample_size") or 0
    try:
        count_val = float(record_count)
        if count_val > 0:
            impact_score = min(15.0, math.log10(count_val + 1.0) * 3.0)
    except Exception:
        pass

    total_priority = base_severity + category_bonus + magnitude_score + impact_score
    return round(total_priority, 2)


def rank_insights(insights: list[BusinessInsight]) -> list[BusinessInsight]:
    """
    Assigns deterministic priority scores to all insights and sorts them descending.
    """
    for insight in insights:
        insight.priority = calculate_insight_priority(insight)

    insights.sort(key=lambda x: x.priority, reverse=True)
    return insights
