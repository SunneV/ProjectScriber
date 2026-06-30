# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [2.2.0] - 2026-06-30

A major upgrade driven by three rounds of code audit. Adds an interactive dependency-graph visualization, real graph algorithms, a parallel native scanner, three opt-in build-time features (BPE tokenizer, tree-sitter AST, graph snapshot), and numerous correctness/performance fixes. All new Cargo features are **off by default** and degrade gracefully when absent.

### Added
- **Interactive dependency-graph visualization**: `render_graph_html()` produces a self-contained, dependency-free HTML file with a Canvas force-directed layout. Auto-emitted to `.scriber/graph.html` next to every pack (`emit_graph_html = true`, suppress with `--no-graph-html`). Features: per-component gravity (uncorrelated languages form separate islands), radial/hierarchical init from dependency depth, hub emphasis, weight/confidence-aware springs, minimap, search, inertial pan, keyboard nav, hover tooltips, in-pack highlighting, and embedded Scriber branding.
- **Graph export formats**: `--graph-dot` (Graphviz), `--graph-mermaid` (GitHub/Notion native), `--graph-html`, alongside the existing `--graph-json`. All render every relation kind, not just imports.
- **Graph algorithms** (`engine/graph_algorithms.py`): Tarjan SCC for import-cycle detection, Kahn topological layering, weighted-degree centrality, and PageRank. Wired into `--explain-graph` (cycles, top hubs, top influential, architectural layers) and the ranker (centrality bonus).
- **Symbol-level relations** (`type_reference`, `inherits`): emitted by the Python AST symbol extractor on the Python builder path, and by tree-sitter on the native path (when the `treesitter` feature is enabled).
- **Java import extraction**: `parse_java_imports` / `resolve_java_import` resolve `com.example.Foo` to `src/main/java`/`src/test/java`.
- **BPE tokenizer** (Cargo feature `bpe`): exact offline token counting via `tiktoken-rs` (cl100k_base / o200k_base). `TokenConfig.encoding` selects the encoding; `has_bpe_tokenizer()` probes availability; falls back to the calibrated estimator when absent.
- **tree-sitter AST backend** (Cargo feature `treesitter`): walks the Python AST to emit `type_reference`/`inherits` edges on the native path where they were previously dead. Pluggable per-grammar.
- **Graph snapshot + restore** (`graph/snapshot.py`): persists the whole RelationGraph to `.scriber/cache/graph.json`, restored on the next run when no file changed. Closes the native "write-only" cache defect.
- **Configurable cache LRU** (`cache.max_entries`, default 50 000, `0` = unlimited): replaces the hard 1000-entry cap.
- **Real budget enforcement**: every content mode consumes the budget with calibrated weights (`MODE_TOKEN_WEIGHT`); allocator respects a true `hard_limit`.
- **LLM profiles in CLI**: `gpt`, `focused-gpt`, `full` exposed in `--profile` choices.
- **Calibrated token estimation**: `estimator="auto"` selects a per-language chars-per-token ratio instead of flat `len//4`.
- **JS/TS bare-specifier alias resolution**: reads `tsconfig.json` paths + `package.json` imports/exports.
- **Collapse fix**: the native `build_relation_graph` now preserves the real per-language edge kind (import / mod / use / include) instead of hardcoding `"import"`.
- **Parallel native directory walk** + **parallel analyzers**: `WalkBuilder::build_parallel()` and `ThreadPoolExecutor`.
- **Binary detection fast-path + cache**: known extensions skip the read syscall.

### Changed
- `max_files`/`max_tokens` defaults aligned with the loader (`0` = unlimited).
- Token estimation unified: the ranker uses the shared `estimate_tokens_from_bytes()` helper.
- Config-refs/docs analyzers match basenames on word boundaries (no more `api.py`-in-`rapid` false positives).
- Robust project-root detection via `os.path.commonpath` fallback.
- Memoized glob matching via `lru_cache`.
- Real centrality replaces the `centrality_bonus = 0` placeholder.
- Redundant scoring pass skipped for `gpt`/`focused-gpt`/`full` profiles.
- `render_graph_html()` serializes edge `confidence`; springs use `linkStrength = base × confidence`.

### Fixed
- Cache load/write errors logged instead of silently swallowed.
- Bare `except: pass` in analyzers replaced with logged warnings.
- `RelationGraph.add_edge` deduplicates by `(source, target, kind)`.
- Minimap viewport rect computed from the main canvas dimensions (not the minimap's own).
- `__TITLE__` placeholder rendering (case mismatch fixed).

### Removed
- Unused `_walk_neighbors` (scorer), `relations_v1.jsonl` path, dead `BudgetPolicy` ratio fields, dead `GraphNode` class, dead `"react"` language case.
- graph.html single global center force (root cause of uncorrelated components collapsing).


## [2.1.0] - 2026-05-31

### Added
- **Frontend Graph Tracking**: Added dependency parsing support for modern frontend frameworks (`.vue`, `.svelte`, `.astro`), HTML templates, and CSS stylesheets within JS/TS graph construction.
- **Packaging Profiles (`--profile`)**: Added `default`, `audit`, `debug`, `refactor`, and `docs` profiles to quickly bias the file scoring and inclusion criteria without manually tweaking config options.
- **CLI Introspection**: Added `--explain` flag as an alias. Enhanced `--why` output to show estimated token cost, content mode, and omission reasons for any target file.
- **Automated README Sync**: Added `scripts/sync_readme.py` tool to automatically sync CLI arguments, profiles documentation, and version tags across the `README.md`.
- **AI-Native Navigation & Optimization**: Implemented XML anchors for symbols, aggressive test file quarantine, and support file pruning to keep focused mode clean and strictly token-capped.
- **Dependency Limiting**: Introduced `top_dependencies` (defaulting to 10) in the configuration to limit the width of the graph traversal and pull in only the highest-confidence dependencies per file.
- **Version Alignment**: Synchronized Python and Rust crate versions. `scriber --version` now reports both Python and native API versions.

### Fixed
- **Cache Stability**: Fixed graph warm-cache edge generation and stale import cache validation (now strictly validating `mtime` and `size`).
- **Resilience & Scanners**: Added pure-Python fallback for `read_text_lossy`, optimized scanner ordering (whitelist before binary check), and corrected the test role classifier to prevent false positives on files naturally named `tests.py`.
- **Excerpt Fallback Bug**: Fixed rendering and token estimations for empty excerpt files; they now correctly fall back to outline AST structures or full content if budget allows.

## [2.0.0] - 2026-05-30

### Added
- **Native Rust Acceleration (`scriber._native`)**: Full transition of filesystem scanning, high-performance file reading/writing, and binary classification to a compiled Rust extension built using Maturin and PyO3.
- **Fast Parallel Scanner**: Re-engineered directory scanning utilizing the `WalkBuilder` from the `ignore` crate, fully respecting `.gitignore` rules with blazing fast native execution.
- **Rigorous Verification & Equivalence Testing**: Comprehensive suite of regression and equivalence tests validating 100% exact matching behavior between Rust and Python scanner modules.
- **Multi-Platform Binary Wheels**: CI/CD integration using `PyO3/maturin-action` to compile and distribute native wheels across Linux, macOS, and Windows.


## [1.1.2] - 2025-09-30

### Fixed
- Resolved a `UnicodeEncodeError` that occurred on legacy Windows terminals. The CLI now detects incompatible consoles and disables emoji characters in the output to prevent crashes, ensuring compatibility.

## [1.1.1] - 2025-09-15

### Added
- A `--single-process` flag and `single_process` configuration option to run file analysis in a single thread, ensuring compatibility with environments like Celery that restrict child process creation.
- A `--copy-only` flag to generate the project map and copy it directly to the clipboard without creating an output file.

### Changed
- Refactored the internal configuration management from a dictionary to a `dataclass` (`ScriberConfig`). This improves type safety, code readability, and makes programmatic configuration more intuitive and less error-prone.
- Enhanced the `exclude` configuration option to support `.gitignore`-style pattern matching. This allows for more precise rules, such as matching directories only (e.g., `build/`) or root-level files (e.g., `/config.yaml`).

## [1.1.0] - 2025-09-15

### Added
- A comprehensive developer API for using `Scriber` as a library.
- The `Scriber` class can now be initialized with a list of paths to scan multiple directories at once.
- `Scriber` can now be initialized with a configuration dictionary directly.
- New method `get_output_as_string()` to get the project map without writing to a file.
- New getter methods `get_tree()` and `get_mapped_files()` to access processed data.
- Expanded `README.md` with a detailed "Library Usage" section and API examples.
- Created two installation options: a minimal default (`project-scriber`) and an enhanced version with rich terminal output (`project-scriber[rich]`).
- The `Scriber` class is now exposed for direct import and programmatic use (`from scriber import Scriber`).
- A `hidden` configuration option to prevent a file's content from being written to the output, while still including it in the file tree.
This is useful for large files like `poetry.lock`.
- Added a prompt for `hidden` patterns to the interactive `scriber init` command.

### Changed
- The default installation no longer includes `rich` as a dependency, making it more lightweight.
The CLI now falls back to simple text-based output if `rich` is not installed.
- Improved performance of file analysis by using multi-threading to process files concurrently.

## [1.0.1] - 2025-08-30

### Added
- Configured a GitHub Actions pipeline for automated testing and releases.
- `-v` and `--version` to scriber app
- The `--config` flag now accepts a path to a `pyproject.toml` file, providing more flexibility for monorepo configurations.

### Fixed
- Refined the default exclusion list in `DEFAULT_CONFIG`.

## [1.0.0] - 2025-08-28

### Initial Release
- **Project Structure Mapping**: Implemented smart file and folder structure mapping.
- **Gitignore Support**: Added logic to respect `.gitignore` files, automatically excluding specified files and directories from the mapping process.
- **Code Analysis**: Included functionality to analyze Python source code.
- **Clipboard Integration**: Enabled copying the generated project structure to the clipboard.
- **Command-Line Interface**: Created a command-line tool with a configurable `init` command for saving settings to `pyproject.toml`.
- **Configuration**: Introduced `pyproject.toml` as the single source of truth for project metadata and configuration.
- **Testing**: Added a test suite using `pytest` to ensure core functionality and CLI commands work as expected.
