"""
backend/app/intelligence/knowledge/entity_registry.py

Phase 9.1: Business Entity Registry & Semantic Discovery
Discovers business entity candidates from database schema, primary/foreign keys,
and row structure. Inferred entities are explicitly marked as SCHEMA_DERIVED and PROPOSED.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from app.intelligence.schema_analyzer import analyze_schema
from app.intelligence.business_intelligence.business_context import ENTITY_KEYWORDS
from app.intelligence.knowledge.models import (
    BusinessEntity,
    EntityImportance,
    KnowledgeProvenance,
    KnowledgeStatus,
)
from app.intelligence.knowledge.knowledge_store import (
    save_entity,
    list_entities,
    get_entity,
)

logger = logging.getLogger("bgai.knowledge.entity_registry")


def _singularize(word: str) -> str:
    """Simple heuristic singularization for common English table names."""
    w = word.strip().lower()
    if w.endswith("ies") and len(w) > 3:
        return (w[:-3] + "y").capitalize()
    if w.endswith("es") and len(w) > 3 and (w.endswith("shes") or w.endswith("ches") or w.endswith("xes")):
        return w[:-2].capitalize()
    if w.endswith("s") and not w.endswith("ss") and len(w) > 2:
        return w[:-1].capitalize()
    return w.capitalize()


def discover_and_sync_entities(
    engine: Any,
    db_type: str,
    user_id: str,
    database_identity: str,
) -> list[BusinessEntity]:
    """
    Discovers candidate business entities from active schema and synchronizes with knowledge store.
    Never overwrites user-confirmed entities.
    """
    if engine is None or db_type == "none":
        return list_entities(user_id=user_id, database_identity=database_identity)

    schema_info = analyze_schema(engine, db_type)
    tables = schema_info.get("tables", {})
    if not tables:
        return list_entities(user_id=user_id, database_identity=database_identity)

    existing_entities = {e.table_name: e for e in list_entities(user_id=user_id, database_identity=database_identity)}
    discovered: list[BusinessEntity] = []

    for tbl_name, tbl_meta in tables.items():
        # If user already confirmed or created an entity for this table, preserve it
        if tbl_name in existing_entities:
            discovered.append(existing_entities[tbl_name])
            continue

        cols = tbl_meta.get("columns", [])
        pk = tbl_meta.get("primary_key")
        fks = tbl_meta.get("foreign_keys", [])

        # Heuristic entity naming
        clean_tbl = re.sub(r"^(tbl_|dim_|fact_|t_)", "", tbl_name.lower())
        singular_name = _singularize(clean_tbl)
        plural_name = tbl_name.replace("_", " ").title()

        # Assess importance
        is_known_entity = any(kw in clean_tbl for kw in ENTITY_KEYWORDS)
        if is_known_entity or len(cols) >= 5:
            importance = EntityImportance.PRIMARY.value
            confidence = 0.85
        else:
            importance = EntityImportance.SECONDARY.value
            confidence = 0.65

        # Format foreign keys
        fk_list = []
        for fk in fks:
            fk_list.append({
                "column": fk.get("constrained_columns", [""])[0] if fk.get("constrained_columns") else "",
                "target_table": fk.get("referred_table", ""),
                "target_column": fk.get("referred_columns", [""])[0] if fk.get("referred_columns") else "",
            })

        entity = BusinessEntity(
            entity_id=f"ent_{tbl_name}",
            name=singular_name,
            plural_name=plural_name,
            table_name=tbl_name,
            description=f"Represents {plural_name.lower()} records discovered from table '{tbl_name}'.",
            importance=importance,
            primary_key=pk if isinstance(pk, str) else (pk[0] if isinstance(pk, list) and pk else None),
            foreign_keys=fk_list,
            provenance=KnowledgeProvenance.SCHEMA_DERIVED.value,
            status=KnowledgeStatus.PROPOSED.value,
            confidence=confidence,
            user_id=user_id,
            database_identity=database_identity,
        )

        saved = save_entity(entity)
        discovered.append(saved)

    return discovered
