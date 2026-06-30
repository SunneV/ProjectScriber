"""Graph export formatters: DOT (Graphviz) and Mermaid (audit finding #14).

These produce static text representations of the RelationGraph that integrate
with common tooling (Graphviz, GitHub/Notion Mermaid diagrams). Complements
the interactive ``render_graph_html`` renderer.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scriber.graph.model import RelationGraph


# Edge style per relation kind for DOT output.
_DOT_EDGE_STYLE = {
    "import": ("solid", "black"),
    "reexport": ("solid", "#444444"),
    "call": ("dashed", "#6b7894"),
    "type_reference": ("dashed", "#38bdf8"),
    "inherits": ("bold", "#a78bfa"),
    "implements": ("bold", "#5eead4"),
    "test_of": ("dotted", "#4ade80"),
    "fixture_for": ("dotted", "#22c55e"),
    "config_refs_code": ("dashed", "#fbbf24"),
    "env_key": ("dotted", "#f59e0b"),
    "doc_mentions_code": ("dotted", "#9aa8c2"),
    "same_package": ("dotted", "#4a5670"),
    "same_dir": ("dotted", "#3a4660"),
    "name_similarity": ("dotted", "#2e3d5c"),
}


def _dot_node_id(path: Path) -> str:
    """Stable, DOT-safe node identifier from a path."""
    import re

    raw = path.as_posix()
    return "n_" + re.sub(r"[^a-zA-Z0-9]", "_", raw)


def _dot_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def render_dot(graph: RelationGraph, title: str = "Scriber Relation Graph") -> str:
    """Render the graph as a Graphviz DOT digraph (audit #14)."""
    lines = [
        f'digraph "{_dot_escape(title)}" {{',
        "  rankdir=LR;",
        '  graph [fontname="Helvetica"];',
        '  node [fontname="Helvetica", shape=box, style="rounded,filled", fillcolor="#1c2640", fontcolor="#e6ecf5"];',
        '  edge [fontname="Helvetica", fontcolor="#9aa8c2"];',
    ]

    # Nodes.
    for node in graph.nodes:
        nid = _dot_node_id(node)
        label = _dot_escape(node.name)
        lines.append(f'  {nid} [label="{label}"];')

    # Edges.
    for edge in graph.edges:
        style, color = _DOT_EDGE_STYLE.get(edge.kind, ("solid", "#6b7894"))
        src = _dot_node_id(edge.source)
        tgt = _dot_node_id(edge.target)
        attrs = [f"style={style}", f'color="{color}"']
        if edge.kind != "import":
            attrs.append(f'label="{edge.kind}"')
        lines.append(f"  {src} -> {tgt} [{', '.join(attrs)}];")

    lines.append("}")
    return "\n".join(lines) + "\n"


def render_mermaid(graph: RelationGraph, title: str = "Scriber Relation Graph") -> str:
    """Render the graph as a Mermaid flowchart (audit #14).

    Mermaid renders natively on GitHub, Notion and many markdown viewers.
    """
    lines = ["```mermaid", "---", f"title: {title}", "---", "flowchart LR"]

    # Nodes (Mermaid uses sanitized ids).
    import re

    seen_nodes: set[str] = set()
    for node in graph.nodes:
        nid = "n_" + re.sub(r"[^a-zA-Z0-9]", "_", node.as_posix())
        if nid in seen_nodes:
            continue
        seen_nodes.add(nid)
        label = node.name.replace('"', "'")
        lines.append(f'  {nid}["{label}"]')

    # Edges — group imports to keep the diagram readable; label others.
    for edge in graph.edges:
        src = "n_" + re.sub(r"[^a-zA-Z0-9]", "_", edge.source.as_posix())
        tgt = "n_" + re.sub(r"[^a-zA-Z0-9]", "_", edge.target.as_posix())
        if edge.kind == "import":
            lines.append(f"  {src} --> {tgt}")
        else:
            lines.append(f"  {src} -. {edge.kind} .-> {tgt}")

    lines.append("```")
    return "\n".join(lines) + "\n"
