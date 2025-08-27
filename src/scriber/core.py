import fnmatch
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, TextIO

try:
    import tomllib
except ImportError:
    import tomli as tomllib

import tiktoken
from rich.console import Console

_DEFAULT_OUTPUT_FILENAME = "scriber_output.txt"
_CONFIG_FILE_NAME = ".scriber.json"
DEFAULT_CONFIG = {
    "use_gitignore": True,
    "exclude": [
        # Common
        "LICENSE"
        
        # Version Control
        ".git",

        # IDE / Editor Config
        ".idea", ".vscode", ".project", ".settings", ".classpath",

        # Python
        "__pycache__", "*.pyc", ".venv", "venv", ".pytest_cache", "uv.lock",

        # Node.js
        "node_modules", "npm-debug.log*", "yarn-error.log",

        # Build Artifacts
        "build", "dist", "target", "bin", "obj", "out",

        # Dependencies
        "vendor", "bower_components",

        # Logs & Temp Files
        "*.log", "*.lock", "*.tmp", "temp", "tmp",

        # OS-specific
        ".DS_Store", "Thumbs.db", "*~", "*.swp", "*.swo",

        # Scriber's own files
        _DEFAULT_OUTPUT_FILENAME, _CONFIG_FILE_NAME
    ],
    "include": [],
    "output": _DEFAULT_OUTPUT_FILENAME,
}


class Scriber:
    _CONFIG_FILE_NAME = _CONFIG_FILE_NAME
    _LANGUAGE_MAP = {
        ".asm": "asm", ".s": "asm", ".html": "html", ".htm": "html", ".css": "css",
        ".scss": "scss", ".sass": "sass", ".less": "less", ".js": "javascript",
        ".mjs": "javascript", ".cjs": "javascript", ".jsx": "jsx", ".ts": "typescript",
        ".tsx": "tsx", ".vue": "vue", ".svelte": "svelte", ".py": "python", ".pyw": "python",
        ".rb": "ruby", ".java": "java", ".kt": "kotlin", ".kts": "kotlin", ".scala": "scala",
        ".go": "go", ".php": "php", ".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp",
        ".cs": "csharp", ".rs": "rust", ".swift": "swift", ".dart": "dart", ".pl": "perl",
        ".pm": "perl", ".hs": "haskell", ".lua": "lua", ".erl": "erlang", ".ex": "elixir",
        ".exs": "elixir", ".clj": "clojure", ".lisp": "lisp", ".f": "fortran",
        ".f90": "fortran", ".zig": "zig", ".d": "d", ".v": "v", ".cr": "crystal",
        ".nim": "nim", ".pas": "pascal", ".ml": "ocaml", ".sh": "bash", ".bash": "bash",
        ".zsh": "zsh", ".fish": "fish", ".ps1": "powershell", ".bat": "batch",
        ".json": "json", ".jsonc": "jsonc", ".xml": "xml", ".yaml": "yaml", ".yml": "yaml",
        ".toml": "toml", ".ini": "ini", ".properties": "properties", ".env": "dotenv",
        "Dockerfile": "dockerfile", ".tf": "terraform", ".hcl": "hcl", ".groovy": "groovy",
        ".gradle": "groovy", ".cmake": "cmake", "CMakeLists.txt": "cmake", ".md": "markdown",
        ".mdx": "mdx", ".rst": "rst", ".tex": "latex", "LICENSE": "text", ".sql": "sql",
        ".graphql": "graphql", ".proto": "protobuf", ".glsl": "glsl", ".frag": "glsl",
        ".vert": "glsl", ".vb": "vbnet", ".vbs": "vbscript",
    }

    def __init__(self, root_path: Path, config_path: Optional[Path] = None):
        self.root_path = root_path.resolve()
        self.mapped_files: List[Path] = []
        self._user_config_path = config_path
        self._console = Console(stderr=True, style="bold red")
        self.config: Dict[str, Any] = {}
        self.config_path_used: Optional[Path] = None
        self.gitignore_spec: Optional[Any] = None

        self.stats = {
            "total_files": 0,
            "total_size_bytes": 0,
            "total_tokens": 0,
            "language_counts": Counter(),
            "skipped_binary": 0,
        }

        self._load_config()
        try:
            self._tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self._tokenizer = None

    def _create_default_config_file(self) -> None:
        """Creates a default .scriber.json config file if no other config is found."""
        config_path = self.root_path / self._CONFIG_FILE_NAME
        self._console.print(f"✨ [yellow]No config found. Creating default configuration at:[/] {config_path}")

        file_config = {
            "use_gitignore": DEFAULT_CONFIG.get("use_gitignore", True),
            "exclude": DEFAULT_CONFIG.get("exclude", []),
            "include": DEFAULT_CONFIG.get("include", [])
        }
        try:
            with config_path.open("w", encoding="utf-8") as f:
                json.dump(file_config, f, indent=2)
        except IOError as e:
            self._console.print(f"❌ [bold red]Could not create default config file:[/] {e}")

    def _load_config(self) -> None:
        config = DEFAULT_CONFIG.copy()
        toml_config_found = False
        toml_path = self.root_path / "pyproject.toml"

        if toml_path.is_file():
            try:
                with toml_path.open("rb") as f:
                    toml_data = tomllib.load(f)
                    if "tool" in toml_data and "scriber" in toml_data["tool"]:
                        config.update(toml_data["tool"]["scriber"])
                        toml_config_found = True
            except tomllib.TOMLDecodeError:
                self._console.print(f"Warning: Invalid pyproject.toml format in {toml_path}")

        config_path_to_use = self._user_config_path or (self.root_path / self._CONFIG_FILE_NAME)

        if not toml_config_found and not config_path_to_use.is_file() and not self._user_config_path:
            self._create_default_config_file()

        if config_path_to_use.is_file():
            self.config_path_used = config_path_to_use
            try:
                with config_path_to_use.open("r", encoding="utf-8") as f:
                    config.update(json.load(f))
            except json.JSONDecodeError as e:
                self._console.print(f"Error: Invalid JSON in {config_path_to_use}. Details: {e}")
            except IOError:
                pass

        self.config = config
        self.include_patterns: List[str] = self.config.get("include", [])
        self.exclude_patterns: Set[str] = set(self.config.get("exclude", []))
        self._load_gitignore(self.config.get("use_gitignore", True))

    def _load_gitignore(self, use_gitignore: bool) -> None:
        try:
            import pathspec
        except ImportError:
            self._console.print("Warning: 'pathspec' not installed. .gitignore files will be ignored.")
            self.gitignore_spec = None
            return

        self.gitignore_spec: Optional[pathspec.PathSpec] = None
        if not use_gitignore: return
        gitignore_path = self.root_path / ".gitignore"
        if gitignore_path.is_file():
            try:
                with gitignore_path.open("r", encoding="utf-8") as f:
                    self.gitignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", f)
            except IOError:
                pass

    def _is_binary(self, path: Path) -> bool:
        try:
            with path.open('rb') as f:
                return b'\0' in f.read(1024)
        except IOError:
            return True

    def _is_excluded(self, path: Path) -> bool:
        try:
            relative_path = path.relative_to(self.root_path)
            check_set = set(relative_path.parts)
        except ValueError:
            return True

        if not self.exclude_patterns.isdisjoint(check_set): return True

        relative_path_str = relative_path.as_posix()
        if self.gitignore_spec and self.gitignore_spec.match_file(relative_path_str): return True
        if any(fnmatch.fnmatch(part, pattern) for pattern in self.exclude_patterns for part in check_set): return True
        if path.is_file() and self.include_patterns:
            return not any(fnmatch.fnmatch(relative_path_str, pattern) for pattern in self.include_patterns)
        return False

    def _collect_files(self) -> None:
        collected = set()
        for root, dirs, files in os.walk(self.root_path, topdown=True):
            current_root = Path(root)
            dirs[:] = [d for d in dirs if not self._is_excluded(current_root / d)]
            for file in files:
                file_path = current_root / file
                if not self._is_excluded(file_path):
                    if self._is_binary(file_path):
                        self.stats['skipped_binary'] += 1
                        continue
                    collected.add(file_path)
        self.mapped_files = sorted(list(collected))

    def map_project(self) -> None:
        """Maps all relevant project files and gathers statistics."""
        self._collect_files()
        self._gather_stats()

    def _gather_stats(self) -> None:
        if not self.mapped_files: return

        self.stats['total_files'] = len(self.mapped_files)
        total_size = 0
        total_tokens = 0

        for file_path in self.mapped_files:
            total_size += file_path.stat().st_size
            lang = self._get_language(file_path) or "other"
            self.stats['language_counts'][lang] += 1
            if self._tokenizer:
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    total_tokens += len(self._tokenizer.encode(content))
                except Exception:
                    pass

        self.stats['total_size_bytes'] = total_size
        self.stats['total_tokens'] = total_tokens

    def get_stats(self) -> Dict:
        """Returns the raw project statistics."""
        return self.stats

    def get_file_count(self) -> int:
        """Returns the number of files that will be mapped."""
        return len(self.mapped_files)

    def generate_output_file(self, output_filename: str, tree_only: bool = False, progress=None, task_id=None) -> None:
        """Generates the consolidated project structure output file."""
        output_filepath = self.root_path / output_filename
        with output_filepath.open("w", encoding="utf-8") as f:
            self._write_output(f, tree_only, progress, task_id)

    def _write_output(self, f: TextIO, tree_only: bool, progress, task_id) -> None:
        f.write("=" * 3 + "\n Mapped Folder Structure\n" + "=" * 3 + "\n\n")
        f.write(self._get_tree_representation() + "\n")

        if tree_only: return

        for file_path in self.mapped_files:
            self._write_file_content(f, file_path)
            if progress and task_id is not None:
                progress.update(task_id, advance=1)

    def _write_file_content(self, f: TextIO, file_path: Path) -> None:
        try:
            relative_path = file_path.relative_to(self.root_path).as_posix()
            file_size = file_path.stat().st_size
            lang = self._get_language(file_path)
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, ValueError):
            return

        f.write("\n" + "-" * 3 + "\n")
        f.write(f"File: {relative_path}\nSize: {file_size} bytes\n" + "-" * 3 + "\n")
        f.write(f"```{lang}\n{content}\n```\n")

    def _get_language(self, file_path: Path) -> str:
        return self._LANGUAGE_MAP.get(file_path.suffix, self._LANGUAGE_MAP.get(file_path.name, ""))

    def _get_tree_representation(self) -> str:
        tree = self._build_file_tree()
        if not tree: return "No files or folders to map."

        def format_tree(d: Dict, prefix: str = "") -> List[str]:
            lines = []
            items = sorted(d.keys())
            for i, key in enumerate(items):
                is_last = i == len(items) - 1
                connector = "└── " if is_last else "├── "
                lines.append(f"{prefix}{connector}{key}")
                if d[key]:
                    new_prefix = prefix + ("    " if is_last else "│   ")
                    lines.extend(format_tree(d[key], new_prefix))
            return lines

        root_name = list(tree.keys())[0]
        output_lines = [root_name]
        output_lines.extend(format_tree(tree[root_name]))
        return "\n".join(output_lines)

    def _build_file_tree(self) -> Dict[str, Any]:
        if not self.mapped_files: return {}
        tree = {self.root_path.name: {}}
        project_level = tree[self.root_path.name]
        for path in self.mapped_files:
            parts = path.relative_to(self.root_path).parts
            current_level = project_level
            for part in parts:
                current_level = current_level.setdefault(part, {})
        return tree