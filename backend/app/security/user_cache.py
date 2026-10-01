"""
backend/app/security/user_cache.py

Phase 7: User-scoped cache for all intelligence, anomaly, schema, and database profile data.

Cache keys are always (user_id, cache_name).
Clearing a user's cache does NOT affect any other user's data.

Modules that previously used global caches:
  - intelligence/scanner.py   → _cached_intelligence_report (global)  → user_cache
  - intelligence/anomaly/detector.py → _cached_anomaly_report (global) → user_cache
  - database/database_context.py → _profile (global)                   → user_cache
"""
from __future__ import annotations

import threading
from typing import Any, Optional

_cache_lock = threading.Lock()
_cache: dict[tuple[str, str], Any] = {}   # (user_id, cache_key) → value


def cache_set(user_id: str, key: str, value: Any) -> None:
    """Store a value in the user-scoped cache."""
    with _cache_lock:
        _cache[(user_id, key)] = value


def cache_get(user_id: str, key: str) -> Optional[Any]:
    """Retrieve a value from the user-scoped cache. Returns None if absent."""
    with _cache_lock:
        return _cache.get((user_id, key))


def cache_delete(user_id: str, key: str) -> None:
    """Delete a specific cache entry for a user."""
    with _cache_lock:
        _cache.pop((user_id, key), None)


def cache_clear_user(user_id: str) -> None:
    """
    Clear ALL cache entries for a user.
    Called on /disconnect. Does NOT affect other users.
    """
    with _cache_lock:
        to_remove = [k for k in _cache if k[0] == user_id]
        for k in to_remove:
            del _cache[k]


def cache_clear_all() -> None:
    """Clear entire cache — test utility only."""
    with _cache_lock:
        _cache.clear()


# ── Named cache keys (constants to prevent typos) ─────────────────────────────
CACHE_INTELLIGENCE_REPORT = "intelligence_report"
CACHE_ANOMALY_REPORT = "anomaly_report"
CACHE_DATABASE_PROFILE = "database_profile"
CACHE_SCHEMA = "schema"
CACHE_ANALYTICS = "analytics"
CACHE_FORECAST = "forecast"
CACHE_INSIGHTS_REPORT = "insights_report"
CACHE_JOIN_PATHS = "join_paths"
CACHE_BI_CONTEXT = "bi_context"
CACHE_CROSS_TABLE_INSIGHTS = "cross_table_insights"
