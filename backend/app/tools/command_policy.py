"""backend/app/tools/command_policy.py

Centralized, dialect-aware command policy engine for BG AI 2.0.
Classifies and validates SQL and native database commands by impact, dialect,
connection capabilities, and safety boundaries.

Supported categories:
1. READ: SELECT, joins, CTEs, subqueries, EXPLAIN, safe metadata queries.
2. DATA_MUTATION: INSERT, UPDATE, DELETE, upsert/merge, and bulk data mutations.
3. SCHEMA_CHANGE: CREATE, ALTER ADD/RENAME, indexes, views, constraints.
4. DESTRUCTIVE_DDL: DROP, TRUNCATE, ALTER DROP, and equivalent destructive operations.
5. ADMINISTRATION: GRANT, REVOKE, maintenance (VACUUM, ANALYZE, OPTIMIZE), database management.
6. TRANSACTION_CONTROL: BEGIN, START TRANSACTION, COMMIT, ROLLBACK, SAVEPOINT.
7. NATIVE_CONNECTOR_OPERATION: validated MongoDB, Redis, Qdrant, Chroma operations.
8. PROHIBITED_SYSTEM: ATTACH/DETACH arbitrary files, external process execution, host escapes.
"""

from __future__ import annotations

import re
import json
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

try:
    import sqlparse
    from sqlparse.sql import Statement, Token, TokenList
    from sqlparse import tokens as T
    HAS_SQLPARSE = True
except ImportError:
    HAS_SQLPARSE = False


class CommandCategory(str, Enum):
    READ = "READ"
    DATA_MUTATION = "DATA_MUTATION"
    SCHEMA_CHANGE = "SCHEMA_CHANGE"
    DESTRUCTIVE_DDL = "DESTRUCTIVE_DDL"
    ADMINISTRATION = "ADMINISTRATION"
    TRANSACTION_CONTROL = "TRANSACTION_CONTROL"
    NATIVE_CONNECTOR_OPERATION = "NATIVE_CONNECTOR_OPERATION"
    PROHIBITED_SYSTEM = "PROHIBITED_SYSTEM"

    # Backward compatibility aliases
    MUTATION = "DATA_MUTATION"
    HIGH_IMPACT_MUTATION = "DATA_MUTATION"
    DDL_STRUCTURE = "SCHEMA_CHANGE"
    DDL_DESTRUCTIVE = "DESTRUCTIVE_DDL"
    TRANSACTION = "TRANSACTION_CONTROL"
    ADMINISTRATIVE = "ADMINISTRATION"


@dataclass
class PolicyValidationResult:
    allowed: bool
    operation: str
    category: CommandCategory
    requires_confirmation: bool
    is_high_risk: bool
    target_objects: List[str] = field(default_factory=list)
    primary_table: Optional[str] = None
    estimated_affected_rows: Optional[int] = None
    impact_summary: str = ""
    rollback_supported: bool = True
    rollback_limitations: str = ""
    reason: Optional[str] = None
    dialect_notes: Optional[str] = None
    fingerprint: Optional[str] = None
    clean_sql: str = ""
    dangerous: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "operation": self.operation.lower(),
            "category": self.category.value,
            "requires_confirmation": self.requires_confirmation,
            "is_high_risk": self.is_high_risk,
            "target_objects": self.target_objects,
            "primary_table": self.primary_table,
            "estimated_affected_rows": self.estimated_affected_rows,
            "impact_summary": self.impact_summary,
            "rollback_supported": self.rollback_supported,
            "rollback_limitations": self.rollback_limitations,
            "reason": self.reason,
            "dialect_notes": self.dialect_notes,
            "fingerprint": self.fingerprint,
            "clean_sql": self.clean_sql,
            "dangerous": self.dangerous,
        }


# Dangerous administrative commands that compromise host or escape database boundaries
PROHIBITED_SYSTEM_PATTERNS = [
    re.compile(r"\bATTACH\s+(?:DATABASE\s+)?['\"`\[]", re.I),
    re.compile(r"\bDETACH\s+(?:DATABASE\s+)?", re.I),
    re.compile(r"\bLOAD\s+DATA\s+(?:LOCAL\s+)?INFILE\b", re.I),
    re.compile(r"\bINTO\s+(?:OUTFILE|DUMPFILE)\b", re.I),
    re.compile(r"\b(?:EXEC|EXECUTE)\s+(?:xp_\w*|sp_configure|sp_makewebtask)\b", re.I),
    re.compile(r"\bSHUTDOWN\b", re.I),
    re.compile(r"\bCOPY\s+.*?FROM\s+PROGRAM\b", re.I),
]

# Trivial WHERE patterns (where condition always evaluates to true)
TRIVIAL_WHERE_PATTERNS = [
    re.compile(r"^\s*1\s*=\s*1\s*$", re.I),
    re.compile(r"^\s*0\s*=\s*0\s*$", re.I),
    re.compile(r"^\s*true\s*$", re.I),
    re.compile(r"^\s*1\s*$", re.I),
    re.compile(r"^\s*['\"]1['\"]\s*=\s*['\"]1['\"]\s*$", re.I),
    re.compile(r"^\s*['\"]a['\"]\s*=\s*['\"]a['\"]\s*$", re.I),
]


class CommandPolicy:
    """
    Centralized command execution policy validator and classifier.
    """

    @classmethod
    def clean_sql(cls, sql: str) -> str:
        """Strip SQL comments and extraneous whitespace while preserving string contents."""
        if not sql or not isinstance(sql, str):
            return ""
        # Remove /* ... */ multi-line comments
        cleaned = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
        # Remove -- ... single-line comments
        cleaned = re.sub(r"--[^\n]*", " ", cleaned)
        return cleaned.strip()

    @classmethod
    def has_multiple_statements(cls, sql: str) -> bool:
        """
        Check if query contains multiple executable SQL statements.
        Handles semicolons within string literals and quoted identifiers safely.
        """
        cleaned = cls.clean_sql(sql)
        if not cleaned:
            return False

        # Dialect-safe semicolon check outside quotes and comments
        in_single = False
        in_double = False
        in_backtick = False
        in_bracket = False
        i = 0
        n = len(cleaned)
        statements_found = 0
        has_content = False

        while i < n:
            ch = cleaned[i]

            if ch == "'" and not in_double and not in_backtick and not in_bracket:
                if in_single and i + 1 < n and cleaned[i + 1] == "'":
                    i += 2
                    continue
                in_single = not in_single
            elif ch == '"' and not in_single and not in_backtick and not in_bracket:
                in_double = not in_double
            elif ch == '`' and not in_single and not in_double and not in_bracket:
                in_backtick = not in_backtick
            elif ch == '[' and not in_single and not in_double and not in_backtick:
                in_bracket = True
            elif ch == ']' and in_bracket:
                in_bracket = False
            elif ch == ';' and not in_single and not in_double and not in_backtick and not in_bracket:
                if has_content:
                    statements_found += 1
                    has_content = False
            elif not ch.isspace():
                has_content = True

            i += 1

        if has_content:
            statements_found += 1

        return statements_found > 1

    @classmethod
    def _extract_root_operation(cls, cleaned_sql: str) -> Tuple[str, str]:
        """
        Extract the root keyword and primary operation, properly handling CTEs (WITH ...).
        Returns (root_keyword, full_context_phrase).
        """
        if HAS_SQLPARSE:
            parsed = sqlparse.parse(cleaned_sql)
            if parsed:
                stmt = parsed[0]
                stmt_type = stmt.get_type()
                first_token = stmt.token_first(skip_ws=True, skip_cm=True)
                ft_val = str(first_token).upper() if first_token else ""

                if ft_val == "WITH":
                    for tok in stmt.tokens:
                        if tok.is_keyword and tok.value.upper() in (
                            "SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP"
                        ):
                            return tok.value.upper(), ft_val
                    if stmt_type and stmt_type != "UNKNOWN":
                        return stmt_type.upper(), ft_val
                    return "SELECT", ft_val

                if stmt_type and stmt_type != "UNKNOWN":
                    return stmt_type.upper(), ft_val

                if ft_val:
                    return ft_val, ft_val

        # Fallback extraction
        tokens = cleaned_sql.split()
        if not tokens:
            return "", ""
        first_word = tokens[0].upper()
        if first_word == "WITH":
            for verb in ("INSERT", "UPDATE", "DELETE", "SELECT"):
                if re.search(rf"\b{verb}\b", cleaned_sql, re.I):
                    return verb, first_word
            return "SELECT", first_word

        return first_word, first_word

    @classmethod
    def _validate_nonrelational(
        cls,
        cmd_text: str,
        dialect: str,
        connector: Optional[Any] = None,
        user_id: Optional[str] = None,
    ) -> PolicyValidationResult:
        """
        Validates native non-relational operations for MongoDB, Redis, and Vector connectors.
        """
        clean = cmd_text.strip()
        is_read_only = getattr(connector, "is_read_only", False)
        conn_name = getattr(connector, "name", dialect)

        # -------------------------------------------------------------
        # MongoDB Validation
        # -------------------------------------------------------------
        if dialect in ("mongodb", "mongo"):
            action = "find"
            target_col = "unknown"
            is_mutation = False
            is_destructive = False
            is_schema = False

            if clean.startswith("{") and clean.endswith("}"):
                try:
                    data = json.loads(clean)
                    action = str(data.get("action", "find")).lower()
                    target_col = str(data.get("collection") or data.get("from") or "collection")
                except Exception:
                    action = "find"
            elif clean.startswith("db."):
                m_create = re.match(r'db\.createCollection\(["\']([a-zA-Z0-9_-]+)["\']\)', clean)
                if m_create:
                    action = "create_collection"
                    target_col = m_create.group(1)
                else:
                    m_op = re.match(r'db\.([a-zA-Z0-9_-]+)\.([a-zA-Z0-9_]+)\(', clean)
                    if m_op:
                        target_col = m_op.group(1)
                        action = m_op.group(2).lower()
            else:
                # Raw SQL sent to MongoDB is invalid
                if re.match(r"^(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b", clean, re.I):
                    return PolicyValidationResult(
                        allowed=False,
                        operation="SQL_SYNTAX",
                        category=CommandCategory.NATIVE_CONNECTOR_OPERATION,
                        requires_confirmation=False,
                        is_high_risk=False,
                        reason="MongoDB connector requires JSON or MQL commands (e.g. db.collection.find({})). Raw SQL is not supported.",
                        clean_sql=clean,
                    )

            if action in ("find", "find_one", "findone", "aggregate", "count", "countdocuments"):
                return PolicyValidationResult(
                    allowed=True,
                    operation=action,
                    category=CommandCategory.READ,
                    requires_confirmation=False,
                    is_high_risk=False,
                    target_objects=[target_col],
                    primary_table=target_col,
                    rollback_supported=False,
                    rollback_limitations="MongoDB operations are executed directly and do not support transactional rollback outside multi-document transactions.",
                    clean_sql=clean,
                )

            if action in ("insert", "insertone", "insertmany", "update", "updateone", "updatemany", "delete", "deleteone", "deletemany"):
                if is_read_only:
                    return PolicyValidationResult(
                        allowed=False,
                        operation=action,
                        category=CommandCategory.DATA_MUTATION,
                        requires_confirmation=False,
                        is_high_risk=False,
                        reason=f"Connection '{conn_name}' is configured as READ-ONLY. Mutation '{action}' is blocked.",
                        clean_sql=clean,
                    )
                return PolicyValidationResult(
                    allowed=True,
                    operation=action,
                    category=CommandCategory.DATA_MUTATION,
                    requires_confirmation=True,
                    is_high_risk=False,
                    target_objects=[target_col],
                    primary_table=target_col,
                    impact_summary=f"Modify documents in MongoDB collection '{target_col}' ({action}).",
                    rollback_supported=False,
                    rollback_limitations="MongoDB operations do not support automatic rollback.",
                    clean_sql=clean,
                )

            if action in ("create_collection", "createcollection", "create_index", "createindex"):
                if is_read_only:
                    return PolicyValidationResult(
                        allowed=False,
                        operation=action,
                        category=CommandCategory.SCHEMA_CHANGE,
                        requires_confirmation=False,
                        is_high_risk=False,
                        reason=f"Connection '{conn_name}' is configured as READ-ONLY. Schema modification '{action}' is blocked.",
                        clean_sql=clean,
                    )
                return PolicyValidationResult(
                    allowed=True,
                    operation=action,
                    category=CommandCategory.SCHEMA_CHANGE,
                    requires_confirmation=True,
                    is_high_risk=False,
                    target_objects=[target_col],
                    primary_table=target_col,
                    impact_summary=f"Create or modify MongoDB collection/index '{target_col}'.",
                    rollback_supported=False,
                    rollback_limitations="Collection creation cannot be rolled back automatically.",
                    clean_sql=clean,
                )

            if action in ("drop", "drop_collection", "dropcollection", "drop_database", "dropdatabase"):
                if is_read_only:
                    return PolicyValidationResult(
                        allowed=False,
                        operation=action,
                        category=CommandCategory.DESTRUCTIVE_DDL,
                        requires_confirmation=False,
                        is_high_risk=True,
                        reason=f"Connection '{conn_name}' is configured as READ-ONLY. Destructive action '{action}' is blocked.",
                        clean_sql=clean,
                    )
                return PolicyValidationResult(
                    allowed=True,
                    operation=action,
                    category=CommandCategory.DESTRUCTIVE_DDL,
                    requires_confirmation=True,
                    is_high_risk=True,
                    target_objects=[target_col],
                    primary_table=target_col,
                    impact_summary=f"Permanently DROP MongoDB collection/database '{target_col}'.",
                    rollback_supported=False,
                    rollback_limitations="Dropping a MongoDB collection permanently removes all its data and cannot be rolled back.",
                    clean_sql=clean,
                    dangerous=True,
                )

        # -------------------------------------------------------------
        # Redis Validation
        # -------------------------------------------------------------
        elif dialect == "redis":
            cmd_name = ""
            key_name = ""
            if clean.startswith("{") and clean.endswith("}"):
                try:
                    p = json.loads(clean)
                    cmd_name = str(p.get("command", "")).upper()
                    key_name = str(p.get("key", ""))
                except Exception:
                    pass
            elif clean.upper().startswith("SELECT"):
                # Pseudo-SQL SELECT * FROM pattern
                return PolicyValidationResult(
                    allowed=True,
                    operation="SCAN",
                    category=CommandCategory.READ,
                    requires_confirmation=False,
                    is_high_risk=False,
                    rollback_supported=False,
                    clean_sql=clean,
                )
            else:
                tokens = clean.split()
                if tokens:
                    cmd_name = tokens[0].upper()
                    if len(tokens) > 1:
                        key_name = tokens[1]

            if not cmd_name:
                return PolicyValidationResult(
                    allowed=False,
                    operation="",
                    category=CommandCategory.NATIVE_CONNECTOR_OPERATION,
                    requires_confirmation=False,
                    is_high_risk=False,
                    reason="Invalid or empty Redis command.",
                    clean_sql=clean,
                )

            # Block server administration / dangerous host escapes
            if cmd_name in ("SHUTDOWN", "CONFIG", "SLAVEOF", "REPLICAOF", "DEBUG", "MODULE", "EVAL", "EVALSHA"):
                return PolicyValidationResult(
                    allowed=False,
                    operation=cmd_name,
                    category=CommandCategory.PROHIBITED_SYSTEM,
                    requires_confirmation=False,
                    is_high_risk=True,
                    reason=f"Redis administrative/scripting command '{cmd_name}' is prohibited by security policy.",
                    clean_sql=clean,
                    dangerous=True,
                )

            # Safe inspection
            if cmd_name in ("GET", "MGET", "HGET", "HGETALL", "HKEYS", "HVALS", "LRANGE", "SMEMBERS", "ZRANGE", "KEYS", "SCAN", "PING", "INFO", "DBSIZE", "TYPE", "TTL", "EXISTS"):
                return PolicyValidationResult(
                    allowed=True,
                    operation=cmd_name,
                    category=CommandCategory.READ,
                    requires_confirmation=False,
                    is_high_risk=False,
                    target_objects=[key_name] if key_name else [],
                    rollback_supported=False,
                    clean_sql=clean,
                )

            # Mutations
            if cmd_name in ("SET", "SETEX", "MSET", "HSET", "HMSET", "LPUSH", "RPUSH", "SADD", "ZADD", "INCR", "DECR", "DEL", "EXPIRE"):
                if is_read_only:
                    return PolicyValidationResult(
                        allowed=False,
                        operation=cmd_name,
                        category=CommandCategory.DATA_MUTATION,
                        requires_confirmation=False,
                        is_high_risk=False,
                        reason=f"Connection '{conn_name}' is configured as READ-ONLY. Mutating command '{cmd_name}' is blocked.",
                        clean_sql=clean,
                    )
                return PolicyValidationResult(
                    allowed=True,
                    operation=cmd_name,
                    category=CommandCategory.DATA_MUTATION,
                    requires_confirmation=True,
                    is_high_risk=False,
                    target_objects=[key_name] if key_name else [],
                    impact_summary=f"Redis key mutation: {cmd_name} on '{key_name or 'key'}'.",
                    rollback_supported=False,
                    rollback_limitations="Redis does not support rolling back individual key mutations.",
                    clean_sql=clean,
                )

            # Destructive flush
            if cmd_name in ("FLUSHDB", "FLUSHALL"):
                if is_read_only:
                    return PolicyValidationResult(
                        allowed=False,
                        operation=cmd_name,
                        category=CommandCategory.DESTRUCTIVE_DDL,
                        requires_confirmation=False,
                        is_high_risk=True,
                        reason=f"Connection '{conn_name}' is configured as READ-ONLY. Destructive command '{cmd_name}' is blocked.",
                        clean_sql=clean,
                    )
                return PolicyValidationResult(
                    allowed=True,
                    operation=cmd_name,
                    category=CommandCategory.DESTRUCTIVE_DDL,
                    requires_confirmation=True,
                    is_high_risk=True,
                    target_objects=["redis_database"],
                    impact_summary=f"Permanently remove ALL keys from Redis database ({cmd_name}).",
                    rollback_supported=False,
                    rollback_limitations="FLUSH operations completely erase Redis memory and cannot be rolled back.",
                    clean_sql=clean,
                    dangerous=True,
                )

        # -------------------------------------------------------------
        # Vector Validation (Qdrant / Chroma)
        # -------------------------------------------------------------
        elif dialect in ("qdrant", "chroma"):
            action = "search"
            target_col = "default"
            if clean.startswith("{") and clean.endswith("}"):
                try:
                    p = json.loads(clean)
                    action = str(p.get("action", "search")).lower()
                    target_col = str(p.get("collection", "default"))
                except Exception:
                    pass

            if action in ("search", "query", "find", "get"):
                return PolicyValidationResult(
                    allowed=True,
                    operation=action,
                    category=CommandCategory.READ,
                    requires_confirmation=False,
                    is_high_risk=False,
                    target_objects=[target_col],
                    rollback_supported=False,
                    clean_sql=clean,
                )

            if action in ("upsert", "insert", "add", "delete_points"):
                if is_read_only:
                    return PolicyValidationResult(
                        allowed=False,
                        operation=action,
                        category=CommandCategory.DATA_MUTATION,
                        requires_confirmation=False,
                        is_high_risk=False,
                        reason=f"Connection '{conn_name}' is configured as READ-ONLY. Mutation '{action}' is blocked.",
                        clean_sql=clean,
                    )
                return PolicyValidationResult(
                    allowed=True,
                    operation=action,
                    category=CommandCategory.DATA_MUTATION,
                    requires_confirmation=True,
                    is_high_risk=False,
                    target_objects=[target_col],
                    impact_summary=f"Modify vector points in collection '{target_col}'.",
                    rollback_supported=False,
                    clean_sql=clean,
                )

            if action in ("delete_collection", "drop_collection"):
                if is_read_only:
                    return PolicyValidationResult(
                        allowed=False,
                        operation=action,
                        category=CommandCategory.DESTRUCTIVE_DDL,
                        requires_confirmation=False,
                        is_high_risk=True,
                        reason=f"Connection '{conn_name}' is configured as READ-ONLY. Action '{action}' is blocked.",
                        clean_sql=clean,
                    )
                return PolicyValidationResult(
                    allowed=True,
                    operation=action,
                    category=CommandCategory.DESTRUCTIVE_DDL,
                    requires_confirmation=True,
                    is_high_risk=True,
                    target_objects=[target_col],
                    impact_summary=f"Permanently DROP vector collection '{target_col}'.",
                    rollback_supported=False,
                    clean_sql=clean,
                    dangerous=True,
                )

        return PolicyValidationResult(
            allowed=True,
            operation="query",
            category=CommandCategory.NATIVE_CONNECTOR_OPERATION,
            requires_confirmation=False,
            is_high_risk=False,
            rollback_supported=False,
            clean_sql=clean,
        )

    @classmethod
    def validate(
        cls,
        sql: str,
        dialect: Optional[str] = None,
        connector: Optional[Any] = None,
        user_id: Optional[str] = None,
    ) -> PolicyValidationResult:
        """
        Evaluates a SQL query or native command against the centralized command policy.
        """
        clean = cls.clean_sql(sql)
        if not clean:
            return PolicyValidationResult(
                allowed=False,
                operation="",
                category=CommandCategory.READ,
                requires_confirmation=False,
                is_high_risk=False,
                reason="Empty database command.",
                clean_sql="",
            )

        resolved_dialect = (
            dialect
            or (getattr(connector, "connector_type", None) if connector else None)
            or "sqlite"
        ).lower()

        # Handle Non-Relational connectors natively
        is_non_relational = (
            (connector and getattr(connector, "category", "") != "relational")
            or resolved_dialect in ("mongodb", "mongo", "redis", "qdrant", "chroma")
        )
        if is_non_relational:
            return cls._validate_nonrelational(
                cmd_text=clean,
                dialect=resolved_dialect,
                connector=connector,
                user_id=user_id,
            )

        # 1. Single-statement enforcement (blocks semicolon chaining)
        if cls.has_multiple_statements(clean):
            return PolicyValidationResult(
                allowed=False,
                operation="MULTIPLE",
                category=CommandCategory.PROHIBITED_SYSTEM,
                requires_confirmation=False,
                is_high_risk=True,
                reason="Multiple SQL statements are not allowed.",
                clean_sql=clean,
                dangerous=True,
            )

        # 2. Prohibited system command check
        for pattern in PROHIBITED_SYSTEM_PATTERNS:
            if pattern.search(clean):
                return PolicyValidationResult(
                    allowed=False,
                    operation="PROHIBITED_SYSTEM",
                    category=CommandCategory.PROHIBITED_SYSTEM,
                    requires_confirmation=False,
                    is_high_risk=True,
                    reason="System-level command or host file system operation is blocked by security policy.",
                    clean_sql=clean,
                    dangerous=True,
                )

        root_op, context_word = cls._extract_root_operation(clean)

        # Check Read-Only Connection Status
        is_read_only = getattr(connector, "is_read_only", False)

        # Compute Dialect Rollback Capabilities
        rollback_supported = True
        rollback_limitations = ""

        if resolved_dialect in ("mysql", "mariadb"):
            if root_op in ("DROP", "ALTER", "CREATE", "TRUNCATE"):
                rollback_supported = False
                rollback_limitations = (
                    f"{resolved_dialect.title()} executes an implicit commit for DDL/TRUNCATE. "
                    "Changes cannot be rolled back."
                )
        elif resolved_dialect == "sqlite":
            if root_op == "TRUNCATE":
                rollback_supported = True
                rollback_limitations = (
                    "SQLite does not have a native 'TRUNCATE' keyword. "
                    "In SQLite, this executes as 'DELETE FROM <table>'."
                )
            else:
                rollback_supported = True
                rollback_limitations = "SQLite supports transactional DDL rollback."
        elif resolved_dialect in ("postgres", "postgresql"):
            rollback_supported = True
            rollback_limitations = (
                "PostgreSQL supports full transactional DDL. Changes can be rolled back if an error occurs."
            )
        elif resolved_dialect in ("mssql", "sqlserver"):
            rollback_supported = True
            rollback_limitations = "SQL Server supports transactional DDL rollback."

        # -------------------------------------------------------------
        # CATEGORY 1: READ OPERATIONS
        # -------------------------------------------------------------
        if root_op in ("SELECT", "SHOW", "DESCRIBE", "EXPLAIN"):
            return PolicyValidationResult(
                allowed=True,
                operation=root_op,
                category=CommandCategory.READ,
                requires_confirmation=False,
                is_high_risk=False,
                rollback_supported=rollback_supported,
                rollback_limitations=rollback_limitations,
                clean_sql=clean,
            )

        if root_op == "PRAGMA":
            # Disallow PRAGMA statements setting configuration (e.g. PRAGMA key = val)
            if "=" in clean:
                return PolicyValidationResult(
                    allowed=False,
                    operation="PRAGMA",
                    category=CommandCategory.ADMINISTRATION,
                    requires_confirmation=False,
                    is_high_risk=True,
                    reason="PRAGMA configuration statements modifying database parameters are not permitted.",
                    clean_sql=clean,
                )
            return PolicyValidationResult(
                allowed=True,
                operation="PRAGMA",
                category=CommandCategory.READ,
                requires_confirmation=False,
                is_high_risk=False,
                rollback_supported=rollback_supported,
                rollback_limitations=rollback_limitations,
                clean_sql=clean,
            )

        # -------------------------------------------------------------
        # Read-Only Connection Guardrail (Blocks any mutation/DDL/Admin)
        # -------------------------------------------------------------
        if is_read_only:
            conn_name = getattr(connector, "name", "active connection")
            return PolicyValidationResult(
                allowed=False,
                operation=root_op,
                category=CommandCategory.DATA_MUTATION,
                requires_confirmation=False,
                is_high_risk=False,
                reason=f"Connection '{conn_name}' is configured as READ-ONLY. Mutation '{root_op}' is blocked.",
                clean_sql=clean,
            )

        # -------------------------------------------------------------
        # CATEGORY 2: TRANSACTION MANAGEMENT
        # -------------------------------------------------------------
        if root_op in ("BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "START"):
            return PolicyValidationResult(
                allowed=True,
                operation=root_op,
                category=CommandCategory.TRANSACTION_CONTROL,
                requires_confirmation=False,
                is_high_risk=False,
                impact_summary=f"Transaction control command: {root_op}",
                clean_sql=clean,
            )

        # -------------------------------------------------------------
        # CATEGORY 3: DDL - DROP & TRUNCATE (High-Impact / Destructive)
        # -------------------------------------------------------------
        if root_op == "DROP":
            m_drop = re.search(
                r"\bDROP\s+(TABLE|DATABASE|VIEW|INDEX|TRIGGER|SEQUENCE|SCHEMA)\s+(?:IF\s+EXISTS\s+)?([`\"\[\w\.]+)",
                clean,
                re.I,
            )
            obj_type = m_drop.group(1).upper() if m_drop else "OBJECT"
            raw_target = m_drop.group(2) if m_drop else "unknown"
            clean_target = raw_target.strip("`\"[]")
            is_high = obj_type in ("TABLE", "DATABASE", "SCHEMA")

            return PolicyValidationResult(
                allowed=True,
                operation="DROP",
                category=CommandCategory.DESTRUCTIVE_DDL,
                requires_confirmation=True,
                is_high_risk=is_high,
                target_objects=[clean_target],
                primary_table=clean_target if obj_type == "TABLE" else None,
                impact_summary=f"Permanently DROP {obj_type.lower()} '{clean_target}' and its associated data.",
                rollback_supported=rollback_supported,
                rollback_limitations=rollback_limitations,
                clean_sql=clean,
                dangerous=True,
            )

        if root_op == "TRUNCATE":
            m_trunc = re.search(
                r"\bTRUNCATE\s+(?:TABLE\s+)?([`\"\[\w\.]+)", clean, re.I
            )
            raw_target = m_trunc.group(1) if m_trunc else "unknown"
            clean_target = raw_target.strip("`\"[]")

            dialect_note = None
            if resolved_dialect == "sqlite":
                dialect_note = "SQLite uses 'DELETE FROM <table>' to achieve table truncation."

            return PolicyValidationResult(
                allowed=True,
                operation="TRUNCATE",
                category=CommandCategory.DESTRUCTIVE_DDL,
                requires_confirmation=True,
                is_high_risk=True,
                target_objects=[clean_target],
                primary_table=clean_target,
                impact_summary=f"Permanently remove ALL records from table '{clean_target}'.",
                rollback_supported=rollback_supported,
                rollback_limitations=rollback_limitations,
                dialect_notes=dialect_note,
                clean_sql=clean,
                dangerous=True,
            )

        # -------------------------------------------------------------
        # CATEGORY 4: DDL - ALTER TABLE
        # -------------------------------------------------------------
        if root_op == "ALTER":
            m_alter = re.search(
                r"\bALTER\s+TABLE\s+([`\"\[\w\.]+)\s+(ADD|DROP|RENAME|MODIFY|ALTER)\s+(?:COLUMN\s+)?([`\"\[\w\.]+)?",
                clean,
                re.I,
            )
            raw_table = m_alter.group(1) if m_alter else "unknown"
            clean_table = raw_table.strip("`\"[]")
            action = m_alter.group(2).upper() if m_alter else "ALTER"
            col_target = m_alter.group(3).strip("`\"[]") if m_alter and m_alter.group(3) else ""

            is_drop_col = (action == "DROP")
            cat = CommandCategory.DESTRUCTIVE_DDL if is_drop_col else CommandCategory.SCHEMA_CHANGE

            impact = f"Alter schema of table '{clean_table}' ({action} {col_target})."
            if is_drop_col:
                impact = f"Permanently DROP column '{col_target}' from table '{clean_table}' along with all its data."

            return PolicyValidationResult(
                allowed=True,
                operation="ALTER",
                category=cat,
                requires_confirmation=True,
                is_high_risk=is_drop_col,
                target_objects=[clean_table] + ([col_target] if col_target else []),
                primary_table=clean_table,
                impact_summary=impact,
                rollback_supported=rollback_supported,
                rollback_limitations=rollback_limitations,
                clean_sql=clean,
                dangerous=is_drop_col,
            )

        # -------------------------------------------------------------
        # CATEGORY 5: DDL - CREATE TABLE / INDEX / VIEW / TRIGGER
        # -------------------------------------------------------------
        if root_op == "CREATE":
            m_create_tbl = re.search(
                r"\bCREATE\s+(?:TEMP|TEMPORARY\s+)?(?:TABLE|VIEW)\s+(?:IF\s+NOT\s+EXISTS\s+)?([`\"\[\w\.]+)",
                clean,
                re.I,
            )
            m_create_idx = re.search(
                r"\bCREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?([`\"\[\w\.]+)\s+ON\s+([`\"\[\w\.]+)",
                clean,
                re.I,
            )

            target = "new_object"
            impact = "Create database object."
            if m_create_tbl:
                target = m_create_tbl.group(1).strip("`\"[]")
                impact = f"Create new entity/table '{target}' in the database."
            elif m_create_idx:
                idx_name = m_create_idx.group(1).strip("`\"[]")
                tbl_name = m_create_idx.group(2).strip("`\"[]")
                target = idx_name
                impact = f"Create index '{idx_name}' on table '{tbl_name}'."

            return PolicyValidationResult(
                allowed=True,
                operation="CREATE",
                category=CommandCategory.SCHEMA_CHANGE,
                requires_confirmation=True,
                is_high_risk=False,
                target_objects=[target],
                primary_table=target,
                impact_summary=impact,
                rollback_supported=rollback_supported,
                rollback_limitations=rollback_limitations,
                clean_sql=clean,
            )

        # -------------------------------------------------------------
        # CATEGORY 6: ADMINISTRATION (GRANT, REVOKE, VACUUM, ANALYZE)
        # -------------------------------------------------------------
        if root_op in ("GRANT", "REVOKE"):
            return PolicyValidationResult(
                allowed=True,
                operation=root_op,
                category=CommandCategory.ADMINISTRATION,
                requires_confirmation=True,
                is_high_risk=True,
                impact_summary=f"Privilege modification command: {root_op}",
                clean_sql=clean,
                dangerous=True,
            )

        if root_op in ("VACUUM", "ANALYZE", "OPTIMIZE", "REINDEX", "CHECK"):
            return PolicyValidationResult(
                allowed=True,
                operation=root_op,
                category=CommandCategory.ADMINISTRATION,
                requires_confirmation=True,
                is_high_risk=False,
                impact_summary=f"Database maintenance command: {root_op}",
                clean_sql=clean,
            )

        # -------------------------------------------------------------
        # CATEGORY 7: DATA MUTATION (INSERT, UPDATE, DELETE, UPSERT)
        # -------------------------------------------------------------
        if root_op in ("INSERT", "REPLACE"):
            m_ins = re.search(
                r"\b(?:INSERT\s+(?:INTO\s+)?|REPLACE\s+(?:INTO\s+)?)([`\"\[\w\.]+)",
                clean,
                re.I,
            )
            raw_table = m_ins.group(1) if m_ins else "table"
            clean_table = raw_table.strip("`\"[]")

            return PolicyValidationResult(
                allowed=True,
                operation="INSERT",
                category=CommandCategory.DATA_MUTATION,
                requires_confirmation=True,
                is_high_risk=False,
                target_objects=[clean_table],
                primary_table=clean_table,
                impact_summary=f"Insert new record(s) into table '{clean_table}'.",
                rollback_supported=rollback_supported,
                rollback_limitations=rollback_limitations,
                clean_sql=clean,
            )

        if root_op in ("UPDATE", "DELETE"):
            target_table = "table"
            where_clause = None

            if root_op == "UPDATE":
                m_upd = re.search(r"\bUPDATE\s+([`\"\[\w\.]+)", clean, re.I)
                if m_upd:
                    target_table = m_upd.group(1).strip("`\"[]")
            else:
                m_del = re.search(r"\bDELETE\s+FROM\s+([`\"\[\w\.]+)", clean, re.I)
                if m_del:
                    target_table = m_del.group(1).strip("`\"[]")

            # Extract WHERE clause
            m_where = re.search(r"\bWHERE\b\s+(.*)$", clean, re.I | re.DOTALL)
            if m_where:
                where_clause = m_where.group(1).strip().rstrip(";")

            # Check for unconstrained / mass mutation
            is_unconstrained = False
            if not where_clause:
                is_unconstrained = True
            else:
                for tp in TRIVIAL_WHERE_PATTERNS:
                    if tp.match(where_clause):
                        is_unconstrained = True
                        break

            cat = CommandCategory.DESTRUCTIVE_DDL if (root_op == "DELETE" and is_unconstrained) else CommandCategory.DATA_MUTATION
            impact = f"Update records in '{target_table}' matching filter."
            if root_op == "DELETE":
                impact = f"Delete records from '{target_table}' matching filter."

            if is_unconstrained:
                impact = f"WARNING: {root_op.upper()} without a restrictive filter will {'delete' if root_op == 'DELETE' else 'affect'} ALL records in '{target_table}'."

            return PolicyValidationResult(
                allowed=True,
                operation=root_op,
                category=cat,
                requires_confirmation=True,
                is_high_risk=is_unconstrained,
                target_objects=[target_table],
                primary_table=target_table,
                impact_summary=impact,
                rollback_supported=rollback_supported,
                rollback_limitations=rollback_limitations,
                clean_sql=clean,
                dangerous=is_unconstrained,
            )

        # -------------------------------------------------------------
        # Unrecognized / Unsupported Command
        # -------------------------------------------------------------
        return PolicyValidationResult(
            allowed=False,
            operation=root_op,
            category=CommandCategory.PROHIBITED_SYSTEM,
            requires_confirmation=False,
            is_high_risk=False,
            reason=f"Operation '{root_op}' is not a recognized or supported database command.",
            clean_sql=clean,
        )


def generate_command_fingerprint(
    operation: str,
    target: str,
    sql: str,
    database_identity: Optional[str] = None,
    connection_id: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    params: Optional[Any] = None,
    expires_at: Optional[float] = None,
) -> str:
    """
    Generates a cryptographically strong, full-length (64-character hex SHA-256) fingerprint
    binding the approval to canonical command, parameters, database identity, connection ID,
    authenticated user, session, and expiry.
    """
    canon_sql = " ".join(sql.strip().split())
    canon_target = target.strip("`\"[]").lower() if target else ""
    canon_op = operation.strip().lower()
    canon_db = (database_identity or "").strip().lower()
    canon_conn = (connection_id or "").strip()
    canon_user = (user_id or "").strip()
    canon_session = (session_id or "").strip()
    canon_params = json.dumps(params, sort_keys=True) if params else ""
    canon_exp = str(int(expires_at)) if expires_at else ""

    payload = f"{canon_op}|{canon_target}|{canon_sql}|{canon_db}|{canon_conn}|{canon_user}|{canon_session}|{canon_params}|{canon_exp}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
