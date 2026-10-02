"""
backend/app/intelligence/proactive/alert_store.py

Phase 8.3: Persistent, User-Scoped Alert Storage
Provides thread-safe storage, retrieval, deduplication, and status tracking for proactive alerts.
Keeps alert state in BG AI application storage (bgai_proactive.db), completely isolated
from connected user databases.

Strictly enforces user isolation: User A cannot read or mutate User B's alerts.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import (
    Column, String, Float, DateTime, Text, Index,
    create_engine, desc
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.intelligence.proactive.models import (
    BusinessAlert,
    AlertStatus,
    AlertSeverity,
    AlertCategory,
)

Base = declarative_base()
_store_lock = threading.Lock()

# Default SQLite application DB for proactive alerts (separated from user databases)
_DEFAULT_DB_PATH = Path(__file__).resolve().parents[4] / "bgai_proactive.db"

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
                    "BGAI_PROACTIVE_DB_URL",
                    f"sqlite:///{_DEFAULT_DB_PATH}"
                )
                _engine = create_engine(
                    db_url,
                    connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
                    pool_pre_ping=True,
                )
                Base.metadata.create_all(_engine)
                _SessionFactory = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def set_alert_store_engine(custom_engine) -> None:
    """Configures a custom SQLAlchemy engine (useful for in-memory test suites)."""
    _get_engine(custom_engine)


def _get_session() -> Session:
    _get_engine()
    return _SessionFactory()


class AlertRecord(Base):
    """SQLAlchemy persistent entity for proactive business alerts."""
    __tablename__ = "proactive_alerts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    alert_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    category = Column(String(40), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    status = Column(String(20), nullable=False, default=AlertStatus.NEW, index=True)
    metric = Column(String(200), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    previous_value = Column(Float, nullable=True)
    current_value = Column(Float, nullable=True)
    delta = Column(Float, nullable=True)
    delta_percent = Column(Float, nullable=True)
    threshold_applied = Column(String(200), nullable=True)
    source_tables_json = Column(Text, nullable=False, default="[]")
    source_columns_json = Column(Text, nullable=False, default="[]")
    lineage_steps_json = Column(Text, nullable=False, default="[]")
    sql = Column(Text, nullable=True)
    evidence_json = Column(Text, nullable=False, default="{}")
    explanation = Column(Text, nullable=False, default="")
    recommendation = Column(Text, nullable=False, default="")
    action_suggestion_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


Index("ix_proactive_user_created", AlertRecord.user_id, AlertRecord.created_at)
Index("ix_proactive_user_status", AlertRecord.user_id, AlertRecord.status)
Index("ix_proactive_user_metric_status", AlertRecord.user_id, AlertRecord.metric, AlertRecord.status)


def _resolve_user_id(user_id: Optional[str]) -> str:
    """Resolves and validates the target user_id, ensuring user isolation."""
    if user_id and str(user_id).strip():
        return str(user_id).strip()

    try:
        from app.database.connection_context import get_request_user_id
        ctx_user = get_request_user_id()
        if ctx_user and str(ctx_user).strip():
            return str(ctx_user).strip()
    except Exception:
        pass

    raise ValueError("User ID must be provided or established in request context.")


def _entity_to_model(rec: AlertRecord) -> BusinessAlert:
    """Converts a database entity back into a typed BusinessAlert domain model."""
    return BusinessAlert(
        alert_id=rec.alert_id,
        user_id=rec.user_id,
        timestamp=rec.timestamp.isoformat() if isinstance(rec.timestamp, datetime) else str(rec.timestamp),
        category=rec.category,
        severity=rec.severity,
        title=rec.title,
        metric=rec.metric,
        previous_value=rec.previous_value,
        current_value=rec.current_value,
        delta=rec.delta,
        delta_percent=rec.delta_percent,
        threshold_applied=rec.threshold_applied,
        source_tables=json.loads(rec.source_tables_json or "[]"),
        source_columns=json.loads(rec.source_columns_json or "[]"),
        lineage_steps=json.loads(rec.lineage_steps_json or "[]"),
        sql=rec.sql,
        evidence=json.loads(rec.evidence_json or "{}"),
        explanation=rec.explanation or "",
        recommendation=rec.recommendation or "",
        action_suggestion=json.loads(rec.action_suggestion_json) if rec.action_suggestion_json else None,
        status=rec.status,
        created_at=rec.created_at.isoformat() if isinstance(rec.created_at, datetime) else str(rec.created_at),
        updated_at=rec.updated_at.isoformat() if isinstance(rec.updated_at, datetime) else str(rec.updated_at),
        resolved_at=rec.resolved_at.isoformat() if isinstance(rec.resolved_at, datetime) else (str(rec.resolved_at) if rec.resolved_at else None),
    )


def save_alert(alert: BusinessAlert, user_id: Optional[str] = None) -> BusinessAlert:
    """
    Persists a BusinessAlert in user-scoped storage.
    If an alert with the same alert_id exists for the user, it updates it.
    """
    uid = _resolve_user_id(user_id or alert.user_id)
    session = _get_session()
    try:
        existing = (
            session.query(AlertRecord)
            .filter(AlertRecord.user_id == uid, AlertRecord.alert_id == alert.alert_id)
            .first()
        )

        now = datetime.utcnow()
        if existing:
            existing.title = alert.title
            existing.severity = alert.severity
            existing.category = alert.category
            existing.status = alert.status
            existing.current_value = alert.current_value
            existing.previous_value = alert.previous_value
            existing.delta = alert.delta
            existing.delta_percent = alert.delta_percent
            existing.threshold_applied = alert.threshold_applied
            existing.source_tables_json = json.dumps(alert.source_tables)
            existing.source_columns_json = json.dumps(alert.source_columns)
            existing.lineage_steps_json = json.dumps(alert.lineage_steps)
            existing.sql = alert.sql
            existing.evidence_json = json.dumps(alert.evidence)
            existing.explanation = alert.explanation
            existing.recommendation = alert.recommendation
            existing.action_suggestion_json = json.dumps(alert.action_suggestion) if alert.action_suggestion else None
            existing.updated_at = now
            if alert.status == AlertStatus.RESOLVED and not existing.resolved_at:
                existing.resolved_at = now
            session.commit()
            return _entity_to_model(existing)

        rec = AlertRecord(
            id=str(uuid.uuid4()),
            alert_id=alert.alert_id,
            user_id=uid,
            timestamp=datetime.fromisoformat(alert.timestamp) if "T" in alert.timestamp else now,
            category=alert.category,
            severity=alert.severity,
            status=alert.status,
            metric=alert.metric,
            title=alert.title,
            previous_value=alert.previous_value,
            current_value=alert.current_value,
            delta=alert.delta,
            delta_percent=alert.delta_percent,
            threshold_applied=alert.threshold_applied,
            source_tables_json=json.dumps(alert.source_tables),
            source_columns_json=json.dumps(alert.source_columns),
            lineage_steps_json=json.dumps(alert.lineage_steps),
            sql=alert.sql,
            evidence_json=json.dumps(alert.evidence),
            explanation=alert.explanation,
            recommendation=alert.recommendation,
            action_suggestion_json=json.dumps(alert.action_suggestion) if alert.action_suggestion else None,
            created_at=now,
            updated_at=now,
            resolved_at=now if alert.status == AlertStatus.RESOLVED else None,
        )
        session.add(rec)
        session.commit()
        return _entity_to_model(rec)
    finally:
        session.close()


def get_alerts(
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50,
) -> list[BusinessAlert]:
    """Retrieves alerts strictly scoped to the requesting user."""
    uid = _resolve_user_id(user_id)
    session = _get_session()
    try:
        q = session.query(AlertRecord).filter(AlertRecord.user_id == uid)
        if status:
            q = q.filter(AlertRecord.status == status)
        if category:
            q = q.filter(AlertRecord.category == category)
        if severity:
            q = q.filter(AlertRecord.severity == severity)

        recs = q.order_by(desc(AlertRecord.created_at)).limit(max(1, limit)).all()
        return [_entity_to_model(r) for r in recs]
    finally:
        session.close()


def get_alert(alert_id: str, user_id: Optional[str] = None) -> Optional[BusinessAlert]:
    """Retrieves a single alert ensuring ownership by the requesting user."""
    uid = _resolve_user_id(user_id)
    session = _get_session()
    try:
        rec = (
            session.query(AlertRecord)
            .filter(AlertRecord.user_id == uid, AlertRecord.alert_id == alert_id)
            .first()
        )
        return _entity_to_model(rec) if rec else None
    finally:
        session.close()


def update_alert_status(
    alert_id: str,
    new_status: str,
    user_id: Optional[str] = None,
) -> Optional[BusinessAlert]:
    """
    Updates the lifecycle status of an existing user-owned alert.
    Validates status against AlertStatus.ALL.
    """
    if new_status not in AlertStatus.ALL:
        raise ValueError(f"Invalid alert status: {new_status}. Allowed: {sorted(AlertStatus.ALL)}")

    uid = _resolve_user_id(user_id)
    session = _get_session()
    try:
        rec = (
            session.query(AlertRecord)
            .filter(AlertRecord.user_id == uid, AlertRecord.alert_id == alert_id)
            .first()
        )
        if not rec:
            return None

        rec.status = new_status
        rec.updated_at = datetime.utcnow()
        if new_status == AlertStatus.RESOLVED:
            rec.resolved_at = datetime.utcnow()
        session.commit()
        return _entity_to_model(rec)
    finally:
        session.close()


def find_active_alert(
    metric: str,
    category: str,
    user_id: Optional[str] = None,
) -> Optional[BusinessAlert]:
    """
    Deduplication helper: finds an active (NEW, ACKNOWLEDGED, or INVESTIGATING)
    alert for the same metric and category under the given user.
    """
    uid = _resolve_user_id(user_id)
    session = _get_session()
    try:
        rec = (
            session.query(AlertRecord)
            .filter(
                AlertRecord.user_id == uid,
                AlertRecord.metric == metric,
                AlertRecord.category == category,
                AlertRecord.status.in_(list(AlertStatus.ACTIVE_STATUSES)),
            )
            .order_by(desc(AlertRecord.created_at))
            .first()
        )
        return _entity_to_model(rec) if rec else None
    finally:
        session.close()


def clear_user_alerts(user_id: str) -> int:
    """Clears all stored alerts for a specific user (useful on account reset or disconnect)."""
    uid = _resolve_user_id(user_id)
    session = _get_session()
    try:
        count = session.query(AlertRecord).filter(AlertRecord.user_id == uid).delete()
        session.commit()
        return count
    finally:
        session.close()
