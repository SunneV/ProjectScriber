from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from scriber.core.models import FileNode, PythonConfig


@dataclass(frozen=True, slots=True)
class ImportRecord:
    kind: str
    module: str
    names: tuple[str, ...] = ()
    level: int = 0


def parse_python_imports(path: Path, source: str) -> list[ImportRecord]:
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    imports: list[ImportRecord] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(ImportRecord(kind="import", module=alias.name, names=(), level=0))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = tuple(alias.name for alias in node.names if alias.name != "*")
            imports.append(ImportRecord(kind="from", module=module, names=names, level=node.level))
    return imports


def _is_under(rel: Path, root: str) -> bool:
    if root in {"", "."}:
        return True
    root_path = PurePosixPath(root)
    rel_path = PurePosixPath(rel.as_posix())
    try:
        rel_path.relative_to(root_path)
        return True
    except ValueError:
        return False


def _relative_to_root(rel: Path, root: str) -> Path:
    if root in {"", "."}:
        return rel
    return Path(PurePosixPath(rel.as_posix()).relative_to(PurePosixPath(root)))


def module_name_for_file(file: FileNode, python: PythonConfig) -> str | None:
    if file.language != "python":
        return None
    rel = file.relative
    roots = sorted(python.source_roots, key=lambda item: 0 if item == "." else len(item), reverse=True)
    for source_root in roots:
        if not _is_under(rel, source_root):
            continue
        under = _relative_to_root(rel, source_root)
        if under.suffix not in {".py", ".pyi"}:
            continue
        parts = list(under.with_suffix("").parts)
        if not parts:
            continue
        if under.name in python.module_init_files:
            parts = parts[:-1]
        if not parts:
            continue
        return ".".join(parts)
    return None


def build_module_map(files: dict[Path, FileNode], python: PythonConfig) -> tuple[dict[str, Path], dict[Path, str]]:
    module_to_path: dict[str, Path] = {}
    path_to_module: dict[Path, str] = {}
    for rel, file in files.items():
        module = module_name_for_file(file, python)
        if not module:
            continue
        path_to_module[rel] = module
        module_to_path.setdefault(module, rel)
    return module_to_path, path_to_module


def resolve_relative_module(current_module: str, current_is_init: bool, record: ImportRecord) -> str:
    if record.level <= 0:
        return record.module
    if current_is_init:
        package = current_module
    else:
        package = current_module.rsplit(".", 1)[0] if "." in current_module else ""
    parts = package.split(".") if package else []
    up = max(0, record.level - 1)
    if up:
        parts = parts[:-up] if up <= len(parts) else []
    if record.module:
        parts.extend(record.module.split("."))
    return ".".join(part for part in parts if part)


def resolve_import_record(
    record: ImportRecord,
    *,
    current_file: FileNode,
    current_module: str,
    module_to_path: dict[str, Path],
) -> set[Path]:
    candidates: list[str] = []
    current_is_init = current_file.absolute.name == "__init__.py"

    if record.kind == "import":
        candidates.append(record.module)
    else:
        base = resolve_relative_module(current_module, current_is_init, record) if record.level else record.module
        for name in record.names:
            if base:
                candidates.append(f"{base}.{name}")
            else:
                candidates.append(name)
        if base:
            candidates.append(base)

    resolved: set[Path] = set()
    for candidate in candidates:
        if not candidate:
            continue
        parts = candidate.split(".")
        # Try the exact module first, then walk up to a package. This handles
        # both `from package import symbol` and `from package import module`.
        for end in range(len(parts), 0, -1):
            module = ".".join(parts[:end])
            path = module_to_path.get(module)
            if path is not None:
                resolved.add(path)
                break
    return resolved
