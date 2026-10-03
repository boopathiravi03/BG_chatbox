"""
backend/app/intelligence/knowledge/knowledge_resolver.py

Phase 9.1: Knowledge Lineage & Semantic Resolution Engine
Resolves complete provenance lineage from business entity down to executable SQL,
and answers business semantic questions using verified enterprise knowledge.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.intelligence.knowledge.models import (
    KnowledgeLineage,
    KnowledgeLineageNode,
    KnowledgeStatus,
    KnowledgeProvenance,
)
from app.intelligence.knowledge.knowledge_store import (
    get_metric,
    list_metrics,
    get_entity,
    list_entities,
    list_rules,
)
from app.intelligence.knowledge.metric_registry import resolve_metric_calculation

logger = logging.getLogger("bgai.knowledge.resolver")


def build_metric_lineage(
    metric_id_or_name: str,
    user_id: str,
    database_identity: str,
    db_type: str = "sqlite",
) -> KnowledgeLineage:
    """
    Constructs an end-to-end visual lineage graph for a metric:
    Business Entity -> Metric -> Definition -> Business Rules -> Database Table -> Column -> SQL.
    """
    # 1. Retrieve metric
    metric = get_metric(metric_id_or_name, user_id=user_id, database_identity=database_identity)
    if not metric:
        all_metrics = list_metrics(user_id=user_id, database_identity=database_identity)
        for m in all_metrics:
            if m.name.lower() == metric_id_or_name.lower():
                metric = m
                break

    if not metric:
        return KnowledgeLineage(
            target_id=metric_id_or_name,
            target_name=metric_id_or_name,
            nodes=[
                KnowledgeLineageNode(
                    step="UNKNOWN",
                    type="DEFINITION",
                    label=f"Metric '{metric_id_or_name}' not configured in knowledge registry.",
                    details={"error": "Definition not found."},
                )
            ],
            provenance=KnowledgeProvenance.SYSTEM_DEFINED.value,
            status=KnowledgeStatus.PROPOSED.value,
            sql_expression="",
        )

    # 2. Retrieve Entity
    entity = get_entity(f"ent_{metric.table_name}", user_id=user_id, database_identity=database_identity)

    # 3. Resolve Calculation
    calc = resolve_metric_calculation(
        metric_id_or_name=metric.metric_id,
        table_name=metric.table_name,
        column_name=metric.column_name,
        user_id=user_id,
        database_identity=database_identity,
        db_type=db_type,
    )

    nodes: list[KnowledgeLineageNode] = []

    # Node 1: Business Entity
    entity_label = entity.name if entity else metric.table_name.replace("_", " ").title()
    nodes.append(
        KnowledgeLineageNode(
            step="1_ENTITY",
            type="ENTITY",
            label=f"Business Entity: {entity_label}",
            details={
                "table_name": metric.table_name,
                "importance": entity.importance if entity else "SECONDARY",
                "status": entity.status if entity else KnowledgeStatus.PROPOSED.value,
            },
        )
    )

    # Node 2: Metric Concept
    nodes.append(
        KnowledgeLineageNode(
            step="2_METRIC",
            type="METRIC",
            label=f"Metric Concept: {metric.name}",
            details={
                "version": metric.version,
                "provenance": metric.provenance,
                "status": metric.status,
            },
        )
    )

    # Node 3: Applied Rules
    rules_applied = calc.get("rules_applied", [])
    rules_label = f"Rules Applied: {len(rules_applied)} Confirmed Rule(s)" if rules_applied else "Rules Applied: None (Standard Schema Aggregation)"
    nodes.append(
        KnowledgeLineageNode(
            step="3_RULES",
            type="RULE",
            label=rules_label,
            details={
                "rules": rules_applied,
                "has_confirmed_rules": calc.get("has_confirmed_rules", False),
            },
        )
    )

    # Node 4: Table & Column
    col_str = metric.column_name or "*"
    nodes.append(
        KnowledgeLineageNode(
            step="4_SCHEMA",
            type="COLUMN",
            label=f"Database Target: {metric.table_name}.{col_str}",
            details={
                "table": metric.table_name,
                "column": metric.column_name,
                "aggregation": metric.aggregation,
            },
        )
    )

    # Node 5: SQL Calculation
    nodes.append(
        KnowledgeLineageNode(
            step="5_CALCULATION",
            type="SQL",
            label="Executable SQL Calculation",
            details={
                "sql": calc.get("sql_expression", ""),
            },
        )
    )

    return KnowledgeLineage(
        target_id=metric.metric_id,
        target_name=metric.name,
        nodes=nodes,
        provenance=metric.provenance,
        status=metric.status,
        sql_expression=calc.get("sql_expression", ""),
    )


def search_knowledge(
    query: str,
    user_id: str,
    database_identity: str,
) -> dict[str, Any]:
    """
    Searches enterprise knowledge registry for concepts, rules, metrics, or tables.
    Returns honest structured response; states 'Business definition not configured' if not found.
    """
    q_clean = query.strip().lower()
    if not q_clean:
        return {"query": query, "found": False, "answer": "Please enter a valid knowledge query."}

    # Search metrics
    metrics = list_metrics(user_id=user_id, database_identity=database_identity)
    matching_metrics = [m for m in metrics if q_clean in m.name.lower() or q_clean in m.table_name.lower()]

    # Search rules
    rules = list_rules(user_id=user_id, database_identity=database_identity)
    matching_rules = [r for r in rules if q_clean in r.name.lower() or q_clean in r.description.lower() or q_clean in r.target_table.lower()]

    # Search entities
    entities = list_entities(user_id=user_id, database_identity=database_identity)
    matching_entities = [e for e in entities if q_clean in e.name.lower() or q_clean in e.table_name.lower()]

    found = bool(matching_metrics or matching_rules or matching_entities)

    if not found:
        return {
            "query": query,
            "found": False,
            "answer": "Business definition not configured in enterprise knowledge registry.",
            "metrics": [],
            "rules": [],
            "entities": [],
        }

    # Synthesize answer
    answer_parts = []
    if matching_metrics:
        m = matching_metrics[0]
        rules_info = f" with filter '{m.filter_expression}'" if m.filter_expression else ""
        answer_parts.append(
            f"Metric '{m.name}' is defined on table '{m.table_name}' using {m.aggregation}({m.column_name or '*'}){rules_info} (Status: {m.status}, Provenance: {m.provenance})."
        )
    if matching_rules:
        r = matching_rules[0]
        answer_parts.append(
            f"Rule '{r.name}' applies condition '{r.expression}' to table '{r.target_table}' (Status: {r.status})."
        )
    if matching_entities:
        e = matching_entities[0]
        answer_parts.append(
            f"Entity '{e.name}' represents table '{e.table_name}' ({e.description})."
        )

    return {
        "query": query,
        "found": True,
        "answer": " ".join(answer_parts),
        "metrics": [m.to_dict() for m in matching_metrics],
        "rules": [r.to_dict() for r in matching_rules],
        "entities": [e.to_dict() for e in matching_entities],
    }
