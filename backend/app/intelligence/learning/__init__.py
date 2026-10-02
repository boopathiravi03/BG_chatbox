"""
backend/app/intelligence/learning/__init__.py

Phase 8.5: Outcome & Learning Intelligence Package
Provides real outcome recording, user feedback capture, empirical pattern discovery,
and historical recommendation enrichment.
"""
from app.intelligence.learning.models import (
    OutcomeRecord,
    FeedbackRecord,
    OutcomeStatus,
    FeedbackTargetType,
    LearningPattern,
    LearningSummary,
)
from app.intelligence.learning.outcome_store import (
    save_outcome,
    get_outcome,
    list_outcomes,
    save_feedback,
    list_feedbacks,
    clear_learning_store,
)
from app.intelligence.learning.outcome_engine import synthesize_learning_summary
from app.intelligence.learning.feedback import record_user_feedback, get_user_feedbacks
from app.intelligence.learning.recommendation import enrich_recommendations_with_history

__all__ = [
    "OutcomeRecord",
    "FeedbackRecord",
    "OutcomeStatus",
    "FeedbackTargetType",
    "LearningPattern",
    "LearningSummary",
    "save_outcome",
    "get_outcome",
    "list_outcomes",
    "save_feedback",
    "list_feedbacks",
    "clear_learning_store",
    "synthesize_learning_summary",
    "record_user_feedback",
    "get_user_feedbacks",
    "enrich_recommendations_with_history",
]
