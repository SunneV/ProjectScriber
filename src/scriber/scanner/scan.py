from __future__ import annotations

from pathlib import Path
from scriber.core.models import FileNode, ScriberConfig
from scriber.native import require_native


def scan_project(root: Path, config: ScriberConfig) -> dict[Path, FileNode]:
    try:
        from scriber.native import is_native_available

        if is_native_available():
            files, _ = scan_project_with_native(root, config)
            return files
    except Exception:
        pass

    from scriber.scanner.scan_py import scan_project as scan_project_py

    return scan_project_py(root, config)


def scan_project_with_native(
    root: Path, config: ScriberConfig
) -> tuple[dict[Path, FileNode], list]:
    root = root.resolve()
    native = require_native()

    native_files = native.scan_project(
        str(root),
        config.use_gitignore,
        config.hard_ignore_patterns,
        config.code_patterns,
        config.support_patterns,
        config.support_content.full,
        config.support_content.tree_only,
        config.support_content.default,
        config.support,
    )

    files: dict[Path, FileNode] = {}

    from scriber.cache import ScriberCache

    cache = ScriberCache(config, root)
    active_files: set[Path] = set()

    for item in native_files:
        rel = Path(item.relative)
        active_files.add(rel)

        cached_data = cache.get_file(rel, item.mtime_ns, item.size_bytes)
        if cached_data is not None:
            node = FileNode(
                absolute=(root / Path(cached_data["relative"])).resolve(strict=False),
                relative=Path(cached_data["relative"]),
                kind=cached_data["kind"],
                language=cached_data["language"],
                size_bytes=cached_data["size_bytes"],
                is_binary=cached_data["is_binary"],
                support_category=cached_data["support_category"],
                content_policy=cached_data["content_policy"],
            )
            files[node.relative] = node
        else:
            node = FileNode(
                absolute=(root / rel).resolve(strict=False),
                relative=rel,
                kind=item.kind,
                language=item.language,
                size_bytes=item.size_bytes,
                is_binary=item.is_binary,
                support_category=item.support_category,
                content_policy=item.content_policy,
            )
            files[node.relative] = node
            cache.set_file(
                rel,
                item.mtime_ns,
                item.size_bytes,
                {
                    "relative": node.relative.as_posix(),
                    "kind": node.kind,
                    "language": node.language,
                    "size_bytes": node.size_bytes,
                    "is_binary": node.is_binary,
                    "support_category": node.support_category,
                    "content_policy": node.content_policy,
                },
            )

    cache.save(active_files)
    return files, native_files
