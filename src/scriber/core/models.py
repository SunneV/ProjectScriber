from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

FileKind = Literal["code", "support", "other"]
ContentPolicy = Literal["full", "auto", "tree_only"]
OutputFormat = Literal["md", "txt"]
PackMode = Literal["focused", "project_snapshot"]


DEFAULT_SCORING: dict[str, int] = {
    "seed_file": 100,
    "seed_folder_file": 100,
    "direct_dependency": 90,
    "reverse_dependency": 85,
    "related_test": 80,
    "same_package": 65,
    "parent_entrypoint": 60,
    "support_near_seed": 60,
    "project_config": 55,
    "dependency_file": 52,
    "runtime_support": 50,
    "documentation": 45,
    "name_similarity": 45,
    "shared_dependency_bonus": 10,
    "entrypoint_file": 90,
    "code_file": 80,
    "test_file": 60,
    "other_file": 40,
}


@dataclass(slots=True)
class ModuleConfig:
    enabled: bool = True
    depth: int = 2
    include_direct_dependencies: bool = True
    include_reverse_dependencies: bool = True
    include_tests: bool = True
    include_same_package: bool = True
    include_parent_entrypoints: bool = True
    include_project_configs: bool = True
    top_dependencies: int = 10
    content_min_score: int = 50
    tree_min_score: int = 30
    scoring: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_SCORING))


@dataclass(slots=True)
class PythonConfig:
    source_roots: list[str] = field(default_factory=lambda: ["src", "app", "."])
    test_roots: list[str] = field(default_factory=lambda: ["tests", "test"])
    module_init_files: list[str] = field(default_factory=lambda: ["__init__.py"])
    entrypoint_patterns: list[str] = field(
        default_factory=lambda: [
            "main.py",
            "app.py",
            "asgi.py",
            "wsgi.py",
            "routes.py",
            "router.py",
        ]
    )


@dataclass(slots=True)
class SupportContentConfig:
    default: ContentPolicy = "auto"
    full: list[str] = field(default_factory=list)
    tree_only: list[str] = field(default_factory=list)
    auto_max_bytes: int = 80_000


@dataclass(slots=True)
class TokenConfig:
    estimator: str = "chars"
    chars_per_token: int = 4


@dataclass(slots=True)
class CacheConfig:
    enabled: bool = True
    dir: str = ".scriber/cache"


@dataclass(slots=True)
class ScriberConfig:
    version: str = "2"
    format: OutputFormat = "md"
    output: Path = Path(".scriber/scriber_pack.md")
    only_tree: bool = False
    modules: bool = True
    support: bool = True
    use_gitignore: bool = True
    max_files: int = 60
    max_tokens: int = 100_000
    min_score: int = 45
    path_style: str = "project-relative"
    allow_external_paths: bool = False
    code_patterns: list[str] = field(default_factory=list)
    support_patterns: list[str] = field(default_factory=list)
    hard_ignore_patterns: list[str] = field(default_factory=list)
    support_content: SupportContentConfig = field(default_factory=SupportContentConfig)
    modules_config: ModuleConfig = field(default_factory=ModuleConfig)
    python: PythonConfig = field(default_factory=PythonConfig)
    tokens: TokenConfig = field(default_factory=TokenConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)


@dataclass(frozen=True, slots=True)
class FileNode:
    absolute: Path
    relative: Path
    kind: FileKind
    language: str
    size_bytes: int
    is_binary: bool = False
    support_category: str | None = None
    content_policy: ContentPolicy = "auto"
    _cached_text: str | None = field(
        default=None, init=False, repr=False, compare=False, hash=False
    )

    def read_text(self) -> str:
        if self._cached_text is not None:
            return self._cached_text

        try:
            from scriber.native import is_native_available, require_native

            if is_native_available():
                text = require_native().read_text(str(self.absolute))
            else:
                text = self.absolute.read_text(encoding="utf-8", errors="replace")
        except Exception:
            text = self.absolute.read_text(encoding="utf-8", errors="replace")

        object.__setattr__(self, "_cached_text", text)
        return text


@dataclass(slots=True)
class SeedPath:
    original: Path
    absolute: Path
    relative: Path
    is_dir: bool
    expanded_files: list[Path] = field(default_factory=list)


@dataclass(slots=True)
class Candidate:
    file: FileNode
    score: int
    reasons: list[str] = field(default_factory=list)
    seed_sources: set[Path] = field(default_factory=set)
    include_content: bool = False
    content: str | None = None
    token_estimate: int = 0
    omitted_reason: str | None = None
    reason_counts: dict[str, int] = field(default_factory=dict)
    reason_examples: dict[str, list[Path]] = field(default_factory=dict)
    reason_summary: str = ""
    utility: float = 0.0
    raw_score: float = 0.0
    role: str = "unknown"


from scriber.graph.model import RelationEdge, RelationGraph, ModuleGraph  # noqa: E402


@dataclass(slots=True)
class ScriberPack:
    project_root: Path
    config_path: Path
    seed_paths: list[SeedPath]
    candidates: list[Candidate]
    graph: ModuleGraph
    only_tree: bool
    output_format: OutputFormat
    mode: PackMode
    total_tokens: int = 0
    stats: dict[str, Any] = field(default_factory=dict)
    timings: dict[str, float] = field(default_factory=dict)

    @property
    def included_paths(self) -> list[Path]:
        return [candidate.file.relative for candidate in self.candidates]


ContentMode = Literal["full", "excerpt", "outline", "tree", "omit"]

FileRole = Literal[
    "entrypoint",
    "orchestrator",
    "model",
    "config",
    "graph",
    "ranker",
    "renderer",
    "scanner",
    "language_adapter",
    "native_adapter",
    "test",
    "support",
    "docs",
    "generated",
    "unknown",
]


@dataclass(frozen=True, slots=True)
class FileRef:
    path: Path
    kind: FileKind
    language: str
    size_bytes: int
    token_estimate: int
    role: FileRole = "unknown"


@dataclass(frozen=True, slots=True)
class FileOutline:
    path: Path
    language: str
    purpose: str | None
    imports: list[str]
    exports: list[str]
    classes: list[str]
    functions: list[str]
    constants: list[str]
    notes: list[str]
    token_estimate: int


@dataclass(slots=True)
class PackItem:
    file: FileNode
    score: int
    role: FileRole
    content_mode: ContentMode
    reason: str
    reasons: list[str]
    relation_evidence: list[RelationEdge]
    outline: FileOutline | None = None
    content: str | None = None
    excerpts: list[str] = field(default_factory=list)
    token_estimate: int = 0
    item_id: str = ""
    utility: float = 0.0
    raw_score: float = 0.0


@dataclass(slots=True)
class LlmPack:
    project_root: Path
    config_path: Path
    profile: str
    mode: PackMode
    goal: str | None
    budget_target: int
    budget_actual: int
    items: list[PackItem]
    graph: RelationGraph
    stats: dict[str, Any]
    warnings: list[str]
    timings: dict[str, float] = field(default_factory=dict)
