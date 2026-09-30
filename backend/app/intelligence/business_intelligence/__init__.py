"""
backend/app/intelligence/business_intelligence/__init__.py

Phase 8.1: Automated Business Intelligence Package Entry Point
"""
from app.intelligence.business_intelligence.models import (
    BusinessInsight,
    BusinessContext,
    DiscoveredMetric,
    BusinessIntelligenceReport,
    InsightCategory,
    InsightSeverity,
)
from app.intelligence.business_intelligence.business_context import discover_business_context
from app.intelligence.business_intelligence.metric_discovery import discover_business_metrics
from app.intelligence.business_intelligence.insight_ranker import rank_insights
from app.intelligence.business_intelligence.insight_engine import generate_business_intelligence_report

__all__ = [
    "BusinessInsight",
    "BusinessContext",
    "DiscoveredMetric",
    "BusinessIntelligenceReport",
    "InsightCategory",
    "InsightSeverity",
    "discover_business_context",
    "discover_business_metrics",
    "rank_insights",
    "generate_business_intelligence_report",
]
