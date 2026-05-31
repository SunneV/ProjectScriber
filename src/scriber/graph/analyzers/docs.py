from __future__ import annotations
from typing import Iterable, Any
from pathlib import Path
from scriber.core.models import FileNode, ScriberConfig
from scriber.graph.indexes import GraphIndexes


class DocsAnalyzer:
    name = "docs"

    def analyze(
        self,
        files: dict[Path, FileNode],
        indexes: GraphIndexes,
        config: ScriberConfig | None,
        edge_cls: Any,
        is_native: bool,
    ) -> Iterable:
        edges = []
        for rel, node in files.items():
            name_lower = node.relative.name.lower()
            if (
                name_lower in {"readme.md", "readme.txt", "readme"}
                or "doc" in name_lower
            ):
                try:
                    content = node.absolute.read_text(encoding="utf-8", errors="ignore")
                    for crel, cnode in files.items():
                        if cnode.kind == "code":
                            if crel.as_posix() in content or (
                                len(crel.name) > 4
                                and crel.name != "__init__.py"
                                and crel.name in content
                            ):
                                edges.append(
                                    edge_cls(
                                        source=str(rel) if is_native else rel,
                                        target=str(crel) if is_native else crel,
                                        kind="doc_mentions_code",
                                        weight=0.42,
                                        confidence=0.8,
                                        evidence=f"{node.relative.name} mentions {crel.name}",
                                        line=None,
                                        analyzer="docs:indexed",
                                    )
                                )
                except Exception:
                    pass
        return edges
