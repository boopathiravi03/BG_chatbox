"""
backend/app/intelligence/knowledge/__init__.py

Phase 9.1: Enterprise Knowledge & Context Intelligence Public Package
Exports core models, registries, storage functions, context parsers, and lineage resolvers.
"""
from app.intelligence.knowledge.models import (
    KnowledgeProvenance,
    KnowledgeStatus,
    EntityImportance,
    RuleScope,
    RuleType,
    BusinessEntity,
    BusinessRule,
    BusinessMetric,
    ColumnSemantic,
    KnowledgeConflict,
    KnowledgeVersionRecord,
    KnowledgeLineageNode,
    KnowledgeLineage,
    KnowledgeExplanation,
    KnowledgeSummary,
    ContextParseResult,
)
from app.intelligence.knowledge.provenance import (
    is_authoritative,
    is_inferred,
    format_provenance_badge,
)
from app.intelligence.knowledge.knowledge_store import (
    save_entity,
    get_entity,
    list_entities,
    save_rule,
    get_rule,
    list_rules,
    save_metric,
    get_metric,
    list_metrics,
    save_conflict,
    get_conflict,
    list_conflicts,
    list_versions,
    confirm_knowledge_item,
    disable_knowledge_item,
    resolve_knowledge_conflict,
    get_knowledge_summary,
    clear_knowledge_store,
)
from app.intelligence.knowledge.entity_registry import (
    discover_and_sync_entities,
)
from app.intelligence.knowledge.metric_registry import (
    discover_and_sync_metrics,
    resolve_metric_calculation,
)
from app.intelligence.knowledge.business_rules import (
    validate_rule_safety,
    detect_rule_conflicts,
    get_active_filters_for_table,
)
from app.intelligence.knowledge.context_engine import (
    parse_and_propose_context,
)
from app.intelligence.knowledge.knowledge_resolver import (
    build_metric_lineage,
    search_knowledge,
)
from app.intelligence.knowledge.knowledge_explainer import (
    explain_knowledge_item,
)

__all__ = [
    "KnowledgeProvenance",
    "KnowledgeStatus",
    "EntityImportance",
    "RuleScope",
    "RuleType",
    "BusinessEntity",
    "BusinessRule",
    "BusinessMetric",
    "ColumnSemantic",
    "KnowledgeConflict",
    "KnowledgeVersionRecord",
    "KnowledgeLineageNode",
    "KnowledgeLineage",
    "KnowledgeExplanation",
    "KnowledgeSummary",
    "ContextParseResult",
    "is_authoritative",
    "is_inferred",
    "format_provenance_badge",
    "save_entity",
    "get_entity",
    "list_entities",
    "save_rule",
    "get_rule",
    "list_rules",
    "save_metric",
    "get_metric",
    "list_metrics",
    "save_conflict",
    "get_conflict",
    "list_conflicts",
    "list_versions",
    "confirm_knowledge_item",
    "disable_knowledge_item",
    "resolve_knowledge_conflict",
    "get_knowledge_summary",
    "clear_knowledge_store",
    "discover_and_sync_entities",
    "discover_and_sync_metrics",
    "resolve_metric_calculation",
    "validate_rule_safety",
    "detect_rule_conflicts",
    "get_active_filters_for_table",
    "parse_and_propose_context",
    "build_metric_lineage",
    "search_knowledge",
    "explain_knowledge_item",
]
