from typing import Dict, Any


def generate_chart(user_message: str, result: Dict[str, Any]):
    """
    Convert SQL result into chart JSON.
    """

    if not result.get("success"):
        return None

    rows = result.get("rows", [])
    columns = result.get("columns", [])

    if len(columns) < 2 or len(rows) == 0:
        return None

    labels = [str(r[0]) for r in rows]

    values = []
    for col_idx in range(1, len(columns)):
        try:
            values = [float(r[col_idx]) for r in rows]
            if values:
                break
        except (TypeError, ValueError):
            continue

    if not values:
        return None

    message = user_message.lower()

    if "line" in message or "trend" in message:
        chart_type = "line"

    elif "pie" in message or "distribution" in message:
        chart_type = "pie"

    elif "scatter" in message:
        chart_type = "scatter"

    else:
        chart_type = "bar"

    return {
        "chart_type": chart_type,
        "title": user_message.title(),
        "labels": labels,
        "values": values,
    }
