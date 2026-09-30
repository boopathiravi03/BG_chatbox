from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Optional

from app.agents.action_agent import ActionAgent
from app.agents.analyst_agent import AnalystAgent
from app.agents.anomaly_agent import AnomalyAgent
from app.agents.audit import get_current_db_identity
from app.agents.base_agent import BaseAgent
from app.agents.data_quality_agent import DataQualityAgent
from app.agents.database_health_agent import DatabaseHealthAgent
from app.agents.models import AgentInfo, AgentResult, AgentTask
from app.agents.performance_agent import PerformanceAgent

_AGENTS: dict[str, BaseAgent] = {
    "database_health_agent": DatabaseHealthAgent(),
    "data_quality_agent": DataQualityAgent(),
    "analyst_agent": AnalystAgent(),
    "anomaly_agent": AnomalyAgent(),
    "performance_agent": PerformanceAgent(),
    "action_agent": ActionAgent(),
}


def get_available_agents() -> list[AgentInfo]:
    """Returns metadata and permission capabilities for all registered specialist agents."""
    return [agent.get_info() for agent in _AGENTS.values()]


def get_agent(name: str) -> Optional[BaseAgent]:
    """Retrieves an agent instance by exact or normalized name."""
    norm = name.strip().lower()
    if norm in _AGENTS:
        return _AGENTS[norm]
    # Check without suffix
    for k, v in _AGENTS.items():
        if k.replace("_agent", "") == norm.replace("_agent", ""):
            return v
    return None


def route_to_agent(task_prompt: str) -> str:
    """
    Deterministic intent router matching user task prompts to specialized agents.
    """
    p = task_prompt.strip().lower()

    # 1. Action Agent routing (explicit action verbs)
    action_triggers = [
        "fix",
        "delete",
        "update",
        "clean up",
        "remove",
        "reassign",
        "resolve orphan",
        "prepare action",
        "set status",
        "drop",
        "alter",
        "truncate",
    ]
    if any(re.search(rf"\b{re.escape(w)}\b", p) for w in action_triggers):
        return "action_agent"

    # 2. Performance Agent routing
    perf_triggers = [
        "performance",
        "slow",
        "index",
        "indexes",
        "unindexed",
        "indexing",
        "optimize",
        "bottleneck",
    ]
    if any(re.search(rf"\b{re.escape(w)}\b", p) for w in perf_triggers):
        return "performance_agent"

    # 3. Anomaly Agent routing
    anomaly_triggers = [
        "anomaly",
        "anomalies",
        "unusual",
        "outlier",
        "outliers",
        "surge",
        "sudden drop",
        "spike",
        "deviat",
    ]
    if any(re.search(rf"\b{re.escape(w)}\b", p) for w in anomaly_triggers):
        return "anomaly_agent"

    # 4. Data Quality Agent routing
    dq_triggers = [
        "data quality",
        "quality",
        "null",
        "nulls",
        "missing value",
        "missing values",
        "duplicate",
        "duplicates",
        "orphan",
        "orphans",
        "hygiene",
    ]
    if any(re.search(rf"\b{re.escape(w)}\b", p) for w in dq_triggers):
        return "data_quality_agent"

    # 5. Database Health Agent routing
    health_triggers = [
        "health",
        "healthy",
        "database health",
        "health score",
        "schema integrity",
        "relational health",
        "audit database",
    ]
    if any(re.search(rf"\b{re.escape(w)}\b", p) for w in health_triggers):
        return "database_health_agent"

    # 6. Analyst Agent routing (business intelligence questions)
    analyst_triggers = [
        "why",
        "revenue",
        "sales",
        "trend",
        "who",
        "top",
        "bottom",
        "best",
        "worst",
        "growth",
        "quarter",
        "customer",
        "product",
        "metric",
    ]
    if any(re.search(rf"\b{re.escape(w)}\b", p) for w in analyst_triggers):
        return "analyst_agent"

    # Default fallback
    return "analyst_agent"


def run_agent_task(
    task_prompt: str,
    agent_name: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
) -> AgentResult:
    """
    Executes a task against a chosen or automatically routed specialist agent.
    """
    target_name = agent_name or route_to_agent(task_prompt)
    agent = get_agent(target_name)

    if agent is None:
        agent = _AGENTS["analyst_agent"]

    task_id = f"task_{uuid.uuid4().hex[:8]}"
    task = AgentTask(
        task_id=task_id,
        agent_name=agent.name,
        request=task_prompt,
        database_context=get_current_db_identity(),
        status="ANALYZING",
        created_at=datetime.now().isoformat(),
    )

    return agent.run(task, context or {})
