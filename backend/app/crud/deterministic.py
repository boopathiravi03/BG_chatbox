"""
Deterministic write-intent detection for BG AI.

Why this module exists
----------------------
Natural-language write requests were routed to the LLM CRUD intent
parser (``app.crud.intent.parse_crud_intent``) first. That parser is
told to abstain when a request is ambiguous -- and a plain
"add a new customer" is *always* ambiguous, because the user has not
supplied the column values yet. The parser returned ``None``, the CRUD
router returned ``None``, and the request then leaked into the generic
SQL generator, which is intentionally SELECT-only. The result was a
mangled pseudo-SQL error such as ``COULD operations are not supported.``

This module provides a deterministic fallback so that a write request
can never leak into the read-only SQL pipeline:

* the operation is detected from an explicit verb list, and
* the target table is resolved against the LIVE schema.

It never invents a table, and it never produces SQL. It only produces a
validated CRUD intent that the existing ``app.crud.router`` can act on.
"""

from __future__ import annotations

import re
from typing import Any

from app.crud.resolver import resolve_table


# =============================================================
# OPERATION VOCABULARY
# =============================================================

# "set" is deliberately excluded: it collides with ordinary English
# ("a set of customers", "settings"), and misclassifying a read request
# as a write request is worse than missing an uncommon phrasing.

_CREATE_WORDS = (
    "insert",
    "add",
    "create",
    "register",
    "new record",
    "add record",
)

_UPDATE_WORDS = (
    "update",
    "change",
    "modify",
    "edit",
    "rename",
)

_DELETE_WORDS = (
    "delete",
    "remove",
    "erase",
    "discard",
)

_OPERATION_WORDS: dict[str, tuple[str, ...]] = {
    "create": _CREATE_WORDS,
    "update": _UPDATE_WORDS,
    "delete": _DELETE_WORDS,
}

# Destructive operations are detected first so that a mixed request
# ("remove the old row and add a new one") fails safe.
_CHECK_ORDER = ("delete", "update", "create")


# =============================================================
# SPELLING NORMALIZATION
# =============================================================

_SPELLING_FIXES = {
    "delet": "delete",
    "delte": "delete",
    "deleet": "delete",
    "remve": "remove",
    "udpate": "update",
    "upadte": "update",
    "inser": "insert",
    "creat": "create",
    "addd": "add",
}


def _normalize_spelling(message: str) -> str:
    """Correct the common misspellings of the write verbs."""

    normalized = message.strip().lower()

    for wrong, correct in _SPELLING_FIXES.items():
        normalized = re.sub(
            rf"\b{re.escape(wrong)}\b",
            correct,
            normalized,
        )

    return normalized


# Write keywords that also form ordinary English phrasal verbs with a
# READ meaning. "add up the total price" means SUM(price), not INSERT;
# treating it as a create request would hijack a perfectly good read.
_READ_PHRASES = (
    # "add up the totals" / "adding up all the prices"
    (r"\badd(?:s|ing)?\s+up\b", "total"),
    # "add the prices together" -- "together" only meaningfully
    # appears in a summing request, so a short gap is allowed
    # between the verb and it.
    (
        r"\badd(?:s|ing)?\b(?:\s+\w+){0,4}\s+together\b",
        "total",
    ),
)


def _neutralize_read_phrases(message: str) -> str:
    """
    Rewrite read idioms that happen to contain a write keyword.

    Only phrases whose dominant meaning is a calculation are
    rewritten, so genuine write requests are untouched.
    """

    neutralized = message

    for pattern, replacement in _READ_PHRASES:
        neutralized = re.sub(
            pattern,
            replacement,
            neutralized,
            flags=re.IGNORECASE,
        )

    return neutralized


def _normalize_message(message: str) -> str:
    """Apply spelling correction and read-idiom neutralization."""

    return _neutralize_read_phrases(
        _normalize_spelling(message)
    )


def _contains_word(message: str, word: str) -> bool:
    return re.search(
        rf"\b{re.escape(word)}\b",
        message,
    ) is not None


# =============================================================
# PUBLIC API
# =============================================================

def detect_write_operation(user_message: str) -> str | None:
    """
    Return ``create`` / ``update`` / ``delete`` when the message
    clearly asks for a database modification, otherwise ``None``.

    This is intentionally lexical. It does not interpret the request
    and it never guesses a table or column.
    """

    if not user_message:
        return None

    normalized = _normalize_message(user_message)

    for operation in _CHECK_ORDER:
        for word in _OPERATION_WORDS[operation]:
            if _contains_word(normalized, word):
                return operation

    return None


def build_deterministic_intent(
    user_message: str,
    schema: dict,
) -> dict[str, Any] | None:
    """
    Build a CRUD intent using only the live schema.

    The returned shape matches ``app.crud.intent.parse_crud_intent`` so
    the two are interchangeable:

        {
            "operation":   "create" | "update" | "delete",
            "table":       "<exact schema table>" | None,
            "match":       {"column": None, "value": None},
            "changes":     {},
            "confidence":  "deterministic",
            "ambiguities": [],
        }

    Returns ``None`` when the message is not a write request, so callers
    can fall through to the read pipeline.
    """

    operation = detect_write_operation(user_message)

    if not operation:
        return None

    if not schema:
        return None

    table = resolve_table(user_message, schema)

    return {
        "operation": operation,
        "table": table,
        "match": {
            "column": None,
            "value": None,
        },
        "changes": {},
        "confidence": "deterministic",
        "ambiguities": [],
        "deterministic": True,
    }
