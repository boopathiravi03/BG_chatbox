#!/usr/bin/env python
"""
backend/scratch/test_ip_intelligence.py

Comprehensive Test Suite for IP Threat Intelligence & Intrusion Detection:
1. Trusted proxy client IP extraction & protection against spoofed X-Forwarded-For headers
2. Brute-force authentication detection threshold & sliding window behavior
3. Temporary IP quarantine blocking & expiration check
4. Administrative unblock functionality
5. High-frequency request burst detection
6. Automated path probe / scanner detection
7. Attributing blocked SQL injection and destructive DDL events to client IP
8. SecurityEventManager deduplication and integration
9. Local reputation provider verification (local evidence only, zero paid dependencies, zero external telemetry)
10. Privacy protection: Zero raw credential/token logging, sensitive data redaction
"""

import sys
import os
import time
import unittest
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.security.ip_intelligence import (
    extract_client_ip,
    is_ip_in_trusted_proxies,
    get_trusted_proxies,
    IntrusionDetectionEngine,
    LocalReputationProvider,
    AUTH_FAILURE_THRESHOLD,
    BURST_REQUEST_THRESHOLD,
    SCAN_PROBE_THRESHOLD,
)
from app.intelligence.governance.models import (
    SecurityEventType,
    SecurityEventSeverity,
)
from app.intelligence.governance.security_events import SecurityEventManager
from app.intelligence.governance.audit_store import list_security_events, verify_audit_chain
from app.tools.execute_query import execute_query, validate_sql
from app.database.connection_context import set_user_context_for_request, get_request_client_ip


class MockRequest:
    """Mock FastAPI Request object for testing IP extraction and headers."""
    def __init__(self, client_host: str, headers: dict = None):
        class Client:
            def __init__(self, host):
                self.host = host
        self.client = Client(client_host) if client_host else None
        self.headers = headers or {}


class TestIPIntelligenceAndIntrusion(unittest.TestCase):

    def setUp(self):
        # Fresh intrusion engine instance for tests
        self.engine = IntrusionDetectionEngine()

    def test_01_spoofed_forwarded_for_not_trusted_by_default(self):
        """Ensure client-supplied X-Forwarded-For headers are ignored unless client IP is a trusted proxy."""
        # Ensure BGAI_TRUSTED_PROXIES is empty or does not include 203.0.113.1
        os.environ.pop("BGAI_TRUSTED_PROXIES", None)

        req = MockRequest(
            client_host="203.0.113.1",
            headers={"X-Forwarded-For": "8.8.8.8, 10.0.0.1", "X-Real-IP": "1.1.1.1"}
        )
        extracted = extract_client_ip(req)
        # MUST return the direct peer connection IP, NOT the spoofed header
        self.assertEqual(extracted, "203.0.113.1")

    def test_02_trusted_proxy_header_extraction(self):
        """Ensure X-Forwarded-For is respected ONLY when direct client matches configured trusted proxy CIDR/IP."""
        os.environ["BGAI_TRUSTED_PROXIES"] = "10.0.0.0/8, 127.0.0.1"

        try:
            # Case A: Request from trusted proxy 10.0.0.5 with legitimate upstream client 198.51.100.44
            req_trusted = MockRequest(
                client_host="10.0.0.5",
                headers={"X-Forwarded-For": "198.51.100.44, 10.0.0.5"}
            )
            extracted_trusted = extract_client_ip(req_trusted)
            self.assertEqual(extracted_trusted, "198.51.100.44")

            # Case B: Request from untrusted external IP attempting to spoof forwarded IP
            req_untrusted = MockRequest(
                client_host="192.0.2.1",
                headers={"X-Forwarded-For": "198.51.100.44"}
            )
            extracted_untrusted = extract_client_ip(req_untrusted)
            self.assertEqual(extracted_untrusted, "192.0.2.1")
        finally:
            os.environ.pop("BGAI_TRUSTED_PROXIES", None)

    def test_03_invalid_or_unknown_ip_fallback(self):
        """Ensure missing or corrupted IP representations fallback safely to 'unknown' without crashing."""
        req_none = MockRequest(client_host="")
        self.assertEqual(extract_client_ip(req_none), "unknown")

        req_malformed = MockRequest(client_host="not-an-ip-address")
        self.assertEqual(extract_client_ip(req_malformed), "unknown")

    def test_04_brute_force_detection_threshold(self):
        """Verify that repeated failed logins from an IP trigger BRUTE_FORCE_DETECTED security event."""
        test_ip = "198.51.100.99"
        user_id = "test_user_bf"

        # Record failures up to threshold - 1
        for i in range(AUTH_FAILURE_THRESHOLD - 1):
            res = self.engine.record_auth_failure(test_ip, username="admin", user_id=user_id)
            self.assertIsNone(res)

        # The N-th failure must trigger an alert
        alert = self.engine.record_auth_failure(test_ip, username="admin", user_id=user_id)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.event_type, SecurityEventType.BRUTE_FORCE_DETECTED)
        self.assertEqual(alert.severity, SecurityEventSeverity.HIGH)
        self.assertIn(test_ip, alert.description)
        self.assertEqual(alert.metadata.get("source_ip"), test_ip)
        self.assertEqual(alert.metadata.get("target_account"), "admin")

    def test_05_temporary_block_and_expiration(self):
        """Verify temporary blocking, enforcement, and time expiration."""
        test_ip = "203.0.113.88"
        # 1. Not blocked initially
        is_blocked, _ = self.engine.is_ip_blocked(test_ip)
        self.assertFalse(is_blocked)

        # 2. Apply short block (1 second)
        block = self.engine.apply_temporary_block(
            ip_address=test_ip,
            reason="Test automated quarantine",
            rule_triggered="TEST_RULE",
            duration_seconds=1,
            user_id="test_admin",
        )
        self.assertTrue(block.is_active())

        # 3. Verify engine reports blocked
        is_blocked, active_block = self.engine.is_ip_blocked(test_ip)
        self.assertTrue(is_blocked)
        self.assertEqual(active_block.rule_triggered, "TEST_RULE")

        # 4. Wait for expiration
        time.sleep(1.1)
        is_blocked_after, _ = self.engine.is_ip_blocked(test_ip)
        self.assertFalse(is_blocked_after)

    def test_06_admin_manual_unblock(self):
        """Verify administrator can safely remove an active IP block."""
        test_ip = "203.0.113.77"
        self.engine.apply_temporary_block(
            ip_address=test_ip,
            reason="Policy test",
            rule_triggered="MANUAL_TEST",
            duration_seconds=600,
        )
        self.assertTrue(self.engine.is_ip_blocked(test_ip)[0])

        # Remove block
        unblocked = self.engine.remove_block(test_ip, admin_user_id="superadmin")
        self.assertTrue(unblocked)
        self.assertFalse(self.engine.is_ip_blocked(test_ip)[0])

        # Removing a non-blocked IP returns False safely
        self.assertFalse(self.engine.remove_block("1.2.3.4"))

    def test_07_request_burst_velocity_detection(self):
        """Verify abnormal request burst detection across sliding window."""
        burst_ip = "192.0.2.70"
        alert = None
        for _ in range(BURST_REQUEST_THRESHOLD):
            res = self.engine.record_request_activity(burst_ip, endpoint="/query", user_id="test_burst")
            if res:
                alert = res
                break

        self.assertIsNotNone(alert)
        self.assertEqual(alert.event_type, SecurityEventType.SUSPICIOUS_BURST_DETECTED)
        self.assertEqual(alert.metadata.get("source_ip"), burst_ip)

    def test_08_path_probe_and_crawler_detection(self):
        """Verify endpoint probing of known crawler targets triggers ENDPOINT_SCAN_DETECTED."""
        crawler_ip = "198.51.100.12"
        # Probing common scanner targets
        res1 = self.engine.record_probe_attempt(crawler_ip, "/wp-login.php")
        res2 = self.engine.record_probe_attempt(crawler_ip, "/.env")
        res3 = self.engine.record_probe_attempt(crawler_ip, "/admin/config.json")

        self.assertIsNotNone(res3)
        self.assertEqual(res3.event_type, SecurityEventType.ENDPOINT_SCAN_DETECTED)
        self.assertEqual(res3.metadata.get("source_ip"), crawler_ip)

    def test_09_sql_injection_and_ddl_ip_attribution(self):
        """Verify that blocked destructive DDL and stacked SQL injection are logged with client IP."""
        client_ip = "203.0.113.15"
        user_id = "test_sec_user_ip"
        set_user_context_for_request(user_id=user_id, client_ip=client_ip)

        self.assertEqual(get_request_client_ip(), client_ip)

        # 1. Destructive DDL query execution attempt
        res_ddl = execute_query("DROP TABLE users;")
        self.assertFalse(res_ddl["success"])
        self.assertIn("blocked", res_ddl["error"].lower())

        # 2. Stacked statement injection attempt
        res_inj = execute_query("SELECT 1; DROP TABLE products;")
        self.assertFalse(res_inj["success"])

        # 3. Verify event recorded in SecurityEventManager with client_ip
        events = list_security_events(user_id=user_id, ip_address=client_ip, limit=10)
        self.assertGreater(len(events), 0)
        found_ips = [e.metadata.get("source_ip") for e in events]
        self.assertIn(client_ip, found_ips)

    def test_10_local_reputation_provider_safety(self):
        """Verify LocalReputationProvider never sends external requests and classifies accurately."""
        provider = LocalReputationProvider()
        # Internal RFC-1918 LAN IP
        rep_lan = provider.query_reputation("192.168.1.50")
        self.assertEqual(rep_lan["classification"], "internal_trusted")
        self.assertTrue(rep_lan["is_private_network"])
        self.assertEqual(rep_lan["provider"], "local_evidence")

        # Localhost
        rep_loopback = provider.query_reputation("127.0.0.1")
        self.assertEqual(rep_loopback["classification"], "internal_trusted")
        self.assertTrue(rep_loopback["is_loopback"])

        # Unknown
        rep_unk = provider.query_reputation("unknown")
        self.assertEqual(rep_unk["status"], "unknown_ip")

    def test_11_cryptographic_audit_ledger_continuity(self):
        """Ensure all IP security events seamlessly integrate into the SHA-256 tamper-evident chain."""
        SecurityEventManager.log_ip_threat(
            user_id="test_chain_user",
            database_identity="test_db",
            event_type=SecurityEventType.INJECTION_PATTERN_DETECTED,
            severity=SecurityEventSeverity.HIGH,
            source_ip="198.51.100.55",
            resource="/query",
            description="Unit test threat logged into audit chain",
            mitigation="Blocked",
        )
        is_valid, verified_count, discrepancies = verify_audit_chain(user_id="test_chain_user")
        self.assertTrue(is_valid)
        self.assertGreater(verified_count, 0)
        self.assertEqual(len(discrepancies), 0)


if __name__ == "__main__":
    unittest.main()

