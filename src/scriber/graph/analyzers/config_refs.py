from __future__ import annotations
from typing import Iterable, Any
from pathlib import Path
from scriber.core.models import FileNode, ScriberConfig
from scriber.graph.indexes import GraphIndexes


def is_config_file(f: FileNode) -> bool:
    name = f.relative.name.lower()
    return name in {
        "pyproject.toml",
        "setup.py",
        "package.json",
        "dockerfile",
    } or f.relative.suffix.lower() in {".toml", ".yaml", ".yml", ".json"}


class ConfigRefsAnalyzer:
    name = "config_refs"

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
            if is_config_file(node):
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
                                        kind="config_refs_code",
                                        weight=0.6,
                                        confidence=0.8,
                                        evidence=f"Config {rel.name} references {crel.name}",
                                        line=None,
                                        analyzer="config_refs:indexed",
                                    )
                                )
                except Exception:
                    pass
        return edges
