"""
backend/app/security/firebase_auth.py
Verification of Google OAuth and Firebase ID tokens for BG AI.
Project: bg-platform-4b882
Desktop Client ID: 1045610580763-dvtqgpm0dla9laa7r8q9m883qdr7itjd.apps.googleusercontent.com
"""
import os
import time
import logging
from typing import Optional, Dict, Any, List
import requests
from jose import jwt, jwk, JWTError

logger = logging.getLogger(__name__)

FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "bg-platform-4b882")
DEFAULT_GOOGLE_DESKTOP_CLIENT_ID = (
    "1045610580763-dvtqgpm0dla9laa7r8q9m883qdr7itjd.apps.googleusercontent.com"
)
GOOGLE_DESKTOP_CLIENT_ID = os.getenv(
    "GOOGLE_DESKTOP_CLIENT_ID", DEFAULT_GOOGLE_DESKTOP_CLIENT_ID
)

GOOGLE_CERTS_URL = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
GOOGLE_OAUTH_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"

# In-memory cache for Google public certs
_certs_cache: Dict[str, str] = {}
_certs_cache_time: float = 0
_oauth_certs_cache: Dict[str, Any] = {}
_oauth_certs_time: float = 0
_CACHE_TTL = 3600  # 1 hour cache


def get_google_public_certs() -> Dict[str, str]:
    """Fetch and cache Google's public x509 certs for Firebase ID tokens."""
    global _certs_cache, _certs_cache_time
    now = time.time()
    if _certs_cache and (now - _certs_cache_time) < _CACHE_TTL:
        return _certs_cache

    try:
        resp = requests.get(GOOGLE_CERTS_URL, timeout=10)
        if resp.status_code == 200:
            _certs_cache = resp.json()
            _certs_cache_time = now
            return _certs_cache
    except Exception as e:
        logger.error(f"Failed to fetch Google public certs: {e}")
        if _certs_cache:
            return _certs_cache
    return {}


def get_google_oauth_certs() -> Dict[str, Any]:
    """Fetch and cache Google's public JWK certs for Google OAuth ID tokens."""
    global _oauth_certs_cache, _oauth_certs_time
    now = time.time()
    if _oauth_certs_cache and (now - _oauth_certs_time) < _CACHE_TTL:
        return _oauth_certs_cache

    try:
        resp = requests.get(GOOGLE_OAUTH_CERTS_URL, timeout=10)
        if resp.status_code == 200:
            _oauth_certs_cache = resp.json()
            _oauth_certs_time = now
            return _oauth_certs_cache
    except Exception as e:
        logger.error(f"Failed to fetch Google OAuth certs: {e}")
        if _oauth_certs_cache:
            return _oauth_certs_cache
    return {}


def get_allowed_google_client_ids() -> List[str]:
    """Return all authorized Google OAuth Client IDs for token audience verification."""
    ids = {DEFAULT_GOOGLE_DESKTOP_CLIENT_ID}
    env_desktop = os.getenv("GOOGLE_DESKTOP_CLIENT_ID")
    if env_desktop:
        ids.add(env_desktop.strip())
    env_web = os.getenv("GOOGLE_WEB_CLIENT_ID")
    if env_web:
        ids.add(env_web.strip())
    env_general = os.getenv("GOOGLE_CLIENT_ID")
    if env_general:
        ids.add(env_general.strip())
    return list(ids)


def verify_google_id_token(
    id_token: str,
    access_token: Optional[str] = None,
    allowed_audiences: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Cryptographically verifies a Google OAuth 2.0 ID token (OIDC).
    Validates:
      1. RS256 signature using Google's public JWK certificates.
      2. Token expiration (exp claim).
      3. Token issuer (accounts.google.com or https://accounts.google.com).
      4. Token audience (must match authorized Google OAuth Client ID).
      5. at_hash claim if access_token is provided.
    Returns verified payload dict containing 'uid', 'email', 'name', etc., or None.
    """
    if not id_token or not isinstance(id_token, str):
        return None

    try:
        headers = jwt.get_unverified_header(id_token)
        kid = headers.get("kid")
        alg = headers.get("alg")
        if not kid or alg != "RS256":
            logger.warning("[Google Auth] Missing kid or unsupported alg in token header")
            return None

        unverified_claims = jwt.get_unverified_claims(id_token)
        issuer = unverified_claims.get("iss", "")
        if issuer not in ("https://accounts.google.com", "accounts.google.com"):
            logger.warning(f"[Google Auth] Invalid issuer: {issuer}")
            return None

        # Verify audience is among authorized Google Client IDs
        token_aud = unverified_claims.get("aud")
        allowed = allowed_audiences or get_allowed_google_client_ids()
        matched_aud = None
        if isinstance(token_aud, str) and token_aud in allowed:
            matched_aud = token_aud
        elif isinstance(token_aud, list):
            for aud in token_aud:
                if aud in allowed:
                    matched_aud = aud
                    break

        if not matched_aud:
            logger.warning(
                f"[Google Auth] Audience mismatch: token aud={token_aud} not in authorized list"
            )
            return None

        oauth_certs = get_google_oauth_certs()
        matching_key = next((k for k in oauth_certs.get("keys", []) if k.get("kid") == kid), None)
        if not matching_key:
            logger.warning(f"[Google Auth] Public key not found for kid: {kid}")
            return None

        decode_options = {
            "verify_signature": True,
            "verify_exp": True,
            "verify_iss": True,
            "verify_aud": True,
        }

        # If access_token provided, verify at_hash; otherwise bypass at_hash check so
        # python-jose doesn't fail on missing access_token
        if access_token:
            decode_options["verify_at_hash"] = True
            decoded = jwt.decode(
                id_token,
                matching_key,
                algorithms=["RS256"],
                audience=matched_aud,
                issuer=issuer,
                access_token=access_token,
                options=decode_options,
            )
        else:
            decode_options["verify_at_hash"] = False
            decoded = jwt.decode(
                id_token,
                matching_key,
                algorithms=["RS256"],
                audience=matched_aud,
                issuer=issuer,
                options=decode_options,
            )

        uid = decoded.get("sub")
        if not uid:
            logger.warning("[Google Auth] Missing sub claim in verified token")
            return None

        email = decoded.get("email")
        name = decoded.get("name")
        if not name and email:
            name = email.split("@")[0]

        return {
            "uid": uid,
            "email": email,
            "name": name or "google_user",
            "provider": "google.com",
            "email_verified": decoded.get("email_verified", True),
            "claims": decoded,
        }
    except JWTError as e:
        logger.warning(f"[Google Auth] Token verification failed: {e}")
        return None
    except Exception as e:
        logger.error(f"[Google Auth] Unexpected error during verification: {e}")
        return None


def verify_firebase_id_token(
    id_token: str,
    project_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Verifies a Firebase ID token using Google public certificates.
    Validates:
      1. RS256 signature using Google's x509 certs.
      2. Token expiration.
      3. Token issuer (https://securetoken.google.com/<project_id>).
      4. Token audience (<project_id>).
    Returns token payload (containing 'uid', 'email', 'name', etc.) if valid, None otherwise.
    """
    if not id_token or not isinstance(id_token, str):
        return None

    target_project_id = project_id or FIREBASE_PROJECT_ID

    # First attempt: if firebase_admin is installed and initialized, use it
    try:
        import firebase_admin
        from firebase_admin import auth as admin_auth

        if firebase_admin._apps:
            decoded = admin_auth.verify_id_token(id_token)
            return {
                "uid": decoded.get("uid") or decoded.get("sub"),
                "email": decoded.get("email"),
                "name": decoded.get("name")
                or (
                    decoded.get("email", "").split("@")[0]
                    if decoded.get("email")
                    else "firebase_user"
                ),
                "provider": "firebase",
                "firebase": decoded.get("firebase", {}),
            }
    except Exception:
        pass

    # Standard RS256 JWT verification via Google / Firebase public certs
    try:
        headers = jwt.get_unverified_header(id_token)
        kid = headers.get("kid")
        alg = headers.get("alg")
        if not kid or alg != "RS256":
            return None

        unverified_claims = jwt.get_unverified_claims(id_token)
        issuer = unverified_claims.get("iss", "")
        expected_issuer = f"https://securetoken.google.com/{target_project_id}"

        if issuer != expected_issuer:
            logger.warning(
                f"[Firebase Auth] Invalid issuer: {issuer}, expected: {expected_issuer}"
            )
            return None

        certs = get_google_public_certs()
        cert = certs.get(kid)
        if not cert:
            return None

        decoded = jwt.decode(
            id_token,
            cert,
            algorithms=["RS256"],
            audience=target_project_id,
            issuer=expected_issuer,
        )

        uid = decoded.get("sub") or decoded.get("user_id")
        if not uid:
            return None

        email = decoded.get("email")
        name = decoded.get("name") or (
            email.split("@")[0] if email else "firebase_user"
        )

        return {
            "uid": uid,
            "email": email,
            "name": name,
            "provider": "firebase",
            "firebase": decoded.get("firebase", {}),
        }
    except JWTError as e:
        logger.warning(f"[Firebase Auth] Token verification failed: {e}")
        return None
    except Exception as e:
        logger.error(f"[Firebase Auth] Unexpected error during verification: {e}")
        return None


def verify_identity_token(
    token: str,
    access_token: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Inspects token issuer and delegates to the appropriate cryptographic verifier:
    - Direct Google OAuth OIDC tokens -> verify_google_id_token
    - Firebase ID tokens -> verify_firebase_id_token
    """
    if not token or not isinstance(token, str):
        return None

    try:
        unverified = jwt.get_unverified_claims(token)
        issuer = unverified.get("iss", "")

        if issuer in ("https://accounts.google.com", "accounts.google.com"):
            return verify_google_id_token(token, access_token=access_token)

        if "securetoken.google.com" in issuer:
            return verify_firebase_id_token(token)

        logger.warning(f"[Auth] Unsupported token issuer: {issuer}")
        return None
    except Exception as e:
        logger.warning(f"[Auth] Failed to inspect token claims: {e}")
        return None
