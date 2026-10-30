from __future__ import annotations

import re
from typing import Dict, Any, Optional


def generate_chart(user_message: str, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Intelligently converts query result rows and columns into chart JSON.
    Auto-detects suitable label and value columns and recommends bar, line, or pie visualization.
    """
    if not result or not result.get("success"):
        return None

    rows = result.get("rows", [])
    columns = result.get("columns", [])

    if len(columns) < 2 or len(rows) == 0:
        return None

    def get_val(row, col_name):
        if isinstance(row, dict):
            return row.get(col_name)
        if isinstance(row, (list, tuple)):
            try:
                idx = columns.index(col_name)
                return row[idx]
            except Exception:
                return None
        return getattr(row, col_name, None)

    # 1. Classify columns as numeric candidate or label candidate
    numeric_col = None
    label_col = None

    # Preferred measure column names
    measure_keywords = ["revenue", "amount", "total", "sales", "price", "count", "qty", "quantity", "cost", "sum", "avg", "val"]
    label_keywords = ["name", "title", "category", "product", "customer", "date", "month", "year", "status", "type", "country", "label"]

    for col in columns:
        # Check if column values can be parsed as float
        is_num = True
        num_count = 0
        for r in rows[:10]:
            v = get_val(r, col)
            if v is not None:
                try:
                    float(v)
                    num_count += 1
                except (ValueError, TypeError):
                    is_num = False
                    break
        if is_num and num_count > 0:
            if numeric_col is None or any(kw in col.lower() for kw in measure_keywords):
                # Don't pick ID as numeric measure if a real measure exists
                if not col.lower().endswith("_id") and col.lower() != "id":
                    numeric_col = col
                elif numeric_col is None:
                    numeric_col = col
        else:
            if label_col is None or any(kw in col.lower() for kw in label_keywords):
                label_col = col

    # Fallback if detection didn't find both
    if label_col is None:
        label_col = columns[0]
    if numeric_col is None:
        for c in columns:
            if c != label_col:
                numeric_col = c
                break

    if not numeric_col:
        return None

    # 2. Extract labels and values
    labels = []
    values = []

    for r in rows[:30]:  # Cap chart points for readability
        l_val = get_val(r, label_col)
        v_val = get_val(r, numeric_col)
        try:
            f_val = float(v_val) if v_val is not None else 0.0
            labels.append(str(l_val) if l_val is not None else "Unknown")
            values.append(round(f_val, 2))
        except (ValueError, TypeError):
            continue

    if not values:
        return None

    # 3. Determine best chart type
    msg = user_message.lower()
    lbl_lower = label_col.lower()

    if "pie" in msg or "distribution" in msg or "proportion" in msg:
        chart_type = "pie"
    elif "line" in msg or "trend" in msg or "month" in msg or any(k in lbl_lower for k in ["date", "time", "month", "year", "day"]):
        chart_type = "line"
    elif "scatter" in msg:
        chart_type = "scatter"
    elif len(labels) <= 6 and ("share" in msg or "breakdown" in msg):
        chart_type = "pie"
    else:
        chart_type = "bar"

    title = user_message.strip("?.! ").title()
    if len(title) > 60:
        title = f"{numeric_col.replace('_', ' ').title()} by {label_col.replace('_', ' ').title()}"

    return {
        "chart_type": chart_type,
        "title": title,
        "labels": labels,
        "values": values,
        "x_key": label_col,
        "y_keys": [numeric_col],
    }
