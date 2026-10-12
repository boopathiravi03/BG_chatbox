"""backend/app/intelligence/cross_db/__init__.py

BG AI 2.0 Intelligent Cross-Database Querying & Federation Package.
"""

from app.intelligence.cross_db.models import (
    CrossDatabaseResponse,
    QueryIntentType,
    SourceQueryPlan,
    SourceQueryResult,
)
from app.intelligence.cross_db.router import CrossDatabaseRouter
from app.intelligence.cross_db.planner import CrossDatabasePlanner
from app.intelligence.cross_db.combiner import CrossDatabaseCombiner
from app.intelligence.cross_db.engine import CrossDatabaseEngine

__all__ = [
    "CrossDatabaseResponse",
    "QueryIntentType",
    "SourceQueryPlan",
    "SourceQueryResult",
    "CrossDatabaseRouter",
    "CrossDatabasePlanner",
    "CrossDatabaseCombiner",
    "CrossDatabaseEngine",
]

