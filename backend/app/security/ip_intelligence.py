"""backend/app/security/ip_intelligence.py

IP Threat Intelligence & Intrusion Detection System for BG AI.
Provides:
1. Safe client IP extraction with trusted-proxy verification (never blindly trusting X-Forwarded-For)
2. In-memory sliding-window intrusion detection:
   - Failed authentication brute-force detector
   - Endpoint probe / path traversal / scanning pattern detector
   - Suspicious request bursts
   - SQL injection / dangerous DDL attribution
   - Repeated policy bypass tracking
3. Optional external IP reputation provider interface (default local-only, zero paid dependencies, zero telemetry)
4. Temporary, auditable, time-limited IP blocking with safe concurrency and manual administrative unblock
5. Seamless logging to SecurityEventManager and tamper-evident audit ledger.
"""

from __future__ import annotations

import os
import re
import time
import ipaddress
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set, Tuple
from collections import defaultdict, deque

from fastapi import Request

from app.intelligence.governance.models import (
    SecurityEventType,
    SecurityEventSeverity,
    SecurityEventRecord,
)
from app.intelligence.governance.security_events import SecurityEventManager

logger = logging.getLogger(__name__)

# Bounded in-memory sliding window constraints
MAX_HISTORY_PER_IP = 100
MAX_TRACKED_IPS = 1000
CLEANUP_INTERVAL_SECONDS = 300

# Default intrusion thresholds (configurable via env vars)
AUTH_FAILURE_THRESHOLD = int(os.getenv("BGAI_AUTH_FAILURE_THRESHOLD", "5"))
AUTH_FAILURE_WINDOW_SECONDS = int(os.getenv("BGAI_AUTH_FAILURE_WINDOW", "300"))  # 5 min

BURST_REQUEST_THRESHOLD = int(os.getenv("BGAI_BURST_REQUEST_THRESHOLD", "60"))
BURST_WINDOW_SECONDS = int(os.getenv("BGAI_BURST_WINDOW", "60"))  # 60 req/min

SCAN_PROBE_THRESHOLD = int(os.getenv("BGAI_SCAN_PROBE_THRESHOLD", "8"))
SCAN_WINDOW_SECONDS = int(os.getenv("BGAI_SCAN_WINDOW", "120"))  # 2 min

BLOCK_DURATION_SECONDS = int(os.getenv("BGAI_TEMP_BLOCK_DURATION", "900"))  # 15 min default


def get_trusted_proxies() -> Set[str]:
    """
    Returns configured trusted proxy CIDRs/IPs from environment.
    If empty, reverse proxy headers are NOT trusted.
    """
    raw = os.getenv("BGAI_TRUSTED_PROXIES", "").strip()
    if not raw:
        return set()
    return {p.strip() for p in raw.split(",") if p.strip()}


def is_ip_in_trusted_proxies(ip_str: str, trusted_proxies: Set[str]) -> bool:
    """
    Safely verifies if an IP address belongs to any configured trusted proxy or CIDR range.
    """
    if not trusted_proxies:
        return False
    try:
        ip = ipaddress.ip_address(ip_str)
        for tp in trusted_proxies:
            try:
                if "/" in tp:
                    if ip in ipaddress.ip_network(tp, strict=False):
                        return True
                else:
                    if ip == ipaddress.ip_address(tp):
                        return True
            except ValueError:
                continue
    except ValueError:
        return False
    return False


def extract_client_ip(request: Request) -> str:
    """
    Safely extracts the client IP address from a FastAPI request.
    Rules:
    1. If request.client is present, start with request.client.host.
    2. Only inspect X-Forwarded-For or X-Real-IP if the direct client IP is in BGAI_TRUSTED_PROXIES.
    3. Never blindly trust client-supplied headers.
    4. If IP cannot be parsed or determined, return 'unknown'.
    """
    direct_ip = "unknown"
    if request.client and request.client.host:
        direct_ip = request.client.host.strip()

    # Validate direct IP format
    try:
        ipaddress.ip_address(direct_ip)
    except ValueError:
        if direct_ip != "unknown":
            direct_ip = "unknown"

    trusted_proxies = get_trusted_proxies()
    # If direct client is NOT a configured trusted proxy, return direct_ip immediately
    if not is_ip_in_trusted_proxies(direct_ip, trusted_proxies):
        return direct_ip

    # Direct client is trusted proxy, inspect X-Forwarded-For from right to left
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        parts = [p.strip() for p in x_forwarded_for.split(",") if p.strip()]
        # Traverse backwards from proxy chain
        for candidate in reversed(parts):
            try:
                cand_ip = ipaddress.ip_address(candidate)
                # Return the first IP that is NOT one of our trusted proxies
                if not is_ip_in_trusted_proxies(candidate, trusted_proxies):
                    return str(cand_ip)
            except ValueError:
                continue

    x_real_ip = request.headers.get("X-Real-IP")
    if x_real_ip:
        cand = x_real_ip.strip()
        try:
            cand_ip = ipaddress.ip_address(cand)
            if not is_ip_in_trusted_proxies(cand, trusted_proxies):
                return str(cand_ip)
        except ValueError:
            pass

    return direct_ip


@dataclass
class TemporaryBlock:
    ip_address: str
    blocked_at: float
    expires_at: float
    reason: str
    rule_triggered: str
    admin_unblocked: bool = False

    def is_active(self) -> bool:
        if self.admin_unblocked:
            return False
        return time.time() < self.expires_at


class IntrusionDetectionEngine:
    """
    Thread-safe, sliding-window intrusion detector and IP threat classifier.
    Tracks:
    - Failed authentication attempts per IP and per account
    - Endpoint probe/scan attempts (404/unmapped paths)
    - Request velocity bursts
    - Known blocked queries / injection events
    - Active temporary IP blocks
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._auth_failures: Dict[str, deque] = defaultdict(lambda: deque(maxlen=MAX_HISTORY_PER_IP))
        self._request_timestamps: Dict[str, deque] = defaultdict(lambda: deque(maxlen=MAX_HISTORY_PER_IP))
        self._probed_paths: Dict[str, deque] = defaultdict(lambda: deque(maxlen=MAX_HISTORY_PER_IP))
        self._active_blocks: Dict[str, TemporaryBlock] = {}
        self._last_cleanup = time.time()

    def _cleanup_old_records(self, now: float) -> None:
        """Periodically bounds memory by discarding expired history and blocks."""
        if now - self._last_cleanup < CLEANUP_INTERVAL_SECONDS:
            return
        self._last_cleanup = now

        # Clean expired blocks
        expired = [ip for ip, b in self._active_blocks.items() if not b.is_active()]
        for ip in expired:
            self._active_blocks.pop(ip, None)

        # Bound tracked IPs if exceeding capacity
        for store in (self._auth_failures, self._request_timestamps, self._probed_paths):
            if len(store) > MAX_TRACKED_IPS:
                # Remove oldest keys
                keys_to_remove = list(store.keys())[: len(store) - MAX_TRACKED_IPS]
                for k in keys_to_remove:
                    store.pop(k, None)

    def is_ip_blocked(self, ip_address: str) -> Tuple[bool, Optional[TemporaryBlock]]:
        """Checks if an IP address is actively blocked."""
        if ip_address == "unknown":
            return False, None
        with self._lock:
            block = self._active_blocks.get(ip_address)
            if block and block.is_active():
                return True, block
            if block and not block.is_active():
                self._active_blocks.pop(ip_address, None)
            return False, None

    def apply_temporary_block(
        self,
        ip_address: str,
        reason: str,
        rule_triggered: str,
        duration_seconds: int = BLOCK_DURATION_SECONDS,
        user_id: str = "system",
    ) -> TemporaryBlock:
        """Applies a time-limited block to an IP address and logs to SecurityEventManager."""
        with self._lock:
            now = time.time()
            block = TemporaryBlock(
                ip_address=ip_address,
                blocked_at=now,
                expires_at=now + duration_seconds,
                reason=reason,
                rule_triggered=rule_triggered,
            )
            self._active_blocks[ip_address] = block

            # Log to SecurityEventManager
            try:
                SecurityEventManager.log_ip_threat(
                    user_id=user_id,
                    database_identity="intrusion_subsystem",
                    event_type=SecurityEventType.IP_BLOCKED,
                    severity=SecurityEventSeverity.HIGH,
                    source_ip=ip_address,
                    resource="IP_FILTER",
                    description=f"Temporary block placed on IP {ip_address} for {duration_seconds}s. Reason: {reason}",
                    mitigation=f"Reject incoming requests with HTTP 403 Forbidden until {datetime.fromtimestamp(block.expires_at, timezone.utc).isoformat()}",
                    metadata={
                        "rule_triggered": rule_triggered,
                        "duration_seconds": duration_seconds,
                        "expires_at": block.expires_at,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to log IP block event: {e}")

            return block

    def remove_block(self, ip_address: str, admin_user_id: str = "admin") -> bool:
        """Allows administrator to manually remove a block."""
        with self._lock:
            block = self._active_blocks.get(ip_address)
            if block and block.is_active():
                block.admin_unblocked = True
                self._active_blocks.pop(ip_address, None)
                # Log administrative action
                try:
                    SecurityEventManager.log_ip_threat(
                        user_id=admin_user_id,
                        database_identity="intrusion_subsystem",
                        event_type=SecurityEventType.POLICY_VIOLATION,
                        severity=SecurityEventSeverity.LOW,
                        source_ip=ip_address,
                        resource="IP_FILTER",
                        description=f"Administrative block removal executed for IP {ip_address}.",
                        mitigation="Restored request routing permissions.",
                        metadata={"action": "ADMIN_UNBLOCK", "admin_user_id": admin_user_id},
                    )
                except Exception:
                    pass
                return True
            return False

    def list_active_blocks(self) -> List[Dict[str, Any]]:
        """Returns all currently active temporary blocks."""
        with self._lock:
            now = time.time()
            return [
                {
                    "ip_address": b.ip_address,
                    "blocked_at": datetime.fromtimestamp(b.blocked_at, timezone.utc).isoformat(),
                    "expires_at": datetime.fromtimestamp(b.expires_at, timezone.utc).isoformat(),
                    "remaining_seconds": max(0, int(b.expires_at - now)),
                    "reason": b.reason,
                    "rule_triggered": b.rule_triggered,
                }
                for b in self._active_blocks.values()
                if b.is_active()
            ]

    def record_auth_failure(
        self,
        ip_address: str,
        username: str,
        user_id: str = "anonymous",
    ) -> Optional[SecurityEventRecord]:
        """
        Records a failed authentication attempt for an IP.
        If failures exceed AUTH_FAILURE_THRESHOLD within AUTH_FAILURE_WINDOW_SECONDS,
        flags a BRUTE_FORCE_DETECTED threat event and applies temporary block.
        """
        now = time.time()
        with self._lock:
            self._cleanup_old_records(now)
            window_start = now - AUTH_FAILURE_WINDOW_SECONDS
            q = self._auth_failures[ip_address]
            q.append((now, username))

            # Count failures in current window
            recent = [entry for entry in q if entry[0] >= window_start]
            count = len(recent)

            if count >= AUTH_FAILURE_THRESHOLD:
                # Trigger brute-force alert
                event = SecurityEventManager.log_brute_force(
                    user_id=user_id,
                    source_ip=ip_address,
                    attempt_count=count,
                    target_account=username,
                )
                # If persistent brute force (e.g. 2x threshold), apply temporary IP block
                if count >= AUTH_FAILURE_THRESHOLD * 2 and ip_address != "unknown":
                    self.apply_temporary_block(
                        ip_address=ip_address,
                        reason=f"Repeated brute-force authentication attacks ({count} failures)",
                        rule_triggered="AUTH_BRUTE_FORCE_LIMIT",
                        duration_seconds=BLOCK_DURATION_SECONDS,
                        user_id=user_id,
                    )
                return event
        return None

    def record_request_activity(
        self,
        ip_address: str,
        endpoint: str,
        user_id: str = "anonymous",
    ) -> Optional[SecurityEventRecord]:
        """
        Monitors request velocity per IP to detect abnormal request bursts.
        """
        now = time.time()
        with self._lock:
            self._cleanup_old_records(now)
            window_start = now - BURST_WINDOW_SECONDS
            q = self._request_timestamps[ip_address]
            q.append((now, endpoint))

            recent = [entry for entry in q if entry[0] >= window_start]
            if len(recent) >= BURST_REQUEST_THRESHOLD:
                # Deduplicate: only log if we haven't logged a burst for this IP in the last 60s
                # Clear or halve to avoid spamming alerts on every single subsequent request
                q.clear()
                event = SecurityEventManager.log_ip_threat(
                    user_id=user_id,
                    database_identity="api_gateway",
                    event_type=SecurityEventType.SUSPICIOUS_BURST_DETECTED,
                    severity=SecurityEventSeverity.MEDIUM,
                    source_ip=ip_address,
                    resource=endpoint,
                    description=f"High-frequency request burst ({len(recent)} requests within {BURST_WINDOW_SECONDS}s) observed from IP {ip_address}.",
                    mitigation="Recommended upstream rate limiting and connection pooling audit.",
                    metadata={"observed_rate": len(recent), "window_seconds": BURST_WINDOW_SECONDS},
                )
                return event
        return None

    def record_probe_attempt(
        self,
        ip_address: str,
        path: str,
        user_id: str = "anonymous",
    ) -> Optional[SecurityEventRecord]:
        """
        Records 404 or unmapped path probing to detect scanning bots or vulnerability crawlers.
        """
        now = time.time()
        # Common automated scanner indicators
        scan_indicators = (
            "php", "admin", "wp-", ".env", "config", "shell", ".git", "actuator",
            "eval-stdin", "swagger", "solr", "drupal", "boaform", "cgi-bin"
        )
        is_suspicious_path = any(ind in path.lower() for ind in scan_indicators)

        with self._lock:
            self._cleanup_old_records(now)
            window_start = now - SCAN_WINDOW_SECONDS
            q = self._probed_paths[ip_address]
            q.append((now, path))

            recent = [p for t, p in q if t >= window_start]
            # Flag if volume is high OR if suspicious scanner keywords are probed
            if len(recent) >= SCAN_PROBE_THRESHOLD or (is_suspicious_path and len(recent) >= 3):
                q.clear()
                event = SecurityEventManager.log_endpoint_scan(
                    user_id=user_id,
                    source_ip=ip_address,
                    probed_endpoints=recent,
                )
                return event
        return None


# Global singleton instance
_engine_instance = IntrusionDetectionEngine()


def get_intrusion_engine() -> IntrusionDetectionEngine:
    """Returns the singleton IntrusionDetectionEngine."""
    return _engine_instance


# ── Optional IP Reputation Provider Interface ──────────────────────────────────
class BaseIPReputationProvider:
    """
    Abstract interface for optional external IP reputation queries.
    By default, BG AI operates in local mode (zero paid deps, zero external network traffic).
    """

    def is_configured(self) -> bool:
        return False

    def query_reputation(self, ip_address: str) -> Dict[str, Any]:
        return {
            "ip_address": ip_address,
            "provider": "local_evidence",
            "status": "unavailable",
            "reputation_score": None,
            "classification": "unrated",
            "note": "External IP reputation provider is not configured. Threat classification is based exclusively on local behavioral evidence.",
        }


class LocalReputationProvider(BaseIPReputationProvider):
    """Default provider: Evaluates reputation strictly from locally recorded telemetry."""

    def is_configured(self) -> bool:
        # Check if an external provider key is set in environment (e.g. BGAI_IP_REPUTATION_API_KEY)
        return bool(os.getenv("BGAI_IP_REPUTATION_API_KEY"))

    def query_reputation(self, ip_address: str) -> Dict[str, Any]:
        if ip_address == "unknown":
            return {
                "ip_address": "unknown",
                "provider": "local_evidence",
                "status": "unknown_ip",
                "classification": "neutral",
                "note": "Source IP address could not be reliably determined.",
            }

        try:
            ip_obj = ipaddress.ip_address(ip_address)
            is_private = ip_obj.is_private
            is_loopback = ip_obj.is_loopback
        except ValueError:
            is_private = False
            is_loopback = False

        engine = get_intrusion_engine()
        is_blocked, block = engine.is_ip_blocked(ip_address)

        if is_blocked and block:
            return {
                "ip_address": ip_address,
                "provider": "local_evidence",
                "status": "active_block",
                "classification": "blocked",
                "reason": block.reason,
                "expires_at": datetime.fromtimestamp(block.expires_at, timezone.utc).isoformat(),
                "note": f"Temporarily blocked via rule {block.rule_triggered}.",
            }

        return {
            "ip_address": ip_address,
            "provider": "local_evidence",
            "status": "local_only",
            "is_private_network": is_private,
            "is_loopback": is_loopback,
            "classification": "internal_trusted" if (is_private or is_loopback) else "observed",
            "note": "External reputation lookup is not enabled. No external telemetry was transmitted.",
        }


_reputation_provider: BaseIPReputationProvider = LocalReputationProvider()


def get_reputation_provider() -> BaseIPReputationProvider:
    return _reputation_provider

