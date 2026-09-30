from __future__ import annotations

from typing import Any, Optional


def calculate_mae(actuals: list[float], predictions: list[float]) -> Optional[float]:
    """Computes Mean Absolute Error (MAE)."""
    if not actuals or not predictions or len(actuals) != len(predictions):
        return None
    errors = [abs(a - p) for a, p in zip(actuals, predictions)]
    return round(sum(errors) / len(errors), 2)


def calculate_mape(actuals: list[float], predictions: list[float]) -> tuple[Optional[float], Optional[str]]:
    """
    Computes Mean Absolute Percentage Error (MAPE).
    Strictly avoids division by zero when actual values contain 0.
    """
    if not actuals or not predictions or len(actuals) != len(predictions):
        return None, "Insufficient data for percentage error."

    # Zero check
    if any(a == 0 for a in actuals):
        return None, "MAPE omitted: actual series contains zero values (division by zero)."

    pct_errors = [abs((a - p) / a) * 100 for a, p in zip(actuals, predictions)]
    return round(sum(pct_errors) / len(pct_errors), 2), None


def validate_holdout(
    train_history: list[float],
    test_actuals: list[float],
    predict_fn: Any,
) -> dict[str, Any]:
    """
    Runs holdout validation by simulating predictions on test_actuals using model fit on train_history.
    Returns MAE, MAPE (if valid), and honest caveats.
    """
    if len(train_history) < 3 or not test_actuals:
        return {
            "validation_performed": False,
            "reason": "Historical series too short (< 5 periods) for split holdout validation.",
            "mae": None,
            "mape": None,
            "limitation": "Full series utilized for training to maximize parameter stability on limited history.",
        }

    # Generate predictions for the holdout length
    horizon = len(test_actuals)
    preds = predict_fn(train_history, horizon)

    mae = calculate_mae(test_actuals, preds)
    mape, mape_note = calculate_mape(test_actuals, preds)

    return {
        "validation_performed": True,
        "train_observations": len(train_history),
        "holdout_observations": horizon,
        "mae": mae,
        "mape": mape,
        "mape_note": mape_note,
        "limitation": "Validation conducted on historical holdout. Future variances may exceed historical errors if structural shifts occur.",
    }
