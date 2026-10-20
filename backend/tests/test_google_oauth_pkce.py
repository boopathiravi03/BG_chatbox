"""
backend/tests/test_google_oauth_pkce.py
Focused tests for Google OAuth RFC 8252 PKCE flow, ID token verification, and backend exchange.
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
from app.security.sessions import sync_firebase_user, get_user_db, UserRecord

class TestGoogleOAuthPKCE(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_pkce_challenge_computation(self):
        """Verify standard S256 PKCE computation matches RFC 7636."""
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

if __name__ == "__main__":
    unittest.main()

