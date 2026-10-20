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
        # Check if incoming token is a direct Google Firebase ID token
        try:
            from app.security.firebase_auth import verify_firebase_id_token
            fb_payload = verify_firebase_id_token(credentials.credentials)
            if fb_payload:
                uid = fb_payload.get("uid")
                email = fb_payload.get("email")
                name = fb_payload.get("name")
                u_info = sync_firebase_user(uid=uid, email=email, display_name=name)
                return AuthenticatedUser(user_id=u_info["user_id"], username=u_info["username"])
        except Exception:
            pass

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


# ── Firebase User Sync ────────────────────────────────────────────────────────
def sync_firebase_user(
    uid: str,
    email: Optional[str] = None,
    display_name: Optional[str] = None,
) -> dict:
    """
    Sync or retrieve a Firebase-authenticated user in the local BG AI user registry.
    Ensures user_id integrity for per-user database connections and telemetry.
    """
    from datetime import datetime
    db = get_user_db()
    try:
        record = db.query(UserRecord).filter(UserRecord.id == uid).first()
        if not record and email:
            record = db.query(UserRecord).filter(
                UserRecord.email == email.strip().lower()
            ).first()

        clean_username = (
            (display_name or (email.split("@")[0] if email else f"user_{uid[:8]}"))
            .strip()
            .lower()
        )

        if not record:
            candidate_username = clean_username
            suffix_counter = 1
            while db.query(UserRecord).filter(UserRecord.username == candidate_username).first():
                candidate_username = f"{clean_username}_{uid[-4:]}_{suffix_counter}"
                suffix_counter += 1
            clean_username = candidate_username

            record = UserRecord(
                id=uid,
                username=clean_username,
                email=email.strip().lower() if email else None,
                hashed_password="FIREBASE_AUTHENTICATED",
                is_active=True,
                created_at=datetime.utcnow(),
                last_login=datetime.utcnow(),
            )
            db.add(record)
        else:
            record.last_login = datetime.utcnow()
            if email and not record.email:
                record.email = email.strip().lower()

        db.commit()
        return {
            "user_id": record.id,
            "username": record.username,
            "email": record.email,
        }
    finally:
        db.close()


# ── User CRUD operations ──────────────────────────────────────────────────────
def register_user(username: str, password: str, email: str = "") -> dict:
    """
    Register a new user. Hashes password with bcrypt.
    Returns dict with user_id and username on success.
    Raises ValueError if username already exists.
    """
    db = get_user_db()
    try:
        clean_user = username.strip().lower()
        clean_email = email.strip().lower() if email else None

        existing = db.query(UserRecord).filter(
            UserRecord.username == clean_user
        ).first()
        if existing:
            raise ValueError(f"Username '{username}' is already taken.")

        if clean_email:
            existing_email = db.query(UserRecord).filter(
                UserRecord.email == clean_email
            ).first()
            if existing_email:
                raise ValueError(f"An account with email '{email}' already exists. Please sign in instead.")

        user_id = str(uuid.uuid4())
        hashed = hash_password(password)

        record = UserRecord(
            id=user_id,
            username=clean_user,
            email=clean_email,
            hashed_password=hashed,
        )
        db.add(record)
        db.commit()
        return {"user_id": user_id, "username": record.username}
    finally:
        db.close()


def authenticate_user_detailed(username: str, password: str) -> tuple[Optional[dict], str]:
    """
    Verify credentials with precise status diagnosis.
    Returns (user_dict, status_reason):
    - status_reason: "SUCCESS", "USER_NOT_FOUND", "ACCOUNT_INACTIVE", "INVALID_PASSWORD", "DATABASE_ERROR"
    Supports either username or email. Updates last_login timestamp on success.
    """
    from datetime import datetime
    clean = username.strip().lower()
    if not clean or not password:
        return None, "INVALID_INPUT"

    try:
        db = get_user_db()
    except Exception as e:
        return None, f"DATABASE_ERROR: {str(e)}"

    try:
        record = db.query(UserRecord).filter(
            (UserRecord.username == clean) | (UserRecord.email == clean)
        ).first()
        if not record:
            return None, "USER_NOT_FOUND"
        if not record.is_active:
            return None, "ACCOUNT_INACTIVE"
        if record.hashed_password == "FIREBASE_AUTHENTICATED":
            return None, "GOOGLE_AUTH_REQUIRED"
        if not verify_password(password, record.hashed_password):
            return None, "INVALID_PASSWORD"

        # Update last login
        record.last_login = datetime.utcnow()
        db.commit()
        return {
            "user_id": record.id,
            "username": record.username,
            "email": record.email,
        }, "SUCCESS"
    except Exception as e:
        return None, f"DATABASE_ERROR: {str(e)}"
    finally:
        try:
            db.close()
        except Exception:
            pass


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """
    Verify credentials. Returns user dict on success, None on failure.
    Updates last_login timestamp.
    Supports either username or email.
    """
    user, _ = authenticate_user_detailed(username, password)
    return user


def lookup_user_email(identifier: str) -> Optional[dict]:
    """
    Looks up whether an identifier (username or email) corresponds to an existing user.
    Returns dict with username and email, or None. Never returns password hash.
    """
    clean = identifier.strip().lower()
    if not clean:
        return None
    db = get_user_db()
    try:
        record = db.query(UserRecord).filter(
            (UserRecord.username == clean) | (UserRecord.email == clean)
        ).first()
        if not record:
            return None
        return {
            "user_id": record.id,
            "username": record.username,
            "email": record.email,
        }
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
