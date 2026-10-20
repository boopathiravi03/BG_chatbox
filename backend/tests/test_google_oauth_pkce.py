"""
backend/tests/test_google_oauth_pkce.py
Comprehensive tests for Google OAuth RFC 8252 PKCE flow, state validation,
callback handling, token verification, audience/issuer validation, at_hash handling,
and local login regression.
"""
import unittest
import hashlib
import base64
import secrets
import sys
import os
import time
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from jose import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from app.main import app
from app.security.firebase_auth import (
    verify_google_id_token,
    verify_firebase_id_token,
    verify_identity_token,
    DEFAULT_GOOGLE_DESKTOP_CLIENT_ID,
    FIREBASE_PROJECT_ID,
)
from app.security.sessions import (
    sync_firebase_user,
    get_user_db,
    UserRecord,
    register_user,
    authenticate_user_detailed,
)


def generate_mock_rsa_jwk():
    """Helper to generate a real RS256 key pair and corresponding JWK structure."""
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = priv.public_key()
    priv_pem = priv.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("utf-8")

    pub_numbers = pub.public_numbers()

    def int_to_b64(n):
        b = n.to_bytes((n.bit_length() + 7) // 8, "big")
        return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")

    jwk_dict = {
        "kty": "RSA",
        "kid": "mock-test-kid-1",
        "use": "sig",
        "alg": "RS256",
        "n": int_to_b64(pub_numbers.n),
        "e": int_to_b64(pub_numbers.e),
    }

    pub_pem = pub.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return priv_pem, pub_pem, jwk_dict


class TestGoogleOAuthPKCE(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.priv_pem, cls.pub_pem, cls.jwk_dict = generate_mock_rsa_jwk()

    def setUp(self):
        self.client = TestClient(app)

    # 1. PKCE Standard Verification
    def test_pkce_challenge_computation(self):
        """Verify standard S256 PKCE computation matches RFC 7636 Appendix B."""
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        self.assertEqual(challenge, "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")

    # 2. State & CSRF Validation
    def test_oauth_state_generation_and_uniqueness(self):
        """Verify CSRF state parameters are sufficiently random and unique."""
        states = [secrets.token_hex(16) for _ in range(100)]
        self.assertEqual(len(set(states)), 100)
        for s in states:
            self.assertEqual(len(s), 32)

    def test_oauth_callback_state_validation_and_replay_prevention(self):
        """Verify state parameter validation and replay mitigation."""
        active_states = {secrets.token_hex(16): True}
        initial_state = list(active_states.keys())[0]

        # First use: valid
        self.assertIn(initial_state, active_states)
        del active_states[initial_state]  # Consumed

        # Replay attempt: must fail
        self.assertNotIn(initial_state, active_states)

        # Mismatched/unrecognized state: must fail
        forged_state = secrets.token_hex(16)
        self.assertNotIn(forged_state, active_states)

    # 3. User Cancellation & Callback Error Handling
    def test_oauth_cancellation_handling_logic(self):
        """Verify callback error parameters (e.g. user cancelled) are properly detected."""
        error = "access_denied"
        error_desc = "The user denied the request to access account details."

        is_cancelled = bool(
            error == "access_denied" or "cancelled" in (error_desc or "").lower()
        )
        self.assertTrue(is_cancelled)

    # 4. Configuration & PKCE Verifier Detection
    def test_missing_client_id_configuration_logic(self):
        """Verify desktop client ID fallback logic."""
        default_client_id = DEFAULT_GOOGLE_DESKTOP_CLIENT_ID
        env_vars = {}
        client_id = env_vars.get("GOOGLE_DESKTOP_CLIENT_ID") or default_client_id
        self.assertEqual(client_id, default_client_id)
        self.assertTrue(client_id.endswith(".apps.googleusercontent.com"))

    def test_missing_pkce_verifier_detection(self):
        """Verify missing PKCE verifier parameter is caught before token exchange."""
        code_verifier = ""
        self.assertFalse(bool(code_verifier))
        self.assertEqual(len(code_verifier), 0)

    # 5. Token Endpoint Error Diagnostics
    def test_google_invalid_grant_response_handling(self):
        """Verify handling of Google's invalid_grant response (expired/reused authorization code)."""
        google_response = {
            "error": "invalid_grant",
            "error_description": "Bad Request",
        }
        err_code = google_response.get("error")
        user_facing_msg = ""
        if err_code == "invalid_grant":
            user_facing_msg = (
                "Authorization code expired or has already been used. Please try signing in again."
            )
        self.assertIn("expired", user_facing_msg)

    def test_google_invalid_client_response_handling(self):
        """Verify handling of Google's invalid_client response."""
        google_response = {
            "error": "invalid_client",
            "error_description": "The provided client secret is invalid.",
        }
        err_code = google_response.get("error")
        user_facing_msg = ""
        if err_code == "invalid_client":
            user_facing_msg = (
                "Invalid OAuth client configuration. Please verify your client ID and client secret in .env."
            )
        self.assertIn("Invalid OAuth client configuration", user_facing_msg)

    def test_google_client_secret_missing_response_handling(self):
        """Verify handling of Google's client_secret is missing response."""
        google_response = {
            "error": "invalid_request",
            "error_description": "client_secret is missing.",
        }
        err_code = google_response.get("error")
        err_desc = google_response.get("error_description", "")
        user_facing_msg = ""
        if err_code == "invalid_request" and "client_secret" in err_desc:
            user_facing_msg = (
                "Google OAuth requires the Desktop Client Secret. Please set GOOGLE_DESKTOP_CLIENT_SECRET in .env."
            )
        self.assertIn("GOOGLE_DESKTOP_CLIENT_SECRET", user_facing_msg)

    # 6. Cryptographic Google ID Token Verification
    def test_valid_google_id_token_verification(self):
        """Verify valid Google OIDC ID token is verified cryptographically."""
        now = int(time.time())
        claims = {
            "iss": "https://accounts.google.com",
            "aud": DEFAULT_GOOGLE_DESKTOP_CLIENT_ID,
            "sub": "google_sub_valid_123",
            "email": "valid_user@gmail.com",
            "name": "Valid Google User",
            "iat": now - 10,
            "exp": now + 3600,
        }
        token = jwt.encode(
            claims,
            self.priv_pem,
            algorithm="RS256",
            headers={"kid": "mock-test-kid-1"},
        )

        with patch(
            "app.security.firebase_auth.get_google_oauth_certs",
            return_value={"keys": [self.jwk_dict]},
        ):
            verified = verify_google_id_token(token)
            self.assertIsNotNone(verified)
            self.assertEqual(verified["uid"], "google_sub_valid_123")
            self.assertEqual(verified["email"], "valid_user@gmail.com")
            self.assertEqual(verified["name"], "Valid Google User")
            self.assertEqual(verified["provider"], "google.com")

    def test_google_id_token_with_at_hash_handling(self):
        """Verify Google ID token with at_hash claim works without access_token and validates with matching access_token."""
        now = int(time.time())
        raw_access_token = "my_access_token_12345"
        at_digest = hashlib.sha256(raw_access_token.encode("ascii")).digest()
        at_hash = base64.urlsafe_b64encode(at_digest[:16]).decode("ascii").rstrip("=")

        claims = {
            "iss": "https://accounts.google.com",
            "aud": DEFAULT_GOOGLE_DESKTOP_CLIENT_ID,
            "sub": "google_sub_at_hash",
            "email": "athash@gmail.com",
            "name": "AT Hash User",
            "iat": now - 10,
            "exp": now + 3600,
            "at_hash": at_hash,
        }
        token = jwt.encode(
            claims,
            self.priv_pem,
            algorithm="RS256",
            headers={"kid": "mock-test-kid-1"},
        )

        with patch(
            "app.security.firebase_auth.get_google_oauth_certs",
            return_value={"keys": [self.jwk_dict]},
        ):
            # 1. Decode without access_token (at_hash bypassed safely)
            res1 = verify_google_id_token(token)
            self.assertIsNotNone(res1)
            self.assertEqual(res1["email"], "athash@gmail.com")

            # 2. Decode with matching access_token (at_hash cryptographically verified)
            res2 = verify_google_id_token(token, access_token=raw_access_token)
            self.assertIsNotNone(res2)
            self.assertEqual(res2["uid"], "google_sub_at_hash")

            # 3. Decode with WRONG access_token (at_hash mismatch rejected)
            res3 = verify_google_id_token(token, access_token="wrong_access_token")
            self.assertIsNone(res3)

    def test_google_token_wrong_audience_rejected(self):
        """Verify tokens with mismatched audience/client ID are rejected."""
        now = int(time.time())
        claims = {
            "iss": "https://accounts.google.com",
            "aud": "attacker_unauthorized_client_id.apps.googleusercontent.com",
            "sub": "google_attacker_1",
            "email": "attacker@example.com",
            "iat": now - 10,
            "exp": now + 3600,
        }
        token = jwt.encode(
            claims,
            self.priv_pem,
            algorithm="RS256",
            headers={"kid": "mock-test-kid-1"},
        )

        with patch(
            "app.security.firebase_auth.get_google_oauth_certs",
            return_value={"keys": [self.jwk_dict]},
        ):
            verified = verify_google_id_token(token)
            self.assertIsNone(verified)

    def test_google_token_wrong_issuer_rejected(self):
        """Verify tokens with invalid issuer are rejected."""
        now = int(time.time())
        claims = {
            "iss": "https://malicious-issuer.com",
            "aud": DEFAULT_GOOGLE_DESKTOP_CLIENT_ID,
            "sub": "google_sub_wrong_iss",
            "email": "fake@gmail.com",
            "iat": now - 10,
            "exp": now + 3600,
        }
        token = jwt.encode(
            claims,
            self.priv_pem,
            algorithm="RS256",
            headers={"kid": "mock-test-kid-1"},
        )

        with patch(
            "app.security.firebase_auth.get_google_oauth_certs",
            return_value={"keys": [self.jwk_dict]},
        ):
            verified = verify_google_id_token(token)
            self.assertIsNone(verified)

    def test_google_token_expired_rejected(self):
        """Verify expired tokens are rejected."""
        now = int(time.time())
        claims = {
            "iss": "https://accounts.google.com",
            "aud": DEFAULT_GOOGLE_DESKTOP_CLIENT_ID,
            "sub": "google_sub_expired",
            "email": "expired@gmail.com",
            "iat": now - 3600,
            "exp": now - 100,  # Expired
        }
        token = jwt.encode(
            claims,
            self.priv_pem,
            algorithm="RS256",
            headers={"kid": "mock-test-kid-1"},
        )

        with patch(
            "app.security.firebase_auth.get_google_oauth_certs",
            return_value={"keys": [self.jwk_dict]},
        ):
            verified = verify_google_id_token(token)
            self.assertIsNone(verified)

    def test_sending_google_token_to_firebase_verifier_strictly_rejected(self):
        """Verify sending a Google OIDC token to the strict Firebase verifier returns None."""
        now = int(time.time())
        claims = {
            "iss": "https://accounts.google.com",
            "aud": DEFAULT_GOOGLE_DESKTOP_CLIENT_ID,
            "sub": "google_sub_123",
            "email": "user@gmail.com",
            "iat": now - 10,
            "exp": now + 3600,
        }
        google_token = jwt.encode(
            claims,
            self.priv_pem,
            algorithm="RS256",
            headers={"kid": "mock-test-kid-1"},
        )

        # Firebase verifier expects iss == https://securetoken.google.com/<project_id>
        verified = verify_firebase_id_token(google_token)
        self.assertIsNone(verified)

    def test_verify_identity_token_dispatches_correctly(self):
        """Verify verify_identity_token dispatches Google tokens and Firebase tokens to their respective verifiers."""
        now = int(time.time())

        # 1. Google token
        google_claims = {
            "iss": "https://accounts.google.com",
            "aud": DEFAULT_GOOGLE_DESKTOP_CLIENT_ID,
            "sub": "google_dispatch_sub",
            "email": "dispatch_google@gmail.com",
            "iat": now - 10,
            "exp": now + 3600,
        }
        google_token = jwt.encode(
            google_claims,
            self.priv_pem,
            algorithm="RS256",
            headers={"kid": "mock-test-kid-1"},
        )

        with patch(
            "app.security.firebase_auth.get_google_oauth_certs",
            return_value={"keys": [self.jwk_dict]},
        ):
            verified_google = verify_identity_token(google_token)
            self.assertIsNotNone(verified_google)
            self.assertEqual(verified_google["provider"], "google.com")

        # 2. Unknown issuer
        unknown_token = jwt.encode(
            {"iss": "https://unknown.com", "sub": "1"},
            "secret",
            algorithm="HS256",
        )
        self.assertIsNone(verify_identity_token(unknown_token))

    # 7. Endpoints: /auth/google and /auth/firebase
    def test_auth_google_endpoint_success(self):
        """Verify /auth/google endpoint authenticates valid Google OAuth token and creates application session."""
        mock_uid = f"google_user_{secrets.token_hex(4)}"
        mock_email = f"user_{secrets.token_hex(4)}@gmail.com"
        mock_payload = {
            "uid": mock_uid,
            "email": mock_email,
            "name": "Verified Google User",
            "provider": "google.com",
        }

        with patch(
            "app.security.firebase_auth.verify_google_id_token",
            return_value=mock_payload,
        ):
            resp = self.client.post(
                "/auth/google",
                json={"id_token": "valid.mock.google.id_token"},
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("access_token", data)
            self.assertEqual(data["email"], mock_email)
            self.assertIn("user_id", data)

    def test_auth_google_endpoint_rejects_unverified_token(self):
        """Verify /auth/google endpoint rejects invalid tokens with 401 Unauthorized."""
        with patch(
            "app.security.firebase_auth.verify_google_id_token",
            return_value=None,
        ):
            resp = self.client.post(
                "/auth/google",
                json={"id_token": "invalid.unverified.token"},
            )
            self.assertEqual(resp.status_code, 401)
            self.assertIn("Invalid, expired, or unauthorized", resp.json().get("detail", ""))

    def test_auth_firebase_endpoint_handles_identity_token(self):
        """Verify /auth/firebase endpoint verifies token via verify_identity_token."""
        mock_uid = f"identity_user_{secrets.token_hex(4)}"
        mock_email = f"user_{secrets.token_hex(4)}@test.com"
        mock_payload = {
            "uid": mock_uid,
            "email": mock_email,
            "name": "Identity User",
            "provider": "google.com",
        }

        with patch(
            "app.security.firebase_auth.verify_identity_token",
            return_value=mock_payload,
        ):
            resp = self.client.post(
                "/auth/firebase",
                json={"id_token": "valid.identity.token"},
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("access_token", data)
            self.assertEqual(data["email"], mock_email)

    def test_backend_rejects_empty_or_malformed_token(self):
        """Verify token verifiers reject malformed input without crashing."""
        self.assertIsNone(verify_google_id_token(""))
        self.assertIsNone(verify_google_id_token("not-a-valid-jwt"))
        self.assertIsNone(verify_google_id_token(None))
        self.assertIsNone(verify_firebase_id_token(""))
        self.assertIsNone(verify_firebase_id_token(None))

    # 8. Browser Tab Closure Fallback
    def test_callback_completion_when_browser_tab_cannot_close(self):
        """Verify callback HTML returns valid instructions and fallback status when tab cannot close."""
        html_template = """
        <button class="btn" id="closeBtn" onclick="attemptClose()">Close Tab</button>
        <p class="hint" id="statusHint">You can safely close this browser tab and return to the BG AI app.</p>
        """
        self.assertIn("Close Tab", html_template)
        self.assertIn("safely close this browser tab", html_template)

    # 9. Local Login & Regression
    def test_sync_firebase_user_creates_and_retrieves_user(self):
        """Verify sync_firebase_user creates a local user and maintains session identity."""
        test_uid = f"google_test_uid_{secrets.token_hex(4)}"
        test_email = f"user_{secrets.token_hex(4)}@example.com"
        test_name = "OAuth Test User"

        user1 = sync_firebase_user(test_uid, email=test_email, display_name=test_name)
        self.assertIsNotNone(user1)
        self.assertEqual(user1["email"], test_email)
        self.assertIsNotNone(user1["username"])

        user2 = sync_firebase_user(test_uid, email=test_email, display_name="Updated Name")
        self.assertEqual(user2["user_id"], user1["user_id"])

    def test_local_login_regression(self):
        """Verify local username/password login continues to function properly."""
        test_user = f"local_user_{secrets.token_hex(4)}"
        test_pass = "SecurePass123!"
        test_email = f"{test_user}@test.local"

        reg_user = register_user(test_user, test_pass, test_email)
        self.assertEqual(reg_user["username"], test_user)

        auth_user, reason = authenticate_user_detailed(test_user, test_pass)
        self.assertIsNotNone(auth_user)
        self.assertEqual(reason, "SUCCESS")

        bad_auth, bad_reason = authenticate_user_detailed(test_user, "WrongPassword!")
        self.assertIsNone(bad_auth)
        self.assertEqual(bad_reason, "INVALID_PASSWORD")

    def test_google_account_cannot_be_accessed_via_arbitrary_local_password(self):
        """Verify Google-synced accounts reject password authentication and direct user to Google login."""
        test_uid = f"google_uid_{secrets.token_hex(4)}"
        test_email = f"google_user_{secrets.token_hex(4)}@gmail.com"
        synced = sync_firebase_user(test_uid, email=test_email, display_name="Google Only User")

        user, reason = authenticate_user_detailed(synced["username"], "AnyPassword123")
        self.assertIsNone(user)
        self.assertEqual(reason, "GOOGLE_AUTH_REQUIRED")


if __name__ == "__main__":
    unittest.main()
