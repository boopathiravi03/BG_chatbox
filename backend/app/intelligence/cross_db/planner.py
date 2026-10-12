"""backend/app/intelligence/cross_db/planner.py

Dialect-Specific Query Planner for BG AI 2.0.
Generates safe, targeted queries for each independent database using its
exact reflected schema and native query dialect.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from app.connectors.base import BaseConnector, ConnectorCategory
from app.intelligence.cross_db.models import SourceQueryPlan


class CrossDatabasePlanner:
    """Plans source-specific subqueries based on real schemas."""

    @classmethod
    def plan_subqueries(
        cls,
        message: str,
        target_connectors: List[BaseConnector],
    ) -> List[SourceQueryPlan]:
        plans: List[SourceQueryPlan] = []

        for conn in target_connectors:
            plan = cls._plan_for_single_source(message, conn)
            if plan:
                plans.append(plan)

        return plans

    @classmethod
    def _plan_for_single_source(
        cls,
        message: str,
        connector: BaseConnector,
    ) -> Optional[SourceQueryPlan]:
        schema = connector.get_schema()
        table_names = list(schema.keys())

        if not table_names and connector.category != ConnectorCategory.VECTOR:
            return None

        # Check for vector connector
        if connector.category == ConnectorCategory.VECTOR:
            coll = table_names[0] if table_names else "default"
            # Strip semantic trigger phrases from query
            clean_q = re.sub(
                r"(?i)\b(find|search|documents|semantically|related|to|similar|about)\b",
                " ",
                message,
            ).strip()
            query_spec = json.dumps({"collection": coll, "query_text": clean_q, "limit": 10})
            return SourceQueryPlan(
                source_id=connector.connection_id,
                source_name=connector.name,
                connector_type=connector.connector_type,
                query_text=query_spec,
                expected_entity=coll,
                query_type="vector",
            )

        # Check for MongoDB
        if connector.category == ConnectorCategory.DOCUMENT:
            # Find closest collection
            target_col = cls._find_relevant_table(message, table_names) or table_names[0]
            query_spec = json.dumps({"collection": target_col, "filter": {}, "limit": 50})
            return SourceQueryPlan(
                source_id=connector.connection_id,
                source_name=connector.name,
                connector_type=connector.connector_type,
                query_text=query_spec,
                expected_entity=target_col,
                query_type="mongodb",
            )

        # Relational SQL
        target_table = cls._find_relevant_table(message, table_names)
        if not target_table:
            target_table = table_names[0]

        quote = '"' if connector.connector_type in ("postgres", "sqlite") else '`'
        sql = f"SELECT * FROM {quote}{target_table}{quote} LIMIT 100"

        # Check if user asked for count
        if re.search(r"\b(how many|count|total number)\b", message.lower()):
            sql = f"SELECT COUNT(*) AS total_count FROM {quote}{target_table}{quote}"

        return SourceQueryPlan(
            source_id=connector.connection_id,
            source_name=connector.name,
            connector_type=connector.connector_type,
            query_text=sql,
            expected_entity=target_table,
            query_type="sql",
        )

    @classmethod
    def _find_relevant_table(cls, message: str, table_names: List[str]) -> Optional[str]:
        msg_lower = message.lower()
        for t in table_names:
            if re.search(rf"\b{re.escape(t.lower())}\b", msg_lower):
                return t
        # Match singular/plural forms (e.g. customer vs customers)
        for t in table_names:
            t_base = t.rstrip("s").lower()
            if len(t_base) >= 3 and re.search(rf"\b{re.escape(t_base)}\b", msg_lower):
                return t
        return None

