"""
backend/app/intelligence/actions/action_audit.py

Phase 8.8: Persistent Action Storage & Immutable Audit Trail
Thread-safe, user-isolated storage for ActionProposals and ActionAuditRecords.
Maintains state in local SQLite storage (bgai_actions.db), isolated from connected user databases.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import (
    Column, String, Integer, DateTime, Text, Index,
    create_engine, desc
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.intelligence.actions.models import (
    ActionProposal,
    ActionAuditRecord,
    ActionStatus,
)

Base = declarative_base()
_store_lock = threading.Lock()

_DEFAULT_DB_PATH = Path(__file__).resolve().parents[4] / "bgai_actions.db"
_engine = None
_SessionFactory = None


class ActionEntity(Base):
    __tablename__ = "action_proposals"

    action_id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    action_type = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False, index=True)
    table_name = Column(String(128), nullable=False)
    reason = Column(Text, nullable=True)
    risk = Column(String(16), nullable=False)
    proposal_json = Column(Text, nullable=False)
    created_at = Column(String(64), nullable=False)
    updated_at = Column(String(64), nullable=False)
    database_identity = Column(String(256), nullable=False)

    __table_args__ = (
        Index("idx_act_user_status", "user_id", "status"),
        Index("idx_act_created", "created_at"),
    )


class AuditEntity(Base):
    __tablename__ = "action_audit_log"

    audit_id = Column(String(64), primary_key=True)
    action_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    timestamp = Column(String(64), nullable=False)
    action_type = Column(String(32), nullable=False)
    target_table = Column(String(128), nullable=False)
    risk = Column(String(16), nullable=False)
    affected_rows = Column(Integer, default=0)
    execution_status = Column(String(32), nullable=False)
    verification_status = Column(String(32), nullable=False)
    audit_json = Column(Text, nullable=False)

    __table_args__ = (
        Index("idx_audit_user_time", "user_id", "timestamp"),
    )


def _get_engine(custom_engine=None):
    global _engine, _SessionFactory
    if custom_engine is not None:
        _engine = custom_engine
        Base.metadata.create_all(_engine)
        _SessionFactory = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
        return _engine

    if _engine is None:
        with _store_lock:
            if _engine is None:
                db_url = os.getenv("BGAI_ACTIONS_DB_URL", f"sqlite:///{_DEFAULT_DB_PATH}")
                _engine = create_engine(
                    db_url,
                    connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
                )
                Base.metadata.create_all(_engine)
                _SessionFactory = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def _get_session() -> Session:
    _get_engine()
    return _SessionFactory()


def save_action(proposal: ActionProposal) -> None:
    """Save or update an action proposal strictly bound to user_id."""
    session = _get_session()
    now_str = datetime.now(timezone.utc).isoformat()
    try:
        with _store_lock:
            existing = session.query(ActionEntity).filter(
                ActionEntity.action_id == proposal.action_id,
                ActionEntity.user_id == proposal.user_id,
            ).first()

            if not proposal.created_at:
                proposal.created_at = now_str
            proposal.updated_at = now_str

            data_str = json.dumps(proposal.to_dict(), default=str)

            if existing:
                existing.status = proposal.status
                existing.action_type = proposal.action_type
                existing.table_name = proposal.target.table if proposal.target else ""
                existing.reason = proposal.reason
                existing.risk = proposal.risk
                existing.proposal_json = data_str
                existing.updated_at = now_str
                existing.database_identity = proposal.database_identity
            else:
                entity = ActionEntity(
                    action_id=proposal.action_id,
                    user_id=proposal.user_id,
                    action_type=proposal.action_type,
                    status=proposal.status,
                    table_name=proposal.target.table if proposal.target else "",
                    reason=proposal.reason,
                    risk=proposal.risk,
                    proposal_json=data_str,
                    created_at=proposal.created_at,
                    updated_at=now_str,
                    database_identity=proposal.database_identity,
                )
                session.add(entity)

            session.commit()
    finally:
        session.close()


def get_action(action_id: str, user_id: str) -> Optional[ActionProposal]:
    """Retrieve an action proposal verifying authenticated user ownership."""
    session = _get_session()
    try:
        entity = session.query(ActionEntity).filter(
            ActionEntity.action_id == action_id,
            ActionEntity.user_id == user_id,
        ).first()

        if not entity:
            return None

        d = json.loads(entity.proposal_json)
        return ActionProposal.from_dict(d)
    finally:
        session.close()


def list_actions(user_id: str, status: Optional[str] = None, limit: int = 50) -> list[ActionProposal]:
    """List action proposals for the requesting user."""
    session = _get_session()
    try:
        q = session.query(ActionEntity).filter(ActionEntity.user_id == user_id)
        if status:
            q = q.filter(ActionEntity.status == status)
        entities = q.order_by(desc(ActionEntity.created_at)).limit(max(1, limit)).all()

        results = []
        for e in entities:
            try:
                results.append(ActionProposal.from_dict(json.loads(e.proposal_json)))
            except Exception:
                pass
        return results
    finally:
        session.close()


def record_audit(audit: ActionAuditRecord) -> None:
    """Store an immutable audit entry."""
    session = _get_session()
    now_str = datetime.now(timezone.utc).isoformat()
    try:
        with _store_lock:
            if not audit.timestamp:
                audit.timestamp = now_str

            entity = AuditEntity(
                audit_id=audit.audit_id,
                action_id=audit.action_id,
                user_id=audit.user_id,
                timestamp=audit.timestamp,
                action_type=audit.action_type,
                target_table=audit.target_table,
                risk=audit.risk,
                affected_rows=audit.affected_rows,
                execution_status=audit.execution_status,
                verification_status=audit.verification_status,
                audit_json=json.dumps(audit.to_dict(), default=str),
            )
            session.add(entity)
            session.commit()
    finally:
        session.close()


def list_audits(user_id: str, limit: int = 50) -> list[ActionAuditRecord]:
    """Retrieve audit history for the authenticated user."""
    session = _get_session()
    try:
        entities = session.query(AuditEntity).filter(
            AuditEntity.user_id == user_id
        ).order_by(desc(AuditEntity.timestamp)).limit(max(1, limit)).all()

        results = []
        for e in entities:
            try:
                results.append(ActionAuditRecord.from_dict(json.loads(e.audit_json)))
            except Exception:
                pass
        return results
    finally:
        session.close()


def clear_actions_store() -> None:
    """Testing utility: Clear action store tables."""
    session = _get_session()
    try:
        with _store_lock:
            session.query(ActionEntity).delete()
            session.query(AuditEntity).delete()
            session.commit()
    finally:
        session.close()
