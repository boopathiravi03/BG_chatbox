from __future__ import annotations

import re
from typing import Any

from difflib import get_close_matches


def _word_set(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9_]+", text.lower()))


def resolve_table(
    user_message: str,
    schema: dict,
) -> str | None:
    """
    Resolve the target table from the user's message using
    the live schema as the source of truth.

    Resolution order:
    1. Exact table name
    2. Singular / plural
    3. Underscore-delimited friendly name
    4. Column-driven inference
    5. Semantic aliases
    6. Fuzzy match
    """

    if not schema:
        return None

    message = user_message.lower().strip()
    table_names = list(schema.keys())

    for table in table_names:
        if re.search(rf"\b{re.escape(table.lower())}\b", message):
            return table

    for table in table_names:
        table_lower = table.lower()
        singular = table_lower[:-1] if table_lower.endswith("s") else table_lower
        if singular and re.search(rf"\b{re.escape(singular)}\b", message):
            return table

    for table in table_names:
        friendly = table.lower().replace("_", " ")
        if re.search(rf"\b{re.escape(friendly)}\b", message):
            return table

    message_words = _word_set(message)

    candidate_tables: list[str] = []

    for table in table_names:
        columns = schema.get(table, {})
        if not isinstance(columns, dict):
            continue

        for column in columns.keys():
            column_lower = column.lower()
            friendly = column_lower.replace("_", " ")
            if (
                column_lower in message_words
                or friendly in message_words
                or any(word in message_words for word in _word_set(column_lower))
            ):
                candidate_tables.append(table)
                break

    candidate_tables = list(dict.fromkeys(candidate_tables))

    if len(candidate_tables) == 1:
        return candidate_tables[0]

    for word in _word_set(message):
        matches = get_close_matches(
            word,
            [t.lower() for t in table_names],
            n=1,
            cutoff=0.75,
        )
        if matches:
            matched = matches[0]
            for table in table_names:
                if table.lower() == matched:
                    return table

    return None


def resolve_column(
    value: str,
    columns: list[str],
) -> str | None:
    """
    Resolve a column name from user-provided text against
    the actual column list from the live schema.
    """

    if not columns:
        return None

    normalized = re.sub(r"[^a-z0-9]", "_", value.lower()).strip("_")
    compact = normalized.replace("_", "")

    for column in columns:
        if column.lower() == normalized:
            return column
        if column.lower().replace("_", "") == compact:
            return column

    matches = get_close_matches(
        normalized,
        [column.lower() for column in columns],
        n=1,
        cutoff=0.70,
    )
    if matches:
        for column in columns:
            if column.lower() == matches[0]:
                return column

    return None


def find_text_columns(
    table_schema: dict[str, Any],
    preferred_names: list[str] | None = None,
) -> list[str]:
    """
    Return text-like columns from a table schema, preferring
    common human-readable name columns when present.
    """

    preferred_names = preferred_names or [
        "name",
        "full_name",
        "customer_name",
        "student_name",
        "employee_name",
        "product_name",
        "username",
        "display_name",
        "title",
        "description",
    ]

    columns = list(table_schema.keys())
    result: list[str] = []

    for preferred in preferred_names:
        for column in columns:
            if column.lower() == preferred:
                result.append(column)
                break

    for column in columns:
        if column in result:
            continue
        column_info = table_schema.get(column, {})
        column_type = str(column_info.get("type", "")).lower()
        if any(
            text_type in column_type
            for text_type in ["char", "text", "varchar", "string"]
        ):
            if not column_info.get("primary_key", False):
                result.append(column)

    return result
