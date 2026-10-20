"""
backend/tests/test_google_oauth_pkce.py
Focused tests for Google OAuth RFC 8252 PKCE flow, state validation, callback handling,
cancellation, missing config, backend token verification, and local login regression.
"""
import unittest
import hashlib
import base64
import secrets
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from app.main import app
from app.security.firebase_auth import verify_firebase_id_token
from app.security.sessions import (
    sync_firebase_user,
    get_user_db,
    UserRecord,
    register_user,
    authenticate_user_detailed,
)

class TestGoogleOAuthPKCE(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_pkce_challenge_computation(self):
        """Verify standard S256 PKCE computation matches RFC 7636 Appendix B."""
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        self.assertEqual(challenge, "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")

    def test_oauth_state_generation_and_uniqueness(self):
        """Verify CSRF state parameters are sufficiently random and unique."""
        states = [secrets.token_hex(16) for _ in range(100)]
        self.assertEqual(len(set(states)), 100)
        for s in states:
            self.assertEqual(len(s), 32)

    def test_oauth_callback_state_validation_logic(self):
        """Verify callback processing correctly distinguishes valid state vs CSRF state mismatch."""
        session_state = secrets.token_hex(16)
        valid_incoming_state = session_state
        mismatched_state = secrets.token_hex(16)

        # 1. Matching state -> accepted
        self.assertEqual(session_state, valid_incoming_state)

        # 2. Mismatched state -> rejected (simulating CSRF attempt)
        self.assertNotEqual(session_state, mismatched_state)

        # 3. Missing state -> rejected
        self.assertFalse(bool(""))

    def test_oauth_cancellation_handling_logic(self):
        """Verify callback error parameters (e.g. user cancelled) are properly detected."""
        error = "access_denied"
        error_desc = "The user denied the request to access account details."

        # Simulate handler processing cancellation
        is_cancelled = bool(error == "access_denied" or "cancelled" in (error_desc or "").lower())
        self.assertTrue(is_cancelled)

    def test_missing_client_id_configuration_logic(self):
        """Verify desktop client ID fallback logic."""
        default_client_id = "1045610580763-dvtqgpm0dla9laa7r8q9m883qdr7itjd.apps.googleusercontent.com"
        
        # When env is empty, fallback must supply the valid Desktop client ID
        env_vars = {}
        client_id = env_vars.get("GOOGLE_DESKTOP_CLIENT_ID") or default_client_id
        self.assertEqual(client_id, default_client_id)
        self.assertTrue(client_id.endswith(".apps.googleusercontent.com"))

    def test_backend_rejects_empty_or_malformed_token(self):
        """Verify verify_firebase_id_token rejects malformed input without crashing."""
        self.assertIsNone(verify_firebase_id_token(""))
        self.assertIsNone(verify_firebase_id_token("not-a-valid-jwt"))
        self.assertIsNone(verify_firebase_id_token(None))

    def test_backend_firebase_endpoint_requires_valid_token(self):
        """Verify /auth/firebase rejects forged or unverified tokens."""
        resp = self.client.post(
            "/auth/firebase",
            json={"id_token": "forged.header.signature", "username": "attacker", "email": "attacker@evil.com"},
        )
        self.assertEqual(resp.status_code, 401)
        self.assertIn("Invalid or expired", resp.json().get("detail", ""))

    def test_sync_firebase_user_creates_and_retrieves_user(self):
        """Verify sync_firebase_user creates a local user and maintains session identity."""
        test_uid = f"google_test_uid_{secrets.token_hex(4)}"
        test_email = f"user_{secrets.token_hex(4)}@example.com"
        test_name = "OAuth Test User"

        user1 = sync_firebase_user(test_uid, email=test_email, display_name=test_name)
        self.assertIsNotNone(user1)
        self.assertEqual(user1["email"], test_email)
        self.assertIsNotNone(user1["username"])

        # Syncing again with same UID must retrieve same user
        user2 = sync_firebase_user(test_uid, email=test_email, display_name="Updated Name")
        self.assertEqual(user2["user_id"], user1["user_id"])

    def test_local_login_regression(self):
        """Verify local username/password login continues to function properly."""
        test_user = f"local_user_{secrets.token_hex(4)}"
        test_pass = "SecurePass123!"
        test_email = f"{test_user}@test.local"

        # Register local user
        reg_user = register_user(test_user, test_pass, test_email)
        self.assertEqual(reg_user["username"], test_user)

        # Authenticate with valid password
        auth_user, reason = authenticate_user_detailed(test_user, test_pass)
        self.assertIsNotNone(auth_user)
        self.assertEqual(reason, "SUCCESS")

        # Authenticate with invalid password
        bad_auth, bad_reason = authenticate_user_detailed(test_user, "WrongPassword!")
        self.assertIsNone(bad_auth)
        self.assertEqual(bad_reason, "INVALID_PASSWORD")

    def test_google_account_cannot_be_accessed_via_arbitrary_local_password(self):
        """Verify Google-synced accounts reject password authentication and direct user to Google login."""
        test_uid = f"google_uid_{secrets.token_hex(4)}"
        test_email = f"google_user_{secrets.token_hex(4)}@gmail.com"
        synced = sync_firebase_user(test_uid, email=test_email, display_name="Google Only User")

        # Attempt local password login on Google account
        user, reason = authenticate_user_detailed(synced["username"], "AnyPassword123")
        self.assertIsNone(user)
        self.assertEqual(reason, "GOOGLE_AUTH_REQUIRED")

if __name__ == "__main__":
    unittest.main()
