# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- A comprehensive developer API for using `Scriber` as a library.
  - `Scriber` can now be initialized with a configuration dictionary directly.
  - New method `get_output_as_string()` to get the project map without writing to a file.
  - New getter methods `get_tree()` and `get_mapped_files()` to access processed data.
- Expanded `README.md` with a detailed "Library Usage" section and API examples.
- Created two installation options: a minimal default (`project-scriber`) and an enhanced version with rich terminal output (`project-scriber[rich]`).
- The `Scriber` class is now exposed for direct import and programmatic use (`from scriber import Scriber`).
- A `hidden` configuration option to prevent a file's content from being written to the output, while still including it in the file tree. This is useful for large files like `poetry.lock`.
- Added a prompt for `hidden` patterns to the interactive `scriber init` command.

### Changed
- The default installation no longer includes `rich` as a dependency, making it more lightweight. The CLI now falls back to simple text-based output if `rich` is not installed.
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