"""Phase 8.6 — Executive summary generator.

Deterministic first; Groq narrows the headline optionally.
Never invents data; only synthesises from already-computed MonitoringItems.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import MonitoringReport, MonitoringItem

from .models import ExecutiveSummary, MonitoringSeverity


# ── Helpers ───────────────────────────────────────────────────────────────────

def _overall_status(critical: int, warning: int) -> str:
    if critical > 0:
        return "critical"
    if warning > 0:
        return "attention_needed"
    return "healthy"


def _deterministic_headline(status: str, critical: int, warning: int, info: int) -> str:
    total = critical + warning + info
    if status == "critical":
        return (
            f"{critical} critical signal(s) detected requiring immediate attention "
            f"({warning} warning(s), {info} informational)."
        )
    if status == "attention_needed":
        return (
            f"{warning} warning(s) detected across the connected database "
            f"({info} informational). No critical issues found."
        )
    if total == 0:
        return "No significant issues detected. Connected database appears healthy."
    return f"{info} informational signal(s) detected. Overall health looks good."


def _top_risks(items: list) -> list[str]:
    """Return up to 3 risk bullets from critical/warning items."""
    risks = []
    for item in items:
        sev = item.severity.value if isinstance(item.severity, MonitoringSeverity) else item.severity
        if sev in ("critical", "warning"):
            risks.append(f"{item.title}: {item.business_impact[:120]}")
        if len(risks) >= 3:
            break
    return risks


def _top_opportunities(items: list) -> list[str]:
    """Return up to 3 opportunity bullets from info items."""
    opps = []
    for item in items:
        sev = item.severity.value if isinstance(item.severity, MonitoringSeverity) else item.severity
        if sev == "info":
            opps.append(f"{item.recommended_next_step[:120]}")
        if len(opps) >= 3:
            break
    return opps


# ── Main entry ────────────────────────────────────────────────────────────────

def generate_executive_summary(report: "MonitoringReport") -> ExecutiveSummary:
    """Build an ExecutiveSummary from an already-populated MonitoringReport."""
    items = report.items

    critical = sum(
        1 for i in items
        if (i.severity.value if isinstance(i.severity, MonitoringSeverity) else i.severity) == "critical"
    )
    warning = sum(
        1 for i in items
        if (i.severity.value if isinstance(i.severity, MonitoringSeverity) else i.severity) == "warning"
    )
    info = sum(
        1 for i in items
        if (i.severity.value if isinstance(i.severity, MonitoringSeverity) else i.severity) == "info"
    )

    overall = _overall_status(critical, warning)
    headline = _deterministic_headline(overall, critical, warning, info)

    # Optional Groq polish — never alters counts or items, only rephrases headline
    try:
        from app.agent.groq_agent import ask_groq
        evidence_summary = f"critical={critical}, warning={warning}, info={info}, db_type={report.db_type}"
        prompt = (
            "You are a senior business analyst writing an executive briefing headline.\n"
            f"Database type: {report.db_type}\n"
            f"Signal counts: {evidence_summary}\n"
            f"Deterministic headline: {headline}\n\n"
            "Rewrite the headline in clear, professional English (one sentence, max 200 chars). "
            "Do NOT change the signal counts. Do NOT add information not in the deterministic headline. "
            "Output ONLY the headline sentence."
        )
        polished = ask_groq(prompt)
        if polished and len(polished.strip()) > 10:
            headline = polished.strip()[:250]
    except Exception:
        pass  # deterministic fallback already set

    return ExecutiveSummary(
        overall_status=overall,
        headline=headline,
        critical_count=critical,
        warning_count=warning,
        info_count=info,
        top_risks=_top_risks(items),
        top_opportunities=_top_opportunities(items),
        generated_at=datetime.now(tz=timezone.utc).isoformat(),
    )
