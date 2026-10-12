"""
backend/app/database/connection_context.py

Phase 7 & BG AI 2.0: Per-user database context registry and multi-connection bridge.

Replaces the global engine pattern with user-scoped DatabaseContext objects and
integrates with the centralized ConnectionRegistry.
Uses Python contextvars.ContextVar so existing get_engine() / get_current_db_type()
calls transparently return the correct engine for the current request without
requiring changes to existing call sites.
"""
from __future__ import annotations

import threading
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import create_engine, URL, text
from sqlalchemy.engine import Engine

# ── ContextVars (per-request isolation) ───────────────────────────────────────
_request_engine: ContextVar[Optional[Engine]] = ContextVar("_request_engine", default=None)
_request_db_type: ContextVar[str] = ContextVar("_request_db_type", default="none")
_request_user_id: ContextVar[Optional[str]] = ContextVar("_request_user_id", default=None)
_request_context_id: ContextVar[Optional[str]] = ContextVar("_request_context_id", default=None)
_request_connection_id: ContextVar[Optional[str]] = ContextVar("_request_connection_id", default=None)


# ── Per-user context dataclass (Phase 7 backward-compatibility) ───────────────
@dataclass
class DatabaseContext:
    """Holds the per-user engine + metadata. Never stores raw password."""
    context_id: str
    user_id: str
    database_type: str                  # sqlite | mysql | postgres | none
    database_identity: str              # sanitized URL (no password)
    engine: Optional[Engine]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_used_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def touch(self):
        self.last_used_at = datetime.now(timezone.utc).isoformat()

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
    """Return the user's active DatabaseContext, creating an empty one if absent."""
    with _registry_lock:
        if user_id not in _registry:
            _registry[user_id] = _make_empty_context(user_id)
        return _registry[user_id]


def set_user_engine(
    user_id: str,
    engine: Engine,
    database_type: str,
    database_identity: str,
    connection_id: Optional[str] = None,
) -> DatabaseContext:
    """
    Register/replace the user's active engine.
    """
    with _registry_lock:
        cid = connection_id or str(uuid.uuid4())
        ctx = DatabaseContext(
            context_id=cid,
            user_id=user_id,
            database_type=database_type,
            database_identity=database_identity,
            engine=engine,
        )
        _registry[user_id] = ctx
        return ctx


def clear_user_context(user_id: str, connection_id: Optional[str] = None) -> None:
    """
    Disconnect a specific connection or all user connections.
    """
    try:
        from app.connectors.registry import get_connection_registry
        reg = get_connection_registry()
        if connection_id:
            reg.disconnect_connector(user_id, connection_id)
            reg.remove_connector(user_id, connection_id)
            # If removing active, update _registry with newly active or empty
            active = reg.get_active_connector(user_id)
            with _registry_lock:
                if active and hasattr(active, "engine") and active.engine is not None:
                    _registry[user_id] = DatabaseContext(
                        context_id=active.connection_id,
                        user_id=user_id,
                        database_type=active.connector_type,
                        database_identity=active.name,
                        engine=active.engine,
                    )
                else:
                    _registry.pop(user_id, None)
            return
        else:
            reg.disconnect_all(user_id)
    except Exception:
        pass

    with _registry_lock:
        ctx = _registry.pop(user_id, None)
        if ctx and ctx.engine is not None:
            try:
                ctx.engine.dispose()
            except Exception:
                pass


# ── Request-scoped context activation ────────────────────────────────────────
def set_user_context_for_request(
    user_id: str, connection_id: Optional[str] = None
) -> DatabaseContext:
    """
    Called at the top of every authenticated endpoint handler.
    Activates the user's selected/active engine in the current async task's ContextVar,
    so downstream get_engine() / get_current_db_type() calls return
    the correct isolated engine without needing modification.
    """
    engine: Optional[Engine] = None
    db_type = "none"
    ctx_id = None

    # Check Multi-Connection Registry first
    try:
        from app.connectors.registry import get_connection_registry
        from app.connectors.relational import RelationalConnector
        reg = get_connection_registry()
        connector = None
        if connection_id:
            reg.set_active_connector(user_id, connection_id)
            connector = reg.get_connector(user_id, connection_id)
        if not connector:
            connector = reg.get_active_connector(user_id)

        if connector:
            ctx_id = connector.connection_id
            db_type = connector.connector_type
            if isinstance(connector, RelationalConnector):
                engine = connector.engine

            _request_connection_id.set(connector.connection_id)
    except Exception:
        pass

    # If registry didn't have an engine, fall back to legacy user context
    if engine is None and db_type == "none":
        ctx = get_user_context(user_id)
        ctx.touch()
        engine = ctx.engine
        db_type = ctx.database_type
        ctx_id = ctx.context_id
        _request_connection_id.set(ctx.context_id)
    else:
        ctx = DatabaseContext(
            context_id=ctx_id or str(uuid.uuid4()),
            user_id=user_id,
            database_type=db_type,
            database_identity=db_type,
            engine=engine,
        )
        with _registry_lock:
            _registry[user_id] = ctx

    _request_engine.set(engine)
    _request_db_type.set(db_type)
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


def get_request_connection_id() -> Optional[str]:
    return _request_connection_id.get()


# ── Connect helpers (Bridge to Multi-Connection Registry) ─────────────────────
def connect_sqlite_for_user(
    user_id: str, path: str, name: Optional[str] = None
) -> DatabaseContext:
    from app.connectors.registry import get_connection_registry
    from app.connectors.relational import SQLiteConnector
    reg = get_connection_registry()

    conn_id = f"conn_sqlite_{uuid.uuid4().hex[:8]}"
    disp_name = name or (f"SQLite: {Path(path).name}" if path != ":memory:" else "In-Memory SQLite")
    connector = SQLiteConnector(
        connection_id=conn_id,
        name=disp_name,
        database_path=path,
        user_id=user_id,
    )
    if not connector.connect():
        raise RuntimeError(connector.last_error or "Failed to connect to SQLite")

    reg.register_connector(connector)
    reg.set_active_connector(user_id, conn_id)

    identity = f"sqlite:///{path}"
    return set_user_engine(user_id, connector.engine, "sqlite", identity, connection_id=conn_id)


def connect_mysql_for_user(
    user_id: str,
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
    name: Optional[str] = None,
) -> DatabaseContext:
    from app.connectors.registry import get_connection_registry
    from app.connectors.relational import MySQLConnector
    reg = get_connection_registry()

    conn_id = f"conn_mysql_{uuid.uuid4().hex[:8]}"
    disp_name = name or f"MySQL: {database} ({host})"
    connector = MySQLConnector(
        connection_id=conn_id,
        name=disp_name,
        host=host,
        port=port,
        database=database,
        username=username,
        password=password,
        user_id=user_id,
    )
    if not connector.connect():
        raise RuntimeError(connector.last_error or "Failed to connect to MySQL")

    reg.register_connector(connector)
    reg.set_active_connector(user_id, conn_id)

    identity = f"mysql://{username}@{host}:{port}/{database}"
    return set_user_engine(user_id, connector.engine, "mysql", identity, connection_id=conn_id)


def connect_postgres_for_user(
    user_id: str,
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
    name: Optional[str] = None,
) -> DatabaseContext:
    from app.connectors.registry import get_connection_registry
    from app.connectors.relational import PostgreSQLConnector
    reg = get_connection_registry()

    conn_id = f"conn_pg_{uuid.uuid4().hex[:8]}"
    disp_name = name or f"PostgreSQL: {database} ({host})"
    connector = PostgreSQLConnector(
        connection_id=conn_id,
        name=disp_name,
        host=host,
        port=port,
        database=database,
        username=username,
        password=password,
        user_id=user_id,
    )
    if not connector.connect():
        raise RuntimeError(connector.last_error or "Failed to connect to PostgreSQL")

    reg.register_connector(connector)
    reg.set_active_connector(user_id, conn_id)

    identity = f"postgresql://{username}@{host}:{port}/{database}"
    return set_user_engine(user_id, connector.engine, "postgres", identity, connection_id=conn_id)
