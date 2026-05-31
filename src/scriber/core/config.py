from __future__ import annotations

from pathlib import Path
from typing import Any
from dataclasses import dataclass

try:  # pragma: no cover - exercised on Python < 3.11 only
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

from .models import (
    CacheConfig,
    ModuleConfig,
    PythonConfig,
    ScriberConfig,
    SupportContentConfig,
    TokenConfig,
)

DEFAULT_CODE_PATTERNS = [
    "**/*.py",
    "**/*.pyi",
    "**/*.rs",
    "**/*.js",
    "**/*.jsx",
    "**/*.ts",
    "**/*.tsx",
    "**/*.go",
    "**/*.java",
    "**/*.kt",
    "**/*.c",
    "**/*.cpp",
    "**/*.h",
    "**/*.hpp",
    "**/*.html",
    "**/*.htm",
    "**/*.vue",
    "**/*.svelte",
    "**/*.astro",
    "**/*.css",
    "**/*.scss",
    "**/*.sass",
    "**/*.less",
]

DEFAULT_SUPPORT_PATTERNS = [
    "**/*.toml",
    "**/*.lock",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "requirements/*.txt",
    "tox.ini",
    "pytest.ini",
    "mypy.ini",
    "ruff.toml",
    ".ruff.toml",
    "Pipfile",
    "README.md",
    "README.rst",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "docs/**/*.md",
    ".env.example",
    ".env.template",
    "config/*.toml",
    "config/*.yaml",
    "config/*.yml",
    "config/*.json",
    "settings/*.toml",
    "settings/*.yaml",
    "settings/*.yml",
    "Dockerfile",
    "Dockerfile.*",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
    ".gitlab-ci.yml",
    ".pre-commit-config.yaml",
    "package.json",
    "tsconfig.json",
    "vite.config.*",
    "webpack.config.*",
    "Cargo.toml",
    "Cargo.lock",
    "go.mod",
    "go.sum",
    "poetry.lock",
    "uv.lock",
    "Pipfile.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "**/*.svg",
    "**/*.json",
]

DEFAULT_SUPPORT_FULL = [
    "**/*.toml",
    "pyproject.toml",
    "requirements.txt",
    "requirements/*.txt",
    "pytest.ini",
    "tox.ini",
    "mypy.ini",
    "ruff.toml",
    ".ruff.toml",
    ".env.example",
    ".env.template",
    "Dockerfile",
    "Dockerfile.*",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
    "README.md",
    "Cargo.toml",
    "go.mod",
    "**/*.json",
]

DEFAULT_SUPPORT_TREE_ONLY = [
    "**/*.svg",
    "**/*.lock",
    "Cargo.lock",
    "poetry.lock",
    "uv.lock",
    "Pipfile.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "go.sum",
]

DEFAULT_HARD_IGNORE = [
    ".git/**",
    ".idea/**",
    ".hg/**",
    ".svn/**",
    ".scriber/**",
    ".venv/**",
    "venv/**",
    "env/**",
    "__pycache__/**",
    ".pytest_cache/**",
    ".mypy_cache/**",
    ".ruff_cache/**",
    "node_modules/**",
    "dist/**",
    "build/**",
    "target/**",
    ".next/**",
    ".turbo/**",
]

DEFAULT_CONFIG_BLOCK = """
[tool.scriber]
version = "2"
format = "md"
output = ".scriber/scriber_pack.md"
only_tree = false
use_gitignore = true
max_files = 0
max_tokens = 0
min_score = 45
path_style = "project-relative"
allow_external_paths = false

[tool.scriber.code_files]
patterns = ["**/*.py", "**/*.pyi", "**/*.rs", "**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx"]

[tool.scriber.support_files]
enabled = true
patterns = [
  "**/*.toml",
  "**/*.lock",
  "pyproject.toml",
  "README.md",
  "requirements.txt",
  "requirements/*.txt",
  ".env.example",
  "Dockerfile",
  "docker-compose.yml",
  ".github/workflows/*.yml",
  "**/*.svg",
]

[tool.scriber.support_files.content]
default = "auto"
full = ["**/*.toml", "pyproject.toml", "README.md", "requirements.txt", "requirements/*.txt", ".env.example", "Dockerfile", "docker-compose.yml", ".github/workflows/*.yml"]
tree_only = ["**/*.svg", "**/*.lock"]

[tool.scriber.modules]
enabled = true
depth = 2
include_direct_dependencies = true
include_reverse_dependencies = true
include_tests = true
include_same_package = true
include_parent_entrypoints = true
include_project_configs = true
content_min_score = 50
tree_min_score = 30

[tool.scriber.python]
source_roots = ["src", "app", "."]
test_roots = ["tests", "test"]
entrypoint_patterns = ["main.py", "app.py", "asgi.py", "wsgi.py", "routes.py", "router.py"]

[tool.scriber.tokens]
estimator = "chars"
chars_per_token = 4
""".strip()


def load_raw_pyproject(config_path: Path) -> dict[str, Any]:
    with config_path.open("rb") as handle:
        return tomllib.load(handle)


def load_config(config_path: Path) -> ScriberConfig:
    raw = load_raw_pyproject(config_path)
    tool = raw.get("tool", {}) if isinstance(raw, dict) else {}
    data = tool.get("scriber", {}) if isinstance(tool, dict) else {}

    config = ScriberConfig(
        code_patterns=list(DEFAULT_CODE_PATTERNS),
        support_patterns=list(DEFAULT_SUPPORT_PATTERNS),
        hard_ignore_patterns=list(DEFAULT_HARD_IGNORE),
    )

    if not isinstance(data, dict):
        return config

    config.version = str(data.get("version", config.version))
    config.format = data.get("format", config.format)
    config.output = Path(data.get("output", str(config.output)))
    config.only_tree = bool(data.get("only_tree", config.only_tree))
    config.use_gitignore = bool(data.get("use_gitignore", config.use_gitignore))
    config.max_files = int(data.get("max_files", config.max_files))
    config.max_tokens = int(data.get("max_tokens", config.max_tokens))
    config.min_score = int(data.get("min_score", config.min_score))
    config.path_style = str(data.get("path_style", config.path_style))
    config.allow_external_paths = bool(
        data.get("allow_external_paths", config.allow_external_paths)
    )

    code_files = data.get("code_files", {})
    if isinstance(code_files, dict) and isinstance(code_files.get("patterns"), list):
        config.code_patterns = [str(item) for item in code_files["patterns"]]

    support_files = data.get("support_files", {})
    if isinstance(support_files, dict):
        config.support = bool(support_files.get("enabled", config.support))
        if isinstance(support_files.get("patterns"), list):
            config.support_patterns = [str(item) for item in support_files["patterns"]]
        content = support_files.get("content", {})
        if isinstance(content, dict):
            config.support_content = SupportContentConfig(
                default=content.get("default", config.support_content.default),
                full=[
                    str(item)
                    for item in content.get("full", config.support_content.full)
                ],
                tree_only=[
                    str(item)
                    for item in content.get(
                        "tree_only", config.support_content.tree_only
                    )
                ],
                auto_max_bytes=int(
                    content.get("auto_max_bytes", config.support_content.auto_max_bytes)
                ),
            )
    if not config.support_content.full:
        config.support_content.full = list(DEFAULT_SUPPORT_FULL)
    if not config.support_content.tree_only:
        config.support_content.tree_only = list(DEFAULT_SUPPORT_TREE_ONLY)

    hard_ignore = data.get("hard_ignore", {})
    if isinstance(hard_ignore, dict) and isinstance(hard_ignore.get("patterns"), list):
        config.hard_ignore_patterns = [str(item) for item in hard_ignore["patterns"]]

    modules = data.get("modules", {})
    if isinstance(modules, dict):
        scoring = dict(config.modules_config.scoring)
        raw_scoring = modules.get("scoring", {})
        if isinstance(raw_scoring, dict):
            scoring.update({str(key): int(value) for key, value in raw_scoring.items()})
        config.modules_config = ModuleConfig(
            enabled=bool(modules.get("enabled", config.modules_config.enabled)),
            depth=int(modules.get("depth", config.modules_config.depth)),
            include_direct_dependencies=bool(
                modules.get(
                    "include_direct_dependencies",
                    config.modules_config.include_direct_dependencies,
                )
            ),
            include_reverse_dependencies=bool(
                modules.get(
                    "include_reverse_dependencies",
                    config.modules_config.include_reverse_dependencies,
                )
            ),
            include_tests=bool(
                modules.get("include_tests", config.modules_config.include_tests)
            ),
            include_same_package=bool(
                modules.get(
                    "include_same_package", config.modules_config.include_same_package
                )
            ),
            include_parent_entrypoints=bool(
                modules.get(
                    "include_parent_entrypoints",
                    config.modules_config.include_parent_entrypoints,
                )
            ),
            include_project_configs=bool(
                modules.get(
                    "include_project_configs",
                    config.modules_config.include_project_configs,
                )
            ),
            content_min_score=int(
                modules.get(
                    "content_min_score", config.modules_config.content_min_score
                )
            ),
            tree_min_score=int(
                modules.get("tree_min_score", config.modules_config.tree_min_score)
            ),
            scoring=scoring,
        )
        config.modules = config.modules_config.enabled

    python = data.get("python", {})
    if isinstance(python, dict):
        config.python = PythonConfig(
            source_roots=[
                str(item)
                for item in python.get("source_roots", config.python.source_roots)
            ],
            test_roots=[
                str(item) for item in python.get("test_roots", config.python.test_roots)
            ],
            module_init_files=[
                str(item)
                for item in python.get(
                    "module_init_files", config.python.module_init_files
                )
            ],
            entrypoint_patterns=[
                str(item)
                for item in python.get(
                    "entrypoint_patterns", config.python.entrypoint_patterns
                )
            ],
        )

    tokens = data.get("tokens", {})
    if isinstance(tokens, dict):
        config.tokens = TokenConfig(
            estimator=str(tokens.get("estimator", config.tokens.estimator)),
            chars_per_token=int(
                tokens.get("chars_per_token", config.tokens.chars_per_token)
            ),
        )

    cache = data.get("cache", {})
    if isinstance(cache, dict):
        config.cache = CacheConfig(
            enabled=bool(cache.get("enabled", config.cache.enabled)),
            dir=str(cache.get("dir", config.cache.dir)),
        )

    return config


def apply_overrides(
    config: ScriberConfig,
    *,
    output: str | None = None,
    output_format: str | None = None,
    only_tree: bool | None = None,
    modules: bool | None = None,
    support: bool | None = None,
    max_files: int | None = None,
    max_tokens: int | None = None,
    min_score: int | None = None,
    support_content: str | None = None,
) -> ScriberConfig:
    if output is not None:
        config.output = Path(output)
    if output_format is not None:
        config.format = output_format  # type: ignore[assignment]
    if only_tree is not None:
        config.only_tree = only_tree
    if modules is not None:
        config.modules = modules
        config.modules_config.enabled = modules
    if support is not None:
        config.support = support
    if max_files is not None:
        config.max_files = max_files
    if max_tokens is not None:
        config.max_tokens = max_tokens
    if min_score is not None:
        config.min_score = min_score
    if support_content is not None:
        if support_content not in {"full", "auto", "tree_only"}:
            raise ValueError("support_content must be one of: full, auto, tree_only")
        config.support_content.default = support_content  # type: ignore[assignment]
    return config


@dataclass(slots=True)
class ConfigIssue:
    severity: str  # "warning" or "error"
    message: str


def validate_raw_config(raw_data: dict[str, Any]) -> list[ConfigIssue]:
    issues: list[ConfigIssue] = []

    # 1. check if raw_data contains tool.scriber
    tool = raw_data.get("tool", {}) if isinstance(raw_data, dict) else {}
    if not isinstance(tool, dict):
        issues.append(ConfigIssue("error", "[tool] in pyproject.toml must be a table."))
        return issues

    data = tool.get("scriber", {}) if isinstance(tool, dict) else {}
    if not data:
        issues.append(
            ConfigIssue("warning", "[tool.scriber] section is missing or empty.")
        )
        return issues

    if not isinstance(data, dict):
        issues.append(ConfigIssue("error", "[tool.scriber] must be a table."))
        return issues

    # 2. check output format
    if "format" in data and data["format"] not in {"md", "txt"}:
        issues.append(
            ConfigIssue(
                "error", f"Invalid format: '{data['format']}'. Must be 'md' or 'txt'."
            )
        )

    # 4. check support_content default
    support_files = data.get("support_files", {})
    if isinstance(support_files, dict):
        content = support_files.get("content", {})
        if isinstance(content, dict) and "default" in content:
            val = content["default"]
            if val not in {"full", "auto", "tree_only"}:
                issues.append(
                    ConfigIssue(
                        "error",
                        f"Invalid support_files.content.default: '{val}'. Must be 'full', 'auto', or 'tree_only'.",
                    )
                )

    # 5. check numeric values >= 0
    for field in ["max_files", "max_tokens", "min_score"]:
        if field in data:
            try:
                val = int(data[field])
                if val < 0:
                    issues.append(
                        ConfigIssue(
                            "error", f"{field} must be a number >= 0. Got: {val}"
                        )
                    )
            except (ValueError, TypeError):
                issues.append(
                    ConfigIssue(
                        "error", f"{field} must be an integer. Got: {data[field]}"
                    )
                )

    # 6. check patterns are list of strings
    def check_pattern_list(parent_dict: dict[str, Any], path_name: str) -> None:
        if "patterns" in parent_dict:
            patterns = parent_dict["patterns"]
            if not isinstance(patterns, list):
                issues.append(
                    ConfigIssue(
                        "error", f"{path_name}.patterns must be a list of strings."
                    )
                )
            else:
                for item in patterns:
                    if not isinstance(item, str):
                        issues.append(
                            ConfigIssue(
                                "error",
                                f"Pattern in {path_name}.patterns must be a string. Got: {item}",
                            )
                        )

    code_files = data.get("code_files", {})
    if isinstance(code_files, dict):
        check_pattern_list(code_files, "code_files")
    elif "code_files" in data:
        issues.append(ConfigIssue("error", "code_files must be a table."))

    if isinstance(support_files, dict):
        check_pattern_list(support_files, "support_files")

        # Check support_files.content full and tree_only patterns
        content = support_files.get("content", {})
        if isinstance(content, dict):
            for field in ["full", "tree_only"]:
                if field in content:
                    patterns = content[field]
                    if not isinstance(patterns, list):
                        issues.append(
                            ConfigIssue(
                                "error",
                                f"support_files.content.{field} must be a list of strings.",
                            )
                        )
                    else:
                        for item in patterns:
                            if not isinstance(item, str):
                                issues.append(
                                    ConfigIssue(
                                        "error",
                                        f"Pattern in support_files.content.{field} must be a string. Got: {item}",
                                    )
                                )
    elif "support_files" in data:
        issues.append(ConfigIssue("error", "support_files must be a table."))

    hard_ignore = data.get("hard_ignore", {})
    if isinstance(hard_ignore, dict):
        check_pattern_list(hard_ignore, "hard_ignore")
    elif "hard_ignore" in data:
        issues.append(ConfigIssue("error", "hard_ignore must be a table."))

    return issues


def validate_config(
    config: ScriberConfig, raw_data: dict[str, Any], config_path: Path | None = None
) -> list[ConfigIssue]:
    issues = validate_raw_config(raw_data)

    # Check output path is not a directory
    output_path = config.output
    if not output_path.is_absolute() and config_path:
        output_path = config_path.parent / output_path

    if output_path.suffix == "" and not str(output_path).endswith("-"):
        issues.append(
            ConfigIssue(
                "warning",
                f"Output path '{output_path}' has no extension. Is it a directory?",
            )
        )
    if output_path.exists() and output_path.is_dir():
        issues.append(
            ConfigIssue(
                "error", f"Output path '{output_path}' points to an existing directory."
            )
        )

    return issues
