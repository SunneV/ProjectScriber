from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from scriber.core.models import FileNode


@dataclass(slots=True)
class GraphIndexes:
    by_dir: dict[Path, list[FileNode]] = field(default_factory=dict)
    by_stem: dict[str, list[FileNode]] = field(default_factory=dict)
    by_clean_stem: dict[str, list[FileNode]] = field(default_factory=dict)
    by_language: dict[str, list[FileNode]] = field(default_factory=dict)
    env_key_to_files: dict[str, list[FileNode]] = field(default_factory=dict)
    config_tokens: dict[Path, set[str]] = field(default_factory=dict)
    doc_tokens: dict[Path, set[str]] = field(default_factory=dict)

    @classmethod
    def build(cls, files: dict[Path, FileNode]) -> GraphIndexes:
        indexes = cls()
        
        for rel, node in files.items():
            indexes.by_dir.setdefault(rel.parent, []).append(node)
            indexes.by_stem.setdefault(rel.stem, []).append(node)
            
            clean_stem = re.sub(r'[^a-zA-Z0-9]', '', rel.stem).lower()
            if clean_stem:
                indexes.by_clean_stem.setdefault(clean_stem, []).append(node)
                
            indexes.by_language.setdefault(node.language, []).append(node)
            
            # Simple indexing for .env and docs is done per analyzer as needed, 
            # but we can initialize the dicts here.
            
        return indexes
