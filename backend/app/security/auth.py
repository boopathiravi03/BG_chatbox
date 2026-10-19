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
    """
    Verify plaintext against bcrypt hash with multi-scheme backwards compatibility:
    1. SHA-256 lowercase hex pre-hash (BG AI standard)
    2. Direct UTF-8 bcrypt
    3. SHA-256 raw binary digest (32 bytes)
    4. SHA-256 uppercase hex pre-hash
    5. Trimmed plaintext variants (if whitespace was inadvertently included)
    """
    if not plain or not hashed:
        return False

    try:
        hashed_bytes = hashed.strip().encode("utf-8")
    except Exception:
        return False

    candidates: list[bytes] = []
    try:
        p_bytes = plain.encode("utf-8")
        # 1. SHA-256 hex lowercase pre-hash (BG AI standard)
        candidates.append(hashlib.sha256(p_bytes).hexdigest().encode("utf-8"))
        # 2. Direct UTF-8
        candidates.append(p_bytes)
        # 3. SHA-256 binary digest (32 bytes)
        candidates.append(hashlib.sha256(p_bytes).digest())
        # 4. SHA-256 uppercase hex
        candidates.append(hashlib.sha256(p_bytes).hexdigest().upper().encode("utf-8"))

        if plain.strip() != plain:
            p_strip = plain.strip().encode("utf-8")
            candidates.append(hashlib.sha256(p_strip).hexdigest().encode("utf-8"))
            candidates.append(p_strip)
            candidates.append(hashlib.sha256(p_strip).digest())
            candidates.append(hashlib.sha256(p_strip).hexdigest().upper().encode("utf-8"))
    except Exception:
        return False

    for cand in candidates:
        try:
            if bcrypt.checkpw(cand, hashed_bytes):
                return True
        except Exception:
            pass

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

