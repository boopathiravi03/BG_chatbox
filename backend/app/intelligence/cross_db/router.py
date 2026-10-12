"""backend/app/intelligence/cross_db/router.py

Intelligent Source Router for BG AI 2.0.
Analyzes user intent, connected database schemas, and explicit selections to
determine the optimal routing: single source, cross-database federation,
vector semantic search, or user disambiguation.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.connectors.base import BaseConnector, ConnectorCategory
from app.connectors.registry import get_connection_registry
from app.intelligence.cross_db.models import QueryIntentType


SEMANTIC_KEYWORDS = {
    "semantic", "semantically", "embedding", "embeddings", "vector",
    "similarity", "similar to", "related documents", "semantic search"
}


class CrossDatabaseRouter:
    """Routes user queries across multiple connected sources."""

    @classmethod
    def route_query(
        cls,
        user_id: str,
        message: str,
        selected_source_ids: Optional[List[str]] = None,
    ) -> Tuple[QueryIntentType, List[BaseConnector], Optional[List[Dict[str, str]]]]:
        """
        Determines:
        1. Intent type (SINGLE_SOURCE, CROSS_SOURCE, VECTOR_SEARCH, AMBIGUOUS, GENERAL)
        2. Target connectors
        3. Disambiguation choices (if ambiguous)
        """
        registry = get_connection_registry()
        connectors = registry.list_connectors(user_id)

        if not connectors:
            return QueryIntentType.GENERAL, [], None

        msg_lower = message.lower().strip()

        # 1. If user explicitly provided selected_source_ids from the UI selector
        if selected_source_ids and len(selected_source_ids) > 0:
            chosen = [c for c in connectors if c.connection_id in selected_source_ids]
            if len(chosen) == 1:
                return QueryIntentType.SINGLE_SOURCE, chosen, None
            elif len(chosen) > 1:
                return QueryIntentType.CROSS_SOURCE, chosen, None

        # 2. Vector Semantic Retrieval Check
        is_semantic = any(kw in msg_lower for kw in SEMANTIC_KEYWORDS)
        vector_connectors = [c for c in connectors if c.category == ConnectorCategory.VECTOR]
        if is_semantic and vector_connectors:
            return QueryIntentType.VECTOR_SEARCH, vector_connectors[:1], None

        # 3. Check for explicit cross-source comparison patterns
        # e.g., "compare mysql ... with postgres ...", "join sqlite with mysql"
        has_multi_db_mention = False
        mentioned_connectors: List[BaseConnector] = []

        for conn in connectors:
            # Check name or type mention
            type_pattern = rf"\b{re.escape(conn.connector_type)}\b"
            name_pattern = rf"\b{re.escape(conn.name.lower())}\b"
            if re.search(type_pattern, msg_lower) or re.search(name_pattern, msg_lower):
                if conn not in mentioned_connectors:
                    mentioned_connectors.append(conn)

        if len(mentioned_connectors) > 1:
            return QueryIntentType.CROSS_SOURCE, mentioned_connectors, None
        elif len(mentioned_connectors) == 1:
            return QueryIntentType.SINGLE_SOURCE, mentioned_connectors, None

        # 4. Schema-based matching
        # Check which database contains the requested tables / entities
        table_to_connectors: Dict[str, List[BaseConnector]] = {}

        for conn in connectors:
            try:
                schema = conn.get_schema()
                for table_name in schema.keys():
                    t_lower = table_name.lower()
                    table_to_connectors.setdefault(t_lower, []).append(conn)
            except Exception:
                pass

        # Identify tables mentioned in the message
        matched_tables: Set[str] = set()
        for t_name in table_to_connectors.keys():
            # Match word boundary
            if re.search(rf"\b{re.escape(t_name)}\b", msg_lower):
                matched_tables.add(t_name)

        # If multiple tables were matched across different databases
        if matched_tables:
            matching_connectors_set: Set[BaseConnector] = set()
            for t in matched_tables:
                matching_connectors_set.update(table_to_connectors[t])

            matching_connectors = list(matching_connectors_set)

            # If exactly 1 table matched, but it exists in multiple databases ambiguously
            if len(matched_tables) == 1:
                t = next(iter(matched_tables))
                candidate_conns = table_to_connectors[t]
                if len(candidate_conns) > 1:
                    # AMBIGUOUS: ask user to choose
                    options = [
                        {"source_id": c.connection_id, "name": c.name, "type": c.connector_type}
                        for c in candidate_conns
                    ]
                    return QueryIntentType.AMBIGUOUS, candidate_conns, options
                else:
                    return QueryIntentType.SINGLE_SOURCE, candidate_conns, None

            # Multiple tables matched
            if len(matching_connectors) == 1:
                return QueryIntentType.SINGLE_SOURCE, matching_connectors, None
            elif len(matching_connectors) > 1:
                # Tables span multiple databases -> Cross-Database query!
                return QueryIntentType.CROSS_SOURCE, matching_connectors, None

        # 5. Fallback to active connector
        active = registry.get_active_connector(user_id)
        if active:
            return QueryIntentType.SINGLE_SOURCE, [active], None

        return QueryIntentType.SINGLE_SOURCE, [connectors[0]], None

