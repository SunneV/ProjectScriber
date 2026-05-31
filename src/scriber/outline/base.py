from __future__ import annotations
from typing import Protocol
from scriber.core.models import FileNode, FileOutline

class Outliner(Protocol):
    def outline(self, file: FileNode, content: str) -> FileOutline:
        ...
