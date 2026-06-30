from __future__ import annotations

import re
import os
import json
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


def build_js_alias_map(
    project_root: Path,
) -> dict[str, str]:
    """Build a bare-specifier → directory alias map (audit finding #24).

    Resolves path aliases from ``tsconfig.json`` ``compilerOptions.paths`` and
    the ``imports``/``exports`` subpath map from ``package.json``. Only static
    prefix aliases (``@/*`` → ``src/*`` style) are supported; dynamic/wildcard
    mappings use the ``*`` placeholder.

    Returns a dict like ``{"@": "src", "@components": "src/components"}`` where
    the value is a project-root-relative posix directory.
    """
    aliases: dict[str, str] = {}
    try:
        tsconfig = project_root / "tsconfig.json"
        if tsconfig.exists():
            data = json.loads(tsconfig.read_text(encoding="utf-8", errors="ignore"))
            paths = (
                data.get("compilerOptions", {}).get("paths", {})
                if isinstance(data, dict)
                else {}
            )
            for spec, targets in paths.items():
                if not isinstance(targets, list) or not targets:
                    continue
                alias = spec.split("/*", 1)[0].split("/", 1)[0]
                target = str(targets[0]).replace("\\", "/").strip("/")
                target = target.split("/*", 1)[0]
                if alias and target:
                    aliases[alias] = target
                    break
    except Exception:
        pass

    try:
        pkg = project_root / "package.json"
        if pkg.exists():
            data = json.loads(pkg.read_text(encoding="utf-8", errors="ignore"))
            imports = data.get("imports", {}) if isinstance(data, dict) else {}
            for spec, target in imports.items():
                if not isinstance(target, str):
                    continue
                # Node subpath imports look like "#lib/foo"; keep the "#name" key.
                if spec.startswith("#"):
                    name = spec.split("/", 1)[0]
                    clean = target.lstrip("./").replace("\\", "/").strip("/")
                    aliases.setdefault(name, clean)
    except Exception:
        pass

    return aliases


def _resolve_via_extensions(
    base_path: Path, absolute_to_file: dict[Path, FileNode]
) -> set[Path]:
    """Try resolving ``base_path`` against a list of extensions + index files."""
    extensions = [
        "",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".d.ts",
        ".vue",
        ".svelte",
        ".astro",
        ".json",
    ]
    for ext in extensions:
        candidate = base_path.with_name(base_path.name + ext) if ext else base_path
        node = absolute_to_file.get(candidate)
        if node and not node.is_binary:
            return {node.relative}

    for index_name in [
        "index.ts",
        "index.tsx",
        "index.js",
        "index.jsx",
        "index.vue",
        "index.svelte",
        "index.astro",
    ]:
        candidate = base_path / index_name
        node = absolute_to_file.get(candidate)
        if node and not node.is_binary:
            return {node.relative}
    return set()


def resolve_javascript_import(
    import_spec: str,
    current_file: FileNode,
    absolute_to_file: dict[Path, FileNode],
    project_root: Path | None = None,
    alias_map: dict[str, str] | None = None,
) -> set[Path]:
    resolved: set[Path] = set()

    spec = import_spec

    # Bare-specifier alias resolution (audit #24): map "@components/Button"
    # or "#lib/utils" to a project-root-relative path before resolving.
    if not spec.startswith(".") and alias_map and "/" in spec:
        head, _, rest = spec.partition("/")
        mapped = alias_map.get(head)
        if mapped and project_root is not None:
            alias_path = (project_root / mapped / rest).resolve(strict=False)
            resolved |= _resolve_via_extensions(alias_path, absolute_to_file)
            if resolved:
                return resolved

    # Only relative specs are resolvable without an alias map.
    if not spec.startswith("."):
        return resolved

    parent = current_file.absolute.parent
    try:
        base_path = Path(os.path.abspath(parent / spec))
    except Exception:
        base_path = (parent / spec).resolve(strict=False)

    resolved |= _resolve_via_extensions(base_path, absolute_to_file)
    return resolved
