from __future__ import annotations

import re
from pathlib import Path
from scriber.core.models import FileNode

# Match `#include "header.h"` or `#include <header.h>`
INCLUDE_RE = re.compile(r'#include\s*["<]([^">]+)[">]')


def parse_cpp_includes(source: str) -> list[str]:
    """Parse all include specifiers from C/C++ source code."""
    includes = []
    for match in INCLUDE_RE.finditer(source):
        val = match.group(1)
        if val:
            includes.append(val)
    return includes


def resolve_cpp_include(
    include_spec: str,
    current_file: FileNode,
    absolute_to_file: dict[Path, FileNode]
) -> set[Path]:
    """Resolve a C/C++ include specifier to a project file path."""
    resolved = set()
    parent = current_file.absolute.parent
    
    # 1. Try resolving relative to current file's directory
    try:
        candidate = (parent / include_spec).resolve(strict=False)
    except Exception:
        candidate = parent / include_spec
        
    node = absolute_to_file.get(candidate)
    if node and not node.is_binary:
        resolved.add(node.relative)
        return resolved

    # 2. Try resolving relative to project root or search paths in absolute_to_file
    for path, n in absolute_to_file.items():
        if n.is_binary:
            continue
        rel_posix = n.relative.as_posix()
        # Match if the relative path matches the include spec exactly or ends with it (e.g. "subdir/header.h")
        if rel_posix == include_spec or rel_posix.endswith("/" + include_spec):
            resolved.add(n.relative)
            return resolved

    return resolved
