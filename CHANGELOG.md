# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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