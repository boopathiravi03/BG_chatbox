"""
backend/app/intelligence/business_intelligence/join_path.py

Phase 8.2: Multi-Table Relationship Graph & Join Path Component
Deterministically discovers, validates, and traverses foreign-key relationships.
Never invents relationships. Enforces maximum join depth and prevents cycles.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional
from app.intelligence.schema_analyzer import quote_identifier


@dataclass
class JoinEdge:
    """Directed edge in the relationship graph derived from foreign keys."""
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    relationship_type: str  # "many-to-one" | "one-to-many"
    is_reverse: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_table": self.source_table,
            "source_column": self.source_column,
            "target_table": self.target_table,
            "target_column": self.target_column,
            "relationship_type": self.relationship_type,
            "is_reverse": self.is_reverse,
        }


@dataclass
class JoinStep:
    """A single hop in a multi-table join path."""
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    join_type: str = "LEFT JOIN"

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_table": self.from_table,
            "from_column": self.from_column,
            "to_table": self.to_table,
            "to_column": self.to_column,
            "join_type": self.join_type,
        }


@dataclass
class JoinPath:
    """A complete, verified join path connecting two or more tables."""
    source_table: str
    target_table: str
    steps: list[JoinStep] = field(default_factory=list)
    source_columns: list[str] = field(default_factory=list)
    target_columns: list[str] = field(default_factory=list)
    relationship_type: str = "direct"  # "direct" | "multi-hop"
    depth: int = 0
    generated_join_clause: str = ""
    lineage: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_table": self.source_table,
            "target_table": self.target_table,
            "depth": self.depth,
            "relationship_type": self.relationship_type,
            "steps": [s.to_dict() for s in self.steps],
            "source_columns": self.source_columns,
            "target_columns": self.target_columns,
            "generated_join_clause": self.generated_join_clause,
            "lineage": self.lineage,
        }


def build_relationship_graph(schema_info: dict[str, Any]) -> dict[str, list[JoinEdge]]:
    """
    Constructs an adjacency list representation of explicit foreign-key relationships.
    Both forward and reverse traversals are supported with clear direction tracking.
    Never guesses or synthesizes non-existent relationships.
    """
    graph: dict[str, list[JoinEdge]] = {}
    tables_data = schema_info.get("tables", {})

    for tbl in tables_data.keys():
        if tbl not in graph:
            graph[tbl] = []

    for table_name, meta in tables_data.items():
        fks = meta.get("foreign_keys", [])
        for fk in fks:
            referred_table = fk.get("referred_table")
            if not referred_table or referred_table not in tables_data:
                continue

            c_cols = fk.get("constrained_columns", [])
            r_cols = fk.get("referred_columns", [])

            if not c_cols or not r_cols:
                continue

            # Forward edge: child (table_name) -> parent (referred_table) [many-to-one]
            edge_fwd = JoinEdge(
                source_table=table_name,
                source_column=c_cols[0],
                target_table=referred_table,
                target_column=r_cols[0],
                relationship_type="many-to-one",
                is_reverse=False,
            )
            graph.setdefault(table_name, []).append(edge_fwd)

            # Reverse edge: parent (referred_table) -> child (table_name) [one-to-many]
            edge_rev = JoinEdge(
                source_table=referred_table,
                source_column=r_cols[0],
                target_table=table_name,
                target_column=c_cols[0],
                relationship_type="one-to-many",
                is_reverse=True,
            )
            graph.setdefault(referred_table, []).append(edge_rev)

    return graph


def find_join_path(
    graph: dict[str, list[JoinEdge]],
    source_table: str,
    target_table: str,
    max_depth: int = 3,
    db_type: str = "sqlite",
) -> Optional[JoinPath]:
    """
    Finds the shortest verified join path between source_table and target_table using BFS.
    Enforces maximum join depth (default 3) and prevents circular traversal.
    Returns None if no verified relationship path exists.
    """
    if source_table not in graph or target_table not in graph:
        return None

    if source_table == target_table:
        return JoinPath(
            source_table=source_table,
            target_table=target_table,
            steps=[],
            depth=0,
            relationship_type="self",
            generated_join_clause="",
            lineage=[f"{source_table} (self)"],
        )

    # Queue of (current_table, list_of_edges, set_of_visited_tables)
    queue: deque[tuple[str, list[JoinEdge], set[str]]] = deque([
        (source_table, [], {source_table})
    ])

    while queue:
        curr_table, edge_path, visited = queue.popleft()

        if len(edge_path) >= max_depth:
            continue

        for edge in graph.get(curr_table, []):
            next_table = edge.target_table
            if next_table in visited:
                continue

            new_path = edge_path + [edge]
            if next_table == target_table:
                # Target reached! Construct JoinPath
                return _construct_join_path(source_table, target_table, new_path, db_type)

            queue.append((next_table, new_path, visited | {next_table}))

    return None


def find_all_join_paths(
    graph: dict[str, list[JoinEdge]],
    max_depth: int = 3,
    db_type: str = "sqlite",
) -> list[JoinPath]:
    """
    Discovers all pairwise verified join paths across all tables up to max_depth.
    """
    all_paths: list[JoinPath] = []
    tables = sorted(list(graph.keys()))

    for i in range(len(tables)):
        for j in range(len(tables)):
            if i == j:
                continue
            src, dst = tables[i], tables[j]
            path = find_join_path(graph, src, dst, max_depth=max_depth, db_type=db_type)
            if path is not None and path.depth > 0:
                all_paths.append(path)

    return all_paths


def _construct_join_path(
    source_table: str,
    target_table: str,
    edges: list[JoinEdge],
    db_type: str,
) -> JoinPath:
    """Internal helper to convert a list of JoinEdges into a fully populated JoinPath."""
    steps: list[JoinStep] = []
    lineage: list[str] = []
    join_clauses: list[str] = []

    for edge in edges:
        step = JoinStep(
            from_table=edge.source_table,
            from_column=edge.source_column,
            to_table=edge.target_table,
            to_column=edge.target_column,
            join_type="LEFT JOIN",
        )
        steps.append(step)

        # Lineage string: e.g. "orders.customer_id -> customers.id"
        lineage.append(f"{edge.source_table}.{edge.source_column} -> {edge.target_table}.{edge.target_column}")

        # Deterministic SQL clause
        to_tbl_sql = quote_identifier(edge.target_table, db_type)
        from_col_sql = f"{quote_identifier(edge.source_table, db_type)}.{quote_identifier(edge.source_column, db_type)}"
        to_col_sql = f"{to_tbl_sql}.{quote_identifier(edge.target_column, db_type)}"
        join_clauses.append(f"LEFT JOIN {to_tbl_sql} ON {from_col_sql} = {to_col_sql}")

    depth = len(steps)
    rel_type = "direct" if depth == 1 else "multi-hop"

    return JoinPath(
        source_table=source_table,
        target_table=target_table,
        steps=steps,
        source_columns=[e.source_column for e in edges],
        target_columns=[e.target_column for e in edges],
        relationship_type=rel_type,
        depth=depth,
        generated_join_clause=" ".join(join_clauses),
        lineage=lineage,
    )


def format_join_sql(
    base_table: str,
    paths: list[JoinPath],
    db_type: str = "sqlite",
) -> str:
    """
    Combines one or more JoinPaths starting from base_table into a single clean SQL JOIN string.
    Deduplicates already-joined tables to prevent duplicate table aliases or Cartesian products.
    """
    joined_tables = {base_table}
    clauses: list[str] = []

    for path in paths:
        for step in path.steps:
            if step.to_table not in joined_tables:
                to_tbl_sql = quote_identifier(step.to_table, db_type)
                from_col_sql = f"{quote_identifier(step.from_table, db_type)}.{quote_identifier(step.from_column, db_type)}"
                to_col_sql = f"{to_tbl_sql}.{quote_identifier(step.to_column, db_type)}"
                clauses.append(f"{step.join_type} {to_tbl_sql} ON {from_col_sql} = {to_col_sql}")
                joined_tables.add(step.to_table)

    return " ".join(clauses)
