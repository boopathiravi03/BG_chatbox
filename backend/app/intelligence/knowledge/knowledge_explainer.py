"""
backend/app/intelligence/knowledge/knowledge_explainer.py

Phase 9.1: Transparent Knowledge Explainer
Generates human-readable explanations of why BG AI uses specific business definitions,
clearly delineating schema facts, algorithmic inferences, user rules, and assumptions.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.intelligence.knowledge.models import (
    KnowledgeExplanation,
    KnowledgeStatus,
    KnowledgeProvenance,
)
from app.intelligence.knowledge.knowledge_store import (
    get_metric,
    get_rule,
    get_entity,
    list_versions,
)

logger = logging.getLogger("bgai.knowledge.explainer")


def explain_knowledge_item(
    knowledge_id: str,
    user_id: str,
    database_identity: str,
) -> KnowledgeExplanation:
    """
    Produces a transparent audit of facts vs inferences vs assumptions for a given knowledge item.
    """
    # 1. Try metric
    metric = get_metric(knowledge_id, user_id=user_id, database_identity=database_identity)
    if metric:
        facts = [
            f"Table '{metric.table_name}' exists in the active database schema.",
            f"Target column '{metric.column_name or '*'}' is defined with standard aggregation {metric.aggregation}.",
        ]
        inferences = []
        assumptions = []

        if metric.provenance == KnowledgeProvenance.SCHEMA_DERIVED.value:
            inferences.append("Metric concept was automatically discovered by schema inspection.")
        elif metric.provenance == KnowledgeProvenance.USER_PROVIDED.value:
            facts.append("Metric definition was explicitly configured by the user.")

        if metric.filter_expression:
            facts.append(f"Calculation incorporates active filter: '{metric.filter_expression}'.")
            if metric.status != KnowledgeStatus.CONFIRMED.value:
                assumptions.append("Filter condition is currently PROPOSED and has not been confirmed by a user.")

        versions = list_versions(metric.metric_id, user_id=user_id, database_identity=database_identity)

        return KnowledgeExplanation(
            knowledge_id=metric.metric_id,
            title=f"Explanation for Metric: {metric.name}",
            provenance=metric.provenance,
            status=metric.status,
            version=metric.version,
            facts=facts,
            inferences=inferences,
            assumptions=assumptions,
            rules_applied=metric.rules_applied or ([metric.filter_expression] if metric.filter_expression else []),
            source_description=f"Version {metric.version} ({len(versions)} prior revisions logged).",
        )

    # 2. Try rule
    rule = get_rule(knowledge_id, user_id=user_id, database_identity=database_identity)
    if rule:
        facts = [
            f"Rule targets table '{rule.target_table}' and column '{rule.target_column or '*'}'."
        ]
        inferences = []
        assumptions = []

        if rule.status in {KnowledgeStatus.CONFIRMED.value, KnowledgeStatus.ACTIVE.value}:
            facts.append(f"Confirmed by user on this database. Expression: '{rule.expression}'.")
        else:
            assumptions.append(f"Rule is {rule.status}. It does NOT automatically alter active calculations.")

        if rule.provenance == KnowledgeProvenance.AI_INFERRED.value:
            inferences.append("Rule expression was proposed by natural language interpretation.")

        return KnowledgeExplanation(
            knowledge_id=rule.rule_id,
            title=f"Explanation for Rule: {rule.name}",
            provenance=rule.provenance,
            status=rule.status,
            version=rule.version,
            facts=facts,
            inferences=inferences,
            assumptions=assumptions,
            rules_applied=[rule.expression],
            source_description=f"Rule type '{rule.rule_type}' scoped to {rule.scope}.",
        )

    # 3. Try entity
    entity = get_entity(knowledge_id, user_id=user_id, database_identity=database_identity)
    if entity:
        facts = [
            f"Mapped to database table '{entity.table_name}'.",
            f"Primary key: {entity.primary_key or 'None designated'}.",
        ]
        inferences = [
            f"Inferred business entity name '{entity.name}' from table name patterns.",
            f"Designated importance level '{entity.importance}'.",
        ]
        assumptions = []
        if entity.status != KnowledgeStatus.CONFIRMED.value:
            assumptions.append("Entity mapping is unconfirmed; human review recommended.")

        return KnowledgeExplanation(
            knowledge_id=entity.entity_id,
            title=f"Explanation for Entity: {entity.name}",
            provenance=entity.provenance,
            status=entity.status,
            version=1,
            facts=facts,
            inferences=inferences,
            assumptions=assumptions,
            rules_applied=[],
            source_description=entity.description,
        )

    # Unknown
    return KnowledgeExplanation(
        knowledge_id=knowledge_id,
        title="Unknown Knowledge Item",
        provenance=KnowledgeProvenance.SYSTEM_DEFINED.value,
        status="NOT_FOUND",
        version=0,
        facts=[],
        inferences=[],
        assumptions=["Item does not exist in the active enterprise knowledge registry."],
        rules_applied=[],
        source_description="Item not found.",
    )
