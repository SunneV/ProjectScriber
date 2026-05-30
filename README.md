<p align="center">
  <img src="https://raw.githubusercontent.com/SunneV/ProjectScriber/main/assets/scriber_logo.svg" alt="ProjectScriber Logo" width="300">
  <br>
  <img src="https://raw.githubusercontent.com/SunneV/ProjectScriber/main/assets/scriber_name.svg" alt="ProjectScriber Name" width="250">
</p>
<p align="center">
    <a href="https://github.com/SunneV/ProjectScriber/blob/main/LICENSE"><img src="https://img.shields.io/github/license/SunneV/ProjectScriber" alt="License"></a>
    <a href="https://github.com/SunneV/ProjectScriber/releases"><img src="https://img.shields.io/github/v/release/SunneV/ProjectScriber?style=flat&label=latest%20version" alt="Latest Version"></a>
    <a href="https://pypi.org/project/project-scriber/"><img src="https://img.shields.io/pypi/v/project-scriber?style=flat" alt="PyPI Version"></a>
</p>

An intelligent tool to map, analyze, and compile project source code into a single, context-optimized text file for Large Language Models (LLMs). **Version 2.0** brings advanced dependency graph analysis, strict whitelist-based file inclusion, zero-dependency lightweight execution, and progress tracking!

-----

## 📖 Table of Contents

- [🤔 Why ProjectScriber 2.0?](#-why-projectscriber-20)
- [✨ Key Features](#-key-features)
- [🚀 Quick Start](#-quick-start)
- [💾 Installation](#-installation)
- [🖥️ Command-Line Usage](#️-command-line-usage)
- [⚙️ Configuration](#️-configuration)
- [🤝 Contributing & Development](#-contributing--development)

-----

## 🤔 Why ProjectScriber 2.0?

When working with Large Language Models, providing the full context of a codebase is crucial for getting accurate analysis, documentation, or refactoring suggestions. However, blindly pasting an entire project wastes tokens and introduces noise.

**ProjectScriber 2.0** automates context building using a **Whitelist-First** philosophy and an **Intelligent Scoring Engine**. It analyzes your codebase's dependency graph (e.g., Python imports), determines which files are most relevant to the code you're working on, and bundles them into a single, clean markdown file, strictly respecting your token budgets and file-type configurations.

<p align="center">
    📁 <b>Your Codebase</b> → 📦 <b>ProjectScriber 2.0</b> → 📋 <b>LLM-Ready Context</b>
</p>

-----

## ✨ Key Features

| Feature | Description |
|:---|:---|
| **🌳 Smart Project Mapping** | Generates a clear and intuitive tree view of your project's structure. |
| **⚡ Native Rust Acceleration** | Accelerates heavy I/O and directory scanning natively via a high-performance Rust backend. |
| **🛡️ Whitelist Philosophy** | By default, only recognized code and support files are included. Binary and lock files are automatically ignored. |
| **🧠 Intelligent Scoring Engine** | Analyzes import graphs and file proximity to prioritize code modules that are directly related to your provided seed files. |
| **💰 Token Budgets** | Set a hard limit on `--max-tokens`. Scriber will fit the most relevant files within your budget to save API costs. |
| **📊 Live Progress & Stats** | Built-in zero-dependency progress spinner and detailed statistics summary at the end of the run. |

-----

## 🚀 Quick Start

1. **Install Scriber:**

    ```shell
    pip install project-scriber
    ```

2. **Navigate to your project's root and initialize config:**

   ```shell
   scriber --init
   ```
   *(This appends a `[tool.scriber]` block to your `pyproject.toml`. Use `--force` to overwrite it.)*

3. **Pack your context!** Just point it to a file, folder, or let it scan the whole project:

   ```shell
   scriber src/main.py --output context.md
   ```

4. **Review your stats:**
   ```text
   Scriber build completed.
   ----------------------------------------
    Code files included:    15
    Support files included: 4
    Files omitted/skipped:  2
    Estimated tokens:       12500
   ----------------------------------------
   Scriber pack written to: context.md
   ```

-----

## 💾 Installation

ProjectScriber distributes pre-compiled binary wheels for Linux, macOS, and Windows. A simple pip command is all you need:

```shell
pip install project-scriber
```

Or if you use `uv`:

```shell
uv pip install project-scriber
```

> [!NOTE]
> If a pre-compiled wheel is not available for your platform/architecture, the package will automatically build from source, which requires a Rust compiler toolchain (Rust 1.70+) installed on your machine.

-----

## 🖥️ Command-Line Usage

### Basic Commands

- **Scan the current directory**:
  ```shell
  scriber .
  ```
- **Scan a specific file and its dependencies**:
  ```shell
  scriber src/my_module.py
  ```
- **Interactive Setup**: Create/Append a default configuration in `pyproject.toml` (use `--force` to overwrite it).
  ```shell
  scriber --init
  ```

### CLI Options

| Option | Description |
|:---|:---|
| `paths` | Project file/folder paths used as seeds. Defaults to current directory `.`. |
| `--config [path]` | Path to `pyproject.toml`. Its parent directory becomes the project root. |
| `--path-base [base]`| Base for relative paths: `project` (default) or `cwd`. |
| `--format [md, txt]` | Output format. Defaults to `md` (Markdown). |
| `--output [file]` | Output file path. Use `-` for stdout. |
| `--dry-run`       | Show pack summary without writing the output file. |
| `--open`          | Open the generated file in the default editor. |
| `--validate-config`| Validate the `[tool.scriber]` configuration and exit. |
| `--only-tree` | Render only the scored tree/map, without any file contents. |
| `--[no-]modules` | Enable/Disable automatic related module selection (dependency graph scanning). |
| `--[no-]support` | Enable/Disable support files (like `.env.example`, `.github/workflows`). |
| `--support-content` | Override support file content policy (`full`, `auto`, `tree_only`). |
| `--max-files` | Maximum number of files in the pack. |
| `--max-tokens` | Approximate token budget using char-based estimation. `0` disables budget. |
| `--min-score` | Minimum relevance score (0-100) for non-seed files to be included. |
| `--init` | Append a default `[tool.scriber]` config to `pyproject.toml` and exit. |
| `--force` | Force overwrite of the config block when used with `--init`. |
| `--version` | Show program's version number and exit. |

-----

## ⚙️ Configuration

ProjectScriber 2.0 configures itself through the standard `pyproject.toml` using the `[tool.scriber]` table.
Generate the default block using:

```shell
scriber --init
```

### Example `pyproject.toml`

> [!NOTE]
> This is a minimal example. Run `scriber --init` to generate the full default configuration.

```toml
[tool.scriber]
format = "md"
max_tokens = 0        # 0 means unlimited
max_files = 0         # 0 means unlimited
only_tree = false     # If true, file contents are omitted
allow_external_paths = false

[tool.scriber.modules]
enabled = true
content_min_score = 50

[tool.scriber.tokens]
estimator = "chars"
chars_per_token = 4

[tool.scriber.code_files]
# Only files matching these are considered "Code"
patterns = [
    "**/*.py",
    "**/*.js",
    "**/*.ts",
    "**/*.tsx"
]

[tool.scriber.support_files]
enabled = true
# Only files matching these are considered "Support"
patterns = [
    "pyproject.toml",
    "Dockerfile",
    "**/*.svg"
]

[tool.scriber.support_files.content]
default = "auto"
auto_max_bytes = 10000
full = [
    "pyproject.toml",
    "requirements.txt",
    "README.md"
]
tree_only = [
    "**/*.svg"
]

[tool.scriber.hard_ignore]
# Folders ignored entirely during the initial scan
patterns = [
    ".git/**",
    "__pycache__/**",
    "node_modules/**",
    ".venv/**"
]
```

### Whitelist Policy
ProjectScriber 2.0 uses a strict **whitelist** approach:
1. Files must match either a `code_pattern` or a `support_pattern` to be considered.
2. Unrecognized extensions and binary files are automatically excluded, keeping your LLM context safe from binary garbage.
3. Lock files are included in the tree by default, but their contents are omitted to save tokens.
4. Support files can be marked as `tree_only` (e.g., `**/*.svg`), meaning they'll show up in the project map but their contents won't be read.

-----

## 🤝 Contributing & Development

Contributions are welcome!

### Development Setup

1. **Clone the Repository**:
   ```shell
   git clone https://github.com/SunneV/ProjectScriber.git
   cd ProjectScriber
   ```

2. **Install Dependencies & Compile Extension** (using `uv` is recommended):
   ```shell
   uv sync --all-extras
   ```
   *(This synchronizes the virtual environment and compiles the native Rust extension automatically!)*

3. **Run Tests**:
   ```shell
   uv run pytest
   ```