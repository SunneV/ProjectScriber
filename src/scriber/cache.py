from __future__ import annotations

import sys
import json
import hashlib
import logging
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from scriber.core.models import ScriberConfig

logger = logging.getLogger("scriber.cache")


def get_config_hash(config: ScriberConfig) -> str:
    from scriber import __version__

    data = {
        "code_patterns": config.code_patterns,
        "support_patterns": config.support_patterns,
        "hard_ignore_patterns": config.hard_ignore_patterns,
        "support": config.support,
        "support_content_default": config.support_content.default,
        "support_content_full": config.support_content.full,
        "support_content_tree_only": config.support_content.tree_only,
        "support_content_auto_max_bytes": config.support_content.auto_max_bytes,
        "use_gitignore": config.use_gitignore,
        "python_source_roots": config.python.source_roots,
        "python_module_init_files": config.python.module_init_files,
        "scriber_version": __version__,
        "native_scanner_version": 1,
    }
    dump = json.dumps(data, sort_keys=True)
    return hashlib.sha256(dump.encode("utf-8")).hexdigest()


class ScriberCache:
    def __init__(self, config: ScriberConfig, project_root: Path):
        self.enabled = config.cache.enabled
        self.project_root = project_root.resolve()
        self.cache_dir = self.project_root / config.cache.dir
        self.files_cache_path = self.cache_dir / "files.json"
        self.imports_cache_path = self.cache_dir / "imports_v2.json"
        self.graph_snapshot_path = self.cache_dir / "graph.json"
        # Configurable LRU cap (audit finding #3). 0 = unlimited.
        self.max_entries = max(0, int(getattr(config.cache, "max_entries", 50_000)))
        self.config_hash = get_config_hash(config)
        self.python_version = f"{sys.version_info.major}.{sys.version_info.minor}"

        self.reads = 0
        self.hits = 0
        self.writes = 0

        self.files_data: dict[str, dict[str, Any]] = {}
        self.imports_data: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.enabled:
            return

        try:
            if self.files_cache_path.exists():
                with self.files_cache_path.open("r", encoding="utf-8") as f:
                    self.files_data = json.load(f)
            if self.imports_cache_path.exists():
                with self.imports_cache_path.open("r", encoding="utf-8") as f:
                    self.imports_data = json.load(f)
        except Exception as exc:
            logger.warning("Cache load failed, starting with empty cache: %s", exc)
            self.files_data = {}
            self.imports_data = {}

    def get_file(
        self, rel_path: Path, mtime_ns: int, size: int
    ) -> dict[str, Any] | None:
        if not self.enabled:
            return None

        key = rel_path.as_posix()
        entry = self.files_data.get(key)
        if entry is None:
            return None

        if (
            entry.get("mtime_ns") == mtime_ns
            and entry.get("size") == size
            and entry.get("python_version") == self.python_version
            and entry.get("config_hash") == self.config_hash
        ):
            return entry.get("data")
        return None

    def set_file(
        self, rel_path: Path, mtime_ns: int, size: int, data: dict[str, Any]
    ) -> None:
        if not self.enabled:
            return
        key = rel_path.as_posix()
        self.files_data[key] = {
            "mtime_ns": mtime_ns,
            "size": size,
            "python_version": self.python_version,
            "config_hash": self.config_hash,
            "data": data,
        }

    def get_imports(self, rel_path: Path, mtime_ns: int, size: int) -> set[Path] | None:
        if not self.enabled:
            return None
        self.reads += 1
        key = rel_path.as_posix()
        imports = self.imports_data.get(key)
        if imports is not None:
            if (
                imports.get("mtime_ns") == mtime_ns
                and imports.get("size") == size
                and imports.get("config_hash") == self.config_hash
            ):
                self.hits += 1
                return {Path(p) for p in imports.get("targets", [])}
        return None

    def set_imports(self, rel_path: Path, imports: set[Path]) -> None:
        if not self.enabled:
            return
        self.writes += 1
        key = rel_path.as_posix()
        try:
            stat = (self.project_root / rel_path).stat()
            mtime_ns = stat.st_mtime_ns
            size = stat.st_size
        except OSError:
            mtime_ns = 0
            size = 0
        self.imports_data[key] = {
            "mtime_ns": mtime_ns,
            "size": size,
            "config_hash": self.config_hash,
            "targets": [p.as_posix() for p in sorted(imports)],
        }

    def add_import_edge(self, source: Path, target: Path) -> None:
        if not self.enabled:
            return
        self.writes += 1
        key = source.as_posix()
        target_str = target.as_posix()
        if key not in self.imports_data:
            try:
                stat = (self.project_root / source).stat()
                mtime_ns = stat.st_mtime_ns
                size = stat.st_size
            except OSError:
                mtime_ns = 0
                size = 0
            self.imports_data[key] = {
                "mtime_ns": mtime_ns,
                "size": size,
                "config_hash": self.config_hash,
                "targets": [target_str],
            }
        else:
            if target_str not in self.imports_data[key].get("targets", []):
                self.imports_data[key].setdefault("targets", []).append(target_str)
                self.imports_data[key]["targets"].sort()

    def load_graph_snapshot(self) -> dict | None:
        """Load a persisted graph snapshot, or None if missing/invalid (audit feature 2)."""
        if not self.enabled:
            return None
        try:
            if self.graph_snapshot_path.exists():
                with self.graph_snapshot_path.open("r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as exc:
            logger.warning("Graph snapshot load failed: %s", exc)
        return None

    def save_graph_snapshot(self, snapshot: dict) -> None:
        """Persist a graph snapshot to disk (audit feature 2)."""
        if not self.enabled:
            return
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with self.graph_snapshot_path.open("w", encoding="utf-8") as f:
                json.dump(snapshot, f)
        except Exception as exc:
            logger.warning("Graph snapshot write failed: %s", exc)

    def save(self, active_files: set[Path] | None = None) -> None:
        if not self.enabled:
            return

        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

            # Simple cleanup mechanism:
            # 1. Prune stale cache entries (entries for files no longer in active_files)
            if active_files is not None:
                active_keys = {p.as_posix() for p in active_files}
                self.files_data = {
                    k: v for k, v in self.files_data.items() if k in active_keys
                }
                self.imports_data = {
                    k: v for k, v in self.imports_data.items() if k in active_keys
                }

            # 2. Enforce configurable LRU cap to prevent unbounded growth.
            #    max_entries == 0 means unlimited. Eviction is by oldest mtime_ns
            #    (LRU proxy) across files_data; imports_data trimmed to match.
            if self.max_entries > 0 and len(self.files_data) > self.max_entries:
                sorted_keys = sorted(
                    self.files_data.keys(),
                    key=lambda k: self.files_data[k].get("mtime_ns", 0),
                )
                to_remove = sorted_keys[: len(sorted_keys) - self.max_entries]
                for k in to_remove:
                    self.files_data.pop(k, None)
                    self.imports_data.pop(k, None)

            with self.files_cache_path.open("w", encoding="utf-8") as f:
                json.dump(self.files_data, f, indent=2)
            with self.imports_cache_path.open("w", encoding="utf-8") as f:
                json.dump(self.imports_data, f, indent=2)
        except Exception as exc:
            # Surface write errors instead of silently dropping them (audit #21).
            logger.warning("Cache write failed: %s", exc)
