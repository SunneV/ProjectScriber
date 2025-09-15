import fnmatch
import io
import json
import multiprocessing
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, TextIO, Union

try:
    import tomllib
except ImportError:
    import tomli as tomllib

try:
    import pathspec
except ImportError:
    pathspec = None

import tiktoken

from .config import ScriberConfig

DEFAULT_CONFIG = ScriberConfig()


def _process_file_worker(
    file_path: Path,
    containing_root: Path,
    hidden_patterns: Set[str],
    language_map: Dict[str, str],
    tokenizer: Optional[Any],
) -> Dict[str, Any]:
    """Processes a single file to gather stats; safe for multiprocessing.

    This function is defined at the top level to avoid pickling issues with
    instance methods that have un-pickleable attributes (like rich.Console).

    Args:
        file_path: The path of the file to process.
        containing_root: The root directory that contains the file.
        hidden_patterns: A set of patterns for files whose content should be hidden.
        language_map: A dictionary mapping file extensions to languages.
        tokenizer: The tiktoken tokenizer instance.

    Returns:
        A dictionary containing the size, token count, and language of the file.
    """
    stats: Dict[str, Any] = {"size": 0, "tokens": 0, "lang": "other"}
    try:
        stats["size"] = file_path.stat().st_size
        stats["lang"] = language_map.get(file_path.suffix, language_map.get(file_path.name, "")) or "other"

        is_hidden = False
        if hidden_patterns:
            relative_path_str = file_path.relative_to(containing_root).as_posix()
            if any(fnmatch.fnmatch(relative_path_str, pattern) for pattern in hidden_patterns):
                is_hidden = True

        if not is_hidden and tokenizer:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            stats["tokens"] = len(tokenizer.encode(content))
    except Exception:
        pass
    return stats


class Scriber:
    """
    Maps, analyzes, and compiles a project's source code into a single output.

    This class can be used programmatically to gain fine-grained control over the
    project mapping process, access intermediate data like file lists and
    statistics, and get the final output as a string for further processing.
    """
    _CONFIG_FILE_NAME = ".scriber.json"
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

    def __init__(
        self,
        root_path: Union[Path, List[Path]],
        config: Optional[Union[Dict[str, Any], ScriberConfig]] = None,
        config_path: Optional[Path] = None
    ):
        """Initializes the Scriber instance.

        Args:
            root_path: An absolute path or a list of absolute paths to the root
                directories of the project(s) to be mapped.
            config: An optional dictionary or ScriberConfig object of settings.
                Takes the highest precedence if provided.
            config_path: An optional path to a specific configuration file.
        """
        raw_paths = [root_path] if isinstance(root_path, Path) else root_path
        self.root_paths: List[Path] = [p.resolve() for p in raw_paths]
        self.primary_root: Path = self.root_paths[0]

        self.mapped_files: List[Path] = []
        self._user_config_path = config_path
        self._user_config_input = config
        self.config: ScriberConfig = ScriberConfig()
        self.config_path_used: Optional[Path] = None
        self.gitignore_spec: Optional[Any] = None
        self.dir_exclude_spec: Optional[Any] = None
        self.general_exclude_spec: Optional[Any] = None
        self.hidden_patterns: Set[str] = set()
        self.include_patterns: List[str] = []
        self.exclude_patterns: List[str] = []
        self.exclude_map: Dict[str, List[str]] = {}
        self.single_process: bool = False

        self.stats = {}
        self._has_mapped = False
        self._reset_stats()
        self._load_config()
        try:
            self._tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self._tokenizer = None

    def _reset_stats(self):
        """Resets the statistics and mapped files to their initial state."""
        self.mapped_files = []
        self.stats = {
            "total_files": 0,
            "total_size_bytes": 0,
            "total_tokens": 0,
            "language_counts": Counter(),
            "skipped_binary": 0,
        }
        self._has_mapped = False

    def _create_default_config_file(self) -> None:
        """Creates a default .scriber.json config file if no other config is found."""
        config_path = self.primary_root / self._CONFIG_FILE_NAME
        print(f"✨ No config found. Creating default configuration at: {config_path}", file=sys.stderr)

        file_config = {
            "use_gitignore": DEFAULT_CONFIG.use_gitignore,
            "exclude": DEFAULT_CONFIG.exclude,
            "include": DEFAULT_CONFIG.include,
            "hidden": DEFAULT_CONFIG.hidden
        }
        try:
            with config_path.open("w", encoding="utf-8") as f:
                json.dump(file_config, f, indent=2)
        except IOError as e:
            print(f"❌ Could not create default config file: {e}", file=sys.stderr)

    def _load_config(self) -> None:
        """Loads configuration with a clear precedence: direct config > config_path > local files."""
        config_data = DEFAULT_CONFIG.to_dict()
        config_source_loaded = False

        if self._user_config_input:
            if isinstance(self._user_config_input, ScriberConfig):
                config_data.update(self._user_config_input.to_dict())
            else:
                config_data.update(self._user_config_input)
            config_source_loaded = True
            self.config_path_used = None
        else:
            config_path_to_use = self._user_config_path
            if config_path_to_use:
                if not config_path_to_use.is_file():
                    print(f"Warning: Config file specified by --config not found at {self._user_config_path}", file=sys.stderr)
                    config_path_to_use = None
            else:
                json_path = self.primary_root / self._CONFIG_FILE_NAME
                toml_path = self.primary_root / "pyproject.toml"
                if json_path.is_file():
                    config_path_to_use = json_path
                elif toml_path.is_file():
                    config_path_to_use = toml_path

            if config_path_to_use:
                self.config_path_used = config_path_to_use
                try:
                    if config_path_to_use.suffix == ".toml":
                        with config_path_to_use.open("rb") as f:
                            toml_data = tomllib.load(f)
                            if "tool" in toml_data and "scriber" in toml_data["tool"]:
                                config_data.update(toml_data["tool"]["scriber"])
                                config_source_loaded = True
                    else:
                        with config_path_to_use.open("r", encoding="utf-8") as f:
                            config_data.update(json.load(f))
                            config_source_loaded = True
                except (json.JSONDecodeError, tomllib.TOMLDecodeError, IOError) as e:
                    print(f"Error parsing config file {self.config_path_used}: {e}", file=sys.stderr)

        if not config_source_loaded and not self._user_config_input and self._user_config_path is None:
            self._create_default_config_file()

        self.config = ScriberConfig(**config_data)
        self.include_patterns = self.config.include
        self.exclude_patterns = self.config.exclude
        self.hidden_patterns = set(self.config.hidden)
        self.exclude_map = self.config.exclude_map
        self.single_process = self.config.single_process

        if not pathspec:
            print("Warning: 'pathspec' not installed. .gitignore and advanced exclude patterns will be ignored.", file=sys.stderr)
        else:
            dir_exclude_patterns = [p for p in self.exclude_patterns if p.endswith('/')]
            general_exclude_patterns = [p for p in self.exclude_patterns if not p.endswith('/')]

            self.dir_exclude_spec = pathspec.PathSpec.from_lines("gitwildmatch", dir_exclude_patterns)
            self.general_exclude_spec = pathspec.PathSpec.from_lines("gitwildmatch", general_exclude_patterns)
            self._load_gitignore(self.config.use_gitignore)

    def _load_gitignore(self, use_gitignore: bool) -> None:
        """Loads gitignore patterns from the .gitignore file if enabled.

        Args:
            use_gitignore: A boolean indicating whether to use .gitignore rules.
        """
        self.gitignore_spec: Optional[pathspec.PathSpec] = None
        if not use_gitignore or not pathspec:
            return

        gitignore_path = self.primary_root / ".gitignore"
        if gitignore_path.is_file():
            try:
                with gitignore_path.open("r", encoding="utf-8") as f:
                    self.gitignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", f)
            except IOError:
                pass

    def _find_containing_root(self, path: Path) -> Optional[Path]:
        """Finds which root directory from self.root_paths contains the given path.

        Args:
            path: The path to check.

        Returns:
            The containing root path, or None if not found.
        """
        for r in self.root_paths:
            try:
                if path.is_relative_to(r):
                    return r
            except ValueError:
                continue
        return None

    def _is_binary(self, path: Path) -> bool:
        """Checks if a file is likely a binary file.

        Args:
            path: The path to the file.

        Returns:
            True if the file contains null bytes, False otherwise.
        """
        try:
            with path.open('rb') as f:
                return b'\0' in f.read(1024)
        except IOError:
            return True

    def _is_excluded(self, path: Path) -> bool:
        """Determines if a file or directory should be excluded from mapping.

        Args:
            path: The path to check.

        Returns:
            True if the path should be excluded, False otherwise.
        """
        containing_root = self._find_containing_root(path)
        if not containing_root:
            return True

        # When checking a directory for pruning, its path might not have a trailing
        # slash, so we treat it as such for matching.
        is_dir = path.is_dir()

        if self.gitignore_spec:
            try:
                relative_path_for_gitignore = path.relative_to(self.primary_root).as_posix()
                if is_dir and not relative_path_for_gitignore.endswith('/'):
                    relative_path_for_gitignore += '/'
                if self.gitignore_spec.match_file(relative_path_for_gitignore):
                    return True
            except ValueError:
                pass

        relative_path_str = path.relative_to(containing_root).as_posix()

        if is_dir:
            path_for_dir_spec = relative_path_str + '/'
            if self.dir_exclude_spec and self.dir_exclude_spec.match_file(path_for_dir_spec):
                return True
            if self.general_exclude_spec and self.general_exclude_spec.match_file(relative_path_str):
                return True
        else:  # Is a file
            if self.general_exclude_spec and self.general_exclude_spec.match_file(relative_path_str):
                return True

        if path.is_file():
            global_patterns = self.exclude_map.get("global", [])
            if any(fnmatch.fnmatch(relative_path_str, pattern) for pattern in global_patterns):
                return True

            lang = self._get_language(path)
            if lang and lang in self.exclude_map:
                lang_patterns = self.exclude_map.get(lang, [])
                if any(fnmatch.fnmatch(relative_path_str, pattern) for pattern in lang_patterns):
                    return True

            if self.include_patterns:
                return not any(fnmatch.fnmatch(relative_path_str, pattern) for pattern in self.include_patterns)

        return False

    def _is_hidden(self, path: Path) -> bool:
        """Checks if a path matches any of the hidden patterns.

        Args:
            path: The path to check.

        Returns:
            True if the path matches a hidden pattern, False otherwise.
        """
        if not self.hidden_patterns:
            return False
        containing_root = self._find_containing_root(path)
        if not containing_root:
            return False
        relative_path_str = path.relative_to(containing_root).as_posix()
        return any(fnmatch.fnmatch(relative_path_str, pattern) for pattern in self.hidden_patterns)

    def _collect_files(self, perform_binary_check: bool = True) -> None:
        """Walks the project directory and collects all non-excluded files.

        Args:
            perform_binary_check: If False, skips the check for binary files.
        """
        collected = set()
        for root_dir in self.root_paths:
            for root, dirs, files in os.walk(root_dir, topdown=True):
                current_root = Path(root)
                dirs[:] = [d for d in dirs if not self._is_excluded(current_root / d)]
                for file in files:
                    file_path = current_root / file
                    if not self._is_excluded(file_path):
                        if perform_binary_check and self._is_binary(file_path):
                            self.stats['skipped_binary'] += 1
                            continue
                        collected.add(file_path)
        self.mapped_files = sorted(list(collected))

    def map_project(self) -> None:
        """Maps all relevant project files and gathers statistics."""
        self._reset_stats()
        self._collect_files(perform_binary_check=True)
        self._gather_stats()
        self._has_mapped = True

    def map_tree_only(self) -> None:
        """Maps only the project file structure without reading file contents."""
        self._reset_stats()
        self._collect_files(perform_binary_check=False)
        self.stats['total_files'] = len(self.mapped_files)
        self._has_mapped = True

    def _gather_stats(self) -> None:
        """Gathers statistics about the mapped files."""
        if not self.mapped_files:
            return

        self.stats['total_files'] = len(self.mapped_files)
        total_size = 0
        total_tokens = 0
        language_counts: Counter = Counter()

        if self.single_process:
            for path in self.mapped_files:
                containing_root = self._find_containing_root(path)
                if containing_root:
                    try:
                        file_stats = _process_file_worker(
                            path, containing_root, self.hidden_patterns, self._LANGUAGE_MAP, self._tokenizer
                        )
                        total_size += file_stats["size"]
                        total_tokens += file_stats["tokens"]
                        language_counts[file_stats["lang"]] += 1
                    except Exception as exc:
                        print(f"File processing generated an exception: {exc}", file=sys.stderr)
        else:
            context = multiprocessing.get_context("spawn")
            with ProcessPoolExecutor(mp_context=context) as executor:
                futures = []
                for path in self.mapped_files:
                    containing_root = self._find_containing_root(path)
                    if containing_root:
                        futures.append(executor.submit(
                            _process_file_worker,
                            path,
                            containing_root,
                            self.hidden_patterns,
                            self._LANGUAGE_MAP,
                            self._tokenizer,
                        ))

                for future in as_completed(futures):
                    try:
                        file_stats = future.result()
                        total_size += file_stats["size"]
                        total_tokens += file_stats["tokens"]
                        language_counts[file_stats["lang"]] += 1
                    except Exception as exc:
                        print(f"File processing generated an exception: {exc}", file=sys.stderr)

        self.stats['total_size_bytes'] = total_size
        self.stats['total_tokens'] = total_tokens
        self.stats['language_counts'] = language_counts

    def get_stats(self) -> Dict:
        """Returns the collected project statistics.

        If the project has not been mapped yet, `map_project()` will be called first.

        Returns:
            A dictionary containing project statistics.
        """
        if not self._has_mapped:
            self.map_project()
        return self.stats

    def get_file_count(self) -> int:
        """Returns the number of files that will be mapped.

        If the project has not been mapped yet, `map_project()` will be called first.

        Returns:
            The total count of mapped files.
        """
        if not self._has_mapped:
            self.map_project()
        return len(self.mapped_files)

    def get_mapped_files(self) -> List[Path]:
        """Returns a list of all mapped file paths.

        If the project has not been mapped yet, `map_project()` will be called first.

        Returns:
            A sorted list of `pathlib.Path` objects for all included files.
        """
        if not self._has_mapped:
            self.map_project()
        return self.mapped_files

    def get_tree(self) -> str:
        """Returns the formatted file tree representation as a string.

        If the project has not been mapped yet, `map_project()` will be called first.

        Returns:
            A string containing the formatted file tree.
        """
        if not self._has_mapped:
            self.map_project()
        return self._get_tree_representation()

    def get_output_as_string(self, tree_only: bool = False, progress=None, task_id=None) -> str:
        """Generates the consolidated project output and returns it as a string.

        If the project has not been mapped yet, `map_project()` will be called first.

        Args:
            tree_only: If True, the string will only contain the file tree.
            progress: An optional Rich Progress instance for updating a progress bar.
            task_id: An optional ID for the task in the Rich Progress instance.

        Returns:
            A string containing the complete project map and file contents.
        """
        if not self._has_mapped:
            if tree_only:
                self.map_tree_only()
            else:
                self.map_project()
        output_buffer = io.StringIO()
        self._write_output(output_buffer, tree_only, progress=progress, task_id=task_id)
        return output_buffer.getvalue()

    def generate_output_file(self, output_filename: str, tree_only: bool = False, progress=None, task_id=None) -> None:
        """Generates the consolidated project structure output file.

        Args:
            output_filename: The name for the output file.
            tree_only: If True, only the file tree is written.
            progress: A Rich Progress instance for updating the progress bar.
            task_id: The ID of the task in the Rich Progress instance.
        """
        if not self._has_mapped:
            if tree_only:
                self.map_tree_only()
            else:
                self.map_project()
        output_filepath = self.primary_root / output_filename
        with output_filepath.open("w", encoding="utf-8") as f:
            self._write_output(f, tree_only, progress, task_id)

    def _write_output(self, f: TextIO, tree_only: bool, progress, task_id) -> None:
        """Writes the complete project map and file contents to an open file stream.

        Args:
            f: The file stream to write to.
            tree_only: If True, only write the file tree.
            progress: A Rich Progress instance for updating the progress bar.
            task_id: The ID of the task in the Rich Progress instance.
        """
        f.write("=" * 3 + "\n Mapped Folder Structure\n" + "=" * 3 + "\n\n")
        f.write(self._get_tree_representation() + "\n")

        if tree_only:
            return

        for file_path in self.mapped_files:
            if self._is_hidden(file_path):
                self._write_hidden_file_placeholder(f, file_path)
            else:
                self._write_file_content(f, file_path)
            if progress and task_id is not None:
                progress.update(task_id, advance=1)

    def _get_display_path(self, file_path: Path) -> str:
        """Gets the path to display in the output header.

        Args:
            file_path: The absolute path to the file.

        Returns:
            A string representing the path for display.
        """
        containing_root = self._find_containing_root(file_path)
        if not containing_root:
            return file_path.name

        relative_path = file_path.relative_to(containing_root)
        if len(self.root_paths) > 1:
            return (Path(containing_root.name) / relative_path).as_posix()
        return relative_path.as_posix()

    def _write_hidden_file_placeholder(self, f: TextIO, file_path: Path) -> None:
        """Writes a placeholder for a hidden file's content.

        Args:
            f: The file stream to write to.
            file_path: The path of the hidden file.
        """
        try:
            display_path = self._get_display_path(file_path)
            file_size = file_path.stat().st_size
        except (OSError, ValueError):
            return

        f.write("\n" + "-" * 3 + "\n")
        f.write(f"File: {display_path}\nSize: {file_size} bytes\n" + "-" * 3 + "\n")
        f.write("```\n[Content hidden based on configuration]\n```\n")

    def _write_file_content(self, f: TextIO, file_path: Path) -> None:
        """Writes a single file's content to the output stream.

        Args:
            f: The file stream to write to.
            file_path: The path of the file to write.
        """
        try:
            display_path = self._get_display_path(file_path)
            file_size = file_path.stat().st_size
            lang = self._get_language(file_path)
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, ValueError):
            return

        f.write("\n" + "-" * 3 + "\n")
        f.write(f"File: {display_path}\nSize: {file_size} bytes\n" + "-" * 3 + "\n")
        f.write(f"```{lang}\n{content}\n```\n")

    def _get_language(self, file_path: Path) -> str:
        """Determines the programming language of a file based on its extension.

        Args:
            file_path: The path to the file.

        Returns:
            A string representing the language, or an empty string if not found.
        """
        return self._LANGUAGE_MAP.get(file_path.suffix, self._LANGUAGE_MAP.get(file_path.name, ""))

    def _get_tree_representation(self) -> str:
        """Generates a string representation of the project's file tree.

        Returns:
            A formatted string of the file tree.
        """
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

        if len(self.root_paths) == 1:
            root_name = list(tree.keys())[0]
            output_lines = [root_name]
            output_lines.extend(format_tree(tree[root_name]))
        else:
            output_lines = []
            for root_name, subtree in sorted(tree.items()):
                output_lines.append(root_name)
                output_lines.extend(format_tree(subtree))
        return "\n".join(output_lines)

    def _build_file_tree(self) -> Dict[str, Any]:
        """Builds a nested dictionary representing the file tree structure.

        Returns:
            A dictionary representing the project's file hierarchy.
        """
        if not self.mapped_files: return {}

        if len(self.root_paths) == 1:
            tree = {self.primary_root.name: {}}
            project_level = tree[self.primary_root.name]
            for path in self.mapped_files:
                parts = path.relative_to(self.primary_root).parts
                current_level = project_level
                for part in parts:
                    current_level = current_level.setdefault(part, {})
            return tree
        else:
            tree = {}
            for path in self.mapped_files:
                containing_root = self._find_containing_root(path)
                if not containing_root:
                    continue

                root_name = containing_root.name
                if root_name not in tree:
                    tree[root_name] = {}

                parts = path.relative_to(containing_root).parts
                current_level = tree[root_name]
                for part in parts:
                    current_level = current_level.setdefault(part, {})
            return tree