from __future__ import annotations
from typing import Iterable, Any
from pathlib import Path
from scriber.core.models import FileNode, ScriberConfig
from scriber.graph.indexes import GraphIndexes


class PackageAnalyzer:
    name = "package"

    def analyze(
        self,
        files: dict[Path, FileNode],
        indexes: GraphIndexes,
        config: ScriberConfig | None,
        edge_cls: Any,
        is_native: bool,
    ) -> Iterable:
        edges = []
        for d, siblings in indexes.by_dir.items():
            code_siblings = [s for s in siblings if s.kind == "code"]
            for s1 in code_siblings:
                count = 0
                for s2 in code_siblings:
                    if s1 == s2:
                        continue
                    count += 1
                    if count > 8:
                        break
                    edges.append(
                        edge_cls(
                            source=str(s1.relative) if is_native else s1.relative,
                            target=str(s2.relative) if is_native else s2.relative,
                            kind="same_package",
                            weight=0.5,
                            confidence=1.0,
                            evidence=None,
                            line=None,
                            analyzer="package:indexed",
                        )
                    )
        return edges
