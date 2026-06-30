"""Graph algorithms over RelationGraph (audit findings #12, #13, #16).

Implements:
- Strongly Connected Components (Tarjan) for import-cycle detection (#12)
- Topological layering (Kahn's algorithm) for architectural layers (#16)
- Centrality metrics: weighted degree + simplified PageRank (#13)

These algorithms operate on the implicit node set derived from edge
endpoints (see ``RelationGraph.adjacency``). All functions are pure and
stateless so they can be cached externally.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scriber.graph.model import RelationGraph

from pathlib import Path


def strongly_connected_components(graph: RelationGraph) -> list[list[Path]]:
    """Return SCCs via Tarjan's iterative algorithm (audit #12).

    Each SCC is a list of node paths. An SCC with more than one node, or a
    single-node SCC with a self-loop, indicates a cycle. Suitable for flagging
    import cycles in the dependency graph.
    """
    adj = graph.adjacency()

    index_counter = [0]
    stack: list[Path] = []
    on_stack: set[Path] = set()
    indices: dict[Path, int] = {}
    lowlinks: dict[Path, int] = {}
    result: list[list[Path]] = []

    # Iterative Tarjan to avoid recursion-limit blowups on large graphs.
    for start in adj:
        if start in indices:
            continue
        work: list[tuple[Path, list[Path]]] = [(start, list(adj[start]))]
        while work:
            node, successors = work[-1]
            if node not in indices:
                indices[node] = index_counter[0]
                lowlinks[node] = index_counter[0]
                index_counter[0] += 1
                stack.append(node)
                on_stack.add(node)

            if successors:
                child = successors.pop()
                if child not in indices:
                    work.append((child, list(adj[child])))
                elif child in on_stack:
                    lowlinks[node] = min(lowlinks[node], indices[child])
            else:
                # All successors processed.
                if lowlinks[node] == indices[node]:
                    scc: list[Path] = []
                    while True:
                        w = stack.pop()
                        on_stack.discard(w)
                        scc.append(w)
                        if w == node:
                            break
                    result.append(scc)
                work.pop()
                if work:
                    parent = work[-1][0]
                    lowlinks[parent] = min(lowlinks[parent], lowlinks[node])

    return result


def detect_cycles(graph: RelationGraph) -> list[list[Path]]:
    """Return cyclic SCCs (length > 1, or a self-looping single node).

    Convenience wrapper over ``strongly_connected_components``.
    """
    adj = graph.adjacency()
    cycles: list[list[Path]] = []
    for scc in strongly_connected_components(graph):
        if len(scc) > 1:
            cycles.append(scc)
        elif len(scc) == 1:
            node = scc[0]
            if node in adj.get(node, set()):
                cycles.append(scc)
    return cycles


def topological_layers(graph: RelationGraph) -> list[list[Path]]:
    """Assign each node to a layer via Kahn's algorithm (audit #16).

    Layer 0 contains nodes with no incoming edges (foundations). A node's
    layer is one more than the max layer of its predecessors. Nodes involved
    in cycles are assigned to the last layer they reach, guaranteeing every
    node is placed even when the graph is not a DAG.

    Returns a list of layers (each a list of paths), ordered root-first.
    """
    adj = graph.adjacency()
    # In-degree counts incoming edges per node.
    in_degree: dict[Path, int] = {n: 0 for n in adj}
    for source, targets in adj.items():
        for t in targets:
            in_degree[t] = in_degree.get(t, 0) + 1

    layers: list[list[Path]] = []
    # Start with zero-in-degree nodes.
    current = [n for n, d in in_degree.items() if d == 0]

    while current:
        layers.append(current)
        next_layer: list[Path] = []
        for node in current:
            for target in adj.get(node, set()):
                in_degree[target] -= 1
                if in_degree[target] == 0:
                    next_layer.append(target)
        current = next_layer

    # Any remaining nodes are part of cycles (non-zero in-degree). Append them
    # as a final "cyclic" layer so they are not lost.
    placed: set[Path] = {n for layer in layers for n in layer}
    cyclic = [n for n in adj if n not in placed]
    if cyclic:
        layers.append(cyclic)

    return layers


def degree_centrality(graph: RelationGraph, weighted: bool = True) -> dict[Path, float]:
    """Degree centrality per node (audit #13).

    With ``weighted=True`` the sum of edge weights (incoming + outgoing) is
    used; otherwise it is the raw in+out edge count. This replaces the
    previous hardcoded ``centrality_bonus = 0`` placeholder in the ranker.
    """
    centrality: dict[Path, float] = defaultdict(float)
    for edge in graph.edges:
        value = edge.weight if weighted else 1.0
        centrality[edge.source] += value
        centrality[edge.target] += value
    return dict(centrality)


def pagerank(
    graph: RelationGraph,
    damping: float = 0.85,
    iterations: int = 100,
    tolerance: float = 1e-6,
) -> dict[Path, float]:
    """Simplified PageRank over the graph (audit #13).

    Handles dangling nodes (no out-edges) by redistributing their rank evenly.
    Converges for connected graphs; for disconnected components each settles
    to its own stationary distribution. Returns a path -> score dict.
    """
    adj = graph.adjacency()
    nodes = list(adj)
    n = len(nodes)
    if n == 0:
        return {}

    rank = {node: 1.0 / n for node in nodes}

    for _ in range(iterations):
        new_rank: dict[Path, float] = {node: 0.0 for node in nodes}
        dangling_sum = 0.0
        for node in nodes:
            targets = adj.get(node, set())
            if not targets:
                dangling_sum += rank[node]

        for node in nodes:
            targets = adj.get(node, set())
            out_count = len(targets)
            if out_count > 0:
                share = (rank[node] * damping) / out_count
                for t in targets:
                    new_rank[t] += share
        # Redistribute dangling mass evenly.
        if dangling_sum > 0:
            base = damping * dangling_sum / n
            for node in nodes:
                new_rank[node] += base
        # Teleportation (1 - damping) spread uniformly.
        teleport = (1.0 - damping) / n
        for node in nodes:
            new_rank[node] += teleport

        delta = sum(abs(new_rank[node] - rank[node]) for node in nodes)
        rank = new_rank
        if delta < tolerance:
            break

    return rank
