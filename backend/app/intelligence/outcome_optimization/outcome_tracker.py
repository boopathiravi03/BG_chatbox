"""
backend/app/intelligence/outcome_optimization/outcome_tracker.py

Phase 8.9: Persistent storage for outcome measurements and adaptive recommendations.
Uses a dedicated SQLite store (bgai_outcome_opt.db), separate from user databases
and from Phase 8.5 learning store.

User isolation: all queries enforce user_id filtering.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Column, String, Integer, Float, Text, Boolean, Index,
    create_engine, desc
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.intelligence.outcome_optimization.models import (
    OutcomeMeasurement,
    AdaptiveRecommendation,
    EffectivenessLabel,
    ConfidenceLevel,
    AttributionStatus,
    MeasurementWindow,
    RecommendationSource,
)

from app.paths import get_app_data_file

Base = declarative_base()
_store_lock = threading.Lock()

_DEFAULT_DB_PATH = get_app_data_file("bgai_outcome_opt.db")
_engine = None
_SessionFactory = None


# ── ORM Models ───────────────────────────────────────────────────────────────

class MeasurementEntity(Base):
    __tablename__ = "outcome_measurements"

    measurement_id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    action_id = Column(String(64), nullable=True, index=True)
    metric_name = Column(String(256), nullable=False)
    source_table = Column(String(128), nullable=False)
    source_column = Column(String(128), nullable=False, default="")
    measurement_sql = Column(Text, nullable=False, default="")
    baseline_value = Column(Float, nullable=True)
    baseline_period = Column(String(64), nullable=True)
    observed_value = Column(Float, nullable=True)
    delta = Column(Float, nullable=True)
    delta_pct = Column(Float, nullable=True)
    window = Column(String(16), nullable=False, default=MeasurementWindow.D7)
    effectiveness = Column(String(32), nullable=False, default=EffectivenessLabel.INSUFFICIENT_DATA)
    confidence = Column(String(16), nullable=False, default=ConfidenceLevel.LIMITED)
    attribution = Column(String(32), nullable=False, default=AttributionStatus.OBSERVED_OUTCOME)
    confounders_json = Column(Text, nullable=True)
    sample_size = Column(Integer, default=0)
    baseline_sample_size = Column(Integer, default=0)
    measured_at = Column(String(64), nullable=False)
    action_executed_at = Column(String(64), nullable=True)
    epistemic_note = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_meas_user_action", "user_id", "action_id"),
        Index("idx_meas_user_table", "user_id", "source_table"),
        Index("idx_meas_measured_at", "measured_at"),
    )


class RecommendationEntity(Base):
    __tablename__ = "adaptive_recommendations"

    recommendation_id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=False)
    action_type = Column(String(64), nullable=False)
    target_table = Column(String(128), nullable=False)
    rationale = Column(Text, nullable=True)
    source = Column(String(64), nullable=False, default=RecommendationSource.COLD_START)
    historical_success_rate = Column(Float, nullable=True)
    historical_sample_size = Column(Integer, default=0)
    confidence = Column(String(16), nullable=False, default=ConfidenceLevel.LIMITED)
    supporting_outcome_ids_json = Column(Text, nullable=True)
    requires_human_confirmation = Column(Boolean, default=True)
    caveat = Column(Text, nullable=True)
    generated_at = Column(String(64), nullable=False)

    __table_args__ = (
        Index("idx_rec_user_table", "user_id", "target_table"),
        Index("idx_rec_generated", "generated_at"),
    )


# ── Engine Initialization ────────────────────────────────────────────────────

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
                    "BGAI_OUTCOME_OPT_DB_URL",
                    f"sqlite:///{_DEFAULT_DB_PATH}",
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


# ── Conversion Helpers ───────────────────────────────────────────────────────

def _row_to_measurement(row: MeasurementEntity) -> OutcomeMeasurement:
    confounders = []
    if row.confounders_json:
        try:
            confounders = json.loads(row.confounders_json)
        except Exception:
            confounders = []
    return OutcomeMeasurement(
        measurement_id=row.measurement_id,
        user_id=row.user_id,
        action_id=row.action_id,
        metric_name=row.metric_name,
        source_table=row.source_table,
        source_column=row.source_column or "",
        measurement_sql=row.measurement_sql or "",
        baseline_value=row.baseline_value,
        baseline_period=row.baseline_period,
        observed_value=row.observed_value,
        delta=row.delta,
        delta_pct=row.delta_pct,
        window=row.window or MeasurementWindow.D7,
        effectiveness=row.effectiveness or EffectivenessLabel.INSUFFICIENT_DATA,
        confidence=row.confidence or ConfidenceLevel.LIMITED,
        attribution=row.attribution or AttributionStatus.OBSERVED_OUTCOME,
        confounders=confounders,
        sample_size=row.sample_size or 0,
        baseline_sample_size=row.baseline_sample_size or 0,
        measured_at=row.measured_at,
        action_executed_at=row.action_executed_at,
        epistemic_note=row.epistemic_note or (
            "Change is observed after the action. Causation is not claimed."
        ),
    )


def _row_to_recommendation(row: RecommendationEntity) -> AdaptiveRecommendation:
    supporting = []
    if row.supporting_outcome_ids_json:
        try:
            supporting = json.loads(row.supporting_outcome_ids_json)
        except Exception:
            supporting = []
    return AdaptiveRecommendation(
        recommendation_id=row.recommendation_id,
        user_id=row.user_id,
        title=row.title,
        description=row.description,
        action_type=row.action_type,
        target_table=row.target_table,
        rationale=row.rationale or "",
        source=row.source or RecommendationSource.COLD_START,
        historical_success_rate=row.historical_success_rate,
        historical_sample_size=row.historical_sample_size or 0,
        confidence=row.confidence or ConfidenceLevel.LIMITED,
        supporting_outcome_ids=supporting,
        requires_human_confirmation=True,
        caveat=row.caveat or "",
        generated_at=row.generated_at,
    )


# ── Public API ───────────────────────────────────────────────────────────────

def save_measurement(m: OutcomeMeasurement) -> OutcomeMeasurement:
    """Persist an outcome measurement (user-scoped)."""
    session = _get_session()
    try:
        existing = session.query(MeasurementEntity).filter_by(
            measurement_id=m.measurement_id,
            user_id=m.user_id,
        ).first()

        c_json = json.dumps(m.confounders) if m.confounders else None

        if existing:
            existing.baseline_value = m.baseline_value
            existing.observed_value = m.observed_value
            existing.delta = m.delta
            existing.delta_pct = m.delta_pct
            existing.effectiveness = m.effectiveness
            existing.confidence = m.confidence
            existing.attribution = m.attribution
            existing.confounders_json = c_json
            existing.sample_size = m.sample_size
            existing.baseline_sample_size = m.baseline_sample_size
            existing.measured_at = m.measured_at
            existing.epistemic_note = m.epistemic_note
        else:
            entity = MeasurementEntity(
                measurement_id=m.measurement_id,
                user_id=m.user_id,
                action_id=m.action_id,
                metric_name=m.metric_name,
                source_table=m.source_table,
                source_column=m.source_column,
                measurement_sql=m.measurement_sql,
                baseline_value=m.baseline_value,
                baseline_period=m.baseline_period,
                observed_value=m.observed_value,
                delta=m.delta,
                delta_pct=m.delta_pct,
                window=m.window,
                effectiveness=m.effectiveness,
                confidence=m.confidence,
                attribution=m.attribution,
                confounders_json=c_json,
                sample_size=m.sample_size,
                baseline_sample_size=m.baseline_sample_size,
                measured_at=m.measured_at,
                action_executed_at=m.action_executed_at,
                epistemic_note=m.epistemic_note,
            )
            session.add(entity)
        session.commit()
        return m
    finally:
        session.close()


def get_measurement(measurement_id: str, user_id: str) -> Optional[OutcomeMeasurement]:
    """Retrieve measurement by ID with strict user isolation."""
    session = _get_session()
    try:
        row = session.query(MeasurementEntity).filter_by(
            measurement_id=measurement_id,
            user_id=user_id,
        ).first()
        return _row_to_measurement(row) if row else None
    finally:
        session.close()


def list_measurements(
    user_id: str,
    action_id: Optional[str] = None,
    source_table: Optional[str] = None,
    limit: int = 50,
) -> list[OutcomeMeasurement]:
    """List outcome measurements for a user (optional filter by action_id or table)."""
    session = _get_session()
    try:
        q = session.query(MeasurementEntity).filter_by(user_id=user_id)
        if action_id:
            q = q.filter_by(action_id=action_id)
        if source_table:
            q = q.filter_by(source_table=source_table)
        rows = q.order_by(desc(MeasurementEntity.measured_at)).limit(
            max(1, min(limit, 200))
        ).all()
        return [_row_to_measurement(r) for r in rows]
    finally:
        session.close()


def save_recommendation(rec: AdaptiveRecommendation) -> AdaptiveRecommendation:
    """Persist an adaptive recommendation (user-scoped)."""
    session = _get_session()
    try:
        existing = session.query(RecommendationEntity).filter_by(
            recommendation_id=rec.recommendation_id,
            user_id=rec.user_id,
        ).first()

        s_json = json.dumps(rec.supporting_outcome_ids) if rec.supporting_outcome_ids else None

        if existing:
            existing.title = rec.title
            existing.description = rec.description
            existing.rationale = rec.rationale
            existing.source = rec.source
            existing.historical_success_rate = rec.historical_success_rate
            existing.historical_sample_size = rec.historical_sample_size
            existing.confidence = rec.confidence
            existing.supporting_outcome_ids_json = s_json
            existing.caveat = rec.caveat
        else:
            entity = RecommendationEntity(
                recommendation_id=rec.recommendation_id,
                user_id=rec.user_id,
                title=rec.title,
                description=rec.description,
                action_type=rec.action_type,
                target_table=rec.target_table,
                rationale=rec.rationale,
                source=rec.source,
                historical_success_rate=rec.historical_success_rate,
                historical_sample_size=rec.historical_sample_size,
                confidence=rec.confidence,
                supporting_outcome_ids_json=s_json,
                requires_human_confirmation=True,
                caveat=rec.caveat,
                generated_at=rec.generated_at,
            )
            session.add(entity)
        session.commit()
        return rec
    finally:
        session.close()


def get_recommendation(
    recommendation_id: str, user_id: str
) -> Optional[AdaptiveRecommendation]:
    """Retrieve recommendation by ID with strict user isolation."""
    session = _get_session()
    try:
        row = session.query(RecommendationEntity).filter_by(
            recommendation_id=recommendation_id,
            user_id=user_id,
        ).first()
        return _row_to_recommendation(row) if row else None
    finally:
        session.close()


def list_recommendations(
    user_id: str,
    limit: int = 20,
) -> list[AdaptiveRecommendation]:
    """List adaptive recommendations for a user, most recent first."""
    session = _get_session()
    try:
        rows = (
            session.query(RecommendationEntity)
            .filter_by(user_id=user_id)
            .order_by(desc(RecommendationEntity.generated_at))
            .limit(max(1, min(limit, 100)))
            .all()
        )
        return [_row_to_recommendation(r) for r in rows]
    finally:
        session.close()


def clear_outcome_opt_store(user_id: Optional[str] = None) -> None:
    """Testing utility: clear store for a user (or all if user_id is None)."""
    session = _get_session()
    try:
        if user_id:
            session.query(MeasurementEntity).filter_by(user_id=user_id).delete()
            session.query(RecommendationEntity).filter_by(user_id=user_id).delete()
        else:
            session.query(MeasurementEntity).delete()
            session.query(RecommendationEntity).delete()
        session.commit()
    finally:
        session.close()


def reset_engine() -> None:
    """Reset internal engine state (useful for isolated tests)."""
    global _engine, _SessionFactory
    with _store_lock:
        _engine = None
        _SessionFactory = None
