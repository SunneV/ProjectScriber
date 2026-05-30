from __future__ import annotations

from pathlib import Path

from scriber.core.matchers import match_pattern, matches_any
from scriber.core.models import ContentPolicy, FileKind, FileNode, ScriberConfig

LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".pyi": "python",
    ".rs": "rust",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".hxx": "cpp",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".md": "markdown",
    ".rst": "rst",
    ".txt": "text",
    ".ini": "ini",
    ".cfg": "ini",
    ".lock": "lock",
}


def is_probably_binary(path: Path) -> bool:
    from scriber.native import require_native
    try:
        return require_native().is_probably_binary(str(path))
    except Exception:
        return True


def language_for(path: Path) -> str:
    if path.name.startswith("Dockerfile"):
        return "dockerfile"
    return LANGUAGE_BY_SUFFIX.get(path.suffix.lower(), "text")


def support_category(rel: Path) -> str:
    s = rel.as_posix()
    name = rel.name
    if name == "pyproject.toml" or name.endswith(".toml") or name in {"setup.py", "setup.cfg", "tox.ini", "pytest.ini", "mypy.ini", "ruff.toml", ".ruff.toml"}:
        return "project config"
    if name.endswith(".lock") or name in {"requirements.txt", "poetry.lock", "uv.lock", "Pipfile", "Pipfile.lock", "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "Cargo.toml", "Cargo.lock", "go.mod", "go.sum"} or s.startswith("requirements/"):
        return "dependency file"
    if name.startswith("README") or name in {"CHANGELOG.md", "CONTRIBUTING.md"} or s.startswith("docs/"):
        return "documentation"
    if name.startswith("Dockerfile") or name.startswith("docker-compose") or name.startswith("compose"):
        return "runtime support"
    if s.startswith(".github/workflows/") or name == ".gitlab-ci.yml":
        return "ci support"
    if name.startswith(".env") or s.startswith("config/") or s.startswith("settings/"):
        return "runtime config"
    if name in {".pre-commit-config.yaml", "tsconfig.json"} or name.startswith("vite.config") or name.startswith("webpack.config"):
        return "tooling config"
    return "support file"


def support_content_policy(rel: Path, config: ScriberConfig) -> ContentPolicy:
    s = rel.as_posix()
    if matches_any(s, config.support_content.tree_only):
        return "tree_only"
    if matches_any(s, config.support_content.full):
        return "full"
    return config.support_content.default


def classify_file(path: Path, root: Path, config: ScriberConfig) -> FileNode | None:
    rel = path.resolve().relative_to(root.resolve())
    rel_s = rel.as_posix()

    if matches_any(rel_s, config.hard_ignore_patterns):
        return None

    binary = is_probably_binary(path)
    kind: FileKind = "other"
    category = None
    policy: ContentPolicy = "auto"

    if matches_any(rel_s, config.code_patterns):
        kind = "code"
    elif config.support and matches_any(rel_s, config.support_patterns):
        kind = "support"
        category = support_category(rel)
        policy = support_content_policy(rel, config)
    else:
        return None

    try:
        size = path.stat().st_size
    except OSError:
        size = 0

    return FileNode(
        absolute=path.resolve(),
        relative=rel,
        kind=kind,
        language=language_for(path),
        size_bytes=size,
        is_binary=binary,
        support_category=category,
        content_policy=policy,
    )


def should_hard_ignore(rel: Path, config: ScriberConfig) -> bool:
    return matches_any(rel.as_posix(), config.hard_ignore_patterns)


def is_text_readable(path: Path) -> bool:
    if is_probably_binary(path):
        return False
    try:
        path.read_text(encoding="utf-8")
        return True
    except UnicodeDecodeError:
        return False
    except OSError:
        return False


def read_text_lossy(path: Path) -> str:
    from scriber.native import require_native
    return require_native().read_text(str(path))



