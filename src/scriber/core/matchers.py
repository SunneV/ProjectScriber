from __future__ import annotations

import fnmatch
from functools import lru_cache
from pathlib import PurePosixPath


def normalize_rel(value: str) -> str:
    return value.replace("\\", "/").strip("/")


@lru_cache(maxsize=4096)
def _match_normalized(rel: str, pat: str) -> bool:
    """Match an already-normalized path against a normalized pattern.

    Memoized (audit finding #7): the previous implementation invoked up to 4
    ``fnmatch`` calls plus ``PurePosixPath.match`` per (path, pattern) pair with
    no caching, making classification O(N·P·k). Caching on the normalized
    (rel, pat) tuple collapses repeated lookups for the same pattern list.
    """
    if rel == pat:
        return True

    if pat.endswith("/**"):
        prefix = pat[:-3].strip("/")
        return rel == prefix or rel.startswith(prefix + "/")

    if fnmatch.fnmatch(rel, pat):
        return True

    name = rel.rsplit("/", 1)[-1]
    if "/" not in pat and fnmatch.fnmatch(name, pat):
        return True

    if pat.startswith("**/"):
        short = pat[3:]
        if fnmatch.fnmatch(rel, short) or fnmatch.fnmatch(name, short):
            return True

    try:
        return PurePosixPath(rel).match(pat)
    except ValueError:
        return False


def match_pattern(path: str | PurePosixPath, pattern: str) -> bool:
    """Match a project-relative POSIX path against a pragmatic glob pattern.

    This intentionally stays dependency-free. It is not a full gitwildmatch
    implementation, but it handles the common patterns used in pyproject config:
    `*.py`, `**/*.py`, `dir/**`, `dir/`, exact file paths and basename patterns.
    """
    rel = normalize_rel(str(path))
    pat = pattern.replace("\\", "/").strip()
    if not pat:
        return False
    if pat.startswith("/"):
        pat = pat[1:]
    pat = pat.strip("/") if pat.endswith("/") else pat
    return _match_normalized(rel, pat)


def matches_any(path: str | PurePosixPath, patterns: list[str]) -> bool:
    return any(match_pattern(path, pattern) for pattern in patterns)


class SimpleGitIgnore:
    """Small .gitignore-style matcher used only for dependency-free defaults."""

    def __init__(self, patterns: list[tuple[bool, str]]) -> None:
        self.patterns = patterns

    @classmethod
    def from_file(cls, path):
        if not path.exists():
            return cls([])
        parsed: list[tuple[bool, str]] = []
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            negated = line.startswith("!")
            if negated:
                line = line[1:].strip()
            if line:
                parsed.append((negated, line))
        return cls(parsed)

    def ignores(self, rel_path: str, is_dir: bool = False) -> bool:
        rel = normalize_rel(rel_path)
        ignored = False
        for negated, pattern in self.patterns:
            if self._matches(rel, pattern, is_dir):
                ignored = not negated
        return ignored

    def _matches(self, rel: str, pattern: str, is_dir: bool) -> bool:
        pat = pattern.replace("\\", "/").strip()
        if not pat:
            return False
        if pat.startswith("/"):
            pat = pat[1:]

        if pat.endswith("/"):
            prefix = pat.strip("/")
            return rel == prefix or rel.startswith(prefix + "/")

        if "/" not in pat:
            parts = rel.split("/")
            return any(fnmatch.fnmatch(part, pat) for part in parts)

        return match_pattern(rel, pat)
