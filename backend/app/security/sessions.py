"""
backend/app/security/sessions.py
FastAPI dependency: extract and validate JWT from Authorization header.
Returns the authenticated user_id and username for every protected endpoint.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.security.auth import decode_access_token, hash_password, verify_password
from app.security.models import UserRecord, get_user_db

_bearer = HTTPBearer(auto_error=False)


# ── Pydantic-like response container (no DB dependency) ───────────────────────
class AuthenticatedUser:
    """Lightweight container holding verified user identity for a request."""
    __slots__ = ("user_id", "username")

    def __init__(self, user_id: str, username: str):
        self.user_id = user_id
        self.username = username

    def __repr__(self) -> str:
        return f"AuthenticatedUser(user_id={self.user_id!r}, username={self.username!r})"


# ── Dependency ────────────────────────────────────────────────────────────────
def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> AuthenticatedUser:
    """
    FastAPI dependency: validates Bearer JWT and returns AuthenticatedUser.
    Raises HTTP 401 on missing/invalid/expired token.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    username = payload.get("username", "unknown")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing user identity.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthenticatedUser(user_id=user_id, username=username)


# ── User CRUD operations ──────────────────────────────────────────────────────
def register_user(username: str, password: str, email: str = "") -> dict:
    """
    Register a new user. Hashes password with bcrypt.
    Returns dict with user_id and username on success.
    Raises ValueError if username already exists.
    """
    db = get_user_db()
    try:
        existing = db.query(UserRecord).filter(
            UserRecord.username == username.strip().lower()
        ).first()
        if existing:
            raise ValueError(f"Username '{username}' is already taken.")

        user_id = str(uuid.uuid4())
        hashed = hash_password(password)

        record = UserRecord(
            id=user_id,
            username=username.strip().lower(),
            email=email.strip() if email else None,
            hashed_password=hashed,
        )
        db.add(record)
        db.commit()
        return {"user_id": user_id, "username": record.username}
    finally:
        db.close()


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """
    Verify credentials. Returns user dict on success, None on failure.
    Updates last_login timestamp.
    """
    from datetime import datetime
    db = get_user_db()
    try:
        record = db.query(UserRecord).filter(
            UserRecord.username == username.strip().lower()
        ).first()
        if not record:
            return None
        if not verify_password(password, record.hashed_password):
            return None
        # Update last login
        record.last_login = datetime.utcnow()
        db.commit()
        return {"user_id": record.id, "username": record.username}
    finally:
        db.close()


def get_user_by_id(user_id: str) -> Optional[dict]:
    """Fetch user info by ID. Never returns password hash."""
    db = get_user_db()
    try:
        record = db.query(UserRecord).filter(UserRecord.id == user_id).first()
        if not record:
            return None
        return {
            "user_id": record.id,
            "username": record.username,
            "email": record.email,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "last_login": record.last_login.isoformat() if record.last_login else None,
        }
    finally:
        db.close()
