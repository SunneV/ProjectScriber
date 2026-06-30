from __future__ import annotations

import re
from pathlib import Path
from scriber.core.models import FileNode


# Java: "import com.example.service.UserService;" (optionally "static")
IMPORT_RE = re.compile(r"\bimport\s+(?:static\s+)?([a-zA-Z_][\w.]*)\s*;")


def parse_java_imports(source: str) -> list[str]:
    """Parse Java import statements (audit finding #18).

    Returns the fully-qualified import specifiers (e.g.
    ``com.example.service.UserService`` or ``com.example.utils.*``).
    """
    imports: list[str] = []
    for match in IMPORT_RE.finditer(source):
        spec = match.group(1).strip()
        if spec:
            imports.append(spec)
    return imports


def resolve_java_import(
    import_spec: str,
    current_file: FileNode,
    absolute_to_file: dict[Path, FileNode],
    project_root: Path,
) -> set[Path]:
    """Resolve a Java import to a source file (audit finding #18).

    Java maps package+class to a directory tree (``com.example.Foo`` ->
    ``com/example/Foo.java``). We translate the dotted specifier to a posix
    path and look for a matching ``.java`` file in the file set, checking the
    common ``src/main/java`` and ``src/test/java`` roots plus the project root.

    Wildcard imports (``com.example.*``) are not resolved to individual files.
    """
    resolved: set[Path] = set()
    if import_spec.endswith(".*"):
        return resolved

    rel_posix = import_spec.replace(".", "/") + ".java"
    candidate_roots = [
        project_root,
        project_root / "src" / "main" / "java",
        project_root / "src" / "test" / "java",
        project_root / "src",
    ]

    for base in candidate_roots:
        candidate = (base / rel_posix).resolve(strict=False)
        node = absolute_to_file.get(candidate)
        if node and node.language == "java" and not node.is_binary:
            resolved.add(node.relative)
            return resolved

    # Fallback: match by the class basename anywhere in the file set.
    class_name = import_spec.rsplit(".", 1)[-1] + ".java"
    for node in absolute_to_file.values():
        if (
            node.language == "java"
            and node.absolute.name == class_name
            and not node.is_binary
        ):
            resolved.add(node.relative)
    return resolved
