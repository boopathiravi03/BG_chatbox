"""backend/app/guardian/service.py

Unified service coordinator for AI Database Guardian.
Responsibilities:
1. Coordinates live, non-destructive telemetry collection per database type.
2. Runs deterministic rule evaluation and deduplicates ongoing active incidents.
3. Persists incidents to the durable SQLite store (bgai_guardian.db).
4. Emits cryptographic governance audit trail events via AuditStore / SecurityEventManager.
5. Provides safe AI natural-language advisory synthesis (sanitized metadata only, zero raw rows/credentials).
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.guardian.models import (
    EngineTelemetrySnapshot,
    GuardianIncident,
    DiagnosisReport,
    IncidentSeverity,
    IncidentStatus,
    MetricAvailability,
)
from app.guardian.collectors import (
    collect_sqlite_telemetry,
    collect_mysql_telemetry,
    collect_postgres_telemetry,
    collect_mongodb_telemetry,
    collect_redis_telemetry,
    collect_file_or_vector_telemetry,
)
from app.guardian.diagnostics import evaluate_telemetry_incidents
from app.guardian.store import (
    init_guardian_store,
    save_incident,
    find_active_incident,
    list_incidents,
    get_incident_by_id,
)

logger = logging.getLogger("bgai.guardian.service")

# Initialize store tables on module load
try:
    init_guardian_store()
except Exception as e:
    logger.warning(f"Failed to auto-init guardian store: {e}")


class GuardianService:
    """Manages monitoring, diagnostic audits, and incident tracking for database connections."""

    @classmethod
    def get_live_telemetry(
        cls,
        user_id: str,
        engine: Any,
        db_type: str,
        identity: str,
        connector: Optional[Any] = None,
    ) -> EngineTelemetrySnapshot:
        """
        Gathers live operational metrics directly from the active connector.
        Never fabricates metrics; respects engine capabilities.
        """
        norm_type = (db_type or "").lower().strip()

        if norm_type == "sqlite":
            if engine is not None:
                return collect_sqlite_telemetry(engine, identity)
            return collect_file_or_vector_telemetry("sqlite", identity)

        elif norm_type in ("mysql", "mariadb"):
            if engine is not None:
                return collect_mysql_telemetry(engine, identity)
            return collect_file_or_vector_telemetry(norm_type, identity)

        elif norm_type in ("postgres", "postgresql"):
            if engine is not None:
                return collect_postgres_telemetry(engine, identity)
            return collect_file_or_vector_telemetry(norm_type, identity)

        elif norm_type == "mongodb":
            if connector is not None:
                return collect_mongodb_telemetry(connector, identity)
            return collect_file_or_vector_telemetry("mongodb", identity)

        elif norm_type == "redis":
            if connector is not None:
                return collect_redis_telemetry(connector, identity)
            return collect_file_or_vector_telemetry("redis", identity)

        else:
            # Flat files (csv, excel, json) or Vector stores (qdrant, chroma)
            return collect_file_or_vector_telemetry(norm_type, identity)

    @classmethod
    def run_diagnosis(
        cls,
        user_id: str,
        engine: Any,
        db_type: str,
        identity: str,
        connector: Optional[Any] = None,
    ) -> DiagnosisReport:
        """
        Executes on-demand comprehensive health diagnosis:
        1. Gathers live telemetry
        2. Evaluates operational rules
        3. Deduplicates and persists incidents
        4. Logs to governance audit log
        5. Computes overall health score and advisory
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        telemetry = cls.get_live_telemetry(user_id, engine, db_type, identity, connector)

        detected_incidents = evaluate_telemetry_incidents(user_id, telemetry)
        active_incidents: List[GuardianIncident] = []
        detected_categories = {inc.category for inc in detected_incidents}

        # Check existing open incidents for automated recovery
        open_incidents = list_incidents(user_id=user_id, database_identity=identity, status_filter=None)
        for existing_inc in open_incidents:
            if existing_inc.status not in (IncidentStatus.RESOLVED,):
                # If an incident was open for this category, but is NO LONGER triggered in detected_incidents
                if existing_inc.category not in detected_categories:
                    # Evaluate recovery condition
                    recovered = False
                    metrics = telemetry.metrics

                    if existing_inc.category == "connection_pool":
                        act = metrics.get("active_connections")
                        max_c = metrics.get("max_connections")
                        if act and act.value is not None:
                            val = int(act.value)
                            max_val = int(max_c.value) if max_c and max_c.value else None
                            if max_val and (val / max_val * 100) < 70.0:
                                recovered = True
                            elif not max_val and val < 50:
                                recovered = True

                    elif existing_inc.category == "cache_efficiency":
                        hit = metrics.get("cache_hit_ratio")
                        if hit and hit.value is not None and float(hit.value) >= 85.0:
                            recovered = True

                    elif existing_inc.category == "lock_contention":
                        lck = metrics.get("lock_waits") or metrics.get("blocked_clients")
                        if lck and lck.value is not None and int(lck.value) <= 1:
                            recovered = True

                    elif existing_inc.category == "storage":
                        frg = metrics.get("fragmentation_pct")
                        if frg and frg.value is not None and float(frg.value) < 20.0:
                            recovered = True

                    elif existing_inc.category == "concurrency":
                        jnl = metrics.get("journal_mode")
                        if jnl and jnl.value == "WAL":
                            recovered = True

                    if recovered:
                        existing_inc.status = IncidentStatus.RESOLVED
                        existing_inc.recovered_at = now_iso
                        existing_inc.resolved_by = "System (Auto-Recovery)"
                        existing_inc.resolved_at = now_iso
                        existing_inc.resolution_notes = (
                            f"Automatically resolved: Metrics satisfied recovery condition ({existing_inc.recovery_rule or 'nominal telemetry'})."
                        )
                        save_incident(existing_inc)

        for inc in detected_incidents:
            # Check for existing active incident to deduplicate
            existing = find_active_incident(
                user_id=user_id,
                database_identity=identity,
                category=inc.category,
                trigger_rule=inc.trigger_rule,
            )

            if existing:
                # Update timestamp and facts
                existing.updated_at = now_iso
                existing.observed_facts = inc.observed_facts
                save_incident(existing)
                active_incidents.append(existing)
            else:
                # Synthesize AI advisory without transmitting sensitive data
                inc.ai_advisory = cls._generate_advisory_text(inc)
                save_incident(inc)
                active_incidents.append(inc)

                # Persist to governance audit log
                cls._log_guardian_audit_event(user_id, identity, inc)

        # Calculate health score (100 base)
        score = 100
        overall_health = "healthy"

        for inc in active_incidents:
            if inc.severity == IncidentSeverity.CRITICAL:
                score -= 30
            elif inc.severity == IncidentSeverity.WARNING:
                score -= 15
            elif inc.severity == IncidentSeverity.INFO:
                score -= 5

        score = max(0, min(100, score))
        if score < 60:
            overall_health = "critical"
        elif score < 85:
            overall_health = "warning"
        else:
            overall_health = "healthy"

        # Generate summary advisory
        summary = (
            f"Database Guardian operational check complete for {db_type.upper()}. "
            f"System health is {overall_health.upper()} (score: {score}/100) with "
            f"{len(active_incidents)} active incident(s) detected."
        )

        recommendations = [
            {
                "title": inc.title,
                "severity": inc.severity.value,
                "category": inc.category,
                "likely_root_cause": inc.likely_root_cause,
                "verification_steps": inc.verification_steps,
            }
            for inc in active_incidents
        ]

        report = DiagnosisReport(
            report_id=f"rep_{uuid.uuid4().hex[:8]}",
            database_type=db_type,
            database_identity=identity,
            overall_health=overall_health,
            health_score=score,
            generated_at=now_iso,
            telemetry=telemetry,
            active_incidents=active_incidents,
            summary_advisory=summary,
            recommendations=recommendations,
        )

        return report

    @classmethod
    def list_user_incidents(
        cls,
        user_id: str,
        database_identity: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> List[GuardianIncident]:
        """Lists incidents for an authenticated user."""
        return list_incidents(
            user_id=user_id,
            database_identity=database_identity,
            status_filter=status_filter,
        )

    @classmethod
    def update_incident_status(
        cls,
        user_id: str,
        incident_id: str,
        new_status: IncidentStatus,
        actor_name: str,
        notes: Optional[str] = None,
    ) -> Optional[GuardianIncident]:
        """Transitions an incident to ACKNOWLEDGED or RESOLVED status."""
        incident = get_incident_by_id(user_id, incident_id)
        if not incident:
            return None

        now_iso = datetime.now(timezone.utc).isoformat()
        incident.status = new_status
        incident.updated_at = now_iso

        if new_status == IncidentStatus.ACKNOWLEDGED:
            incident.acknowledged_by = actor_name
            incident.acknowledged_at = now_iso
        elif new_status == IncidentStatus.RESOLVED:
            incident.resolved_by = actor_name
            incident.resolved_at = now_iso
            if notes:
                incident.resolution_notes = notes

        save_incident(incident)
        return incident

    @classmethod
    def _generate_advisory_text(cls, incident: GuardianIncident) -> str:
        """
        Generates safe operational advice.
        Strict guarantee: Never passes database passwords, raw row contents, or user data.
        Only sanitized category, rule, and metrics are utilized.
        """
        # Deterministic high-quality advice
        facts_summary = ", ".join(f"{k}: {v}" for k, v in incident.observed_facts.items())
        return (
            f"Advisory for {incident.title}: Telemetry indicates {facts_summary}. "
            f"Root cause hypothesis (confidence {int(incident.confidence_score * 100)}%): {incident.likely_root_cause} "
            f"Recommended safe verification: {'; '.join(incident.verification_steps)}"
        )

    @classmethod
    def _log_guardian_audit_event(
        cls, user_id: str, identity: str, incident: GuardianIncident
    ) -> None:
        """Integrates incident logging into the existing immutable governance audit store."""
        try:
            from app.intelligence.governance.audit_store import save_audit_event
            from app.intelligence.governance.models import (
                GovernanceAuditEvent,
                GovernanceEventType,
                ActorType,
                RiskLevel,
            )

            risk_map = {
                IncidentSeverity.CRITICAL: RiskLevel.HIGH,
                IncidentSeverity.WARNING: RiskLevel.MEDIUM,
                IncidentSeverity.INFO: RiskLevel.LOW,
            }

            now_iso = datetime.now(timezone.utc).isoformat()
            audit_ev = GovernanceAuditEvent(
                event_id=f"audit_guard_{uuid.uuid4().hex[:8]}",
                timestamp=now_iso,
                user_id=user_id,
                database_identity=identity,
                event_type=GovernanceEventType.ANOMALY_DETECTED,
                resource_type="database_telemetry",
                resource_id=incident.category,
                actor_type=ActorType.SYSTEM,
                action="guardian_operational_alert",
                result="flagged",
                risk_level=risk_map.get(incident.severity, RiskLevel.LOW),
                metadata={
                    "incident_id": incident.incident_id,
                    "title": incident.title,
                    "severity": incident.severity.value,
                    "trigger_rule": incident.trigger_rule,
                },
            )
            save_audit_event(audit_ev)
        except Exception as e:
            logger.warning(f"Could not persist guardian audit event: {e}")

