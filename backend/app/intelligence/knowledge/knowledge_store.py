"""
backend/app/intelligence/knowledge/knowledge_store.py

Phase 9.1: Persistent Storage for Enterprise Knowledge & Context
Uses a dedicated SQLite store (bgai_knowledge.db) separate from user databases,
with full multi-tenant isolation, thread safety, and historical versioning.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import (
    Column, String, Integer, Float, Text, Boolean, Index,
    create_engine, desc
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.intelligence.knowledge.models import (
    BusinessEntity,
    BusinessRule,
    BusinessMetric,
    ColumnSemantic,
    KnowledgeConflict,
    KnowledgeVersionRecord,
    KnowledgeStatus,
    KnowledgeSummary,
)

logger = logging.getLogger("bgai.knowledge.store")

Base = declarative_base()
_store_lock = threading.Lock()

_DEFAULT_DB_PATH = Path(__file__).resolve().parents[4] / "bgai_knowledge.db"
_engine = None
_SessionFactory = None


# ── ORM Models ───────────────────────────────────────────────────────────────

class EntityRecord(Base):
    __tablename__ = "knowledge_entities"

    entity_id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    database_identity = Column(String(256), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    plural_name = Column(String(128), nullable=False)
    table_name = Column(String(128), nullable=False, index=True)
    description = Column(Text, nullable=False, default="")
    importance = Column(String(32), nullable=False, default="SECONDARY")
    primary_key = Column(String(128), nullable=True)
    foreign_keys_json = Column(Text, nullable=False, default="[]")
    provenance = Column(String(64), nullable=False, default="SCHEMA_DERIVED")
    status = Column(String(32), nullable=False, default="PROPOSED")
    confidence = Column(Float, nullable=False, default=0.7)
    created_at = Column(String(64), nullable=False)
    updated_at = Column(String(64), nullable=False)


class RuleRecord(Base):
    __tablename__ = "knowledge_rules"

    rule_id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    database_identity = Column(String(256), nullable=False, index=True)
    name = Column(String(256), nullable=False)
    description = Column(Text, nullable=False, default="")
    scope = Column(String(32), nullable=False, default="METRIC")
    target_table = Column(String(128), nullable=False, index=True)
    target_column = Column(String(128), nullable=True)
    rule_type = Column(String(32), nullable=False, default="EXCLUSION")
    expression = Column(Text, nullable=False, default="")
    status = Column(String(32), nullable=False, default="PROPOSED", index=True)
    provenance = Column(String(64), nullable=False, default="USER_PROVIDED")
    version = Column(Integer, nullable=False, default=1)
    affected_metrics_json = Column(Text, nullable=False, default="[]")
    created_at = Column(String(64), nullable=False)
    updated_at = Column(String(64), nullable=False)


class MetricRecord(Base):
    __tablename__ = "knowledge_metrics"

    metric_id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    database_identity = Column(String(256), nullable=False, index=True)
    name = Column(String(256), nullable=False, index=True)
    description = Column(Text, nullable=False, default="")
    table_name = Column(String(128), nullable=False, index=True)
    column_name = Column(String(128), nullable=True)
    aggregation = Column(String(32), nullable=False, default="SUM")
    filter_expression = Column(Text, nullable=True)
    conditions_json = Column(Text, nullable=False, default="[]")
    rules_applied_json = Column(Text, nullable=False, default="[]")
    version = Column(Integer, nullable=False, default=1)
    provenance = Column(String(64), nullable=False, default="SCHEMA_DERIVED")
    status = Column(String(32), nullable=False, default="PROPOSED", index=True)
    confidence = Column(Float, nullable=False, default=0.8)
    created_at = Column(String(64), nullable=False)
    updated_at = Column(String(64), nullable=False)


class SemanticRecord(Base):
    __tablename__ = "knowledge_semantics"

    semantic_id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    database_identity = Column(String(256), nullable=False, index=True)
    table_name = Column(String(128), nullable=False, index=True)
    column_name = Column(String(128), nullable=False)
    business_meaning = Column(Text, nullable=False)
    data_type = Column(String(64), nullable=False, default="string")
    is_primary_key = Column(Boolean, nullable=False, default=False)
    is_foreign_key = Column(Boolean, nullable=False, default=False)
    provenance = Column(String(64), nullable=False, default="SCHEMA_DERIVED")
    status = Column(String(32), nullable=False, default="PROPOSED")
    confidence = Column(Float, nullable=False, default=0.7)
    created_at = Column(String(64), nullable=False)
    updated_at = Column(String(64), nullable=False)


class ConflictRecord(Base):
    __tablename__ = "knowledge_conflicts"

    conflict_id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    database_identity = Column(String(256), nullable=False, index=True)
    knowledge_type = Column(String(32), nullable=False)
    item_id_a = Column(String(64), nullable=False)
    item_id_b = Column(String(64), nullable=False)
    target_name = Column(String(256), nullable=False)
    description = Column(Text, nullable=False)
    statement_a = Column(Text, nullable=False)
    statement_b = Column(Text, nullable=False)
    source_a = Column(String(64), nullable=False)
    source_b = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="UNRESOLVED", index=True)
    resolution_notes = Column(Text, nullable=True)
    resolved_by = Column(String(64), nullable=True)
    created_at = Column(String(64), nullable=False)
    resolved_at = Column(String(64), nullable=True)


class VersionRecord(Base):
    __tablename__ = "knowledge_versions"

    version_id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    database_identity = Column(String(256), nullable=False, index=True)
    item_id = Column(String(64), nullable=False, index=True)
    item_type = Column(String(32), nullable=False)
    version = Column(Integer, nullable=False)
    snapshot_json = Column(Text, nullable=False)
    change_summary = Column(Text, nullable=False)
    created_at = Column(String(64), nullable=False)


# ── Initialization & Engine Setup ─────────────────────────────────────────────

def _get_engine(db_path: Optional[str] = None):
    global _engine, _SessionFactory
    if _engine is None:
        path = db_path or str(_DEFAULT_DB_PATH)
        _engine = create_engine(
            f"sqlite:///{path}",
            connect_args={"check_same_thread": False},
            echo=False,
        )
        Base.metadata.create_all(_engine)
        _SessionFactory = sessionmaker(bind=_engine)
    return _engine


def _get_session(db_path: Optional[str] = None) -> Session:
    global _SessionFactory
    _get_engine(db_path)
    return _SessionFactory()


# ── Entity Operations ────────────────────────────────────────────────────────

def save_entity(entity: BusinessEntity, db_path: Optional[str] = None) -> BusinessEntity:
    with _store_lock:
        session = _get_session(db_path)
        try:
            existing = session.query(EntityRecord).filter(
                EntityRecord.entity_id == entity.entity_id,
                EntityRecord.user_id == entity.user_id,
            ).first()

            if existing:
                existing.name = entity.name
                existing.plural_name = entity.plural_name
                existing.table_name = entity.table_name
                existing.description = entity.description
                existing.importance = entity.importance
                existing.primary_key = entity.primary_key
                existing.foreign_keys_json = json.dumps(entity.foreign_keys)
                existing.provenance = entity.provenance
                existing.status = entity.status
                existing.confidence = entity.confidence
                existing.database_identity = entity.database_identity
                existing.updated_at = datetime.now(timezone.utc).isoformat()
            else:
                rec = EntityRecord(
                    entity_id=entity.entity_id,
                    user_id=entity.user_id,
                    database_identity=entity.database_identity,
                    name=entity.name,
                    plural_name=entity.plural_name,
                    table_name=entity.table_name,
                    description=entity.description,
                    importance=entity.importance,
                    primary_key=entity.primary_key,
                    foreign_keys_json=json.dumps(entity.foreign_keys),
                    provenance=entity.provenance,
                    status=entity.status,
                    confidence=entity.confidence,
                    created_at=entity.created_at,
                    updated_at=entity.updated_at,
                )
                session.add(rec)
            session.commit()
            return entity
        finally:
            session.close()


def get_entity(entity_id: str, user_id: str, database_identity: str, db_path: Optional[str] = None) -> Optional[BusinessEntity]:
    with _store_lock:
        session = _get_session(db_path)
        try:
            rec = session.query(EntityRecord).filter(
                EntityRecord.entity_id == entity_id,
                EntityRecord.user_id == user_id,
                EntityRecord.database_identity == database_identity,
            ).first()
            if not rec:
                return None
            return BusinessEntity(
                entity_id=rec.entity_id,
                name=rec.name,
                plural_name=rec.plural_name,
                table_name=rec.table_name,
                description=rec.description,
                importance=rec.importance,
                primary_key=rec.primary_key,
                foreign_keys=json.loads(rec.foreign_keys_json),
                provenance=rec.provenance,
                status=rec.status,
                confidence=rec.confidence,
                user_id=rec.user_id,
                database_identity=rec.database_identity,
                created_at=rec.created_at,
                updated_at=rec.updated_at,
            )
        finally:
            session.close()


def list_entities(user_id: str, database_identity: str, status: Optional[str] = None, db_path: Optional[str] = None) -> list[BusinessEntity]:
    with _store_lock:
        session = _get_session(db_path)
        try:
            q = session.query(EntityRecord).filter(
                EntityRecord.user_id == user_id,
                EntityRecord.database_identity == database_identity,
            )
            if status:
                q = q.filter(EntityRecord.status == status)
            records = q.all()
            return [
                BusinessEntity(
                    entity_id=r.entity_id,
                    name=r.name,
                    plural_name=r.plural_name,
                    table_name=r.table_name,
                    description=r.description,
                    importance=r.importance,
                    primary_key=r.primary_key,
                    foreign_keys=json.loads(r.foreign_keys_json),
                    provenance=r.provenance,
                    status=r.status,
                    confidence=r.confidence,
                    user_id=r.user_id,
                    database_identity=r.database_identity,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                )
                for r in records
            ]
        finally:
            session.close()


# ── Rule Operations ──────────────────────────────────────────────────────────

def save_rule(rule: BusinessRule, db_path: Optional[str] = None) -> BusinessRule:
    with _store_lock:
        session = _get_session(db_path)
        try:
            existing = session.query(RuleRecord).filter(
                RuleRecord.rule_id == rule.rule_id,
                RuleRecord.user_id == rule.user_id,
            ).first()

            now_iso = datetime.now(timezone.utc).isoformat()
            if existing:
                # Log version history before updating
                ver_rec = VersionRecord(
                    version_id=f"ver_{rule.rule_id}_{existing.version}",
                    user_id=rule.user_id,
                    database_identity=rule.database_identity,
                    item_id=rule.rule_id,
                    item_type="RULE",
                    version=existing.version,
                    snapshot_json=json.dumps({
                        "name": existing.name,
                        "description": existing.description,
                        "expression": existing.expression,
                        "status": existing.status,
                    }),
                    change_summary=f"Updated rule to version {rule.version}",
                    created_at=now_iso,
                )
                session.add(ver_rec)

                existing.name = rule.name
                existing.description = rule.description
                existing.scope = rule.scope
                existing.target_table = rule.target_table
                existing.target_column = rule.target_column
                existing.rule_type = rule.rule_type
                existing.expression = rule.expression
                existing.status = rule.status
                existing.provenance = rule.provenance
                existing.version = rule.version
                existing.affected_metrics_json = json.dumps(rule.affected_metrics)
                existing.database_identity = rule.database_identity
                existing.updated_at = now_iso
            else:
                rec = RuleRecord(
                    rule_id=rule.rule_id,
                    user_id=rule.user_id,
                    database_identity=rule.database_identity,
                    name=rule.name,
                    description=rule.description,
                    scope=rule.scope,
                    target_table=rule.target_table,
                    target_column=rule.target_column,
                    rule_type=rule.rule_type,
                    expression=rule.expression,
                    status=rule.status,
                    provenance=rule.provenance,
                    version=rule.version,
                    affected_metrics_json=json.dumps(rule.affected_metrics),
                    created_at=rule.created_at,
                    updated_at=rule.updated_at,
                )
                session.add(rec)
            session.commit()
            return rule
        finally:
            session.close()


def get_rule(rule_id: str, user_id: str, database_identity: str, db_path: Optional[str] = None) -> Optional[BusinessRule]:
    with _store_lock:
        session = _get_session(db_path)
        try:
            rec = session.query(RuleRecord).filter(
                RuleRecord.rule_id == rule_id,
                RuleRecord.user_id == user_id,
                RuleRecord.database_identity == database_identity,
            ).first()
            if not rec:
                return None
            return BusinessRule(
                rule_id=rec.rule_id,
                name=rec.name,
                description=rec.description,
                scope=rec.scope,
                target_table=rec.target_table,
                target_column=rec.target_column,
                rule_type=rec.rule_type,
                expression=rec.expression,
                status=rec.status,
                provenance=rec.provenance,
                version=rec.version,
                affected_metrics=json.loads(rec.affected_metrics_json),
                user_id=rec.user_id,
                database_identity=rec.database_identity,
                created_at=rec.created_at,
                updated_at=rec.updated_at,
            )
        finally:
            session.close()


def list_rules(user_id: str, database_identity: str, status: Optional[str] = None, target_table: Optional[str] = None, db_path: Optional[str] = None) -> list[BusinessRule]:
    with _store_lock:
        session = _get_session(db_path)
        try:
            q = session.query(RuleRecord).filter(
                RuleRecord.user_id == user_id,
                RuleRecord.database_identity == database_identity,
            )
            if status:
                q = q.filter(RuleRecord.status == status)
            if target_table:
                q = q.filter(RuleRecord.target_table == target_table)
            records = q.order_by(desc(RuleRecord.updated_at)).all()
            return [
                BusinessRule(
                    rule_id=r.rule_id,
                    name=r.name,
                    description=r.description,
                    scope=r.scope,
                    target_table=r.target_table,
                    target_column=r.target_column,
                    rule_type=r.rule_type,
                    expression=r.expression,
                    status=r.status,
                    provenance=r.provenance,
                    version=r.version,
                    affected_metrics=json.loads(r.affected_metrics_json),
                    user_id=r.user_id,
                    database_identity=r.database_identity,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                )
                for r in records
            ]
        finally:
            session.close()


# ── Metric Operations ────────────────────────────────────────────────────────

def save_metric(metric: BusinessMetric, db_path: Optional[str] = None) -> BusinessMetric:
    with _store_lock:
        session = _get_session(db_path)
        try:
            existing = session.query(MetricRecord).filter(
                MetricRecord.metric_id == metric.metric_id,
                MetricRecord.user_id == metric.user_id,
            ).first()

            now_iso = datetime.now(timezone.utc).isoformat()
            if existing:
                # Log version record
                ver_rec = VersionRecord(
                    version_id=f"ver_{metric.metric_id}_{existing.version}",
                    user_id=metric.user_id,
                    database_identity=metric.database_identity,
                    item_id=metric.metric_id,
                    item_type="METRIC",
                    version=existing.version,
                    snapshot_json=json.dumps({
                        "name": existing.name,
                        "filter_expression": existing.filter_expression,
                        "status": existing.status,
                        "aggregation": existing.aggregation,
                    }),
                    change_summary=f"Updated metric to version {metric.version}",
                    created_at=now_iso,
                )
                session.add(ver_rec)

                existing.name = metric.name
                existing.description = metric.description
                existing.table_name = metric.table_name
                existing.column_name = metric.column_name
                existing.aggregation = metric.aggregation
                existing.filter_expression = metric.filter_expression
                existing.conditions_json = json.dumps(metric.conditions)
                existing.rules_applied_json = json.dumps(metric.rules_applied)
                existing.version = metric.version
                existing.provenance = metric.provenance
                existing.status = metric.status
                existing.confidence = metric.confidence
                existing.database_identity = metric.database_identity
                existing.updated_at = now_iso
            else:
                rec = MetricRecord(
                    metric_id=metric.metric_id,
                    user_id=metric.user_id,
                    database_identity=metric.database_identity,
                    name=metric.name,
                    description=metric.description,
                    table_name=metric.table_name,
                    column_name=metric.column_name,
                    aggregation=metric.aggregation,
                    filter_expression=metric.filter_expression,
                    conditions_json=json.dumps(metric.conditions),
                    rules_applied_json=json.dumps(metric.rules_applied),
                    version=metric.version,
                    provenance=metric.provenance,
                    status=metric.status,
                    confidence=metric.confidence,
                    created_at=metric.created_at,
                    updated_at=metric.updated_at,
                )
                session.add(rec)
            session.commit()
            return metric
        finally:
            session.close()


def get_metric(metric_id: str, user_id: str, database_identity: str, db_path: Optional[str] = None) -> Optional[BusinessMetric]:
    with _store_lock:
        session = _get_session(db_path)
        try:
            rec = session.query(MetricRecord).filter(
                MetricRecord.metric_id == metric_id,
                MetricRecord.user_id == user_id,
                MetricRecord.database_identity == database_identity,
            ).first()
            if not rec:
                return None
            return BusinessMetric(
                metric_id=rec.metric_id,
                name=rec.name,
                description=rec.description,
                table_name=rec.table_name,
                column_name=rec.column_name,
                aggregation=rec.aggregation,
                filter_expression=rec.filter_expression,
                conditions=json.loads(rec.conditions_json),
                rules_applied=json.loads(rec.rules_applied_json),
                version=rec.version,
                provenance=rec.provenance,
                status=rec.status,
                confidence=rec.confidence,
                user_id=rec.user_id,
                database_identity=rec.database_identity,
                created_at=rec.created_at,
                updated_at=rec.updated_at,
            )
        finally:
            session.close()


def list_metrics(user_id: str, database_identity: str, status: Optional[str] = None, table_name: Optional[str] = None, db_path: Optional[str] = None) -> list[BusinessMetric]:
    with _store_lock:
        session = _get_session(db_path)
        try:
            q = session.query(MetricRecord).filter(
                MetricRecord.user_id == user_id,
                MetricRecord.database_identity == database_identity,
            )
            if status:
                q = q.filter(MetricRecord.status == status)
            if table_name:
                q = q.filter(MetricRecord.table_name == table_name)
            records = q.order_by(desc(MetricRecord.updated_at)).all()
            return [
                BusinessMetric(
                    metric_id=r.metric_id,
                    name=r.name,
                    description=r.description,
                    table_name=r.table_name,
                    column_name=r.column_name,
                    aggregation=r.aggregation,
                    filter_expression=r.filter_expression,
                    conditions=json.loads(r.conditions_json),
                    rules_applied=json.loads(r.rules_applied_json),
                    version=r.version,
                    provenance=r.provenance,
                    status=r.status,
                    confidence=r.confidence,
                    user_id=r.user_id,
                    database_identity=r.database_identity,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                )
                for r in records
            ]
        finally:
            session.close()


# ── Conflict Operations ──────────────────────────────────────────────────────

def save_conflict(conflict: KnowledgeConflict, db_path: Optional[str] = None) -> KnowledgeConflict:
    with _store_lock:
        session = _get_session(db_path)
        try:
            existing = session.query(ConflictRecord).filter(
                ConflictRecord.conflict_id == conflict.conflict_id,
                ConflictRecord.user_id == conflict.user_id,
            ).first()

            if existing:
                existing.status = conflict.status
                existing.resolution_notes = conflict.resolution_notes
                existing.resolved_by = conflict.resolved_by
                existing.resolved_at = conflict.resolved_at
            else:
                rec = ConflictRecord(
                    conflict_id=conflict.conflict_id,
                    user_id=conflict.user_id,
                    database_identity=conflict.database_identity,
                    knowledge_type=conflict.knowledge_type,
                    item_id_a=conflict.item_id_a,
                    item_id_b=conflict.item_id_b,
                    target_name=conflict.target_name,
                    description=conflict.description,
                    statement_a=conflict.statement_a,
                    statement_b=conflict.statement_b,
                    source_a=conflict.source_a,
                    source_b=conflict.source_b,
                    status=conflict.status,
                    resolution_notes=conflict.resolution_notes,
                    resolved_by=conflict.resolved_by,
                    created_at=conflict.created_at,
                    resolved_at=conflict.resolved_at,
                )
                session.add(rec)
            session.commit()
            return conflict
        finally:
            session.close()


def get_conflict(conflict_id: str, user_id: str, database_identity: str = "none", db_path: Optional[str] = None) -> Optional[KnowledgeConflict]:
    with _store_lock:
        session = _get_session(db_path)
        try:
            q = session.query(ConflictRecord).filter(
                ConflictRecord.conflict_id == conflict_id,
                ConflictRecord.user_id == user_id,
            )
            if database_identity and database_identity != "none":
                q = q.filter(ConflictRecord.database_identity == database_identity)
            r = q.first()
            if not r:
                return None
            return KnowledgeConflict(
                conflict_id=r.conflict_id,
                knowledge_type=r.knowledge_type,
                item_id_a=r.item_id_a,
                item_id_b=r.item_id_b,
                target_name=r.target_name,
                description=r.description,
                statement_a=r.statement_a,
                statement_b=r.statement_b,
                source_a=r.source_a,
                source_b=r.source_b,
                status=r.status,
                resolution_notes=r.resolution_notes,
                resolved_by=r.resolved_by,
                user_id=r.user_id,
                database_identity=r.database_identity,
                created_at=r.created_at,
                resolved_at=r.resolved_at,
            )
        finally:
            session.close()


def list_conflicts(user_id: str, database_identity: str, status: Optional[str] = None, db_path: Optional[str] = None) -> list[KnowledgeConflict]:
    with _store_lock:
        session = _get_session(db_path)
        try:
            q = session.query(ConflictRecord).filter(
                ConflictRecord.user_id == user_id,
                ConflictRecord.database_identity == database_identity,
            )
            if status:
                q = q.filter(ConflictRecord.status == status)
            records = q.order_by(desc(ConflictRecord.created_at)).all()
            return [
                KnowledgeConflict(
                    conflict_id=r.conflict_id,
                    knowledge_type=r.knowledge_type,
                    item_id_a=r.item_id_a,
                    item_id_b=r.item_id_b,
                    target_name=r.target_name,
                    description=r.description,
                    statement_a=r.statement_a,
                    statement_b=r.statement_b,
                    source_a=r.source_a,
                    source_b=r.source_b,
                    status=r.status,
                    resolution_notes=r.resolution_notes,
                    resolved_by=r.resolved_by,
                    user_id=r.user_id,
                    database_identity=r.database_identity,
                    created_at=r.created_at,
                    resolved_at=r.resolved_at,
                )
                for r in records
            ]
        finally:
            session.close()


# ── Version History Operations ────────────────────────────────────────────────

def list_versions(item_id: str, user_id: str, database_identity: str, db_path: Optional[str] = None) -> list[KnowledgeVersionRecord]:
    with _store_lock:
        session = _get_session(db_path)
        try:
            records = session.query(VersionRecord).filter(
                VersionRecord.item_id == item_id,
                VersionRecord.user_id == user_id,
                VersionRecord.database_identity == database_identity,
            ).order_by(desc(VersionRecord.version)).all()
            return [
                KnowledgeVersionRecord(
                    version_id=r.version_id,
                    item_id=r.item_id,
                    item_type=r.item_type,
                    version=r.version,
                    snapshot=json.loads(r.snapshot_json),
                    change_summary=r.change_summary,
                    user_id=r.user_id,
                    database_identity=r.database_identity,
                    created_at=r.created_at,
                )
                for r in records
            ]
        finally:
            session.close()


# ── Lifecycle Actions: Confirm, Disable, Resolve ──────────────────────────────

def confirm_knowledge_item(item_id: str, user_id: str, database_identity: str, db_path: Optional[str] = None) -> bool:
    """
    Confirms an unconfirmed or proposed knowledge item (rule, entity, or metric).
    Transitions status to CONFIRMED.
    """
    with _store_lock:
        session = _get_session(db_path)
        try:
            # Check rules
            rule = session.query(RuleRecord).filter(
                RuleRecord.rule_id == item_id,
                RuleRecord.user_id == user_id,
                RuleRecord.database_identity == database_identity,
            ).first()
            if rule:
                rule.status = KnowledgeStatus.CONFIRMED.value
                rule.updated_at = datetime.now(timezone.utc).isoformat()
                session.commit()
                return True

            # Check entities
            entity = session.query(EntityRecord).filter(
                EntityRecord.entity_id == item_id,
                EntityRecord.user_id == user_id,
                EntityRecord.database_identity == database_identity,
            ).first()
            if entity:
                entity.status = KnowledgeStatus.CONFIRMED.value
                entity.updated_at = datetime.now(timezone.utc).isoformat()
                session.commit()
                return True

            # Check metrics
            metric = session.query(MetricRecord).filter(
                MetricRecord.metric_id == item_id,
                MetricRecord.user_id == user_id,
                MetricRecord.database_identity == database_identity,
            ).first()
            if metric:
                metric.status = KnowledgeStatus.CONFIRMED.value
                metric.updated_at = datetime.now(timezone.utc).isoformat()
                session.commit()
                return True

            return False
        finally:
            session.close()


def disable_knowledge_item(item_id: str, user_id: str, database_identity: str, db_path: Optional[str] = None) -> bool:
    """
    Disables an active or proposed knowledge item.
    Transitions status to DISABLED.
    """
    with _store_lock:
        session = _get_session(db_path)
        try:
            rule = session.query(RuleRecord).filter(
                RuleRecord.rule_id == item_id,
                RuleRecord.user_id == user_id,
                RuleRecord.database_identity == database_identity,
            ).first()
            if rule:
                rule.status = KnowledgeStatus.DISABLED.value
                rule.updated_at = datetime.now(timezone.utc).isoformat()
                session.commit()
                return True

            metric = session.query(MetricRecord).filter(
                MetricRecord.metric_id == item_id,
                MetricRecord.user_id == user_id,
                MetricRecord.database_identity == database_identity,
            ).first()
            if metric:
                metric.status = KnowledgeStatus.DISABLED.value
                metric.updated_at = datetime.now(timezone.utc).isoformat()
                session.commit()
                return True

            entity = session.query(EntityRecord).filter(
                EntityRecord.entity_id == item_id,
                EntityRecord.user_id == user_id,
                EntityRecord.database_identity == database_identity,
            ).first()
            if entity:
                entity.status = KnowledgeStatus.DISABLED.value
                entity.updated_at = datetime.now(timezone.utc).isoformat()
                session.commit()
                return True

            return False
        finally:
            session.close()


def resolve_knowledge_conflict(
    conflict_id: str,
    resolution_choice: str,
    resolution_notes: str,
    user_id: str,
    database_identity: str,
    db_path: Optional[str] = None,
) -> bool:
    """
    Resolves a recorded conflict by choosing definition A or B (or disabling both),
    updating the conflict status to RESOLVED.
    """
    with _store_lock:
        session = _get_session(db_path)
        try:
            conflict = session.query(ConflictRecord).filter(
                ConflictRecord.conflict_id == conflict_id,
                ConflictRecord.user_id == user_id,
                ConflictRecord.database_identity == database_identity,
            ).first()
            if not conflict:
                return False

            now_iso = datetime.now(timezone.utc).isoformat()
            conflict.status = "RESOLVED"
            conflict.resolution_notes = resolution_notes
            conflict.resolved_by = user_id
            conflict.resolved_at = now_iso

            # Apply winner/loser status if target items are rules
            if resolution_choice == "CHOOSE_A":
                winner = session.query(RuleRecord).filter(RuleRecord.rule_id == conflict.item_id_a).first()
                loser = session.query(RuleRecord).filter(RuleRecord.rule_id == conflict.item_id_b).first()
                if winner:
                    winner.status = KnowledgeStatus.CONFIRMED.value
                if loser:
                    loser.status = KnowledgeStatus.DISABLED.value
            elif resolution_choice == "CHOOSE_B":
                winner = session.query(RuleRecord).filter(RuleRecord.rule_id == conflict.item_id_b).first()
                loser = session.query(RuleRecord).filter(RuleRecord.rule_id == conflict.item_id_a).first()
                if winner:
                    winner.status = KnowledgeStatus.CONFIRMED.value
                if loser:
                    loser.status = KnowledgeStatus.DISABLED.value

            session.commit()
            return True
        finally:
            session.close()


def get_knowledge_summary(user_id: str, database_identity: str, db_path: Optional[str] = None) -> KnowledgeSummary:
    """
    Returns an aggregated count summary of entities, metrics, rules, and conflicts.
    """
    with _store_lock:
        session = _get_session(db_path)
        try:
            total_entities = session.query(EntityRecord).filter(
                EntityRecord.user_id == user_id,
                EntityRecord.database_identity == database_identity,
            ).count()

            total_metrics = session.query(MetricRecord).filter(
                MetricRecord.user_id == user_id,
                MetricRecord.database_identity == database_identity,
            ).count()

            rules = session.query(RuleRecord).filter(
                RuleRecord.user_id == user_id,
                RuleRecord.database_identity == database_identity,
            ).all()

            total_rules = len(rules)
            confirmed_rules_count = sum(1 for r in rules if r.status in {KnowledgeStatus.CONFIRMED.value, KnowledgeStatus.ACTIVE.value})
            proposed_rules_count = sum(1 for r in rules if r.status == KnowledgeStatus.PROPOSED.value)

            conflicts_count = session.query(ConflictRecord).filter(
                ConflictRecord.user_id == user_id,
                ConflictRecord.database_identity == database_identity,
                ConflictRecord.status == "UNRESOLVED",
            ).count()

            unconfirmed_count = proposed_rules_count + session.query(EntityRecord).filter(
                EntityRecord.user_id == user_id,
                EntityRecord.database_identity == database_identity,
                EntityRecord.status == KnowledgeStatus.PROPOSED.value,
            ).count()

            return KnowledgeSummary(
                total_entities=total_entities,
                total_metrics=total_metrics,
                total_rules=total_rules,
                confirmed_rules_count=confirmed_rules_count,
                proposed_rules_count=proposed_rules_count,
                conflicts_count=conflicts_count,
                unconfirmed_count=unconfirmed_count,
            )
        finally:
            session.close()


def clear_knowledge_store(user_id: Optional[str] = None, db_path: Optional[str] = None):
    """
    Removes cached knowledge for user or resets store in testing.
    """
    with _store_lock:
        session = _get_session(db_path)
        try:
            if user_id:
                session.query(EntityRecord).filter(EntityRecord.user_id == user_id).delete()
                session.query(RuleRecord).filter(RuleRecord.user_id == user_id).delete()
                session.query(MetricRecord).filter(MetricRecord.user_id == user_id).delete()
                session.query(SemanticRecord).filter(SemanticRecord.user_id == user_id).delete()
                session.query(ConflictRecord).filter(ConflictRecord.user_id == user_id).delete()
                session.query(VersionRecord).filter(VersionRecord.user_id == user_id).delete()
            else:
                session.query(EntityRecord).delete()
                session.query(RuleRecord).delete()
                session.query(MetricRecord).delete()
                session.query(SemanticRecord).delete()
                session.query(ConflictRecord).delete()
                session.query(VersionRecord).delete()
            session.commit()
        finally:
            session.close()
