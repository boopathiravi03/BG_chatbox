"""
backend/app/intelligence/predictive/store.py

Phase 9.0: In-Memory Prediction & Scenario Storage
Maintains recent predictions and scenarios scoped strictly by authenticated user_id
and active database identity. Thread-safe with automatic size bounding.
"""
from __future__ import annotations

import threading
from typing import Optional

from app.intelligence.predictive.models import PredictionResult

_store_lock = threading.Lock()
# Mapping: (user_id, prediction_id) -> PredictionResult
_prediction_cache: dict[tuple[str, str], PredictionResult] = {}
# Mapping: user_id -> list of prediction_ids ordered by recency
_user_prediction_index: dict[str, list[str]] = {}

MAX_CACHE_PER_USER = 50


def save_prediction(pred: PredictionResult) -> PredictionResult:
    """Stores a prediction result strictly indexed by user_id and prediction_id."""
    with _store_lock:
        key = (pred.user_id, pred.prediction_id)
        _prediction_cache[key] = pred

        if pred.user_id not in _user_prediction_index:
            _user_prediction_index[pred.user_id] = []

        # Maintain recency list
        idx_list = _user_prediction_index[pred.user_id]
        if pred.prediction_id in idx_list:
            idx_list.remove(pred.prediction_id)
        idx_list.insert(0, pred.prediction_id)

        # Evict oldest if exceeding capacity
        if len(idx_list) > MAX_CACHE_PER_USER:
            evicted_id = idx_list.pop()
            _prediction_cache.pop((pred.user_id, evicted_id), None)

    return pred


def get_prediction(prediction_id: str, user_id: str) -> Optional[PredictionResult]:
    """Retrieves a prediction verifying user ownership."""
    with _store_lock:
        return _prediction_cache.get((user_id, prediction_id))


def list_predictions(user_id: str, limit: int = 20) -> list[PredictionResult]:
    """Lists recent predictions for the specified user."""
    with _store_lock:
        id_list = _user_prediction_index.get(user_id, [])
        results = []
        for pid in id_list[:limit]:
            p = _prediction_cache.get((user_id, pid))
            if p is not None:
                results.append(p)
        return results


def clear_predictive_store(user_id: Optional[str] = None) -> None:
    """Testing & disconnect utility: clears cache for a user or all users."""
    global _prediction_cache, _user_prediction_index
    with _store_lock:
        if user_id:
            id_list = _user_prediction_index.pop(user_id, [])
            for pid in id_list:
                _prediction_cache.pop((user_id, pid), None)
        else:
            _prediction_cache.clear()
            _user_prediction_index.clear()
