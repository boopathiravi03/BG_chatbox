

"""backend/app/intelligence/investigation/investigation_store.py

Thread-safe, persistent storage for Sprint 3 AI Business Investigation reports.
Manages:
1. Investigation report persistence scoped strictly by user and connection.
2. Structured report payloads containing executive summary, evidence provenance,
   contributing factors, follow-up recommendations, and chart specifications.
3. Historical report listing and single-report retrieval.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Text,
    Index,
    create_engine,
    desc,
)
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.paths import get_app_data_file

logger = logging.getLogger("bgai.investigation.store")

Base = declarative_base()
_store_lock = threading.RLock()

_DEFAULT_DB_PATH = get_app_data_file("bgai_investigations.db")
_engine = None
_SessionFactory = None


def _get_engine(custom_engine=None):
    global _engine, _SessionFactory
    if custom_engine is False:
        _engine = None
        _SessionFactory = None
        return None
    if custom_engine is not None:
        _engine = custom_engine
        Base.metadata.create_all(_engine)
        _SessionFactory = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
        return _engine

    if _engine is None:
        with _store_lock:
            if _engine is None:
                db_url = os.getenv("BGAI_INVESTIGATION_DB_URL", f"sqlite:///{_DEFAULT_DB_PATH}")
                engine_kwargs = {
                    "connect_args": {"check_same_thread": False} if "sqlite" in db_url else {},
                    "pool_pre_ping": True,
                }
                if "sqlite" in db_url:
                    engine_kwargs["poolclass"] = NullPool
                _engine = create_engine(
                    db_url,
                    **engine_kwargs,
                )
                Base.metadata.create_all(_engine)
                _SessionFactory = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def set_investigation_store_engine(custom_engine) -> None:
    """Configures a custom SQLAlchemy engine (useful for in-memory unit tests)."""
    _get_engine(custom_engine)


def _get_session() -> Session:
    _get_engine()
    return _SessionFactory()


class InvestigationReportRecord(Base):
    """SQLAlchemy entity for persisted investigation reports."""
    __tablename__ = "investigation_reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    connection_id = Column(String(64), nullable=False, index=True)
    question = Column(Text, nullable=False)
    title = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False, default="success")  # success, insufficient_evidence, disconnected, error
    summary = Column(Text, nullable=False, default="")
    report_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        Index("ix_user_conn_investigation", "user_id", "connection_id", "created_at"),
    )


def save_investigation_report(
    report_id: str,
    user_id: str,
    connection_id: str,
    question: str,
    title: str,
    status: str,
    summary: str,
    report_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Persists an investigation report scoped strictly to the authenticated user and connection.
    Updates in place if report_id exists.
    """
    with _store_lock:
        session = _get_session()
        try:
            now = datetime.now(timezone.utc)
            rec = (
                session.query(InvestigationReportRecord)
                .filter(
                    InvestigationReportRecord.user_id == user_id,
                    InvestigationReportRecord.report_id == report_id,
                )
                .first()
            )

            if rec is None:
                rec = InvestigationReportRecord(
                    id=str(uuid.uuid4()),
                    report_id=report_id,
                    user_id=user_id,
                    connection_id=connection_id,
                    question=question,
                    title=title,
                    status=status,
                    summary=summary,
                    report_json=json.dumps(report_data),
                    created_at=now,
                )
                session.add(rec)
            else:
                rec.question = question
                rec.title = title
                rec.status = status
                rec.summary = summary
                rec.report_json = json.dumps(report_data)

            session.commit()
            return {
                "report_id": rec.report_id,
                "user_id": rec.user_id,
                "connection_id": rec.connection_id,
                "question": rec.question,
                "title": rec.title,
                "status": rec.status,
                "summary": rec.summary,
                "created_at": rec.created_at.isoformat(),
            }
        finally:
            session.close()


def get_investigation_report(
    report_id: str,
    user_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Retrieves a single investigation report ensuring strict user tenant ownership.
    """
    with _store_lock:
        session = _get_session()
        try:
            rec = (
                session.query(InvestigationReportRecord)
                .filter(
                    InvestigationReportRecord.user_id == user_id,
                    InvestigationReportRecord.report_id == report_id,
                )
                .first()
            )
            if not rec:
                return None

            report_data = json.loads(rec.report_json or "{}")
            return {
                "report_id": rec.report_id,
                "user_id": rec.user_id,
                "connection_id": rec.connection_id,
                "question": rec.question,
                "title": rec.title,
                "status": rec.status,
                "summary": rec.summary,
                "created_at": rec.created_at.isoformat() if rec.created_at else None,
                "report": report_data,
            }
        finally:
            session.close()


def list_investigation_reports(
    user_id: str,
    connection_id: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Returns recent investigation reports strictly filtered by authenticated user.
    """
    with _store_lock:
        session = _get_session()
        try:
            q = session.query(InvestigationReportRecord).filter(
                InvestigationReportRecord.user_id == user_id
            )
            if connection_id:
                q = q.filter(InvestigationReportRecord.connection_id == connection_id)

            records = (
                q.order_by(desc(InvestigationReportRecord.created_at))
                .limit(min(100, max(1, limit)))
                .all()
            )

            return [
                {
                    "report_id": r.report_id,
                    "connection_id": r.connection_id,
                    "question": r.question,
                    "title": r.title,
                    "status": r.status,
                    "summary": r.summary,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in records
            ]
        finally:
            session.close()


def delete_investigation_report(
    report_id: str,
    user_id: str,
) -> bool:
    """Deletes an investigation report owned by the authenticated user."""
    with _store_lock:
        session = _get_session()
        try:
            rec = (
                session.query(InvestigationReportRecord)
                .filter(
                    InvestigationReportRecord.user_id == user_id,
                    InvestigationReportRecord.report_id == report_id,
                )
                .first()
            )
            if not rec:
                return False
            session.delete(rec)
            session.commit()
            return True
        finally:
            session.close()
