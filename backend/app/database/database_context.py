from __future__ import annotations

import threading
from typing import Optional

from app.database.database_manager import (
    get_engine,
    get_current_db_type,
)
from app.tools.analyze_database import analyze_database
from app.agent.database_profile import DatabaseProfile

# Thread-safe profile cache keyed by (user_id, connection_id)
_profile_cache: dict[tuple[str, str], DatabaseProfile] = {}
_cache_lock = threading.RLock()


def _resolve_context_keys(user_id: Optional[str] = None, connection_id: Optional[str] = None) -> tuple[str, str]:
    uid = user_id
    cid = connection_id
    try:
        from app.database.connection_context import get_request_user_id, get_request_connection_id
        if not uid:
            uid = get_request_user_id()
        if not cid:
            cid = get_request_connection_id()
    except Exception:
        pass

    return (uid or "default", cid or "default")


def refresh_database_profile(
    user_id: Optional[str] = None,
    connection_id: Optional[str] = None,
) -> Optional[DatabaseProfile]:
    """
    Refreshes and stores the database profile for the active user and connection.
    Discovers tables, columns, business entities, and audits data health.
    """
    key = _resolve_context_keys(user_id, connection_id)

    profile = analyze_database(user_id=key[0], connection_id=key[1])
    if not profile or not profile.analyzed:
        # If engine was missing, verify if engine exists now
        engine = get_engine()
        if engine is None and profile.total_tables == 0:
            with _cache_lock:
                _profile_cache.pop(key, None)
            return None

    with _cache_lock:
        _profile_cache[key] = profile

    return profile


def get_database_profile(
    user_id: Optional[str] = None,
    connection_id: Optional[str] = None,
) -> Optional[DatabaseProfile]:
    """
    Returns the cached database profile for the active user and connection.
    If no cached profile exists, automatically executes a fresh analysis.
    """
    key = _resolve_context_keys(user_id, connection_id)

    with _cache_lock:
        if key in _profile_cache:
            return _profile_cache[key]

    # Lazy initialization if not cached yet
    return refresh_database_profile(user_id=key[0], connection_id=key[1])


def invalidate_database_profile(
    user_id: Optional[str] = None,
    connection_id: Optional[str] = None,
) -> None:
    """
    Invalidates cached database profile after DDL or schema alterations.
    """
    key = _resolve_context_keys(user_id, connection_id)
    with _cache_lock:
        _profile_cache.pop(key, None)


def clear_database_profile(
    user_id: Optional[str] = None,
    connection_id: Optional[str] = None,
) -> None:
    """
    Clears cached profile for user or clears all if default.
    """
    key = _resolve_context_keys(user_id, connection_id)
    with _cache_lock:
        if key[0] == "default" and key[1] == "default":
            _profile_cache.clear()
        else:
            _profile_cache.pop(key, None)
