from __future__ import annotations

from pathlib import Path

from scriber.core.models import FileNode, ScriberConfig
from scriber.graph.model import ModuleGraph, RelationEdge
from scriber.graph.languages.python import build_module_map, parse_python_imports, resolve_import_record
from scriber.scanner.files import read_text_lossy


def build_graph(files: dict[Path, FileNode], config: ScriberConfig, cache: ScriberCache | None = None) -> ModuleGraph:
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

    sample = next(iter(files.values()))
    root = Path(sample.absolute.as_posix()[:len(sample.absolute.as_posix()) - len(sample.relative.as_posix())]).resolve()

    if cache is None:
        from scriber.cache import ScriberCache
        cache = ScriberCache(config, root)

    module_to_path, path_to_module = build_module_map(files, config.python)

    for rel, file in files.items():
        if file.kind != "code" or file.is_binary or file.language not in {"python", "javascript", "typescript", "rust", "go", "c", "cpp"}:
            continue

        try:
            stat = file.absolute.stat()
            mtime_ns = stat.st_mtime_ns
            size = stat.st_size
        except OSError:
            continue

        cached_data = cache.get_file(rel, mtime_ns, size)
        if cached_data is not None:
            cached_imports = cache.get_imports(rel)
            if cached_imports is not None:
                for target in cached_imports:
                    if target in files:
                        graph.imports.setdefault(rel, set()).add(target)
                        graph.imported_by.setdefault(target, set()).add(rel)
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

        elif file.language in {"javascript", "typescript", "react"}:
            from scriber.graph.languages.javascript import parse_javascript_imports, resolve_javascript_import
            try:
                source = file.read_text()
            except OSError:
                continue
            imports = parse_javascript_imports(source)
            for spec in imports:
                for target in resolve_javascript_import(spec, file, absolute_to_file):
                    if target == rel:
                        continue
                    resolved_set.add(target)

        elif file.language == "rust":
            from scriber.graph.languages.rust import parse_rust_imports, resolve_rust_import
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
            from scriber.graph.languages.cpp import parse_cpp_includes, resolve_cpp_include
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


        from scriber.core.models import RelationEdge

        for target in resolved_set:
            graph.add_edge(RelationEdge(
                source=rel,
                target=target,
                kind="import",
                weight=1.0,
                confidence=0.98,
                analyzer=f"imports:{file.language}",
            ))

        cache.set_imports(rel, resolved_set)

    for rel in files:
        graph.imports.setdefault(rel, set())
        graph.imported_by.setdefault(rel, set())

    cache.save(set(files.keys()))
    return graph
