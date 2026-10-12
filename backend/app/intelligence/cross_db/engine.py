"""backend/app/intelligence/cross_db/engine.py

Unified Cross-Database Orchestration Engine for BG AI 2.0.
Coordinates source routing, schema inspection, dialect-specific query generation,
safe execution, application-layer combination, and provenance explanation.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from app.connectors.registry import get_connection_registry
from app.intelligence.cross_db.combiner import CrossDatabaseCombiner
from app.intelligence.cross_db.models import (
    CrossDatabaseResponse,
    QueryIntentType,
    SourceQueryResult,
)
from app.intelligence.cross_db.planner import CrossDatabasePlanner
from app.intelligence.cross_db.router import CrossDatabaseRouter


class CrossDatabaseEngine:
    """Coordinates cross-database queries across multiple connected databases."""

    @classmethod
    def process(
        cls,
        user_id: str,
        message: str,
        selected_source_ids: Optional[List[str]] = None,
    ) -> CrossDatabaseResponse:
        # 1. Routing
        intent, target_conns, disambig_opts = CrossDatabaseRouter.route_query(
            user_id=user_id,
            message=message,
            selected_source_ids=selected_source_ids,
        )

        if intent == QueryIntentType.AMBIGUOUS:
            return CrossDatabaseResponse(
                intent=intent,
                requires_disambiguation=True,
                disambiguation_options=disambig_opts or [],
                explanation=(
                    "Multiple connected databases contain matching tables. "
                    "Please specify which database you want to query, or select one from below."
                ),
            )

        if not target_conns:
            return CrossDatabaseResponse(
                intent=QueryIntentType.GENERAL,
                explanation="No database is currently connected. Please connect a database first.",
            )

        # 2. Vector Semantic Search
        if intent == QueryIntentType.VECTOR_SEARCH:
            vec_conn = target_conns[0]
            start = time.perf_counter()
            vec_res = vec_conn.execute_query(message)
            elapsed_ms = (time.perf_counter() - start) * 1000

            sub_r = SourceQueryResult(
                source_id=vec_conn.connection_id,
                source_name=vec_conn.name,
                connector_type=vec_conn.connector_type,
                query_text=message,
                success=vec_res.success,
                columns=vec_res.columns,
                rows=vec_res.rows,
                rows_returned=vec_res.rows_returned,
                execution_time_ms=round(elapsed_ms, 2),
                error=vec_res.error,
            )

            explanation = (
                f"Performed semantic similarity search on **{vec_conn.name}** ({vec_conn.connector_type}).\n\n"
                f"Found {vec_res.rows_returned} relevant document(s) matching your request."
            )

            return CrossDatabaseResponse(
                intent=intent,
                sources_used=[vec_conn.to_dict()],
                sub_results=[sub_r],
                combined_result={
                    "columns": vec_res.columns,
                    "rows": vec_res.rows,
                    "rows_returned": vec_res.rows_returned,
                },
                explanation=explanation,
                combination_strategy="vector_retrieval",
            )

        # 3. Planning
        plans = CrossDatabasePlanner.plan_subqueries(message, target_conns)
        if not plans:
            return CrossDatabaseResponse(
                intent=intent,
                explanation="Could not generate queries for the selected sources. Please verify their schemas.",
            )

        # 4. Execution across sources
        sub_results: List[SourceQueryResult] = []
        for plan in plans:
            registry = get_connection_registry()
            conn = registry.get_connector(user_id, plan.source_id)
            if not conn:
                continue

            start = time.perf_counter()
            res = conn.execute_query(plan.query_text)
            elapsed = (time.perf_counter() - start) * 1000

            sub_results.append(
                SourceQueryResult(
                    source_id=plan.source_id,
                    source_name=plan.source_name,
                    connector_type=plan.connector_type,
                    query_text=plan.query_text,
                    success=res.success,
                    columns=res.columns,
                    rows=res.rows,
                    rows_returned=res.rows_returned,
                    execution_time_ms=round(elapsed, 2),
                    error=res.error,
                )
            )

        # 5. Combination
        combined, explanation, strategy = CrossDatabaseCombiner.combine(
            sub_results, message
        )

        sources_summary = [c.to_dict() for c in target_conns]

        return CrossDatabaseResponse(
            intent=intent,
            sources_used=sources_summary,
            sub_results=sub_results,
            combined_result=combined,
            explanation=explanation,
            combination_strategy=strategy,
        )

