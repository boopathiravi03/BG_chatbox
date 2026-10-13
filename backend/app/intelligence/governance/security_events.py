"""backend/app/intelligence/governance/security_events.py

Security Event Tracking & Telemetry for Phase 9.3: Enterprise Governance & Observability.
Captures authentication anomalies, blocked injection attempts, blocked DDL queries,
cross-tenant violations, and rate-limit violations without false malicious accusations.
"""

from __future__ import annotations

import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from app.intelligence.governance.models import (
    SecurityEventRecord,
    SecurityEventType,
    SecurityEventSeverity,
    GovernanceAuditEvent,
    GovernanceEventType,
    ActorType,
    RiskLevel,
)
from app.intelligence.governance.audit_store import save_security_event, save_audit_event

logger = logging.getLogger(__name__)


class SecurityEventManager:
    """
    Standardized logger for security-relevant operational incidents.
    """

    @classmethod
    def log_security_event(
        cls,
        user_id: str,
        database_identity: str,
        event_type: SecurityEventType,
        severity: SecurityEventSeverity,
        source: str,
        resource: str,
        description: str,
        mitigation: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SecurityEventRecord:
        """
        Creates and stores a SecurityEventRecord and adds a corresponding audit chain entry.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        sec_id = f"sec_{uuid.uuid4().hex[:8]}"

        sec_event = SecurityEventRecord(
            event_id=sec_id,
            timestamp=now_iso,
            user_id=user_id,
            database_identity=database_identity,
            event_type=event_type,
            severity=severity,
            source=source,
            resource=resource,
            description=description,
            status="BLOCKED",
            mitigation=mitigation,
            metadata=metadata or {},
        )
        save_security_event(sec_event)

        # Cross-log into tamper-evident governance audit chain
        audit_event = GovernanceAuditEvent(
            event_id=f"ev_{uuid.uuid4().hex[:8]}",
            timestamp=now_iso,
            user_id=user_id,
            database_identity=database_identity,
            event_type=GovernanceEventType.SECURITY_EVENT,
            resource_type="SECURITY_SUBSYSTEM",
            resource_id=sec_id,
            actor_type=ActorType.SYSTEM,
            action=event_type.value,
            result="BLOCKED",
            risk_level=RiskLevel.HIGH if severity in (SecurityEventSeverity.HIGH, SecurityEventSeverity.CRITICAL) else RiskLevel.MEDIUM,
            metadata={"security_event_id": sec_id, "severity": severity.value, "description": description},
        )
        save_audit_event(audit_event)

        logger.warning(f"Security event recorded [{severity.value}]: {description} (source: {source})")
        return sec_event

    @classmethod
    def log_prompt_injection(
        cls,
        user_id: str,
        database_identity: str,
        pattern: str,
        source: str = "orchestration_safety_gate",
    ) -> SecurityEventRecord:
        return cls.log_security_event(
            user_id=user_id,
            database_identity=database_identity,
            event_type=SecurityEventType.INJECTION_PATTERN_DETECTED,
            severity=SecurityEventSeverity.HIGH,
            source=source,
            resource="GOAL_INPUT",
            description=f"Instruction override pattern detected: '{pattern}'",
            mitigation="Neutralized instruction text and treated user input as raw literal data.",
            metadata={"detected_pattern": pattern},
        )

    @classmethod
    def log_ddl_blocked(
        cls,
        user_id: str,
        database_identity: str,
        operation: str,
        source: str = "sql_safety_gate",
    ) -> SecurityEventRecord:
        return cls.log_security_event(
            user_id=user_id,
            database_identity=database_identity,
            event_type=SecurityEventType.DDL_BLOCKED,
            severity=SecurityEventSeverity.CRITICAL,
            source=source,
            resource="DATABASE_SCHEMA",
            description=f"Prohibited DDL schema destruction attempt: '{operation}'",
            mitigation="Denied operation via sys_sql_ddl_safety policy.",
            metadata={"attempted_sql": operation},
        )

    @classmethod
    def log_auth_failure(
        cls,
        user_id: str,
        database_identity: str,
        reason: str,
    ) -> SecurityEventRecord:
        return cls.log_security_event(
            user_id=user_id,
            database_identity=database_identity,
            event_type=SecurityEventType.AUTH_FAILURE,
            severity=SecurityEventSeverity.HIGH,
            source="auth_guard",
            resource="API_AUTH",
            description=f"Authentication validation failed: {reason}",
            mitigation="Rejected token and revoked session permissions.",
            metadata={"reason": reason},
        )

    @classmethod
    def log_cross_tenant_attempt(
        cls,
        user_id: str,
        target_tenant: str,
        resource: str,
    ) -> SecurityEventRecord:
        return cls.log_security_event(
            user_id=user_id,
            database_identity="cross_tenant",
            event_type=SecurityEventType.CROSS_TENANT_BLOCKED,
            severity=SecurityEventSeverity.CRITICAL,
            source="tenant_isolation_boundary",
            resource=resource,
            description=f"Cross-tenant access attempted by user {user_id} targeting tenant {target_tenant}",
            mitigation="Blocked request and reported boundary violation.",
            metadata={"attempting_user": user_id, "target_tenant": target_tenant},
        )

    @classmethod
    def log_rate_limit(
        cls,
        user_id: str,
        database_identity: str,
        endpoint: str,
        source_ip: str = "unknown",
    ) -> SecurityEventRecord:
        return cls.log_security_event(
            user_id=user_id,
            database_identity=database_identity,
            event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
            severity=SecurityEventSeverity.MEDIUM,
            source="rate_limiter",
            resource=endpoint,
            description=f"Operation rate limit exceeded for endpoint: {endpoint}",
            mitigation="Returned HTTP 429 Too Many Requests.",
            metadata={"endpoint": endpoint, "source_ip": source_ip},
        )

    @classmethod
    def log_ip_threat(
        cls,
        user_id: str,
        database_identity: str,
        event_type: SecurityEventType,
        severity: SecurityEventSeverity,
        source_ip: str,
        resource: str,
        description: str,
        mitigation: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SecurityEventRecord:
        meta = metadata or {}
        meta["source_ip"] = source_ip
        return cls.log_security_event(
            user_id=user_id,
            database_identity=database_identity,
            event_type=event_type,
            severity=severity,
            source="intrusion_detector",
            resource=resource,
            description=description,
            mitigation=mitigation,
            metadata=meta,
        )

    @classmethod
    def log_brute_force(
        cls,
        user_id: str,
        source_ip: str,
        attempt_count: int,
        target_account: str,
    ) -> SecurityEventRecord:
        return cls.log_ip_threat(
            user_id=user_id,
            database_identity="auth_subsystem",
            event_type=SecurityEventType.BRUTE_FORCE_DETECTED,
            severity=SecurityEventSeverity.HIGH,
            source_ip=source_ip,
            resource="/auth/login",
            description=f"Repeated authentication failures detected from {source_ip} targeting account '{target_account}'. Observed {attempt_count} failures.",
            mitigation="Temporary exponential delay applied to source IP.",
            metadata={"attempt_count": attempt_count, "target_account": target_account},
        )

    @classmethod
    def log_endpoint_scan(
        cls,
        user_id: str,
        source_ip: str,
        probed_endpoints: List[str],
    ) -> SecurityEventRecord:
        return cls.log_ip_threat(
            user_id=user_id,
            database_identity="api_gateway",
            event_type=SecurityEventType.ENDPOINT_SCAN_DETECTED,
            severity=SecurityEventSeverity.MEDIUM,
            source_ip=source_ip,
            resource="API_ROUTER",
            description=f"Automated path scanning pattern detected from {source_ip} probing {len(probed_endpoints)} unmapped endpoints.",
            mitigation="Enforced request throttling on scanning IP.",
            metadata={"probed_count": len(probed_endpoints), "probed_sample": probed_endpoints[:5]},
        )

