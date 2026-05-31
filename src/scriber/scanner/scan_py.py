from __future__ import annotations

import os
from pathlib import Path

from scriber.core.matchers import SimpleGitIgnore
from scriber.core.models import FileNode, ScriberConfig
from scriber.scanner.files import classify_file, should_hard_ignore


def scan_project(root: Path, config: ScriberConfig) -> dict[Path, FileNode]:
    root = root.resolve()
    gitignore = (
        SimpleGitIgnore.from_file(root / ".gitignore")
        if config.use_gitignore
        else SimpleGitIgnore([])
    )
    files: dict[Path, FileNode] = {}

    from scriber.cache import ScriberCache

    cache = ScriberCache(config, root)
    active_files: set[Path] = set()

    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        rel_dir = current.relative_to(root)

        kept_dirs: list[str] = []
        for dirname in dirnames:
            child_rel = (
                (rel_dir / dirname) if rel_dir.as_posix() != "." else Path(dirname)
            )
            if should_hard_ignore(child_rel, config):
                continue
            if config.use_gitignore and gitignore.ignores(
                child_rel.as_posix(), is_dir=True
            ):
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in filenames:
            path = current / filename
            rel = path.relative_to(root)
            if should_hard_ignore(rel, config):
                continue
            if config.use_gitignore and gitignore.ignores(rel.as_posix(), is_dir=False):
                continue

            try:
                stat = path.stat()
                mtime_ns = stat.st_mtime_ns
                size = stat.st_size
            except OSError:
                continue

            active_files.add(rel)

            cached_data = cache.get_file(rel, mtime_ns, size)
            if cached_data is not None:
                node = FileNode(
                    absolute=(root / Path(cached_data["relative"])).resolve(
                        strict=False
                    ),
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
                node = classify_file(path, root, config)
                if node is not None:
                    files[node.relative] = node
                    cache.set_file(
                        rel,
                        mtime_ns,
                        size,
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
    return files
