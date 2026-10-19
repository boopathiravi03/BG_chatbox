"""
backend/app/agents/audit_db.py

Phase 7: SQLite-backed persistent audit store for agent actions.
Replaces the ephemeral in-memory + audit_log.json approach.

Design:
  - AuditEvent table in bgai_audit.db (separate from user databases)
  - Records are user-scoped (user_id + context_id)
  - Never stores passwords, API keys, or tokens
  - Retention: records are kept indefinitely (deletion requires explicit admin action)
  - Indexing: indexed by user_id, created_at, action_id for fast per-user queries

Retention recommendation:
  Production deployments should archive or delete audit records older than 90 days
  using a scheduled job. This module intentionally does NOT auto-delete records.
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import (
    Column, String, Integer, DateTime, Text, Boolean,
    create_engine, Index, text as sa_text
)
from sqlalchemy.orm import declarative_base, sessionmaker

from app.paths import get_app_data_file

# ── Audit database ─────────────────────────────────────────────────────────────
_AUDIT_DB_PATH = get_app_data_file("bgai_audit.db")

_audit_engine = create_engine(
    f"sqlite:///{_AUDIT_DB_PATH}",
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)

Base = declarative_base()
_lock = threading.Lock()

# Default action expiry: 24 hours after creation
ACTION_EXPIRY_HOURS = 24


class AuditEvent(Base):
    """
    Persistent audit record for every proposed/executed agent action.
    Never stores passwords, tokens, or API keys.
    """
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action_id = Column(String(36), nullable=False, index=True)
    task_id = Column(String(36), nullable=True)
    user_id = Column(String(36), nullable=False, index=True)
    context_id = Column(String(36), nullable=True)
    agent = Column(String(80), nullable=True)
    action_type = Column(String(20), nullable=True)     # UPDATE | DELETE
    table_name = Column(String(200), nullable=True)
    exact_sql = Column(Text, nullable=True)             # stored for audit trail
    verification_sql = Column(Text, nullable=True)
    expected_verification_result = Column(String(50), nullable=True)
    estimated_rows = Column(Integer, nullable=True)
    actual_rows_affected = Column(Integer, nullable=True)
    risk_level = Column(String(10), nullable=True)
    status = Column(String(30), nullable=False, default="AWAITING_CONFIRMATION", index=True)
    verification_status = Column(Boolean, nullable=True)
    database_identity = Column(String(500), nullable=True)  # sanitized — no password
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    expires_at = Column(DateTime, nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    sanitized_details = Column(Text, nullable=True)     # JSON blob, no secrets


# Composite indexes for performance
Index("ix_audit_user_created", AuditEvent.user_id, AuditEvent.created_at)
Index("ix_audit_user_status", AuditEvent.user_id, AuditEvent.status)

Base.metadata.create_all(_audit_engine)
AuditSession = sessionmaker(bind=_audit_engine, autoflush=False, autocommit=False)


# ── ActionPlan compatibility layer ─────────────────────────────────────────────
# We keep the in-memory ActionPlan for the execution pipeline but persist to DB.

from app.agents.models import ActionPlan


def _action_plan_to_event(action: ActionPlan, user_id: str, context_id: str) -> AuditEvent:
    expires = datetime.utcnow() + timedelta(hours=ACTION_EXPIRY_HOURS)
    return AuditEvent(
        id=str(uuid.uuid4()),
        action_id=action.action_id,
        task_id=action.task_id,
        user_id=user_id,
        context_id=context_id,
        agent=action.agent_name,
        action_type=action.action_type,
        table_name=action.table,
        exact_sql=action.exact_sql,
        verification_sql=action.verification_sql,
        expected_verification_result=action.expected_verification_result,
        estimated_rows=action.estimated_rows,
        risk_level=action.risk_level,
        status=action.status,
        database_identity=action.database_identity,
        created_at=datetime.utcnow(),
        expires_at=expires,
    )


def _update_event_from_plan(session, action: ActionPlan) -> None:
    """Update the AuditEvent record from the latest ActionPlan state."""
    ev = session.query(AuditEvent).filter(AuditEvent.action_id == action.action_id).first()
    if not ev:
        return
    ev.status = action.status
    ev.actual_rows_affected = action.actual_rows_affected
    ev.error_message = action.error
    if action.status in {"VERIFIED", "EXECUTED", "FAILED", "VERIFICATION_FAILED"}:
        ev.executed_at = datetime.utcnow()
    session.commit()


# ── Public API ─────────────────────────────────────────────────────────────────

def store_action_persistent(action: ActionPlan, user_id: str, context_id: str) -> None:
    """Persist an ActionPlan as an AuditEvent. Called after store_action()."""
    db = AuditSession()
    try:
        ev = _action_plan_to_event(action, user_id, context_id)
        db.add(ev)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def update_action_persistent(action: ActionPlan) -> None:
    """Update the AuditEvent after execution. Called after confirm_and_execute_action()."""
    db = AuditSession()
    try:
        _update_event_from_plan(db, action)
    except Exception:
        db.rollback()
    finally:
        db.close()


def list_audit_events(user_id: str, limit: int = 100) -> list[dict]:
    """List all audit events for a user, newest first."""
    db = AuditSession()
    try:
        events = (
            db.query(AuditEvent)
            .filter(AuditEvent.user_id == user_id)
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
            .all()
        )
        return [_event_to_dict(ev) for ev in events]
    finally:
        db.close()


def get_audit_event(action_id: str, user_id: str) -> Optional[dict]:
    """Get a specific audit event, enforcing user ownership."""
    db = AuditSession()
    try:
        ev = (
            db.query(AuditEvent)
            .filter(AuditEvent.action_id == action_id, AuditEvent.user_id == user_id)
            .first()
        )
        return _event_to_dict(ev) if ev else None
    finally:
        db.close()


def is_action_expired(action_id: str) -> bool:
    """Check if an action has passed its expiry time."""
    db = AuditSession()
    try:
        ev = db.query(AuditEvent).filter(AuditEvent.action_id == action_id).first()
        if not ev or not ev.expires_at:
            return False
        return datetime.utcnow() > ev.expires_at
    finally:
        db.close()


def _event_to_dict(ev: AuditEvent) -> dict:
    return {
        "id": ev.id,
        "action_id": ev.action_id,
        "task_id": ev.task_id,
        "user_id": ev.user_id,
        "context_id": ev.context_id,
        "agent": ev.agent,
        "action_type": ev.action_type,
        "table_name": ev.table_name,
        "exact_sql": ev.exact_sql,
        "estimated_rows": ev.estimated_rows,
        "actual_rows_affected": ev.actual_rows_affected,
        "risk_level": ev.risk_level,
        "status": ev.status,
        "database_identity": ev.database_identity,
        "error_message": ev.error_message,
        "created_at": ev.created_at.isoformat() if ev.created_at else None,
        "expires_at": ev.expires_at.isoformat() if ev.expires_at else None,
        "confirmed_at": ev.confirmed_at.isoformat() if ev.confirmed_at else None,
        "executed_at": ev.executed_at.isoformat() if ev.executed_at else None,
    }
