"""
backend/app/intelligence/actions/confirmation.py

Phase 8.8: Cryptographic Action Confirmation & Token Binding
Generates and verifies short-lived (5-minute) confirmation tokens bound strictly
to user identity, action ID, database identity, and action content hash.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.intelligence.actions.models import ActionProposal, ActionConfirmation

# Re-use secret key from auth environment or fallback to robust internal seed
SECRET_KEY = os.getenv("SECRET_KEY", "bgai_action_confirmation_secret_key_2026_phase8_8")
TOKEN_EXPIRATION_SECONDS = 300  # 5 minutes


def compute_action_hash(proposal: ActionProposal) -> str:
    """
    Computes a deterministic SHA-256 hash of the proposal's structural mutation parameters.
    If the target table, condition, columns, or values change, the hash changes, invalidating any token.
    """
    data = {
        "action_id": proposal.action_id,
        "action_type": proposal.action_type,
        "table": proposal.target.table,
        "condition_sql": proposal.target.condition_sql or "",
        "condition_params": proposal.target.condition_params or {},
        "changes": [
            {
                "column": c.column,
                "proposed_value": c.proposed_value,
            }
            for c in sorted(proposal.changes, key=lambda x: x.column)
        ],
    }
    payload_str = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()


def generate_confirmation_token(
    proposal: ActionProposal,
    user_id: str,
    db_identity: str,
    ttl_seconds: int = TOKEN_EXPIRATION_SECONDS,
    high_risk_acknowledged: bool = False,
) -> ActionConfirmation:
    """
    Constructs an ActionConfirmation with a signed HMAC-SHA256 token valid for ttl_seconds.
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ttl_seconds)

    action_hash = compute_action_hash(proposal)

    payload = {
        "action_id": proposal.action_id,
        "user_id": user_id,
        "db_identity": db_identity,
        "action_hash": action_hash,
        "iat": now.isoformat(),
        "exp": expires_at.isoformat(),
        "high_risk_ack": high_risk_acknowledged,
    }

    payload_json = json.dumps(payload, sort_keys=True)
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode("utf-8")).decode("utf-8").rstrip("=")

    signature = hmac.new(
        SECRET_KEY.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    token_string = f"act_conf.{payload_b64}.{signature}"

    return ActionConfirmation(
        confirmation_token=token_string,
        confirmed_by=user_id,
        confirmed_at=now.isoformat(),
        expires_at=expires_at.isoformat(),
        high_risk_acknowledged=high_risk_acknowledged,
        is_expired=False,
    )


def validate_confirmation_token(
    token_str: str,
    proposal: ActionProposal,
    user_id: str,
    current_db_identity: str,
) -> tuple[bool, Optional[str]]:
    """
    Verifies that the provided confirmation token is valid, matches the current action proposal,
    is unexpired, and belongs to the authenticated user and database context.
    """
    if not token_str or not token_str.startswith("act_conf."):
        return False, "Invalid token format."

    parts = token_str.split(".")
    if len(parts) != 3:
        return False, "Malformed confirmation token structure."

    prefix, payload_b64, signature = parts

    # 1. Verify HMAC Signature
    expected_sig = hmac.new(
        SECRET_KEY.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_sig):
        return False, "Confirmation token signature verification failed (tampered token)."

    # 2. Decode payload
    try:
        # Add padding back if necessary
        padded_b64 = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(padded_b64.encode("utf-8")).decode("utf-8")
        payload = json.loads(payload_json)
    except Exception as e:
        return False, f"Could not decode token payload: {e}"

    # 3. Check Action ID binding
    if payload.get("action_id") != proposal.action_id:
        return False, f"Token bound to action '{payload.get('action_id')}', but used for '{proposal.action_id}'."

    # 4. Check User ID binding
    if payload.get("user_id") != user_id:
        return False, "Token user ownership mismatch: cannot execute another user's confirmed action."

    # 5. Check Database Identity binding
    if payload.get("db_identity") != current_db_identity:
        return False, "Database connection changed since confirmation was issued. Re-confirmation required."

    # 6. Check Action Content Hash (prevents modifying action after preview/confirm)
    expected_hash = compute_action_hash(proposal)
    if payload.get("action_hash") != expected_hash:
        return False, "Action details have been modified since confirmation. Action must be re-confirmed."

    # 7. Check Expiration
    exp_str = payload.get("exp")
    if not exp_str:
        return False, "Token has no expiration timestamp."

    try:
        exp_dt = datetime.fromisoformat(exp_str)
        now_dt = datetime.now(timezone.utc)
        if now_dt > exp_dt:
            return False, "Confirmation token has expired (5-minute expiration limit exceeded)."
    except Exception:
        return False, "Invalid expiration format in token."

    # 8. Check High Risk Acknowledgment
    if (proposal.risk or "").upper() == "HIGH" and not payload.get("high_risk_ack"):
        return False, "High-risk actions require explicit user acknowledgment."

    return True, None

