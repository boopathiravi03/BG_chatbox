"""
backend/app/intelligence/knowledge/provenance.py

Phase 9.1: Provenance Tracking & Epistemic Authority Verification
Provides helper functions for tracking, labeling, and verifying the epistemic
origin and operational authority of enterprise knowledge items.
"""
from __future__ import annotations

from typing import Any, Optional
from app.intelligence.knowledge.models import (
    KnowledgeProvenance,
    KnowledgeStatus,
)


def is_authoritative(status: str) -> bool:
    """
    Returns True ONLY if the knowledge item has been confirmed or explicitly activated by a human.
    Proposed, draft, disabled, or conflicted items are NOT authoritative and cannot alter analytics.
    """
    return status in {KnowledgeStatus.CONFIRMED.value, KnowledgeStatus.ACTIVE.value}


def is_inferred(provenance: str) -> bool:
    """
    Returns True if the knowledge item originated from algorithmic or AI inference.
    """
    return provenance in {
        KnowledgeProvenance.AI_INFERRED.value,
        KnowledgeProvenance.SCHEMA_DERIVED.value,
    }


def format_provenance_badge(provenance: str, status: str) -> dict[str, str]:
    """
    Returns UI badge configuration for rendering provenance and confirmation status.
    """
    labels = {
        KnowledgeProvenance.USER_PROVIDED.value: "User Confirmed" if is_authoritative(status) else "User Proposed",
        KnowledgeProvenance.SCHEMA_DERIVED.value: "Schema Fact",
        KnowledgeProvenance.DATA_OBSERVED.value: "Observed Data",
        KnowledgeProvenance.AI_INFERRED.value: "AI Inferred (Unconfirmed)",
        KnowledgeProvenance.SYSTEM_DEFINED.value: "Platform Standard",
    }
    colors = {
        KnowledgeStatus.CONFIRMED.value: "emerald",
        KnowledgeStatus.ACTIVE.value: "emerald",
        KnowledgeStatus.PROPOSED.value: "amber",
        KnowledgeStatus.DRAFT.value: "blue",
        KnowledgeStatus.DISABLED.value: "gray",
        KnowledgeStatus.CONFLICTED.value: "rose",
    }

    return {
        "label": labels.get(provenance, provenance),
        "status": status,
        "color": colors.get(status, "gray"),
        "is_authoritative": "true" if is_authoritative(status) else "false",
    }
