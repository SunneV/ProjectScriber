from __future__ import annotations

import re
from pathlib import Path
from scriber.core.models import FileNode


IMPORT_SINGLE_RE = re.compile(r'\bimport\s+[\'"]([^\'"]+)[\'"]')
IMPORT_BLOCK_RE = re.compile(r"\bimport\s*\(([^)]+)\)")


def parse_go_imports(source: str) -> list[str]:
    imports = []
    for match in IMPORT_SINGLE_RE.finditer(source):
        imports.append(match.group(1))
    for match in IMPORT_BLOCK_RE.finditer(source):
        block = match.group(1)
        for line in block.splitlines():
            line = line.strip()
            if line.startswith("//"):
                continue
            m = re.search(r'[\'"]([^\'"]+)[\'"]', line)
            if m:
                imports.append(m.group(1))
    return imports


def resolve_go_import(
    import_spec: str,
    current_file: FileNode,
    dir_to_files: dict[Path, list[FileNode]],
    project_root: Path,
) -> set[Path]:
    resolved = set()
    go_mod_path = project_root / "go.mod"
    module_name = None
    if go_mod_path.exists():
        try:
            content = go_mod_path.read_text(encoding="utf-8")
            m = re.search(r"^\s*module\s+(\S+)", content, re.MULTILINE)
            if m:
                module_name = m.group(1)
        except Exception:
            pass

    if module_name and import_spec.startswith(module_name):
        rel_spec = import_spec[len(module_name) :].lstrip("/")
        target_dir = (project_root / rel_spec).resolve()
        for node in dir_to_files.get(target_dir, []):
            if node.language == "go":
                resolved.add(node.relative)

    return resolved
