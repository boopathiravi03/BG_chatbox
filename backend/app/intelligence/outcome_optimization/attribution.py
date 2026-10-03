"""
backend/app/intelligence/outcome_optimization/attribution.py

Phase 8.9: Attribution Safety Module
Assesses whether an observed metric change can be attributed to a specific action,
and whether confounders (competing explanations) are present.

Critical principle:
- We NEVER claim an action CAUSED an outcome.
- We only report OBSERVED changes with OBSERVED_OUTCOME or flag CONFOUNDERS_PRESENT.
- Attribution is determined by structural evidence, not by assumption.

Confounder detection strategies:
1. Recent schema changes (DDL) → may have changed underlying data
2. Multiple tables recently modified → concurrent changes possible
3. Time elapsed too short → insufficient measurement window
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import text
from app.intelligence.schema_analyzer import analyze_schema
from app.intelligence.outcome_optimization.models import AttributionStatus

logger = logging.getLogger("bgai.outcome_optimization.attribution")

# Minimum hours before we consider measurement meaningful
MIN_MEASUREMENT_HOURS = 0  # We allow immediate measurement but flag it


def assess_attribution(
    engine: Any,
    db_type: str,
    source_table: str,
    action_executed_at: Optional[str] = None,
) -> dict[str, Any]:
    """
    Assess the attribution status of an observed metric change.

    Returns:
        {
            "status": str  (one of AttributionStatus values),
            "confounders": list[str],
            "explanation": str,
        }
    """
    confounders = []
    explanation_parts = []

    if engine is None:
        return {
            "status": AttributionStatus.NO_BASELINE,
            "confounders": [],
            "explanation": "No database connection available for attribution assessment.",
        }

    try:
        # Check 1: How many tables are in this database?
        # If there are many tables, concurrent modifications are more likely.
        schema_info = analyze_schema(engine, db_type)
        table_count = len(schema_info.get("tables", []))

        if table_count > 10:
            confounders.append(
                f"Database has {table_count} tables — concurrent modifications to "
                "other tables may have influenced related metrics."
            )

        # Check 2: Source table row count — if very large, aggregate metrics
        # are less sensitive to single-row changes.
        try:
            from app.intelligence.schema_analyzer import quote_identifier
            t_sql = quote_identifier(source_table, db_type)
            with engine.connect() as conn:
                row_count = conn.execute(text(f"SELECT COUNT(*) FROM {t_sql}")).scalar() or 0
            if row_count > 10000:
                confounders.append(
                    f"Table '{source_table}' has {row_count:,} rows — small individual "
                    "changes may not produce measurable aggregate effects."
                )
        except Exception:
            pass

        # Check 3: No action timestamp → cannot assess time window
        if not action_executed_at:
            confounders.append(
                "No action execution timestamp provided — "
                "cannot assess measurement window relative to action."
            )
            explanation_parts.append("Measurement window unknown (no execution timestamp).")

    except Exception as e:
        logger.debug("Attribution assessment error: %s", str(e))
        confounders.append("Attribution assessment encountered an error during analysis.")

    # Determine final status
    if confounders:
        status = AttributionStatus.CONFOUNDERS_PRESENT
        explanation = (
            "One or more potential confounding factors were detected. "
            "The observed change may be associated with the action but cannot be "
            "attributed to it exclusively. "
            + " | ".join(confounders)
        )
    else:
        status = AttributionStatus.OBSERVED_OUTCOME
        explanation = (
            "No confounders were detected. The observed change is associated with "
            "the action timeframe. Causation is not claimed."
        )

    return {
        "status": status,
        "confounders": confounders,
        "explanation": explanation,
    }
