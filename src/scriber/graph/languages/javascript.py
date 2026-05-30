from __future__ import annotations

import re
import os
from pathlib import Path
from scriber.core.models import FileNode


IMPORT_RE = re.compile(
    r'(?:import|export)\s+(?:[\w*\s{},]*\s+from\s+)?[\'"]([^\'"]+)[\'"]'
    r'|require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)'
)


def parse_javascript_imports(source: str) -> list[str]:
    imports = []
    for match in IMPORT_RE.finditer(source):
        val = match.group(1) or match.group(2)
        if val:
            imports.append(val)
    return imports


def resolve_javascript_import(import_spec: str, current_file: FileNode, absolute_to_file: dict[Path, FileNode]) -> set[Path]:
    resolved = set()
    if not import_spec.startswith("."):
        return resolved

    parent = current_file.absolute.parent
    try:
        base_path = Path(os.path.abspath(parent / import_spec))
    except Exception:
        base_path = (parent / import_spec).resolve(strict=False)
        
    extensions = ["", ".ts", ".tsx", ".js", ".jsx", ".d.ts"]
    for ext in extensions:
        candidate = base_path.with_name(base_path.name + ext) if ext else base_path
        node = absolute_to_file.get(candidate)
        if node and not node.is_binary:
            resolved.add(node.relative)
            return resolved

    # Try index files
    for index_name in ["index.ts", "index.tsx", "index.js", "index.jsx"]:
        candidate = base_path / index_name
        node = absolute_to_file.get(candidate)
        if node and not node.is_binary:
            resolved.add(node.relative)
            return resolved

    return resolved
