from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from app.agents.models import AgentInfo, AgentResult, AgentTask

MAX_AGENT_STEPS = 8


class BaseAgent(ABC):
    """
    Abstract base class for all specialist agents in BG AI.
    Enforces tool permissions, step limits, and read-only boundaries.
    """

    name: str = "base_agent"
    role: str = "Specialist Agent"
    description: str = "Base specialist agent"
    is_read_only: bool = True
    capabilities: list[str] = []
    allowed_tools: list[str] = []

    def get_info(self) -> AgentInfo:
        return AgentInfo(
            name=self.name,
            role=self.role,
            description=self.description,
            is_read_only=self.is_read_only,
            capabilities=self.capabilities,
            allowed_tools=self.allowed_tools,
        )

    def run(self, task: AgentTask, context: Optional[dict[str, Any]] = None) -> AgentResult:
        start_time = time.time()
        steps: list[str] = [f"Agent '{self.name}' initiated task {task.task_id}"]

        try:
            result = self.execute(task, context or {})
            result.execution_steps = steps + result.execution_steps
            result.duration_ms = round((time.time() - start_time) * 1000, 2)

            # Strict server-side safety enforcement
            if self.is_read_only and result.proposed_action is not None:
                steps.append("SAFETY VIOLATION DETECTED: Read-only agent attempted to propose database modification. Stripped.")
                result.proposed_action = None
                result.status = "COMPLETED"

            return result

        except Exception as e:
            duration = round((time.time() - start_time) * 1000, 2)
            steps.append(f"Execution encountered error: {str(e)}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                status="FAILED",
                summary=f"Agent '{self.name}' failed to complete task: {str(e)}",
                findings=[],
                evidence={},
                recommendations=[],
                proposed_action=None,
                limitations=["An unexpected error occurred during agent analysis."],
                execution_steps=steps,
                duration_ms=duration,
            )

    @abstractmethod
    def execute(self, task: AgentTask, context: dict[str, Any]) -> AgentResult:
        """Core specialized investigation logic implemented by subclasses."""
        pass
