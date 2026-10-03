"""backend/app/intelligence/governance/access_tracker.py

Data Access Traceability for Phase 9.3: Enterprise Governance & Observability.
Provides:
1. SQL query fingerprinting with literal/PII redaction.
2. Table reference extraction and telemetry logging.
3. Strict non-logging of raw result rows or sensitive parameters.
"""

from __future__ import annotations

import re
import uuid
import logging
from typing import List, Optional
from datetime import datetime, timezone

from app.intelligence.governance.models import DataAccessEvent
from app.intelligence.governance.audit_store import save_data_access_event

logger = logging.getLogger(__name__)

# Regex for replacing string literals and numeric literals with '?'
_STRING_LITERAL_REGEX = re.compile(r"'(?:''|[^'])*'")
_NUMBER_LITERAL_REGEX = re.compile(r"\b\d+(?:\.\d+)?\b")
_TABLE_REGEX = re.compile(r"\b(?:FROM|JOIN|INTO|UPDATE)\s+([`\"\[]?[\w_]+[`\"\]]?)", re.IGNORECASE)


class GovernanceAccessTracker:
    """
    Normalizes and logs metadata about database access events without storing sensitive data.
    """

    @classmethod
    def fingerprint_sql(cls, sql: str) -> str:
        """
        Normalizes a SQL statement into a canonical fingerprint:
        Replaces literal values with '?' and collapses redundant whitespace.
        Never exposes raw strings, numbers, or passwords.
        """
        if not sql:
            return ""
        # 1. Redact string literals
        redacted = _STRING_LITERAL_REGEX.sub("?", sql)
        # 2. Redact numeric literals
        redacted = _NUMBER_LITERAL_REGEX.sub("?", redacted)
        # 3. Collapse whitespace
        redacted = re.sub(r"\s+", " ", redacted).strip()
        return redacted

    @classmethod
    def extract_tables_from_sql(cls, sql: str) -> List[str]:
        """
        Extracts table names referenced in FROM / JOIN clauses.
        """
        if not sql:
            return []
        matches = _TABLE_REGEX.findall(sql)
        cleaned = []
        for m in matches:
            tbl = m.strip("`\"[] ")
            if tbl and tbl.upper() not in ("SELECT", "WHERE", "GROUP", "ORDER", "LIMIT") and tbl not in cleaned:
                cleaned.append(tbl)
        return cleaned

    @classmethod
    def log_access(
        cls,
        user_id: str,
        database_identity: str,
        operation: str,
        query_text: str,
        tables: Optional[List[str]] = None,
        is_write: bool = False,
        duration_ms: float = 0.0,
        row_count: Optional[int] = None,
        agent_id: Optional[str] = None,
        status: str = "SUCCESS",
    ) -> DataAccessEvent:
        """
        Constructs and persists a sanitized DataAccessEvent.
        """
        fingerprint = cls.fingerprint_sql(query_text)
        referenced_tables = tables or cls.extract_tables_from_sql(query_text)
        access_id = f"acc_{uuid.uuid4().hex[:8]}"

        event = DataAccessEvent(
            access_id=access_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_id=user_id,
            database_identity=database_identity,
            agent_id=agent_id,
            operation=operation,
            query_fingerprint=fingerprint,
            tables_referenced=referenced_tables,
            is_write=is_write,
            duration_ms=round(duration_ms, 2),
            row_count=row_count,
            status=status,
        )
        return save_data_access_event(event)

    track_query = log_access


DataAccessTracker = GovernanceAccessTracker
