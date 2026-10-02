"""
backend/app/intelligence/learning/outcome_store.py

Phase 8.5: Persistent, User-Scoped Outcome & Feedback Storage
Provides thread-safe persistence for recorded decision/action outcomes and explicit
user feedback. Uses a dedicated SQLite application store (bgai_learning.db),
strictly isolated from user database connections.

Strict User Isolation:
All queries strictly enforce user_id filtering. User A cannot access or overwrite
User B's historical outcomes or feedback signals.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import (
    Column, String, Integer, Boolean, Text, DateTime, Index,
    create_engine, desc
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.intelligence.learning.models import (
    OutcomeRecord,
    FeedbackRecord,
    OutcomeStatus,
    FeedbackTargetType,
)

Base = declarative_base()
_store_lock = threading.Lock()

_DEFAULT_DB_PATH = Path(__file__).resolve().parents[4] / "bgai_learning.db"

_engine = None
_SessionFactory = None


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
                db_url = os.getenv(
                    "BGAI_LEARNING_DB_URL",
                    f"sqlite:///{_DEFAULT_DB_PATH}"
                )
                _engine = create_engine(
                    db_url,
                    connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
                    echo=False,
                )
                Base.metadata.create_all(_engine)
                _SessionFactory = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def _get_session() -> Session:
    _get_engine()
    return _SessionFactory()


# ── ORM Models ───────────────────────────────────────────────────────────────

class OutcomeModel(Base):
    __tablename__ = "learning_outcomes"

    outcome_id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    decision_id = Column(String(64), nullable=True)
    question = Column(Text, nullable=True)
    action_id = Column(String(64), nullable=True)
    plan_step = Column(Integer, nullable=True)
    action_type = Column(String(64), nullable=False, default="GENERAL")
    expected_outcome = Column(Text, nullable=False, default="")
    actual_outcome = Column(Text, nullable=False, default="")
    status = Column(String(32), nullable=False, default=OutcomeStatus.UNKNOWN)
    evidence_json = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(String(64), nullable=False)

    __table_args__ = (
        Index("idx_outcomes_user_status", "user_id", "status"),
        Index("idx_outcomes_user_type", "user_id", "action_type"),
    )


class FeedbackModel(Base):
    __tablename__ = "learning_feedbacks"

    feedback_id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    target_type = Column(String(32), nullable=False, default=FeedbackTargetType.DECISION)
    target_id = Column(String(64), nullable=True)
    question = Column(Text, nullable=True)
    useful = Column(Boolean, nullable=True)
    accepted = Column(Boolean, nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(String(64), nullable=False)

    __table_args__ = (
        Index("idx_feedback_user_target", "user_id", "target_type"),
    )


# ── Conversion Helpers ───────────────────────────────────────────────────────

def _row_to_outcome(row: OutcomeModel) -> OutcomeRecord:
    ev = None
    if row.evidence_json:
        try:
            ev = json.loads(row.evidence_json)
        except Exception:
            ev = row.evidence_json

    return OutcomeRecord(
        outcome_id=row.outcome_id,
        user_id=row.user_id,
        decision_id=row.decision_id,
        question=row.question,
        action_id=row.action_id,
        plan_step=row.plan_step,
        action_type=row.action_type,
        expected_outcome=row.expected_outcome,
        actual_outcome=row.actual_outcome,
        status=row.status,
        evidence=ev,
        notes=row.notes,
        created_at=row.created_at,
    )


def _row_to_feedback(row: FeedbackModel) -> FeedbackRecord:
    return FeedbackRecord(
        feedback_id=row.feedback_id,
        user_id=row.user_id,
        target_type=row.target_type,
        target_id=row.target_id,
        question=row.question,
        useful=row.useful,
        accepted=row.accepted,
        comment=row.comment,
        created_at=row.created_at,
    )


# ── Public API ───────────────────────────────────────────────────────────────

def save_outcome(outcome: OutcomeRecord) -> OutcomeRecord:
    """
    Persists a new or updated outcome record for the given user.
    """
    ev_str = None
    if outcome.evidence is not None:
        try:
            ev_str = json.dumps(outcome.evidence)
        except Exception:
            ev_str = str(outcome.evidence)

    session = _get_session()
    try:
        existing = session.query(OutcomeModel).filter_by(
            outcome_id=outcome.outcome_id,
            user_id=outcome.user_id,
        ).first()

        if existing:
            existing.decision_id = outcome.decision_id
            existing.question = outcome.question
            existing.action_id = outcome.action_id
            existing.plan_step = outcome.plan_step
            existing.action_type = outcome.action_type
            existing.expected_outcome = outcome.expected_outcome
            existing.actual_outcome = outcome.actual_outcome
            existing.status = outcome.status
            existing.evidence_json = ev_str
            existing.notes = outcome.notes
        else:
            model = OutcomeModel(
                outcome_id=outcome.outcome_id,
                user_id=outcome.user_id,
                decision_id=outcome.decision_id,
                question=outcome.question,
                action_id=outcome.action_id,
                plan_step=outcome.plan_step,
                action_type=outcome.action_type,
                expected_outcome=outcome.expected_outcome,
                actual_outcome=outcome.actual_outcome,
                status=outcome.status,
                evidence_json=ev_str,
                notes=outcome.notes,
                created_at=outcome.created_at,
            )
            session.add(model)
        session.commit()
        return outcome
    finally:
        session.close()


def get_outcome(outcome_id: str, user_id: str) -> Optional[OutcomeRecord]:
    """
    Retrieves a single outcome record by ID with strict user isolation.
    """
    session = _get_session()
    try:
        row = session.query(OutcomeModel).filter_by(
            outcome_id=outcome_id,
            user_id=user_id,
        ).first()
        return _row_to_outcome(row) if row else None
    finally:
        session.close()


def list_outcomes(
    user_id: str,
    limit: int = 50,
    action_type: Optional[str] = None,
    status: Optional[str] = None,
) -> list[OutcomeRecord]:
    """
    Lists outcomes for a user ordered by creation time descending.
    """
    session = _get_session()
    try:
        q = session.query(OutcomeModel).filter_by(user_id=user_id)
        if action_type:
            q = q.filter_by(action_type=action_type)
        if status:
            q = q.filter_by(status=status.upper())
        rows = q.order_by(desc(OutcomeModel.created_at)).limit(max(1, min(limit, 500))).all()
        return [_row_to_outcome(r) for r in rows]
    finally:
        session.close()


def save_feedback(feedback: FeedbackRecord) -> FeedbackRecord:
    """
    Persists explicit user feedback for the given user.
    """
    session = _get_session()
    try:
        existing = session.query(FeedbackModel).filter_by(
            feedback_id=feedback.feedback_id,
            user_id=feedback.user_id,
        ).first()

        if existing:
            existing.target_type = feedback.target_type
            existing.target_id = feedback.target_id
            existing.question = feedback.question
            existing.useful = feedback.useful
            existing.accepted = feedback.accepted
            existing.comment = feedback.comment
        else:
            model = FeedbackModel(
                feedback_id=feedback.feedback_id,
                user_id=feedback.user_id,
                target_type=feedback.target_type,
                target_id=feedback.target_id,
                question=feedback.question,
                useful=feedback.useful,
                accepted=feedback.accepted,
                comment=feedback.comment,
                created_at=feedback.created_at,
            )
            session.add(model)
        session.commit()
        return feedback
    finally:
        session.close()


def list_feedbacks(
    user_id: str,
    limit: int = 50,
    target_type: Optional[str] = None,
) -> list[FeedbackRecord]:
    """
    Lists user feedback ordered by creation time descending.
    """
    session = _get_session()
    try:
        q = session.query(FeedbackModel).filter_by(user_id=user_id)
        if target_type:
            q = q.filter_by(target_type=target_type.upper())
        rows = q.order_by(desc(FeedbackModel.created_at)).limit(max(1, min(limit, 500))).all()
        return [_row_to_feedback(r) for r in rows]
    finally:
        session.close()


def clear_learning_store(user_id: Optional[str] = None) -> None:
    """
    Clears records for a user, or all records if user_id is None (testing only).
    """
    session = _get_session()
    try:
        if user_id:
            session.query(OutcomeModel).filter_by(user_id=user_id).delete()
            session.query(FeedbackModel).filter_by(user_id=user_id).delete()
        else:
            session.query(OutcomeModel).delete()
            session.query(FeedbackModel).delete()
        session.commit()
    finally:
        session.close()


def reset_engine() -> None:
    """
    Resets the internal engine state (useful for isolated tests).
    """
    global _engine, _SessionFactory
    with _store_lock:
        _engine = None
        _SessionFactory = None
