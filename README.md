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

An intelligent tool to map, analyze, and compile project source code into a single, context-optimized text file for Large Language Models (LLMs). **Version 2** brings advanced dependency graph analysis, strict whitelist-based file inclusion, zero-dependency lightweight execution, and progress tracking!

-----

## 📖 Table of Contents

- [🤔 Why ProjectScriber?](#-why-projectscriber)
- [✨ Key Features](#-key-features)
- [🚀 Quick Start](#-quick-start)
- [💾 Installation](#-installation)
- [🖥️ Command-Line Usage](#️-command-line-usage)
- [⚙️ Configuration](#️-configuration)
- [🤝 Contributing & Development](#-contributing--development)

-----

## 🤔 Why ProjectScriber?

When working with Large Language Models, providing the full context of a codebase is crucial for getting accurate analysis, documentation, or refactoring suggestions. However, blindly pasting an entire project wastes tokens and introduces noise.

**ProjectScriber** automates context building using a **Whitelist-First** philosophy and an **Intelligent Scoring Engine**. It analyzes your codebase's dependency graph (e.g., Python imports), determines which files are most relevant to the code you're working on, and bundles them into a single, clean markdown file, strictly respecting your token budgets and file-type configurations.

<p align="center">
    📁 <b>Your Codebase</b> → 📦 <b>ProjectScriber</b> → 📋 <b>LLM-Ready Context</b>
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

<!-- BEGIN SCRIBER:CLI_OPTIONS -->
| Option | Description |
|:---|:---|
| `paths` | Project file/folder paths used as seeds. Defaults to current directory. |
| `--profile` | Preset configuration profile. |
| `--config` | Path to pyproject.toml. Its parent directory becomes the project root. |
| `--path-base` | Base directory for relative paths when --config is used. |
| `--format` | Output format. |
| `--output` | Output file path, relative to project root unless absolute. Use '-' for stdout. |
| `--only-tree` | Render only scored tree/map, without file contents. |
| `--modules` | Enable automatic related module selection. |
| `--no-modules` | Disable automatic related module selection. |
| `--support` | Enable support files. |
| `--no-support` | Disable support files. |
| `--support-content` | Override default support file content policy. |
| `--max-files` | Maximum number of files in the pack. |
| `--max-tokens` | Approximate token budget for included file contents. 0 disables budget. |
| `--min-score` | Minimum score for non-seed files. |
| `--init` | Append a default [tool.scriber] config to pyproject.toml and exit. |
| `--force` | Allow --init to append even if [tool.scriber] already exists. |
| `--project` | Force project snapshot mode. |
| `--explain, --explain-selection` | Explain reason for file selection in detail. |
| `--explain-graph` | Print relation graph statistics and relations. |
| `--why` | Print exactly which rules/edges pulled the specified file into the pack. |
| `--graph-json` | Export the RelationGraph as a JSON file to the specified path. |
| `--validate-config` | Validate pyproject.toml scriber config. |
| `--dry-run` | Perform a dry run without saving the pack file. |
| `--open` | Open the output file automatically after creation. |
| `--timings` | Show execution timings for each phase. |
| `--version` | Show version information and exit. |
<!-- END SCRIBER:CLI_OPTIONS -->

<!-- BEGIN SCRIBER:PROFILES -->
### Profiles

ProjectScriber comes with several preset profiles to quickly bias the file scoring and inclusion criteria:

| Profile | Description |
|:---|:---|
| `default` | Standard scoring behavior. |
| `audit` | Boosts tests, config files, CI environments, and dependency files. Assumes full support content inclusion. |
| `debug` | Boosts direct/reverse dependencies, tests, runtime support, and files close to the seed path. |
| `refactor` | Boosts files within the same package, related tests, and direct dependencies. |
| `docs` | Heavily boosts documentation files while suppressing test and code file scores. Assumes tree_only support content by default. |
<!-- END SCRIBER:PROFILES -->

-----

## 🛠️ IDE Integrations

### PyCharm / IntelliJ IDEA (External Tools)

You can integrate ProjectScriber directly into PyCharm's right-click context menu to quickly generate LLM context packs for any selected file or folder!

1. Open **Settings / Preferences** ➔ **Tools** ➔ **External Tools**.
2. Click the **`+`** button to add a new tool.
3. Configure it as follows:

* **Name:** `Scriber`
* **Group:** `External Tools`
* **Description:** `Runs ProjectScriber on the selected directory and copies output to clipboard`
* **Program:** `scriber` *(or the absolute path to your `scriber.exe` e.g., `C:\Tools\Python\Python313\Scripts\scriber.exe`)*
* **Arguments:** `"$FilePath$" --config $ProjectFileDir$/pyproject.toml`
* **Working directory:** `$ProjectFileDir$`

Now, you can simply right-click any file or directory in your Project tree, select **External Tools** ➔ **Scriber**, and the context pack will be generated instantly based on your project configuration!

-----

## ⚙️ Configuration

ProjectScriber 2.1.0 configures itself through the standard `pyproject.toml` using the `[tool.scriber]` table.
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
ProjectScriber 2.1.0 uses a strict **whitelist** approach:
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
