from __future__ import annotations
from typing import Iterable, Any
from pathlib import Path
import re
import logging
from scriber.core.models import FileNode, ScriberConfig
from scriber.graph.indexes import GraphIndexes

logger = logging.getLogger("scriber.analyzers.env")


class EnvAnalyzer:
    name = "env"

    def analyze(
        self,
        files: dict[Path, FileNode],
        indexes: GraphIndexes,
        config: ScriberConfig | None,
        edge_cls: Any,
        is_native: bool,
    ) -> Iterable:
        edges = []
        file_envs = {}
        for rel, node in files.items():
            if node.kind != "code":
                continue
            try:
                content = node.absolute.read_text(encoding="utf-8", errors="ignore")
                keys = self.extract_env_keys(content)
                if keys:
                    file_envs[rel] = keys
                    for k in keys:
                        indexes.env_key_to_files.setdefault(k, []).append(node)
            except Exception as exc:
                logger.warning("env: failed to read %s: %s", rel, exc)

        for key, nodes in indexes.env_key_to_files.items():
            for i, n1 in enumerate(nodes):
                for j, n2 in enumerate(nodes):
                    if i == j:
                        continue
                    edges.append(
                        edge_cls(
                            source=str(n1.relative) if is_native else n1.relative,
                            target=str(n2.relative) if is_native else n2.relative,
                            kind="env_key",
                            weight=0.4,
                            confidence=0.9,
                            evidence=f"Shared env key: {key}",
                            line=None,
                            analyzer="env:indexed",
                        )
                    )
        return edges

    def extract_env_keys(self, content: str) -> set[str]:
        keys = set()
        for match in re.finditer(
            r'os\.environ(?:\[|\.get\()[\'"]([A-Za-z0-9_]+)[\'"]', content
        ):
            keys.add(match.group(1))
        for match in re.finditer(r'os\.getenv\([\'"]([A-Za-z0-9_]+)[\'"]\)', content):
            keys.add(match.group(1))
        for match in re.finditer(
            r'process\.env(?:\[[\'"]([A-Za-z0-9_]+)[\'"]\]|\.([A-Za-z0-9_]+))', content
        ):
            keys.add(match.group(1) or match.group(2))
        return keys
