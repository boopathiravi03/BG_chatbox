"""
backend/app/database/connection_context.py

Phase 7: Per-user database context registry.

Replaces the global engine pattern with user-scoped DatabaseContext objects.
Uses Python contextvars.ContextVar so existing get_engine() / get_current_db_type()
calls transparently return the correct engine for the current request without
requiring changes to every call site.

Architecture:
  _context_registry: dict[user_id → DatabaseContext]
  _request_engine:   ContextVar  ← set per-request by set_user_context()
  _request_db_type:  ContextVar  ← set per-request by set_user_context()

Every FastAPI endpoint calls set_user_context(user_id) after authentication.
All downstream code (scanner, CRUD, agents) calls get_engine() / get_current_db_type()
which reads from the ContextVar — isolated per async task/thread.
"""
from __future__ import annotations

import threading
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine, URL, text
from sqlalchemy.engine import Engine

# ── ContextVars (per-request isolation) ───────────────────────────────────────
# These replace the global `engine` and `current_db_type` module variables.
_request_engine: ContextVar[Optional[Engine]] = ContextVar("_request_engine", default=None)
_request_db_type: ContextVar[str] = ContextVar("_request_db_type", default="none")
_request_user_id: ContextVar[Optional[str]] = ContextVar("_request_user_id", default=None)
_request_context_id: ContextVar[Optional[str]] = ContextVar("_request_context_id", default=None)


# ── Per-user context dataclass ────────────────────────────────────────────────
@dataclass
class DatabaseContext:
    """Holds the per-user engine + metadata. Never stores raw password."""
    context_id: str
    user_id: str
    database_type: str                  # sqlite | mysql | postgres | none
    database_identity: str              # sanitized URL (no password)
    engine: Optional[Engine]
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_used_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def touch(self):
        self.last_used_at = datetime.utcnow().isoformat()

    def to_info(self) -> dict:
        """Serializable info — NEVER includes password."""
        return {
            "context_id": self.context_id,
            "user_id": self.user_id,
            "database_type": self.database_type,
            "database_identity": self.database_identity,
            "connected": self.engine is not None,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
        }


# ── Registry ──────────────────────────────────────────────────────────────────
_registry: dict[str, DatabaseContext] = {}   # user_id → DatabaseContext
_registry_lock = threading.Lock()


def _make_empty_context(user_id: str) -> DatabaseContext:
    return DatabaseContext(
        context_id=str(uuid.uuid4()),
        user_id=user_id,
        database_type="none",
        database_identity="none",
        engine=None,
    )


def get_user_context(user_id: str) -> DatabaseContext:
    """Return the user's DatabaseContext, creating an empty one if absent."""
    with _registry_lock:
        if user_id not in _registry:
            _registry[user_id] = _make_empty_context(user_id)
        return _registry[user_id]


def set_user_engine(
    user_id: str,
    engine: Engine,
    database_type: str,
    database_identity: str,
) -> DatabaseContext:
    """
    Register/replace the user's engine.
    Called during connect/upload. Disposes the old engine safely.
    """
    with _registry_lock:
        old = _registry.get(user_id)
        if old and old.engine is not None:
            try:
                old.engine.dispose()
            except Exception:
                pass

        ctx = DatabaseContext(
            context_id=str(uuid.uuid4()),
            user_id=user_id,
            database_type=database_type,
            database_identity=database_identity,
            engine=engine,
        )
        _registry[user_id] = ctx
        return ctx


def clear_user_context(user_id: str) -> None:
    """
    Disconnect and remove a user's context. Called on /disconnect.
    Does NOT affect any other user's context.
    """
    with _registry_lock:
        ctx = _registry.pop(user_id, None)
        if ctx and ctx.engine is not None:
            try:
                ctx.engine.dispose()
            except Exception:
                pass


# ── Request-scoped context activation ────────────────────────────────────────
def set_user_context_for_request(user_id: str) -> DatabaseContext:
    """
    Called at the top of every authenticated endpoint handler.
    Activates the user's engine in the current async task's ContextVar,
    so downstream get_engine() / get_current_db_type() calls return
    the correct isolated engine without needing modification.

    Returns the user's DatabaseContext.
    """
    ctx = get_user_context(user_id)
    ctx.touch()

    _request_engine.set(ctx.engine)
    _request_db_type.set(ctx.database_type)
    _request_user_id.set(user_id)
    _request_context_id.set(ctx.context_id)

    return ctx


def get_request_engine() -> Optional[Engine]:
    """Get the engine bound to the current request's ContextVar."""
    return _request_engine.get()


def get_request_db_type() -> str:
    """Get the db_type bound to the current request's ContextVar."""
    return _request_db_type.get()


def get_request_user_id() -> Optional[str]:
    return _request_user_id.get()


def get_request_context_id() -> Optional[str]:
    return _request_context_id.get()


# ── Connect helpers ───────────────────────────────────────────────────────────
def connect_sqlite_for_user(user_id: str, path: str) -> DatabaseContext:
    engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    identity = f"sqlite:///{path}"
    return set_user_engine(user_id, engine, "sqlite", identity)


def connect_mysql_for_user(
    user_id: str, host: str, port: int, database: str, username: str, password: str
) -> DatabaseContext:
    mysql_url = URL.create(
        drivername="mysql+pymysql",
        username=username,
        password=password,
        host=host,
        port=int(port),
        database=database,
    )
    engine = create_engine(mysql_url, pool_pre_ping=True, pool_recycle=1800)
    with engine.connect() as conn:
        conn.exec_driver_sql("SELECT 1")

    identity = f"mysql://{username}@{host}:{port}/{database}"  # no password
    return set_user_engine(user_id, engine, "mysql", identity)


def connect_postgres_for_user(
    user_id: str, host: str, port: int, database: str, username: str, password: str
) -> DatabaseContext:
    pg_url = URL.create(
        drivername="postgresql+psycopg2",
        username=username,
        password=password,
        host=host,
        port=int(port),
        database=database,
    )
    engine = create_engine(pg_url, pool_pre_ping=True, pool_recycle=1800)
    with engine.connect() as conn:
        conn.exec_driver_sql("SELECT 1")

    identity = f"postgresql://{username}@{host}:{port}/{database}"  # no password
    return set_user_engine(user_id, engine, "postgres", identity)
