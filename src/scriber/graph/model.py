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
        self.edges.append(edge)
        self.outgoing.setdefault(edge.source, []).append(edge)
        self.incoming.setdefault(edge.target, []).append(edge)

        if edge.kind in {"import", "reexport"}:
            self.imports.setdefault(edge.source, set()).add(edge.target)
            self.imported_by.setdefault(edge.target, set()).add(edge.source)


@dataclass(slots=True)
class ModuleGraph(RelationGraph):
    pass
