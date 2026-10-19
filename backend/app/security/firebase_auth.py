"""
backend/app/security/firebase_auth.py
Verification of Google Firebase ID tokens for BG AI.
Project: bg-platform-4b882
"""
import os
import time
import logging
from typing import Optional, Dict, Any
import requests
from jose import jwt, JWTError

logger = logging.getLogger(__name__)

FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "bg-platform-4b882")
GOOGLE_CERTS_URL = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"

# In-memory cache for Google public certs
_certs_cache: Dict[str, str] = {}
_certs_cache_time: float = 0
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


def verify_firebase_id_token(id_token: str) -> Optional[Dict[str, Any]]:
    """
    Verifies a Firebase ID token using Google public certificates.
    Returns token payload (containing 'uid', 'email', 'name', etc.) if valid, None otherwise.
    """
    if not id_token or not isinstance(id_token, str):
        return None

    # First attempt: if firebase_admin is installed and initialized, use it
    try:
        import firebase_admin
        from firebase_admin import auth as admin_auth
        if firebase_admin._apps:
            decoded = admin_auth.verify_id_token(id_token)
            return {
                "uid": decoded.get("uid") or decoded.get("sub"),
                "email": decoded.get("email"),
                "name": decoded.get("name"),
                "firebase": decoded.get("firebase", {}),
            }
    except Exception:
        pass

    # Standard RS256 JWT verification via Google's public certs
    try:
        headers = jwt.get_unverified_header(id_token)
        kid = headers.get("kid")
        if not kid:
            return None

        certs = get_google_public_certs()
        cert = certs.get(kid)
        if not cert:
            return None

        expected_issuer = f"https://securetoken.google.com/{FIREBASE_PROJECT_ID}"
        decoded = jwt.decode(
            id_token,
            cert,
            algorithms=["RS256"],
            audience=FIREBASE_PROJECT_ID,
            issuer=expected_issuer,
        )

        uid = decoded.get("sub") or decoded.get("user_id")
        if not uid:
            return None

        return {
            "uid": uid,
            "email": decoded.get("email"),
            "name": decoded.get("name"),
            "firebase": decoded.get("firebase", {}),
        }
    except JWTError as e:
        logger.warning(f"Firebase token verification failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Error during Firebase token verification: {e}")
        return None

