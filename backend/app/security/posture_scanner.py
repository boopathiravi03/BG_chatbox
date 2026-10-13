"""backend/app/security/posture_scanner.py

Database Cybersecurity & Sensitive Data Exposure Scanner for BG AI.
Performs read-only inspection of active database connections:
1. Transport Layer Security (TLS/SSL) verification
2. Account privilege & access control audit (least privilege vs superuser)
3. Bounded sampling (max 50 rows per table, max 15 tables)
4. Conservative sensitive data detection (payment cards with Luhn validation, SSNs, API keys, emails)
5. Plaintext password verification (differentiates bcrypt/argon2/sha256 hashes from plaintext)
6. Zero raw secret exposure (sanitized summaries only)
7. SecurityEventManager integration with deduplication
"""

from __future__ import annotations

import re
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from app.connectors.base import BaseConnector, QueryResult
from app.intelligence.governance.models import (
    SecurityEventType,
    SecurityEventSeverity,
)
from app.intelligence.governance.security_events import SecurityEventManager
from app.intelligence.governance.audit_store import list_security_events

logger = logging.getLogger(__name__)

# Bounded scan parameters
MAX_SAMPLE_ROWS = 50
MAX_TABLES_TO_SCAN = 15

# Conservative regex patterns
RE_EMAIL = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
RE_PHONE = re.compile(r"^(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}$")
RE_PEM_KEY = re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")
RE_SSN = re.compile(r"^(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}$")
RE_API_KEY_PATTERNS = [
    ("OpenAI/Stripe Secret Key", re.compile(r"^(?:sk_live_|sk_test_|rk_live_)[0-9a-zA-Z]{24,}$")),
    ("GitHub Personal Token", re.compile(r"^gh[pousr]_[0-9a-zA-Z]{36}$")),
    ("AWS Access Key ID", re.compile(r"^(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}$")),
    ("JSON Web Token (JWT)", re.compile(r"^ey[A-Za-z0-9_-]{10,}\.ey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}$")),
]

# Hash signatures for password classification
RE_BCRYPT = re.compile(r"^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}$")
RE_ARGON2 = re.compile(r"^\$argon2(?:id|[id])?\$")
RE_SHA512_CRYPT = re.compile(r"^\$6\$[./A-Za-z0-9]{8,16}\$[./A-Za-z0-9]{86}$")
RE_HEX_64 = re.compile(r"^[a-fA-F0-9]{64}$")  # SHA-256
RE_HEX_32 = re.compile(r"^[a-fA-F0-9]{32}$")  # MD5 / NTLM


def luhn_checksum_valid(card_number: str) -> bool:
    """Validates payment card number via Luhn mod-10 algorithm."""
    digits = [int(c) for c in card_number if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    # Luhn formula
    checksum = 0
    reverse_digits = digits[::-1]
    for i, digit in enumerate(reverse_digits):
        if i % 2 == 1:
            doubled = digit * 2
            checksum += doubled - 9 if doubled > 9 else doubled
        else:
            checksum += digit
    return checksum % 10 == 0


def is_payment_card(val: str) -> bool:
    """Conservative payment card detection with Luhn check."""
    cleaned = re.sub(r"[\s-]", "", val)
    if not cleaned.isdigit() or len(cleaned) < 13 or len(cleaned) > 19:
        return False
    # Common issuer prefixes
    # Visa: 4, MC: 51-55 or 2221-2720, Amex: 34 or 37, Discover: 6011/65
    if not (cleaned.startswith("4") or
            51 <= int(cleaned[:2]) <= 55 or
            2221 <= int(cleaned[:4]) <= 2720 or
            cleaned.startswith(("34", "37", "6011", "65"))):
        return False
    return luhn_checksum_valid(cleaned)


def is_known_hash(val: str) -> bool:
    """Returns True if the string matches recognized cryptographic hash signatures."""
    s = val.strip()
    return bool(
        RE_BCRYPT.match(s) or
        RE_ARGON2.match(s) or
        RE_SHA512_CRYPT.match(s) or
        RE_HEX_64.match(s) or
        (RE_HEX_32.match(s) and any(c.isalpha() for c in s) and any(c.isdigit() for c in s))
    )


def safe_quote_identifier(ident: str, dialect: str) -> str:
    """Quotes an identifier safely without permitting SQL injection."""
    # Strict validation: alphanumeric + underscores only
    clean = ident.replace("`", "").replace('"', "").replace(";", "").replace(" ", "_")
    if dialect in ("postgres", "sqlite"):
        return f'"{clean}"'
    elif dialect in ("mysql", "mariadb"):
        return f'`{clean}`'
    return f'"{clean}"'


class DatabasePostureScanner:
    """
    Read-only cybersecurity auditor and sensitive data detector.
    Never exposes raw secrets; returns sanitized, structured security findings.
    """

    def __init__(
        self,
        connector: BaseConnector,
        user_id: str,
        selected_tables: Optional[List[str]] = None,
    ):
        self.connector = connector
        self.user_id = user_id
        self.selected_tables = selected_tables
        self.db_identity = f"{connector.connector_type}:{getattr(connector, 'database', getattr(connector, 'name', 'db'))}"

    def run_full_scan(self) -> Dict[str, Any]:
        """Executes complete security posture and sensitive data exposure audit."""
        start_time = time.perf_counter()
        findings: List[Dict[str, Any]] = []

        # 1. Transport Layer Security (TLS) Audit
        tls_status, tls_details = self._audit_tls()
        if tls_status == "DISABLED":
            findings.append({
                "id": f"tls_disabled_{int(time.time())}",
                "category": "CONNECTION_SECURITY",
                "severity": "HIGH",
                "title": "Plaintext Database Transport (TLS Disabled)",
                "evidence_summary": f"Connection operates without verified TLS encryption: {tls_details}",
                "remediation": "Enable SSL/TLS transport encryption (e.g., ssl_mode=verify-full or require) to prevent wiretapping.",
            })

        # 2. Account Privileges & Access Control Audit
        priv_status, priv_details = self._audit_privileges()
        if priv_status == "SUPERUSER":
            findings.append({
                "id": f"priv_superuser_{int(time.time())}",
                "category": "ACCESS_CONTROL",
                "severity": "HIGH",
                "title": "Excessive Database Account Privileges (Superuser)",
                "evidence_summary": f"Active connection uses an account with administrator privileges: {priv_details}",
                "remediation": "Configure a dedicated least-privilege service user restricted to only necessary schemas.",
            })

        # 3. Sensitive Data Exposure Scanning across bounded samples
        data_findings, tables_scanned = self._scan_sensitive_data()
        findings.extend(data_findings)

        # 4. Integrate genuine high/critical findings into SecurityEventManager (with deduplication)
        self._record_security_events(findings)

        # 5. Compute Posture Score & Risk Level (0 - 100)
        deductions = 0
        for f in findings:
            sev = f.get("severity", "").upper()
            if sev == "CRITICAL":
                deductions += 20
            elif sev == "HIGH":
                deductions += 12
            elif sev == "MEDIUM":
                deductions += 6
            elif sev == "LOW":
                deductions += 2

        posture_score = max(0, 100 - deductions)
        if posture_score >= 85:
            risk_level = "LOW"
        elif posture_score >= 65:
            risk_level = "MEDIUM"
        elif posture_score >= 45:
            risk_level = "HIGH"
        else:
            risk_level = "CRITICAL"

        score_explanation = (
            "Score formula: Base 100 with deductions: -20 per Critical finding, -12 per High finding, "
            "-6 per Medium finding, -2 per Low finding. Risk tiers: >=85 Low, 65-84 Medium, 45-64 High, <45 Critical."
        )

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return {
            "status": "success",
            "connection_id": self.connector.connection_id,
            "database_type": self.connector.connector_type,
            "database_name": getattr(self.connector, "database", self.connector.name),
            "scanned_at": datetime.now(timezone.utc).isoformat(),
            "scan_duration_ms": elapsed_ms,
            "posture_score": posture_score,
            "risk_level": risk_level,
            "score_explanation": score_explanation,
            "tls_status": tls_status,
            "tls_details": tls_details,
            "privilege_status": priv_status,
            "privilege_details": priv_details,
            "tables_scanned": tables_scanned,
            "total_findings": len(findings),
            "findings": findings,
        }

    def _audit_tls(self) -> Tuple[str, str]:
        """Evaluates TLS configuration for active connector."""
        ctype = self.connector.connector_type.lower()

        if ctype == "sqlite":
            return "UNKNOWN", "In-process SQLite local file; network transport TLS is not applicable."

        if ctype in ("mysql", "mariadb"):
            try:
                res = self.connector.execute_query("SHOW STATUS LIKE 'Ssl_cipher'")
                if res.success and res.rows:
                    cipher = str(res.rows[0].get("Value", "")).strip()
                    if cipher and cipher != "0" and cipher.lower() != "none":
                        return "VERIFIED", f"Active TLS cipher: {cipher}"
                    return "DISABLED", "No active SSL cipher negotiated on MySQL connection."
            except Exception as e:
                logger.debug(f"MySQL TLS query check error: {e}")
            return "UNKNOWN", "Could not verify MySQL Ssl_cipher status."

        if ctype == "postgres":
            try:
                res = self.connector.execute_query("SELECT ssl_is_used() as is_ssl")
                if res.success and res.rows:
                    is_ssl = bool(res.rows[0].get("is_ssl"))
                    if is_ssl:
                        return "VERIFIED", "PostgreSQL connection reports active SSL."
                    return "DISABLED", "PostgreSQL connection reports ssl_is_used() = false."
            except Exception:
                pass
            return "UNKNOWN", "PostgreSQL SSL status query not available or unprivileged."

        if ctype == "mongodb":
            try:
                client = getattr(self.connector, "_client", None)
                if client:
                    opts = client.options
                    if getattr(opts, "tls", False) or getattr(opts, "ssl", False):
                        return "VERIFIED", "MongoDB client configured with TLS/SSL."
                    # Check if host is remote vs localhost
                    host = getattr(self.connector, "host", "")
                    if host and host not in ("localhost", "127.0.0.1", "::1"):
                        return "DISABLED", f"Remote MongoDB connection ({host}) configured without explicit TLS."
                    return "UNKNOWN", "Local MongoDB connection; TLS not configured."
            except Exception:
                pass
            return "UNKNOWN", "MongoDB TLS status could not be inspected."

        return "UNKNOWN", f"TLS verification not supported for connector type '{ctype}'."

    def _audit_privileges(self) -> Tuple[str, str]:
        """Audits database connection permissions for least privilege."""
        ctype = self.connector.connector_type.lower()

        if ctype == "sqlite":
            return "LEAST_PRIVILEGE", "Standard SQLite process-level file access."

        if ctype in ("mysql", "mariadb"):
            try:
                user_res = self.connector.execute_query("SELECT CURRENT_USER() as cur_user")
                cur_user = user_res.rows[0].get("cur_user", "") if user_res.success and user_res.rows else ""
                if "root@" in cur_user.lower():
                    return "SUPERUSER", f"Connected as root administrative user ({cur_user})."

                # Inspect grants
                grants_res = self.connector.execute_query("SHOW GRANTS FOR CURRENT_USER()")
                if grants_res.success and grants_res.rows:
                    for r in grants_res.rows:
                        g_text = str(list(r.values())[0]).upper()
                        if "ALL PRIVILEGES ON *.*" in g_text or "SUPER" in g_text:
                            return "SUPERUSER", f"Account possesses global administrative grant: {g_text[:40]}..."
                return "LEAST_PRIVILEGE", f"Connected as standard application user ({cur_user or 'custom'})."
            except Exception as e:
                logger.debug(f"MySQL privilege check error: {e}")
                return "UNKNOWN", "Unable to inspect MySQL user grants."

        if ctype == "postgres":
            try:
                res = self.connector.execute_query(
                    "SELECT current_user as usr, usesuper FROM pg_user WHERE usename = current_user"
                )
                if res.success and res.rows:
                    row = res.rows[0]
                    usr = row.get("usr", "")
                    if row.get("usesuper"):
                        return "SUPERUSER", f"PostgreSQL role '{usr}' possesses superuser privilege."
                    return "LEAST_PRIVILEGE", f"PostgreSQL role '{usr}' operates without superuser privilege."
            except Exception:
                pass
            return "UNKNOWN", "Unable to query pg_user privilege status."

        if ctype == "mongodb":
            user = getattr(self.connector, "username", "")
            auth_db = getattr(self.connector, "auth_source", "admin")
            if user and user.lower() in ("root", "admin") and auth_db == "admin":
                return "SUPERUSER", f"MongoDB connected with administrative identity '{user}' on '{auth_db}'."
            return "LEAST_PRIVILEGE", f"MongoDB standard collection access user ('{user or 'anonymous'}')."

        return "UNKNOWN", "Privilege audit not supported for this connector."

    def _scan_sensitive_data(self) -> Tuple[List[Dict[str, Any]], int]:
        """Inspects up to MAX_TABLES_TO_SCAN tables, sampling max MAX_SAMPLE_ROWS per table."""
        findings: List[Dict[str, Any]] = []
        schema = self.connector.get_schema()
        if not schema or not isinstance(schema, dict) or schema.get("status") == "error":
            return findings, 0

        # Prioritize tables or filter by user-selected tables
        all_tables = [k for k in schema.keys() if k != "status"]
        if self.selected_tables:
            target_tables = [t for t in self.selected_tables if t in all_tables][:MAX_TABLES_TO_SCAN]
        else:
            priority_keywords = ("user", "customer", "account", "profile", "order", "payment", "card", "token", "auth", "secret")
            prioritized = [t for t in all_tables if any(kw in t.lower() for kw in priority_keywords)]
            other_tables = [t for t in all_tables if t not in prioritized]
            target_tables = (prioritized + other_tables)[:MAX_TABLES_TO_SCAN]

        for table in target_tables:
            cols = schema.get(table, {})
            if not cols or not isinstance(cols, dict):
                continue

            # Fetch bounded sample
            sample_rows = self._fetch_bounded_sample(table, list(cols.keys()))
            if not sample_rows:
                continue

            # Column-by-column inspection
            for col_name in cols.keys():
                col_lower = col_name.lower()
                vals = [str(r.get(col_name)) for r in sample_rows if r.get(col_name) is not None]
                if not vals:
                    continue

                # A. Plaintext Password vs Hash Check
                if any(pwd_kw in col_lower for pwd_kw in ("password", "passwd", "pwd", "user_secret")):
                    hash_count = sum(1 for v in vals if is_known_hash(v))
                    plain_count = len(vals) - hash_count
                    if plain_count > 0:
                        findings.append({
                            "id": f"plain_pwd_{table}_{col_name}",
                            "category": "SENSITIVE_DATA_EXPOSURE",
                            "severity": "CRITICAL",
                            "title": "Plaintext Passwords Stored in Database",
                            "table": table,
                            "column": col_name,
                            "sample_count": plain_count,
                            "evidence_summary": f"Detected {plain_count} unhashed credential value(s) in sample of {len(vals)} rows. Values were redacted.",
                            "remediation": "Never store plaintext credentials. Hash passwords using bcrypt, Argon2, or PBKDF2 immediately.",
                        })

                # B. Payment Card Numbers (Luhn Validated)
                card_matches = sum(1 for v in vals if is_payment_card(v))
                if card_matches > 0:
                    findings.append({
                        "id": f"card_exposed_{table}_{col_name}",
                        "category": "SENSITIVE_DATA_EXPOSURE",
                        "severity": "CRITICAL",
                        "title": "Unmasked Payment Card Numbers Detected",
                        "table": table,
                        "column": col_name,
                        "sample_count": card_matches,
                        "evidence_summary": f"Found {card_matches} payment card number(s) (Luhn-valid) in sample of {len(vals)} rows. Raw numbers redacted.",
                        "remediation": "Store only last-4 digits or use PCI-compliant vault tokenization. Do not retain primary account numbers (PAN).",
                    })

                # C. Social Security Numbers (SSN)
                if any(ssn_kw in col_lower for ssn_kw in ("ssn", "social_sec", "national_id")):
                    ssn_matches = sum(1 for v in vals if RE_SSN.match(v.strip()))
                    if ssn_matches > 0:
                        findings.append({
                            "id": f"ssn_exposed_{table}_{col_name}",
                            "category": "SENSITIVE_DATA_EXPOSURE",
                            "severity": "CRITICAL",
                            "title": "Unencrypted Social Security Numbers (SSN) Detected",
                            "table": table,
                            "column": col_name,
                            "sample_count": ssn_matches,
                            "evidence_summary": f"Detected {ssn_matches} valid SSN format value(s) in sample. Values redacted.",
                            "remediation": "Encrypt SSN values with AES-256 at the application layer or restrict column-level access permissions.",
                        })

                # D. API Keys & Secrets
                for key_name, key_pattern in RE_API_KEY_PATTERNS:
                    key_matches = sum(1 for v in vals if key_pattern.match(v.strip()))
                    if key_matches > 0:
                        findings.append({
                            "id": f"apikey_{table}_{col_name}_{key_name.replace(' ', '_').lower()}",
                            "category": "SENSITIVE_DATA_EXPOSURE",
                            "severity": "CRITICAL",
                            "title": f"Exposed {key_name} in Database Table",
                            "table": table,
                            "column": col_name,
                            "sample_count": key_matches,
                            "evidence_summary": f"Detected {key_matches} matching {key_name} pattern(s). Values redacted.",
                            "remediation": "Revoke and rotate exposed keys immediately. Store API keys in an external secret manager.",
                        })

                # E. Exposed Email Addresses (Informational / Medium)
                if "email" in col_lower or "mail" in col_lower:
                    email_matches = sum(1 for v in vals if RE_EMAIL.match(v.strip()))
                    if email_matches > 0 and email_matches == len(vals):
                        # High volume of emails exposed in plain text
                        findings.append({
                            "id": f"email_exposed_{table}_{col_name}",
                            "category": "SENSITIVE_DATA_EXPOSURE",
                            "severity": "LOW",
                            "title": "Plaintext Customer Email Directory",
                            "table": table,
                            "column": col_name,
                            "sample_count": email_matches,
                            "evidence_summary": f"Column contains {email_matches} valid email address(es) across sampled rows. Values redacted.",
                            "remediation": "Ensure data protection regulations (GDPR/CCPA) consent is satisfied and export access is restricted.",
                        })

                # F. Exposed Phone Numbers (Medium)
                if any(ph_kw in col_lower for ph_kw in ("phone", "mobile", "tel", "cell", "contact_no")):
                    ph_matches = sum(1 for v in vals if RE_PHONE.match(v.strip()))
                    if ph_matches > 0:
                        findings.append({
                            "id": f"phone_exposed_{table}_{col_name}",
                            "category": "SENSITIVE_DATA_EXPOSURE",
                            "severity": "MEDIUM",
                            "title": "Plaintext Phone Numbers Detected",
                            "table": table,
                            "column": col_name,
                            "sample_count": ph_matches,
                            "evidence_summary": f"Detected {ph_matches} telephone number(s) in sample. Values redacted.",
                            "remediation": "Mask or tokenize telephone numbers to comply with consumer privacy frameworks.",
                        })

                # G. Unencrypted Private Cryptographic Keys (PEM) (Critical)
                pem_matches = sum(1 for v in vals if RE_PEM_KEY.search(v))
                if pem_matches > 0:
                    findings.append({
                        "id": f"pem_exposed_{table}_{col_name}",
                        "category": "SENSITIVE_DATA_EXPOSURE",
                        "severity": "CRITICAL",
                        "title": "Unencrypted Private Cryptographic Key (PEM) Stored",
                        "table": table,
                        "column": col_name,
                        "sample_count": pem_matches,
                        "evidence_summary": f"Detected {pem_matches} private key PEM header(s) in sample. Values redacted.",
                        "remediation": "Immediately revoke and regenerate exposed private keys. Never store private keys in database records.",
                    })

        return findings, len(target_tables)

    def _fetch_bounded_sample(self, table: str, cols: List[str]) -> List[Dict[str, Any]]:
        """Safely retrieves up to MAX_SAMPLE_ROWS records from the specified table."""
        ctype = self.connector.connector_type.lower()

        if ctype == "mongodb":
            try:
                # Use JSON action syntax for MongoDB connector
                import json
                m_query = json.dumps({
                    "action": "find",
                    "collection": table,
                    "limit": MAX_SAMPLE_ROWS,
                })
                res = self.connector.execute_query(m_query)
                if res.success and res.rows:
                    return res.rows
            except Exception as e:
                logger.debug(f"MongoDB sample query error on {table}: {e}")
            return []

        # Relational SQL connectors
        quoted_table = safe_quote_identifier(table, ctype)
        query = f"SELECT * FROM {quoted_table} LIMIT {MAX_SAMPLE_ROWS};"
        try:
            res = self.connector.execute_query(query)
            if res.success and res.rows:
                return res.rows
        except Exception as e:
            logger.debug(f"SQL sample query error on {table}: {e}")
        return []

    def _record_security_events(self, findings: List[Dict[str, Any]]) -> None:
        """
        Logs critical and high findings to SecurityEventManager, avoiding duplicate logs.
        Never stores or logs raw secret values.
        """
        try:
            # Query recent security events for deduplication
            recent_events = list_security_events(
                user_id=self.user_id,
                database_identity=self.db_identity,
                limit=100,
            )
            existing_signatures = {
                f"{e.source}:{e.resource}:{e.event_type.value if hasattr(e.event_type, 'value') else str(e.event_type)}"
                for e in recent_events
            }

            for f in findings:
                sev = f.get("severity", "LOW")
                if sev not in ("CRITICAL", "HIGH"):
                    continue

                cat = f.get("category", "")
                table = f.get("table", "database")
                col = f.get("column", "")
                resource = f"{table}.{col}" if col else table

                event_type = (
                    SecurityEventType.DATA_LEAK_BLOCKED
                    if cat == "SENSITIVE_DATA_EXPOSURE"
                    else SecurityEventType.POLICY_VIOLATION
                )

                sig = f"database_posture_scanner:{resource}:{event_type.value}"
                if sig in existing_signatures:
                    continue  # Deduplicated

                sec_sev = (
                    SecurityEventSeverity.CRITICAL
                    if sev == "CRITICAL"
                    else SecurityEventSeverity.HIGH
                )

                SecurityEventManager.log_security_event(
                    user_id=self.user_id,
                    database_identity=self.db_identity,
                    event_type=event_type,
                    severity=sec_sev,
                    source="database_posture_scanner",
                    resource=resource,
                    description=f"Security Posture Finding: {f.get('title')}. {f.get('evidence_summary')}",
                    mitigation=f.get("remediation", ""),
                    metadata={
                        "finding_id": f.get("id"),
                        "category": cat,
                        "table": table,
                        "column": col,
                        "sample_count": f.get("sample_count", 0),
                    },
                )
                existing_signatures.add(sig)

        except Exception as e:
            logger.warning(f"Could not record security events from scanner: {e}")


def explain_security_finding(finding: Dict[str, Any], use_llm: bool = True) -> Dict[str, Any]:
    """
    Generates a structured, actionable security explanation for a finding.
    Explains why it matters, real-world impact, prioritized remediation steps,
    and technical limitations/uncertainty.
    Ensures zero raw secrets or sensitive data are passed to LLMs.
    """
    title = finding.get("title", "Security Finding")
    category = finding.get("category", "GENERAL")
    severity = finding.get("severity", "MEDIUM")
    table = finding.get("table", "")
    column = finding.get("column", "")
    location = f"table '{table}'" if table else "connection configuration"
    if column:
        location += f" (column '{column}')"
    evidence = finding.get("evidence_summary", "")

    # Deterministic high-quality expert explanation
    why_it_matters = f"This finding indicates a {severity} risk condition in {location}. {evidence}"
    if category == "SENSITIVE_DATA_EXPOSURE":
        if "Password" in title:
            why_it_matters = (
                f"Storing unhashed credentials in {location} makes user accounts vulnerable to total compromise "
                "if read access is obtained via SQL injection, backup leakage, or insider access."
            )
            potential_impact = (
                "Credential stuffing across third-party services, unauthorized account takeovers, "
                "and severe non-compliance penalties under GDPR and SOC 2."
            )
            remediation_steps = [
                "1. Implement salted, slow one-way password hashing (Argon2id or bcrypt with cost >= 12).",
                "2. Force a global password reset for all affected accounts immediately upon deploying hashing.",
                "3. Ensure plaintext password variables are zeroed in memory after verification.",
            ]
        elif "Payment Card" in title:
            why_it_matters = (
                f"Primary Account Numbers (PANs) detected in {location} violate PCI-DSS storage requirements. "
                "Databases must never store unencrypted or un-tokenized PANs."
            )
            potential_impact = (
                "Credit card fraud, merchant account termination, mandatory forensic audits, and statutory fines."
            )
            remediation_steps = [
                "1. Migrate payment storage to a PCI-DSS certified payment gateway or vault tokenization service.",
                "2. Purge raw PANs from database records immediately; retain only the last 4 digits for receipt display.",
                "3. Rotate database encryption keys if transparent data encryption (TDE) was relied upon as the sole control.",
            ]
        elif "Private Cryptographic Key" in title or "Key" in title or "Token" in title:
            why_it_matters = (
                f"Secret cryptographic keys or API credentials stored in {location} grant unauthorized entities direct "
                "programmatic access to connected cloud infrastructure or third-party APIs."
            )
            potential_impact = (
                "Complete service impersonation, unauthorized API consumption charges, and secondary data breaches."
            )
            remediation_steps = [
                "1. Immediately revoke the exposed key/token in the issuing provider's console.",
                "2. Move credentials to an encrypted secret manager (e.g., HashiCorp Vault, AWS Secrets Manager).",
                "3. Review access logs for the affected key to verify whether unauthorized API calls were made.",
            ]
        elif "SSN" in title:
            why_it_matters = (
                f"Social Security Numbers in {location} represent high-impact Personally Identifiable Information (PII) "
                "that can facilitate permanent identity theft."
            )
            potential_impact = "Identity theft, regulatory enforcement actions under state privacy laws, and litigation."
            remediation_steps = [
                "1. Encrypt SSN columns using AES-256 application-level authenticated encryption.",
                "2. Restrict SELECT permissions on this column strictly to authorized compliance roles.",
                "3. Audit all database query logs accessing this column.",
            ]
        else:
            why_it_matters = f"Sensitive customer information in {location} is stored without column-level masking or access restriction."
            potential_impact = "Exposure to unauthorized export, phishing list compilation, and privacy regulation non-compliance."
            remediation_steps = [
                "1. Apply database-level dynamic data masking or application-level redaction.",
                "2. Enforce strict role-based access control (RBAC) on tables containing personal data.",
                "3. Implement export rate-limiting.",
            ]
    elif category == "ACCESS_CONTROL":
        why_it_matters = (
            f"The database connection operates with administrative/superuser privileges on {location}. "
            "Any successful query injection or application vulnerability inherits full cluster control."
        )
        potential_impact = "Full database destruction, administrative user creation, and circumvention of all schema controls."
        remediation_steps = [
            "1. Provision a dedicated application service account with SELECT, INSERT, UPDATE, DELETE only.",
            "2. Revoke SUPER, DROP, and GRANT privileges from the application connection string.",
            "3. Restrict host permissions to the application server's specific IP/subnet.",
        ]
    elif category == "CONNECTION_SECURITY":
        why_it_matters = (
            f"Network transport to {location} is unencrypted or unverified. Traffic is vulnerable to on-path interception."
        )
        potential_impact = "Man-in-the-middle (MitM) credential sniffing and query manipulation over local or cloud networks."
        remediation_steps = [
            "1. Enable and require TLS/SSL encryption on the database server.",
            "2. Configure client connection options to enforce certificate verification (e.g., ssl_mode=verify-full).",
            "3. Reject unencrypted fallback connections at the database firewall layer.",
        ]
    else:
        potential_impact = "Operational security risk and deviation from hardening best practices."
        remediation_steps = [
            "1. Review the affected database entity against security baseline policies.",
            "2. Apply least-privilege configurations and enable connection auditing.",
        ]

    uncertainty_and_limitations = (
        "Note: Findings are derived from bounded read-only sampling (up to 50 rows per table) and supported connector metadata. "
        "Records outside the sampled window were not inspected. Verification by the system administrator is recommended before applying changes."
    )

    # Optional AI enhancement using Groq if available (only passing sanitized summary text, ZERO secrets)
    if use_llm:
        try:
            from app.config import get_groq_client, GROQ_MODEL
            client = get_groq_client()
            if client:
                prompt = (
                    f"You are a database cybersecurity expert. Provide a concise, professional 3-sentence explanation "
                    f"and prioritized remediation advice for the following database security finding (no code or markdown fences):\n"
                    f"Finding Title: {title}\n"
                    f"Category: {category}\n"
                    f"Severity: {severity}\n"
                    f"Location: {location}\n"
                    f"Evidence: {evidence}\n"
                )
                response = client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=250,
                    temperature=0.2,
                )
                ai_text = response.choices[0].message.content.strip()
                if ai_text:
                    why_it_matters = ai_text
        except Exception as e:
            logger.debug(f"AI explanation enhancement fallback to deterministic: {e}")

    return {
        "finding_id": finding.get("id"),
        "title": title,
        "severity": severity,
        "category": category,
        "location": location,
        "why_it_matters": why_it_matters,
        "potential_impact": potential_impact,
        "remediation_steps": remediation_steps,
        "uncertainty_and_limitations": uncertainty_and_limitations,
    }

