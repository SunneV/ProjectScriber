from __future__ import annotations
from typing import Iterable, Any
from pathlib import Path
import logging
import re
from scriber.core.models import FileNode, ScriberConfig
from scriber.graph.indexes import GraphIndexes

logger = logging.getLogger("scriber.analyzers.docs")


def _matches_whole_word(haystack: str, needle: str) -> bool:
    """Whole-word match for doc → code references (audit finding #22).

    Prevents false positives where a short filename is a substring of an
    unrelated word in documentation prose (e.g. ``api.py`` inside ``rapid``).
    """
    if "/" in needle or "\\" in needle:
        return needle in haystack
    try:
        return (
            re.search(r"(?<![\w./-])" + re.escape(needle) + r"(?![\w])", haystack)
            is not None
        )
    except re.error:
        return needle in haystack


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
                            posix = crel.as_posix()
                            if _matches_whole_word(content, posix) or (
                                len(crel.name) > 4
                                and crel.name != "__init__.py"
                                and _matches_whole_word(content, crel.name)
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
                except Exception as exc:
                    logger.warning("docs: failed to read %s: %s", rel, exc)
        return edges
