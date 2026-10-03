"""
backend/app/intelligence/actions/models.py

Phase 8.8: Controlled Business Actions & Action Intelligence Models
Defines structured, strongly typed data contracts for action proposals,
validation, impact previews, human confirmation, execution, verification, and audit.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ActionType(str, Enum):
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class ActionStatus(str, Enum):
    # Progression states
    PROPOSED = "PROPOSED"
    VALIDATING = "VALIDATING"
    READY_FOR_CONFIRMATION = "READY_FOR_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    EXECUTING = "EXECUTING"
    EXECUTED = "EXECUTED"
    VERIFIED = "VERIFIED"

    # Terminal / failure states
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    BLOCKED = "BLOCKED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    CANCELLED = "CANCELLED"


class ActionRisk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCKED = "BLOCKED"


@dataclass
class ActionTarget:
    table: str
    columns: list[str] = field(default_factory=list)
    condition_sql: Optional[str] = None
    condition_params: dict[str, Any] = field(default_factory=dict)
    primary_keys: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "columns": list(self.columns),
            "condition_sql": self.condition_sql,
            "condition_params": dict(self.condition_params),
            "primary_keys": list(self.primary_keys),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ActionTarget":
        return cls(
            table=d.get("table", ""),
            columns=list(d.get("columns", [])),
            condition_sql=d.get("condition_sql"),
            condition_params=dict(d.get("condition_params", {})),
            primary_keys=list(d.get("primary_keys", [])),
        )


@dataclass
class ActionChange:
    column: str
    current_value: Any = None
    proposed_value: Any = None
    value_type: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "column": self.column,
            "current_value": self.current_value,
            "proposed_value": self.proposed_value,
            "value_type": self.value_type,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ActionChange":
        return cls(
            column=d.get("column", ""),
            current_value=d.get("current_value"),
            proposed_value=d.get("proposed_value"),
            value_type=d.get("value_type"),
        )


@dataclass
class ActionImpact:
    estimated_rows: int = 0
    actual_preview_rows: int = 0
    current_sample_records: list[dict[str, Any]] = field(default_factory=list)
    proposed_sample_records: list[dict[str, Any]] = field(default_factory=list)
    related_records_count: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    is_excessive: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimated_rows": self.estimated_rows,
            "actual_preview_rows": self.actual_preview_rows,
            "current_sample_records": self.current_sample_records,
            "proposed_sample_records": self.proposed_sample_records,
            "related_records_count": dict(self.related_records_count),
            "warnings": list(self.warnings),
            "is_excessive": self.is_excessive,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ActionImpact":
        return cls(
            estimated_rows=d.get("estimated_rows", 0),
            actual_preview_rows=d.get("actual_preview_rows", 0),
            current_sample_records=d.get("current_sample_records", []),
            proposed_sample_records=d.get("proposed_sample_records", []),
            related_records_count=dict(d.get("related_records_count", {})),
            warnings=list(d.get("warnings", [])),
            is_excessive=d.get("is_excessive", False),
        )


@dataclass
class ActionValidation:
    is_valid: bool = False
    reasons: list[str] = field(default_factory=list)
    blocked_reason: Optional[str] = None
    passed_checks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "reasons": list(self.reasons),
            "blocked_reason": self.blocked_reason,
            "passed_checks": list(self.passed_checks),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ActionValidation":
        return cls(
            is_valid=d.get("is_valid", False),
            reasons=list(d.get("reasons", [])),
            blocked_reason=d.get("blocked_reason"),
            passed_checks=list(d.get("passed_checks", [])),
        )


@dataclass
class ActionConfirmation:
    confirmation_token: str
    confirmed_by: str
    confirmed_at: str
    expires_at: str
    high_risk_acknowledged: bool = False
    is_expired: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "confirmation_token": self.confirmation_token,
            "confirmed_by": self.confirmed_by,
            "confirmed_at": self.confirmed_at,
            "expires_at": self.expires_at,
            "high_risk_acknowledged": self.high_risk_acknowledged,
            "is_expired": self.is_expired,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ActionConfirmation":
        return cls(
            confirmation_token=d.get("confirmation_token", ""),
            confirmed_by=d.get("confirmed_by", ""),
            confirmed_at=d.get("confirmed_at", ""),
            expires_at=d.get("expires_at", ""),
            high_risk_acknowledged=d.get("high_risk_acknowledged", False),
            is_expired=d.get("is_expired", False),
        )


@dataclass
class ActionExecutionResult:
    success: bool
    action_id: str
    status: str
    actual_rows_affected: int = 0
    executed_at: str = ""
    error: Optional[str] = None
    transaction_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "action_id": self.action_id,
            "status": self.status,
            "actual_rows_affected": self.actual_rows_affected,
            "executed_at": self.executed_at,
            "error": self.error,
            "transaction_id": self.transaction_id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ActionExecutionResult":
        return cls(
            success=d.get("success", False),
            action_id=d.get("action_id", ""),
            status=d.get("status", ""),
            actual_rows_affected=d.get("actual_rows_affected", 0),
            executed_at=d.get("executed_at", ""),
            error=d.get("error"),
            transaction_id=d.get("transaction_id", ""),
        )


@dataclass
class ActionVerification:
    verified: bool
    verification_sql: str
    expected_value: Any = None
    actual_value: Any = None
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "verified": self.verified,
            "verification_sql": self.verification_sql,
            "expected_value": self.expected_value,
            "actual_value": self.actual_value,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ActionVerification":
        return cls(
            verified=d.get("verified", False),
            verification_sql=d.get("verification_sql", ""),
            expected_value=d.get("expected_value"),
            actual_value=d.get("actual_value"),
            details=d.get("details", ""),
        )


@dataclass
class ActionAuditRecord:
    audit_id: str
    action_id: str
    user_id: str
    timestamp: str
    action_type: str
    target_table: str
    target_columns: list[str] = field(default_factory=list)
    reason: str = ""
    source_signal: Optional[str] = None
    risk: str = "LOW"
    affected_rows: int = 0
    confirmation_token: Optional[str] = None
    execution_status: str = "UNKNOWN"
    verification_status: str = "UNVERIFIED"
    error: Optional[str] = None
    database_identity: str = "none"

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "action_id": self.action_id,
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "action_type": self.action_type,
            "target_table": self.target_table,
            "target_columns": list(self.target_columns),
            "reason": self.reason,
            "source_signal": self.source_signal,
            "risk": self.risk,
            "affected_rows": self.affected_rows,
            "confirmation_token": self.confirmation_token,
            "execution_status": self.execution_status,
            "verification_status": self.verification_status,
            "error": self.error,
            "database_identity": self.database_identity,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ActionAuditRecord":
        return cls(
            audit_id=d.get("audit_id", ""),
            action_id=d.get("action_id", ""),
            user_id=d.get("user_id", ""),
            timestamp=d.get("timestamp", ""),
            action_type=d.get("action_type", ""),
            target_table=d.get("target_table", ""),
            target_columns=list(d.get("target_columns", [])),
            reason=d.get("reason", ""),
            source_signal=d.get("source_signal"),
            risk=d.get("risk", "LOW"),
            affected_rows=d.get("affected_rows", 0),
            confirmation_token=d.get("confirmation_token"),
            execution_status=d.get("execution_status", "UNKNOWN"),
            verification_status=d.get("verification_status", "UNVERIFIED"),
            error=d.get("error"),
            database_identity=d.get("database_identity", "none"),
        )


@dataclass
class ActionProposal:
    action_id: str
    user_id: str
    action_type: str  # INSERT, UPDATE, DELETE
    status: str = ActionStatus.PROPOSED.value
    target: ActionTarget = field(default_factory=lambda: ActionTarget(table=""))
    changes: list[ActionChange] = field(default_factory=list)
    reason: str = ""
    source_signal_id: Optional[str] = None
    risk: str = ActionRisk.LOW.value
    sql_preview: str = ""
    parameterized_sql: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    verification_sql: Optional[str] = None
    expected_verification_result: Optional[str] = None
    validation: Optional[ActionValidation] = None
    impact: Optional[ActionImpact] = None
    confirmation: Optional[ActionConfirmation] = None
    execution_result: Optional[ActionExecutionResult] = None
    verification: Optional[ActionVerification] = None
    created_at: str = ""
    updated_at: str = ""
    database_identity: str = "none"

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "user_id": self.user_id,
            "action_type": self.action_type,
            "status": self.status,
            "target": self.target.to_dict() if self.target else None,
            "changes": [c.to_dict() for c in self.changes],
            "reason": self.reason,
            "source_signal_id": self.source_signal_id,
            "risk": self.risk,
            "sql_preview": self.sql_preview,
            "parameterized_sql": self.parameterized_sql,
            "parameters": dict(self.parameters),
            "verification_sql": self.verification_sql,
            "expected_verification_result": self.expected_verification_result,
            "validation": self.validation.to_dict() if self.validation else None,
            "impact": self.impact.to_dict() if self.impact else None,
            "confirmation": self.confirmation.to_dict() if self.confirmation else None,
            "execution_result": self.execution_result.to_dict() if self.execution_result else None,
            "verification": self.verification.to_dict() if self.verification else None,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "database_identity": self.database_identity,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ActionProposal":
        return cls(
            action_id=d.get("action_id", ""),
            user_id=d.get("user_id", ""),
            action_type=d.get("action_type", ActionType.UPDATE.value),
            status=d.get("status", ActionStatus.PROPOSED.value),
            target=ActionTarget.from_dict(d.get("target", {})) if d.get("target") else ActionTarget(table=""),
            changes=[ActionChange.from_dict(c) for c in d.get("changes", [])],
            reason=d.get("reason", ""),
            source_signal_id=d.get("source_signal_id"),
            risk=d.get("risk", ActionRisk.LOW.value),
            sql_preview=d.get("sql_preview", ""),
            parameterized_sql=d.get("parameterized_sql", ""),
            parameters=dict(d.get("parameters", {})),
            verification_sql=d.get("verification_sql"),
            expected_verification_result=d.get("expected_verification_result"),
            validation=ActionValidation.from_dict(d.get("validation", {})) if d.get("validation") else None,
            impact=ActionImpact.from_dict(d.get("impact", {})) if d.get("impact") else None,
            confirmation=ActionConfirmation.from_dict(d.get("confirmation", {})) if d.get("confirmation") else None,
            execution_result=ActionExecutionResult.from_dict(d.get("execution_result", {})) if d.get("execution_result") else None,
            verification=ActionVerification.from_dict(d.get("verification", {})) if d.get("verification") else None,
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            database_identity=d.get("database_identity", "none"),
        )
