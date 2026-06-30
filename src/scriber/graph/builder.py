from __future__ import annotations
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scriber.cache import ScriberCache

from pathlib import Path

from scriber.core.models import FileNode, ScriberConfig
from scriber.graph.model import ModuleGraph, RelationEdge
from scriber.graph.languages.python import (
    build_module_map,
    parse_python_imports,
    resolve_import_record,
)


def _derive_root(files: dict[Path, FileNode], sample: FileNode) -> Path:
    """Derive the project root from the file set (audit finding #23).

    Primary strategy: strip the relative suffix from each file's absolute
    path and confirm every file agrees on the same root. If they agree, that
    root is used. If they disagree (e.g. symlinked roots or mixed base dirs),
    fall back to ``os.path.commonpath`` over all absolute parents.
    """
    candidate: Path | None = None
    consistent = True
    for node in files.values():
        abs_posix = node.absolute.as_posix()
        rel_posix = node.relative.as_posix()
        if abs_posix.endswith(rel_posix):
            derived = Path(abs_posix[: len(abs_posix) - len(rel_posix)]).resolve()
            if candidate is None:
                candidate = derived
            elif derived != candidate:
                consistent = False
                break
        else:
            consistent = False
            break

    if candidate is not None and consistent:
        return candidate

    # Fallback: common ancestor of all absolute file paths' parents.
    try:
        parents = [str(node.absolute.parent) for node in files.values()]
        if parents:
            common = os.path.commonpath(parents)
            return Path(common).resolve()
    except ValueError:
        # commonpath fails on mixed drives (Windows). Fall through.
        pass

    # Last resort: the original per-file derivation from the sample.
    abs_posix = sample.absolute.as_posix()
    rel_posix = sample.relative.as_posix()
    return Path(
        abs_posix[: len(abs_posix) - len(rel_posix)]
        if abs_posix.endswith(rel_posix)
        else abs_posix
    ).resolve()


def build_graph(
    files: dict[Path, FileNode],
    config: ScriberConfig,
    cache: ScriberCache | None = None,
) -> ModuleGraph:
    graph = ModuleGraph()
    if not files:
        return graph

    path_to_module: dict[Path, str] = {}
    module_to_path: dict[str, Path] = {}

    absolute_to_file: dict[Path, FileNode] = {}
    dir_to_files: dict[Path, list[FileNode]] = {}
    for node in files.values():
        absolute_to_file[node.absolute] = node
        dir_to_files.setdefault(node.absolute.parent, []).append(node)

    # Robust project-root detection (audit finding #23). The previous logic
    # derived root by stripping the relative suffix from the FIRST file only,
    # assuming every file shares one root — fragile under symlinks and
    # monorepo multi-root layouts. We now derive root from the relationship
    # between absolute and relative paths of all files, falling back to a
    # commonpath-based derivation if the per-file computation disagrees.
    sample = next(iter(files.values()))
    root = _derive_root(files, sample)

    if cache is None:
        from scriber.cache import ScriberCache

        cache = ScriberCache(config, root)

    module_to_path, path_to_module = build_module_map(files, config.python)

    for rel, file in files.items():
        if (
            file.kind != "code"
            or file.is_binary
            or file.language
            not in {
                "python",
                "javascript",
                "typescript",
                "rust",
                "go",
                "c",
                "cpp",
                "java",
            }
        ):
            continue

        try:
            stat = file.absolute.stat()
            mtime_ns = stat.st_mtime_ns
            size = stat.st_size
        except OSError:
            continue

        cached_data = cache.get_file(rel, mtime_ns, size)
        if cached_data is not None:
            cached_imports = cache.get_imports(rel, mtime_ns, size)
            if cached_imports is not None:
                for target in cached_imports:
                    if target in files:
                        graph.add_edge(
                            RelationEdge(
                                source=rel,
                                target=target,
                                kind="import",
                                weight=1.0,
                                confidence=0.98,
                                analyzer=f"imports:{file.language}",
                            )
                        )
                continue

        resolved_set = set()

        if file.language == "python":
            current_module = path_to_module.get(rel)
            if current_module:
                try:
                    source = file.read_text()
                except OSError:
                    continue
                imports = parse_python_imports(file.absolute, source)
                for record in imports:
                    for target in resolve_import_record(
                        record,
                        current_file=file,
                        current_module=current_module,
                        module_to_path=module_to_path,
                    ):
                        if target == rel:
                            continue
                        resolved_set.add(target)

        elif file.language in {"javascript", "typescript"}:
            from scriber.graph.languages.javascript import (
                parse_javascript_imports,
                resolve_javascript_import,
                build_js_alias_map,
            )

            try:
                source = file.read_text()
            except OSError:
                continue
            # Build the alias map once per build for bare-specifier resolution
            # (audit #24): tsconfig paths + package.json imports/exports.
            alias_map = build_js_alias_map(root)
            imports = parse_javascript_imports(source)
            for spec in imports:
                for target in resolve_javascript_import(
                    spec,
                    file,
                    absolute_to_file,
                    project_root=root,
                    alias_map=alias_map,
                ):
                    if target == rel:
                        continue
                    resolved_set.add(target)

        elif file.language == "rust":
            from scriber.graph.languages.rust import (
                parse_rust_imports,
                resolve_rust_import,
            )

            try:
                source = file.read_text()
            except OSError:
                continue
            imports = parse_rust_imports(source)
            for kind, spec in imports:
                for target in resolve_rust_import(kind, spec, file, absolute_to_file):
                    if target == rel:
                        continue
                    resolved_set.add(target)

        elif file.language == "go":
            from scriber.graph.languages.go import parse_go_imports, resolve_go_import

            try:
                source = file.read_text()
            except OSError:
                continue
            imports = parse_go_imports(source)
            for spec in imports:
                for target in resolve_go_import(spec, file, dir_to_files, root):
                    if target == rel:
                        continue
                    resolved_set.add(target)

        elif file.language in {"c", "cpp"}:
            from scriber.graph.languages.cpp import (
                parse_cpp_includes,
                resolve_cpp_include,
            )

            try:
                source = file.read_text()
            except OSError:
                continue
            imports = parse_cpp_includes(source)
            for spec in imports:
                for target in resolve_cpp_include(spec, file, absolute_to_file):
                    if target == rel:
                        continue
                    resolved_set.add(target)

        elif file.language == "java":
            # Java import extraction (audit finding #18).
            from scriber.graph.languages.java import (
                parse_java_imports,
                resolve_java_import,
            )

            try:
                source = file.read_text()
            except OSError:
                continue
            imports = parse_java_imports(source)
            for spec in imports:
                for target in resolve_java_import(spec, file, absolute_to_file, root):
                    if target == rel:
                        continue
                    resolved_set.add(target)

        for target in resolved_set:
            graph.add_edge(
                RelationEdge(
                    source=rel,
                    target=target,
                    kind="import",
                    weight=1.0,
                    confidence=0.98,
                    analyzer=f"imports:{file.language}",
                )
            )

        cache.set_imports(rel, resolved_set)

    for rel in files:
        graph.imports.setdefault(rel, set())
        graph.imported_by.setdefault(rel, set())

    # Symbol-level relations (audit finding #15): the Python symbol extractor
    # already existed but was only wired to tests. Now we build a SymbolIndex
    # from the codebase and emit type_reference / inherits edges between a
    # class definition and the files that reference its name in an import.
    _emit_symbol_relations(files, graph, module_to_path, path_to_module, config)

    cache.save(set(files.keys()))
    return graph


def _emit_symbol_relations(
    files: dict[Path, FileNode],
    graph: ModuleGraph,
    module_to_path: dict[str, Path],
    path_to_module: dict[Path, str],
    config: ScriberConfig,
) -> None:
    """Emit symbol-level edges for Python files (audit #15).

    Builds a map of class-name -> defining file from a SymbolIndex, then scans
    each Python file's imported names. If an imported name matches a class
    defined elsewhere, emit a ``type_reference`` edge. ``inherits`` edges are
    emitted when a class's base classes reference names defined in other files.
    """
    try:
        from scriber.core.symbols import SymbolIndex
        from scriber.graph.languages.extractor import extract_python_symbols
        from scriber.graph.languages.python import parse_python_imports
    except Exception:
        return

    symbol_index = SymbolIndex()
    name_to_file: dict[str, Path] = {}

    # Phase 1: collect class definitions across all Python files.
    for rel, node in files.items():
        if node.language != "python" or node.is_binary:
            continue
        try:
            source = node.read_text()
        except OSError:
            continue
        extract_python_symbols(node.absolute, source, symbol_index)
        for sym in symbol_index.get_symbols(node.absolute):
            if sym.kind == "class":
                # Last-writer-wins is acceptable; duplicates across files are rare
                # and the relation is best-effort/heuristic.
                name_to_file.setdefault(sym.name, rel)

    if not name_to_file:
        return

    # Phase 2: scan imports and class bases for references to known classes.
    for rel, node in files.items():
        if node.language != "python" or node.is_binary:
            continue
        try:
            source = node.read_text()
        except OSError:
            continue

        # Imported names referencing a class defined in another file.
        for record in parse_python_imports(node.absolute, source):
            imported_names = _names_from_import_record(record)
            for name in imported_names:
                target = name_to_file.get(name)
                if target and target != rel:
                    graph.add_edge(
                        RelationEdge(
                            source=rel,
                            target=target,
                            kind="type_reference",
                            weight=0.55,
                            confidence=0.7,
                            evidence=f"references class {name}",
                            analyzer="symbols:python",
                        )
                    )

        # Inheritance: classes whose bases reference known classes.
        for sym in symbol_index.get_symbols(node.absolute):
            if sym.kind != "class":
                continue
            bases = _extract_class_bases(source, sym)
            for base in bases:
                target = name_to_file.get(base)
                if target and target != rel:
                    graph.add_edge(
                        RelationEdge(
                            source=rel,
                            target=target,
                            kind="inherits",
                            weight=0.7,
                            confidence=0.75,
                            evidence=f"{sym.name} inherits {base}",
                            analyzer="symbols:python",
                        )
                    )


def _names_from_import_record(record) -> set[str]:
    """Extract the imported symbol names from an import record (best-effort)."""
    names: set[str] = set()
    # An import record is a small dataclass-like object produced by the python
    # language adapter. We tolerate two shapes: a tuple/record with module +
    # names, or an object with .names attribute.
    candidates = []
    if hasattr(record, "names"):
        candidates = list(getattr(record, "names") or [])
    elif isinstance(record, (tuple, list)):
        # Heuristic: records are (module, [names...], level, ...).
        for part in record[1:]:
            if isinstance(part, (list, tuple, set)):
                candidates.extend(part)
            elif isinstance(part, str):
                candidates.append(part)
    for c in candidates:
        if isinstance(c, str) and c and c != "*":
            # Split "module.Name" -> take the last component.
            names.add(c.rsplit(".", 1)[-1])
    return names


def _extract_class_bases(source: str, sym) -> list[str]:
    """Best-effort extraction of base-class names for a given class symbol."""
    import ast

    try:
        tree = ast.parse(source)
    except Exception:
        return []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == sym.name:
            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(base.attr)
            return bases
    return []
