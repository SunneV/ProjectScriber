from __future__ import annotations

import re
from pathlib import Path
from scriber.core.models import FileNode


MOD_RE = re.compile(r'\bmod\s+(\w+)\s*;')
USE_RE = re.compile(r'\buse\s+([^;]+)\s*;')


def parse_rust_imports(source: str) -> list[tuple[str, str]]:
    imports = []
    for match in MOD_RE.finditer(source):
        imports.append(("mod", match.group(1)))
    for match in USE_RE.finditer(source):
        spec = match.group(1).strip()
        if "{" in spec:
            base, rest = spec.split("{", 1)
            base = base.strip()
            rest = rest.replace("}", "").strip()
            for part in rest.split(","):
                part = part.strip()
                if part:
                    imports.append(("use", f"{base}{part}"))
        else:
            imports.append(("use", spec))
    return imports


def resolve_rust_import(kind: str, spec: str, current_file: FileNode, absolute_to_file: dict[Path, FileNode]) -> set[Path]:
    resolved = set()
    parent = current_file.absolute.parent

    if kind == "mod":
        candidates = [
            parent / f"{spec}.rs",
            parent / spec / "mod.rs"
        ]
        for cand in candidates:
            node = absolute_to_file.get(cand)
            if node:
                resolved.add(node.relative)
                return resolved
        return resolved

    parts = spec.split("::")
    if not parts:
        return resolved

    if parts[0] == "crate":
        crate_root = None
        curr = current_file.absolute.parent
        while curr != curr.parent:
            if (curr / "Cargo.toml").exists() or (curr / "src").exists():
                crate_root = curr / "src" if (curr / "src").exists() else curr
                break
            curr = curr.parent
        if not crate_root:
            crate_root = current_file.absolute.parent

        sub_parts = parts[1:]
        if sub_parts:
            for end in range(len(sub_parts), 0, -1):
                module_path = crate_root / Path(*sub_parts[:end])
                candidates = [
                    module_path.with_name(module_path.name + ".rs"),
                    module_path / "mod.rs"
                ]
                for cand in candidates:
                    node = absolute_to_file.get(cand)
                    if node:
                        resolved.add(node.relative)
                        return resolved
    elif parts[0] == "super":
        sub_parts = parts[1:]
        crate_root = parent.parent
        if sub_parts:
            for end in range(len(sub_parts), 0, -1):
                module_path = crate_root / Path(*sub_parts[:end])
                candidates = [
                    module_path.with_name(module_path.name + ".rs"),
                    module_path / "mod.rs"
                ]
                for cand in candidates:
                    node = absolute_to_file.get(cand)
                    if node:
                        resolved.add(node.relative)
                        return resolved
    elif parts[0] == "self":
        sub_parts = parts[1:]
        crate_root = parent
        if sub_parts:
            for end in range(len(sub_parts), 0, -1):
                module_path = crate_root / Path(*sub_parts[:end])
                candidates = [
                    module_path.with_name(module_path.name + ".rs"),
                    module_path / "mod.rs"
                ]
                for cand in candidates:
                    node = absolute_to_file.get(cand)
                    if node:
                        resolved.add(node.relative)
                        return resolved

    return resolved
