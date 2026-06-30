"""Graph snapshot serialization + incremental diff (audit feature 2).

Provides whole-graph persistence so the RelationGraph can be restored across
runs instead of rebuilt from scratch. A snapshot stores:
- the full edge list (each RelationEdge's fields), and
- a signature of every source file (rel -> mtime_ns, size) plus the config_hash,
  used to detect which files changed and thus which edges must be rebuilt.

The incremental algorithm: load the prior snapshot, drop edges touching any
changed file, rebuild only those files' edges (reusing the existing per-language
extractors), and re-add survivors. Because RelationGraph.add_edge dedups by
(source, target, kind), re-inserting survivors is idempotent.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scriber.graph.model import ModuleGraph, RelationEdge, RelationGraph


def _edge_to_dict(edge: RelationEdge) -> dict:
    return {
        "source": edge.source.as_posix(),
        "target": edge.target.as_posix(),
        "kind": edge.kind,
        "weight": edge.weight,
        "confidence": edge.confidence,
        "evidence": edge.evidence,
        "line": edge.line,
        "analyzer": edge.analyzer,
    }


def serialize_graph(graph: RelationGraph) -> dict:
    """Serialize a RelationGraph's edges to a JSON-serializable dict."""
    return {"edges": [_edge_to_dict(e) for e in graph.edges]}


def deserialize_graph(data: dict) -> ModuleGraph:
    """Rebuild a ModuleGraph from a serialized snapshot.

    Uses add_edge (which maintains outgoing/incoming/imports/imported_by and
    dedups), so the result is structurally identical to a freshly-built graph.
    """
    from scriber.graph.model import ModuleGraph, RelationEdge

    graph = ModuleGraph()
    for e in data.get("edges", []):
        try:
            graph.add_edge(
                RelationEdge(
                    source=Path(e["source"]),
                    target=Path(e["target"]),
                    kind=e["kind"],
                    weight=e.get("weight", 1.0),
                    confidence=e.get("confidence", 1.0),
                    evidence=e.get("evidence"),
                    line=e.get("line"),
                    analyzer=e.get("analyzer", "unknown"),
                )
            )
        except (KeyError, TypeError):
            continue
    return graph


def build_snapshot(
    graph: RelationGraph,
    config_hash: str,
    file_signatures: dict[str, tuple[int, int]],
) -> dict:
    """Build a full snapshot dict (edges + validation signature)."""
    return {
        "version": 1,
        "config_hash": config_hash,
        "file_signatures": {
            rel: {"mtime_ns": mt, "size": sz}
            for rel, (mt, sz) in file_signatures.items()
        },
        **serialize_graph(graph),
    }


def changed_files(
    snapshot: dict,
    current_signatures: dict[str, tuple[int, int]],
) -> set[str]:
    """Return the set of rel paths whose signature differs from the snapshot.

    A file is "changed" if it is new, or its (mtime_ns, size) differs. Deleted
    files (in snapshot, not current) are NOT reported here — callers should
    intersect with active files; deleted-file edges are pruned naturally
    because they won't be in current_signatures and the rebuild skips them.
    """
    snap_sigs = snapshot.get("file_signatures", {})
    changed: set[str] = set()
    for rel, (mt, sz) in current_signatures.items():
        prev = snap_sigs.get(rel)
        if prev is None or prev.get("mtime_ns") != mt or prev.get("size") != sz:
            changed.add(rel)
    return changed


def filter_edges_by_changed(
    graph: RelationGraph, changed: set[str]
) -> tuple[list, list]:
    """Split graph edges into (survivors, to_rebuild).

    Edges whose source OR target is in `changed` must be rebuilt; the rest
    survive the incremental update.
    """
    survivors: list = []
    to_rebuild: list = []
    for edge in graph.edges:
        if edge.source.as_posix() in changed or edge.target.as_posix() in changed:
            to_rebuild.append(edge)
        else:
            survivors.append(edge)
    return survivors, to_rebuild
