from __future__ import annotations
from typing import Iterable, Any
from pathlib import Path
import logging
import re
from scriber.core.models import FileNode, ScriberConfig
from scriber.graph.indexes import GraphIndexes

logger = logging.getLogger("scriber.analyzers.config_refs")


def _matches_whole_word(haystack: str, needle: str) -> bool:
    """Whole-word match (audit finding #22).

    Previously a naive substring check was used, so e.g. ``api.py`` matched
    inside ``rapid`` and ``mapping.py`` matched almost anything. We now require
    a word boundary on each side for the basename, while keeping the full
    relative path as a verbatim substring (paths contain ``/`` delimiters and
    are unambiguous).
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
                            posix = crel.as_posix()
                            # Whole-word match (audit #22): path stays verbatim,
                            # basename requires word boundaries to avoid false
                            # positives like "api.py" inside "rapid".
                            if _matches_whole_word(content, posix) or (
                                len(crel.name) > 4
                                and crel.name != "__init__.py"
                                and _matches_whole_word(content, crel.name)
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
                except Exception as exc:
                    logger.warning("config_refs: failed to read %s: %s", rel, exc)
        return edges
