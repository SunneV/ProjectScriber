from __future__ import annotations
from typing import Iterable, Any
from pathlib import Path
from scriber.core.models import FileNode, ScriberConfig
from scriber.graph.indexes import GraphIndexes


class TestsAnalyzer:
    name = "tests"

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
            if node.kind != "code":
                continue
            stem = rel.stem.lower()
            name = rel.name.lower()
            clean_stem = (
                stem.replace("test_", "").replace("_test", "").replace(".test", "")
            )
            is_test = (
                name.startswith("test_")
                or name.endswith("_test.py")
                or ".test." in name
            )

            if is_test and clean_stem:
                targets = indexes.by_clean_stem.get(clean_stem, [])
                for target_node in targets:
                    if target_node.relative == rel:
                        continue
                    target_name = target_node.relative.name.lower()
                    target_is_test = (
                        target_name.startswith("test_")
                        or target_name.endswith("_test.py")
                        or ".test." in target_name
                    )
                    if not target_is_test:
                        edges.append(
                            edge_cls(
                                source=str(rel) if is_native else rel,
                                target=str(target_node.relative)
                                if is_native
                                else target_node.relative,
                                kind="test_of",
                                weight=0.85,
                                confidence=0.9,
                                evidence=f"test filename {rel.name} matches {target_node.relative.name}",
                                line=None,
                                analyzer="tests:indexed",
                            )
                        )
        return edges
