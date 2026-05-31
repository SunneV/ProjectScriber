from __future__ import annotations

from typing import Iterable, Protocol
from pathlib import Path

from scriber.core.models import FileNode, ScriberConfig
from scriber.graph.indexes import GraphIndexes
from scriber.graph.model import RelationEdge


class RelationAnalyzer(Protocol):
    name: str

    def analyze(self, files: dict[Path, FileNode], indexes: GraphIndexes, config: ScriberConfig) -> Iterable[RelationEdge]:
        ...
