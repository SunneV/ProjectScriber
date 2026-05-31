from __future__ import annotations
from scriber.core.models import FileNode, FileOutline
from scriber.outline.base import Outliner


class GenericOutliner(Outliner):
    def outline(self, file: FileNode, content: str) -> FileOutline:
        return FileOutline(
            path=file.relative,
            language=file.language,
            purpose=None,
            imports=[],
            exports=[],
            classes=[],
            functions=[],
            constants=[],
            notes=[
                "Static outline not implemented for this language. Showing generic info."
            ],
            token_estimate=20,
        )
