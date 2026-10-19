"""
backend/app/security/models.py
User model backed by SQLite (bgai_users.db).
Passwords are NEVER stored in plaintext.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    Column, String, DateTime, Boolean, Text,
    create_engine
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.paths import get_app_data_file

# ── User database (separate from user data databases) ─────────────────────────
_USERS_DB_PATH = get_app_data_file("bgai_users.db")

_users_engine = create_engine(
    f"sqlite:///{_USERS_DB_PATH}",
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)

Base = declarative_base()


class UserRecord(Base):
    """Persistent user record. Password is stored as bcrypt hash."""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    email = Column(String(200), unique=True, nullable=True)
    hashed_password = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)


# Create table on import
Base.metadata.create_all(_users_engine)

SessionLocal = sessionmaker(bind=_users_engine, autoflush=False, autocommit=False)


def get_user_db() -> Session:
    return SessionLocal()
