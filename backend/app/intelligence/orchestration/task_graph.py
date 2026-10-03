"""
backend/app/intelligence/orchestration/task_graph.py

DAG validation, cycle detection, topological sorting, and structural limits for Phase 9.2.
Guarantees acyclic step dependencies, max depth constraints, and safe execution ordering.
"""

from __future__ import annotations

import collections
from typing import Dict, List, Set, Tuple, Optional
from app.intelligence.orchestration.models import TaskGraph, PlanStep


MAX_GRAPH_STEPS = 20
MAX_GRAPH_DEPTH = 5


class GraphValidationError(Exception):
    """Raised when a task graph violates DAG or structural constraints."""
    pass


def validate_task_graph(graph: TaskGraph) -> Tuple[bool, List[str]]:
    """
    Validates that a TaskGraph is a well-formed directed acyclic graph (DAG):
    1. Not empty and does not exceed MAX_GRAPH_STEPS.
    2. All step dependencies reference valid step_ids.
    3. No self-loops or cycles (Tarjan / DFS cycle detection).
    4. Max dependency depth does not exceed MAX_GRAPH_DEPTH.
    5. Entry and exit steps are accurately identified.

    Returns (is_valid, list_of_error_messages).
    """
    errors: List[str] = []

    if not graph.steps:
        return False, ["TaskGraph must contain at least one step."]

    if len(graph.steps) > MAX_GRAPH_STEPS:
        errors.append(f"TaskGraph exceeds maximum step limit ({len(graph.steps)} > {MAX_GRAPH_STEPS}).")

    step_ids: Set[str] = {s.step_id for s in graph.steps}
    if len(step_ids) != len(graph.steps):
        errors.append("TaskGraph contains duplicate step_ids.")

    # 1. Dependency existence check
    for step in graph.steps:
        for dep in step.dependencies:
            if dep not in step_ids:
                errors.append(f"Step '{step.step_id}' references non-existent dependency '{dep}'.")
            if dep == step.step_id:
                errors.append(f"Step '{step.step_id}' has a self-referential dependency.")

    if errors:
        return False, errors

    # 2. Cycle detection via DFS
    # 0 = unvisited, 1 = visiting (in stack), 2 = visited
    state: Dict[str, int] = {s.step_id: 0 for s in graph.steps}
    adj: Dict[str, List[str]] = {s.step_id: s.dependencies for s in graph.steps}

    def has_cycle(u: str) -> bool:
        state[u] = 1
        for v in adj.get(u, []):
            if state[v] == 1:
                return True
            if state[v] == 0:
                if has_cycle(v):
                    return True
        state[u] = 2
        return False

    for step in graph.steps:
        if state[step.step_id] == 0:
            if has_cycle(step.step_id):
                errors.append(f"Cycle detected involving step '{step.step_id}'.")
                break

    if errors:
        return False, errors

    # 3. Depth calculation
    # Compute max depth (longest path from any root to node)
    # A root is a step with NO dependencies
    depth_memo: Dict[str, int] = {}

    def get_depth(node_id: str) -> int:
        if node_id in depth_memo:
            return depth_memo[node_id]
        deps = adj.get(node_id, [])
        if not deps:
            depth_memo[node_id] = 1
            return 1
        max_d = 1 + max(get_depth(d) for d in deps)
        depth_memo[node_id] = max_d
        return max_d

    max_observed_depth = max(get_depth(s.step_id) for s in graph.steps)
    if max_observed_depth > MAX_GRAPH_DEPTH:
        errors.append(f"TaskGraph exceeds maximum depth limit ({max_observed_depth} > {MAX_GRAPH_DEPTH}).")

    # 4. Populate / verify entry and exit steps
    entry_steps = [s.step_id for s in graph.steps if not s.dependencies]
    all_deps = set()
    for s in graph.steps:
        all_deps.update(s.dependencies)
    exit_steps = [s.step_id for s in graph.steps if s.step_id not in all_deps]

    graph.entry_steps = entry_steps
    graph.exit_steps = exit_steps
    graph.max_depth = max_observed_depth
    graph.total_steps = len(graph.steps)

    return len(errors) == 0, errors


def get_execution_batches(graph: TaskGraph) -> List[List[PlanStep]]:
    """
    Computes parallel execution batches using Kahn's topological sort.
    Steps in each batch have all their dependencies satisfied in previous batches
    and can safely be executed in parallel.
    """
    is_valid, errors = validate_task_graph(graph)
    if not is_valid:
        raise GraphValidationError(f"Invalid TaskGraph: {'; '.join(errors)}")

    step_map: Dict[str, PlanStep] = {s.step_id: s for s in graph.steps}
    # In Kahn's: in-degree is number of unsatisfied dependencies
    in_degree: Dict[str, int] = {s.step_id: len(s.dependencies) for s in graph.steps}
    # dependents map: who depends on this node?
    dependents: Dict[str, List[str]] = collections.defaultdict(list)
    for s in graph.steps:
        for dep in s.dependencies:
            dependents[dep].append(s.step_id)

    batches: List[List[PlanStep]] = []
    current_batch = [step_map[sid] for sid, deg in in_degree.items() if deg == 0]

    while current_batch:
        batches.append(current_batch)
        next_batch_ids = []
        for step in current_batch:
            for child_id in dependents.get(step.step_id, []):
                in_degree[child_id] -= 1
                if in_degree[child_id] == 0:
                    next_batch_ids.append(child_id)
        current_batch = [step_map[sid] for sid in next_batch_ids]

    return batches


def get_step_by_id(graph: TaskGraph, step_id: str) -> Optional[PlanStep]:
    """Finds a step by ID within the graph."""
    for step in graph.steps:
        if step.step_id == step_id:
            return step
    return None
