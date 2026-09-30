from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text

from app.agents.models import ActionPlan
from app.database.database_manager import get_engine
from app.tools.execute_query import validate_sql

_lock = threading.Lock()
_action_store: dict[str, ActionPlan] = {}

AUDIT_LOG_FILE = os.path.join(os.path.dirname(__file__), "audit_log.json")


def get_current_db_identity() -> str:
    engine = get_engine()
    if engine is None:
        return "none"
    try:
        return engine.url.render_as_string(hide_password=True)
    except Exception:
        return "unknown"


def _persist_to_file() -> None:
    try:
        serializable = [
            action.to_dict()
            for action in _action_store.values()
        ]
        with open(AUDIT_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2)
    except Exception:
        pass


def store_action(action: ActionPlan) -> None:
    with _lock:
        if not action.created_at:
            action.created_at = datetime.now().isoformat()
        if not action.database_identity:
            action.database_identity = get_current_db_identity()
        _action_store[action.action_id] = action
        _persist_to_file()


def get_action(action_id: str) -> Optional[ActionPlan]:
    with _lock:
        return _action_store.get(action_id)


def list_actions(db_identity_only: bool = True) -> list[ActionPlan]:
    with _lock:
        current_id = get_current_db_identity()
        if db_identity_only and current_id == "none":
            return []
        actions = list(_action_store.values())
        if db_identity_only:
            actions = [a for a in actions if a.database_identity == current_id]
        # Return sorted latest first
        actions.sort(key=lambda a: a.created_at, reverse=True)
        return actions


def cancel_action(action_id: str) -> dict[str, Any]:
    with _lock:
        action = _action_store.get(action_id)
        if not action:
            return {"success": False, "error": f"Action '{action_id}' not found."}

        if action.status in {"EXECUTED", "VERIFIED"}:
            return {"success": False, "error": "Cannot cancel an already executed action."}

        action.status = "CANCELLED"
        _persist_to_file()
        return {"success": True, "action": action.to_dict()}


def confirm_and_execute_action(action_id: str) -> dict[str, Any]:
    """
    Executes an action ONLY upon explicit human confirmation within a transaction,
    verifying post-conditions and enforcing strict safety rules.
    """
    with _lock:
        action = _action_store.get(action_id)
        if not action:
            return {"success": False, "error": f"Action '{action_id}' not found."}

        if action.status not in {"PROPOSED", "AWAITING_CONFIRMATION"}:
            return {
                "success": False,
                "error": f"Action '{action_id}' cannot be executed in state '{action.status}'.",
            }

        # Validate database identity
        curr_ident = get_current_db_identity()
        if action.database_identity != curr_ident:
            return {
                "success": False,
                "error": "The active database connection has changed since this action was proposed. Re-plan required.",
            }

        engine = get_engine()
        if engine is None:
            return {"success": False, "error": "No database currently connected."}

        # Server-side validation
        sql = action.exact_sql.strip()
        val = validate_sql(sql)
        if not val.get("allowed"):
            action.status = "FAILED"
            action.error = val.get("reason", "Disallowed SQL statement.")
            _persist_to_file()
            return {"success": False, "error": action.error}

        # Check for forbidden dangerous operations
        lower_sql = sql.lower()
        for forbidden in ["drop ", "alter ", "truncate ", "grant ", "revoke ", "create "]:
            if forbidden in f" {lower_sql} ":
                action.status = "FAILED"
                action.error = f"Forbidden administrative command '{forbidden.strip()}'. Only safe DML is permitted."
                _persist_to_file()
                return {"success": False, "error": action.error}

        action.status = "EXECUTING"
        action.confirmed_at = datetime.now().isoformat()

    # Execute within a managed transaction block
    try:
        with engine.begin() as conn:
            result = conn.execute(text(sql))
            raw_affected = result.rowcount
            actual_affected = raw_affected if (raw_affected is not None and raw_affected >= 0) else action.estimated_rows

            # Verification step inside the transaction
            v_val = None
            if action.verification_sql:
                v_res = conn.execute(text(action.verification_sql)).scalar()
                v_val = v_res
                # Compare against expected verification result
                expected = str(action.expected_verification_result).strip()
                actual_str = str(v_res).strip() if v_res is not None else ""

                if expected and actual_str != expected:
                    raise RuntimeError(
                        f"Post-execution verification failed! Expected '{expected}', got '{actual_str}'. "
                        "Transaction safely rolled back."
                    )

        # Success - Transaction successfully committed
        with _lock:
            action.status = "VERIFIED" if action.verification_sql else "EXECUTED"
            action.executed_at = datetime.now().isoformat()
            action.actual_rows_affected = actual_affected
            action.verification_details = {
                "verified": bool(action.verification_sql),
                "expected": action.expected_verification_result,
                "observed": str(v_val) if v_val is not None else "N/A",
            }
            action.error = None
            _persist_to_file()

        # Invalidate cached intelligence
        try:
            from app.intelligence.anomaly.detector import clear_cached_anomaly_report
            from app.database.database_context import clear_database_profile
            clear_cached_anomaly_report()
            clear_database_profile()
        except Exception:
            pass

        return {
            "success": True,
            "status": action.status,
            "actual_rows_affected": action.actual_rows_affected,
            "action": action.to_dict(),
        }

    except Exception as e:
        err_msg = str(e)
        is_verification_err = "Post-execution verification failed" in err_msg

        with _lock:
            action.status = "VERIFICATION_FAILED" if is_verification_err else "FAILED"
            action.error = err_msg
            _persist_to_file()

        return {
            "success": False,
            "status": action.status,
            "error": err_msg,
            "action": action.to_dict(),
        }


def clear_audit_store() -> None:
    """Utility for test suites."""
    with _lock:
        _action_store.clear()
        if os.path.exists(AUDIT_LOG_FILE):
            try:
                os.remove(AUDIT_LOG_FILE)
            except Exception:
                pass
