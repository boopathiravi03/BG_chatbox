"""
backend/app/intelligence/learning/feedback.py

Phase 8.5: Explicit Feedback Processor
Handles user feedback submissions on decisions, plans, alerts, and recommendations.
Enforces validation and persistence through outcome_store.
"""
from __future__ import annotations

from typing import Optional, Any
from app.intelligence.learning.models import FeedbackRecord, FeedbackTargetType
from app.intelligence.learning.outcome_store import save_feedback, list_feedbacks


def record_user_feedback(
    user_id: str,
    target_type: str = FeedbackTargetType.DECISION,
    target_id: Optional[str] = None,
    question: Optional[str] = None,
    useful: Optional[bool] = None,
    accepted: Optional[bool] = None,
    comment: Optional[str] = None,
) -> FeedbackRecord:
    """
    Validates and persists feedback from the authenticated user.
    """
    clean_target = (target_type or FeedbackTargetType.DECISION).upper()
    if clean_target not in FeedbackTargetType.ALL:
        clean_target = FeedbackTargetType.DECISION

    record = FeedbackRecord(
        user_id=user_id,
        target_type=clean_target,
        target_id=target_id,
        question=question,
        useful=useful,
        accepted=accepted,
        comment=comment.strip() if comment else None,
    )
    return save_feedback(record)


def get_user_feedbacks(
    user_id: str,
    limit: int = 50,
    target_type: Optional[str] = None,
) -> list[FeedbackRecord]:
    """
    Retrieves user feedback history.
    """
    return list_feedbacks(user_id=user_id, limit=limit, target_type=target_type)
