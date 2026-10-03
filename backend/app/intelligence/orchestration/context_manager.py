"""
backend/app/intelligence/orchestration/context_manager.py

Context injection and boundary management for Phase 9.2: Advanced Agent Orchestration.
Gathers verified schema facts, confirmed knowledge rules, and user isolation identifiers.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class OrchestrationContextManager:
    """
    Constructs safe, scoped execution contexts for specialist agents.
    """

    @classmethod
    def build_context(
        cls,
        user_id: str,
        database_identity: str,
        goal: str,
        engine: Optional[Any] = None,
        db_type: str = "sqlite",
    ) -> Dict[str, Any]:
        """
        Builds a comprehensive context bundle for orchestration steps.
        """
        context: Dict[str, Any] = {
            "user_id": user_id,
            "database_identity": database_identity,
            "goal": goal,
            "db_type": db_type,
            "engine": engine,
            "verified_rules": [],
            "verified_metrics": [],
            "schema_tables": [],
        }

        # Attempt to load confirmed business rules and metrics (Phase 9.1)
        try:
            from app.intelligence.knowledge.knowledge_store import list_rules, list_metrics
            rules = list_rules(user_id=user_id, database_identity=database_identity, status="CONFIRMED")
            metrics = list_metrics(user_id=user_id, database_identity=database_identity)
            context["verified_rules"] = [r.to_dict() for r in rules]
            context["verified_metrics"] = [m.to_dict() for m in metrics]
        except Exception as e:
            logger.debug(f"Knowledge context retrieval bypassed: {e}")

        # Schema table discovery
        try:
            from app.tools.get_schema import get_schema
            schema = get_schema()
            if isinstance(schema, dict):
                context["schema_tables"] = list(schema.keys())
        except Exception as e:
            logger.debug(f"Schema discovery bypassed: {e}")

        return context
