"""
backend/app/security/auth.py
JWT creation/verification and password hashing using direct bcrypt + SHA-256 pre-hash.
"""
from __future__ import annotations

import os
import uuid
import hashlib
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt

# ── Secret key — must be set in .env for production ───────────────────────────
SECRET_KEY = os.getenv("BGAI_SECRET_KEY", "bgai-dev-secret-change-in-production-please")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("BGAI_TOKEN_EXPIRE_MINUTES", "1440"))  # 24h


def hash_password(plain: str) -> str:
    """Hash a plaintext password using bcrypt with SHA-256 pre-hash. NEVER call with empty string."""
    if not plain or len(plain) < 6:
        raise ValueError("Password must be at least 6 characters.")
    pwd_bytes = hashlib.sha256(plain.encode("utf-8")).hexdigest().encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify plaintext against bcrypt hash."""
    try:
        pwd_bytes = hashlib.sha256(plain.encode("utf-8")).hexdigest().encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hashed.encode("utf-8"))
    except Exception:
        return False


# ── JWT ───────────────────────────────────────────────────────────────────────
def create_access_token(user_id: str, username: str) -> str:
    """Create a signed JWT access token."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "username": username,
        "iat": now,
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and verify a JWT token.
    Returns payload dict on success, None on failure.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            return None
        return payload
    except JWTError:
        return None

