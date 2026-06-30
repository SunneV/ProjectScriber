from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

RelationKind = Literal[
    "import",
    "reexport",
    "call",
    "type_reference",
    "inherits",
    "implements",
    "test_of",
    "fixture_for",
    "config_refs_code",
    "env_key",
    "doc_mentions_symbol",
    "doc_mentions_code",
    "same_package",
    "same_dir",
    "name_similarity",
    "git_cochange",
    "semantic_similarity",
    "entrypoint_to_module",
]


@dataclass(frozen=True, slots=True)
class RelationEdge:
    source: Path
    target: Path
    kind: RelationKind
    weight: float = 1.0
    confidence: float = 1.0
    evidence: str | None = None
    line: int | None = None
    analyzer: str = "unknown"


@dataclass(slots=True)
class RelationGraph:
    edges: list[RelationEdge] = field(default_factory=list)
    outgoing: dict[Path, list[RelationEdge]] = field(default_factory=dict)
    incoming: dict[Path, list[RelationEdge]] = field(default_factory=dict)
    imports: dict[Path, set[Path]] = field(default_factory=dict)
    imported_by: dict[Path, set[Path]] = field(default_factory=dict)

    def add_edge(self, edge: RelationEdge) -> None:
        # Deduplicate by (source, target, kind): if an equivalent edge already
        # exists, keep the stronger one (max weight & confidence) and drop the
        # duplicate. Previously add_edge was append-only, allowing duplicates
        # to accumulate (audit finding #17).
        bucket = self.outgoing.get(edge.source)
        if bucket:
            for existing in bucket:
                if existing.target == edge.target and existing.kind == edge.kind:
                    # Merge: take the stronger edge.
                    if (edge.weight, edge.confidence) > (
                        existing.weight,
                        existing.confidence,
                    ):
                        # Replace in place across all stores.
                        self._replace_edge(existing, edge)
                    return

        self.edges.append(edge)
        self.outgoing.setdefault(edge.source, []).append(edge)
        self.incoming.setdefault(edge.target, []).append(edge)

        if edge.kind in {"import", "reexport"}:
            self.imports.setdefault(edge.source, set()).add(edge.target)
            self.imported_by.setdefault(edge.target, set()).add(edge.source)

    def _replace_edge(self, old: RelationEdge, new: RelationEdge) -> None:
        """Swap an existing edge for a stronger equivalent one in all stores."""
        try:
            self.edges[self.edges.index(old)] = new
        except ValueError:
            self.edges.append(new)
        out_list = self.outgoing.get(new.source, [])
        if old in out_list:
            out_list[out_list.index(old)] = new
        in_list = self.incoming.get(new.target, [])
        if old in in_list:
            in_list[in_list.index(old)] = new

    @property
    def nodes(self) -> set[Path]:
        """Return the set of all node paths (audit finding #11).

        Nodes are implied by edge endpoints; this materializes them on demand
        without storing a separate set.
        """
        seen: set[Path] = set()
        for edge in self.edges:
            seen.add(edge.source)
            seen.add(edge.target)
        return seen

    def adjacency(self) -> dict[Path, set[Path]]:
        """Unweighted directed adjacency (source -> {targets}).

        Built once and reused by graph algorithms (SCC, toposort, centrality)
        to avoid rebuilding from ``outgoing`` each call.
        """
        adj: dict[Path, set[Path]] = {}
        for edge in self.edges:
            adj.setdefault(edge.source, set()).add(edge.target)
            adj.setdefault(edge.target, set())
        return adj


@dataclass(slots=True)
class ModuleGraph(RelationGraph):
    pass
