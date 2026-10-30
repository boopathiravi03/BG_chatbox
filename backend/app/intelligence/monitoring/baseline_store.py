"""backend/app/intelligence/monitoring/baseline_store.py

Thread-safe, persistent SQLite storage for Sprint 2 Autonomous Business Intelligence & Monitoring.
Manages:
1. Schedule configurations per user and connection.
2. Baseline schema, row count, null distribution, and metric snapshots.
3. Historical monitoring scan runs with diff tracking (new vs resolved findings).
Strictly enforces per-user and per-connection tenant isolation.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Text,
    Index,
    create_engine,
    desc,
)
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.paths import get_app_data_file

Base = declarative_base()
_store_lock = threading.RLock()

_DEFAULT_DB_PATH = get_app_data_file("bgai_monitoring.db")
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
                db_url = os.getenv("BGAI_MONITORING_DB_URL", f"sqlite:///{_DEFAULT_DB_PATH}")
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


def set_monitoring_store_engine(custom_engine) -> None:
    """Configures a custom SQLAlchemy engine (for in-memory test suites)."""
    _get_engine(custom_engine)


def _get_session() -> Session:
    _get_engine()
    return _SessionFactory()


# ── Database Models ───────────────────────────────────────────────────────────

class ScheduleConfigRecord(Base):
    """Stores configurable monitoring schedule per user and connection."""
    __tablename__ = "monitoring_schedules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(64), nullable=False, index=True)
    connection_id = Column(String(64), nullable=False, index=True)
    interval_minutes = Column(Integer, nullable=False, default=60)
    is_enabled = Column(Boolean, nullable=False, default=True)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="idle")  # idle, scanning, paused, error
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_user_conn_schedule", "user_id", "connection_id", unique=True),
    )


class MonitoringBaselineRecord(Base):
    """Stores snapshot baseline for delta comparison across scans."""
    __tablename__ = "monitoring_baselines"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(64), nullable=False, index=True)
    connection_id = Column(String(64), nullable=False, index=True)
    captured_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    health_score = Column(Integer, nullable=False, default=100)
    tables_json = Column(Text, nullable=False, default="[]")
    row_counts_json = Column(Text, nullable=False, default="{}")
    findings_json = Column(Text, nullable=False, default="[]")
    metrics_json = Column(Text, nullable=False, default="{}")

    __table_args__ = (
        Index("ix_user_conn_baseline", "user_id", "connection_id"),
    )


class ScanHistoryRecord(Base):
    """Historical log of completed monitoring scans."""
    __tablename__ = "monitoring_scan_history"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    connection_id = Column(String(64), nullable=False, index=True)
    scanned_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    health_score = Column(Integer, nullable=False, default=100)
    total_findings = Column(Integer, nullable=False, default=0)
    new_findings = Column(Integer, nullable=False, default=0)
    resolved_findings = Column(Integer, nullable=False, default=0)
    anomalies_detected = Column(Integer, nullable=False, default=0)
    scan_duration_ms = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="success")  # success, error, disconnected
    error_message = Column(Text, nullable=True)
    summary_json = Column(Text, nullable=False, default="{}")

    __table_args__ = (
        Index("ix_user_conn_scan_hist", "user_id", "connection_id", "scanned_at"),
    )


# ── Store API Functions ───────────────────────────────────────────────────────

def save_schedule_config(
    user_id: str,
    connection_id: str,
    interval_minutes: int = 60,
    is_enabled: bool = True,
    status: str = "idle",
) -> Dict[str, Any]:
    """Saves or updates schedule configuration for a specific user and connection."""
    with _store_lock:
        session = _get_session()
        try:
            rec = (
                session.query(ScheduleConfigRecord)
                .filter(
                    ScheduleConfigRecord.user_id == user_id,
                    ScheduleConfigRecord.connection_id == connection_id,
                )
                .first()
            )
            now = datetime.now(timezone.utc)
            if rec is None:
                next_run = now + timedelta(minutes=max(1, interval_minutes)) if is_enabled else None
                rec = ScheduleConfigRecord(
                    user_id=user_id,
                    connection_id=connection_id,
                    interval_minutes=max(1, interval_minutes),
                    is_enabled=is_enabled,
                    status=status,
                    created_at=now,
                    updated_at=now,
                    next_run_at=next_run,
                )
                session.add(rec)
            else:
                rec.interval_minutes = max(1, interval_minutes)
                rec.is_enabled = is_enabled
                rec.status = status
                rec.updated_at = now
                existing_next_run = rec.next_run_at
                if existing_next_run is not None and existing_next_run.tzinfo is None:
                    existing_next_run = existing_next_run.replace(tzinfo=timezone.utc)

                if is_enabled and (existing_next_run is None or existing_next_run < now):
                    rec.next_run_at = now + timedelta(minutes=max(1, interval_minutes))
                elif not is_enabled:
                    rec.next_run_at = None

            session.commit()
            return {
                "user_id": rec.user_id,
                "connection_id": rec.connection_id,
                "interval_minutes": rec.interval_minutes,
                "is_enabled": rec.is_enabled,
                "status": rec.status,
                "last_run_at": rec.last_run_at.isoformat() if rec.last_run_at else None,
                "next_run_at": rec.next_run_at.isoformat() if rec.next_run_at else None,
            }
        finally:
            session.close()


def get_schedule_config(user_id: str, connection_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves schedule configuration for user and connection."""
    with _store_lock:
        session = _get_session()
        try:
            rec = (
                session.query(ScheduleConfigRecord)
                .filter(
                    ScheduleConfigRecord.user_id == user_id,
                    ScheduleConfigRecord.connection_id == connection_id,
                )
                .first()
            )
            if not rec:
                return None
            return {
                "user_id": rec.user_id,
                "connection_id": rec.connection_id,
                "interval_minutes": rec.interval_minutes,
                "is_enabled": rec.is_enabled,
                "status": rec.status,
                "last_run_at": rec.last_run_at.isoformat() if rec.last_run_at else None,
                "next_run_at": rec.next_run_at.isoformat() if rec.next_run_at else None,
                "last_error": rec.last_error,
            }
        finally:
            session.close()


def list_active_schedules() -> List[Dict[str, Any]]:
    """Returns all enabled schedules across all connections (for scheduler worker loop)."""
    with _store_lock:
        session = _get_session()
        try:
            records = (
                session.query(ScheduleConfigRecord)
                .filter(ScheduleConfigRecord.is_enabled == True)
                .all()
            )
            return [
                {
                    "user_id": r.user_id,
                    "connection_id": r.connection_id,
                    "interval_minutes": r.interval_minutes,
                    "last_run_at": r.last_run_at,
                    "next_run_at": r.next_run_at,
                    "status": r.status,
                }
                for r in records
            ]
        finally:
            session.close()


def update_schedule_execution_state(
    user_id: str,
    connection_id: str,
    status: str,
    last_run_at: Optional[datetime] = None,
    next_run_at: Optional[datetime] = None,
    error: Optional[str] = None,
) -> None:
    """Updates last run timestamp, next run time, and status for schedule."""
    with _store_lock:
        session = _get_session()
        try:
            rec = (
                session.query(ScheduleConfigRecord)
                .filter(
                    ScheduleConfigRecord.user_id == user_id,
                    ScheduleConfigRecord.connection_id == connection_id,
                )
                .first()
            )
            if rec:
                rec.status = status
                if last_run_at:
                    rec.last_run_at = last_run_at
                if next_run_at:
                    rec.next_run_at = next_run_at
                rec.last_error = error
                rec.updated_at = datetime.now(timezone.utc)
                session.commit()
        finally:
            session.close()


def claim_schedule_execution(
    user_id: str,
    connection_id: str,
    lease_minutes: int = 5,
) -> bool:
    """
    Atomically claims scheduled scan execution for a specific user connection across multiple server worker processes.
    Returns True if successfully claimed, False if already scanning or claimed by another worker.
    Automatically reclaims orphan leases from crashed workers after lease_minutes.
    """
    with _store_lock:
        session = _get_session()
        try:
            now = datetime.now(timezone.utc)
            threshold = now - timedelta(minutes=max(1, lease_minutes))

            rec = (
                session.query(ScheduleConfigRecord)
                .filter(
                    ScheduleConfigRecord.user_id == user_id,
                    ScheduleConfigRecord.connection_id == connection_id,
                    ScheduleConfigRecord.is_enabled == True,
                )
                .first()
            )
            if not rec:
                return False

            up_at = rec.updated_at
            if up_at is not None and up_at.tzinfo is None:
                up_at = up_at.replace(tzinfo=timezone.utc)

            # If currently scanning and within lease window, another worker is executing
            if rec.status == "scanning" and up_at is not None and up_at >= threshold:
                return False

            rec.status = "scanning"
            rec.updated_at = now
            session.commit()
            return True
        finally:
            session.close()


def save_baseline(
    user_id: str,
    connection_id: str,
    health_score: int,
    tables: List[str],
    row_counts: Dict[str, int],
    findings: List[Dict[str, Any]],
    metrics: Dict[str, Any],
) -> Dict[str, Any]:
    """Stores the latest baseline snapshot for user and connection."""
    with _store_lock:
        session = _get_session()
        try:
            now = datetime.now(timezone.utc)
            # Remove existing baselines for this connection to keep store compact
            session.query(MonitoringBaselineRecord).filter(
                MonitoringBaselineRecord.user_id == user_id,
                MonitoringBaselineRecord.connection_id == connection_id,
            ).delete()

            rec = MonitoringBaselineRecord(
                user_id=user_id,
                connection_id=connection_id,
                captured_at=now,
                health_score=health_score,
                tables_json=json.dumps(tables),
                row_counts_json=json.dumps(row_counts),
                findings_json=json.dumps(findings),
                metrics_json=json.dumps(metrics),
            )
            session.add(rec)
            session.commit()

            return {
                "user_id": user_id,
                "connection_id": connection_id,
                "captured_at": now.isoformat(),
                "health_score": health_score,
                "tables": tables,
                "row_counts": row_counts,
                "findings_count": len(findings),
            }
        finally:
            session.close()


def get_latest_baseline(user_id: str, connection_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves the previous baseline snapshot for delta comparison."""
    with _store_lock:
        session = _get_session()
        try:
            rec = (
                session.query(MonitoringBaselineRecord)
                .filter(
                    MonitoringBaselineRecord.user_id == user_id,
                    MonitoringBaselineRecord.connection_id == connection_id,
                )
                .order_by(desc(MonitoringBaselineRecord.captured_at))
                .first()
            )
            if not rec:
                return None

            return {
                "captured_at": rec.captured_at.isoformat() if rec.captured_at else None,
                "health_score": rec.health_score,
                "tables": json.loads(rec.tables_json or "[]"),
                "row_counts": json.loads(rec.row_counts_json or "{}"),
                "findings": json.loads(rec.findings_json or "[]"),
                "metrics": json.loads(rec.metrics_json or "{}"),
            }
        finally:
            session.close()


def record_scan_history(
    scan_id: str,
    user_id: str,
    connection_id: str,
    health_score: int,
    total_findings: int,
    new_findings: int,
    resolved_findings: int,
    anomalies_detected: int,
    scan_duration_ms: int,
    status: str = "success",
    error_message: Optional[str] = None,
    summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Appends an execution record to the monitoring scan history."""
    with _store_lock:
        session = _get_session()
        try:
            now = datetime.now(timezone.utc)
            rec = ScanHistoryRecord(
                scan_id=scan_id,
                user_id=user_id,
                connection_id=connection_id,
                scanned_at=now,
                health_score=health_score,
                total_findings=total_findings,
                new_findings=new_findings,
                resolved_findings=resolved_findings,
                anomalies_detected=anomalies_detected,
                scan_duration_ms=scan_duration_ms,
                status=status,
                error_message=error_message,
                summary_json=json.dumps(summary or {}),
            )
            session.add(rec)
            session.commit()

            return {
                "scan_id": scan_id,
                "user_id": user_id,
                "connection_id": connection_id,
                "scanned_at": now.isoformat(),
                "health_score": health_score,
                "status": status,
            }
        finally:
            session.close()


def get_scan_history(
    user_id: str,
    connection_id: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Fetches recent scan history filtered strictly by authenticated user."""
    with _store_lock:
        session = _get_session()
        try:
            query = session.query(ScanHistoryRecord).filter(ScanHistoryRecord.user_id == user_id)
            if connection_id:
                query = query.filter(ScanHistoryRecord.connection_id == connection_id)

            records = (
                query.order_by(desc(ScanHistoryRecord.scanned_at))
                .limit(min(100, max(1, limit)))
                .all()
            )

            return [
                {
                    "scan_id": r.scan_id,
                    "connection_id": r.connection_id,
                    "scanned_at": r.scanned_at.isoformat() if r.scanned_at else None,
                    "health_score": r.health_score,
                    "total_findings": r.total_findings,
                    "new_findings": r.new_findings,
                    "resolved_findings": r.resolved_findings,
                    "anomalies_detected": r.anomalies_detected,
                    "scan_duration_ms": r.scan_duration_ms,
                    "status": r.status,
                    "error_message": r.error_message,
                    "summary": json.loads(r.summary_json or "{}"),
                }
                for r in records
            ]
        finally:
            session.close()
