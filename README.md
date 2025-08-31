<p align="center">
  <img src="https://raw.githubusercontent.com/SunneV/ProjectScriber/main/assets/scriber_logo.svg" alt="ProjectScriber Logo" width="300">
  <br>
  <img src="https://raw.githubusercontent.com/SunneV/ProjectScriber/main/assets/scriber_name.svg" alt="ProjectScriber Name" width="250">
</p>
<p align="center">
    <a href="https://github.com/SunneV/ProjectScriber/releases"><img src="https://img.shields.io/github/v/release/SunneV/ProjectScriber?style=flat&label=latest%20version" alt="Latest Version"></a>
    <a href="https://pypi.org/project/project-scriber/"><img src="https://img.shields.io/pypi/v/project-scriber?style=flat" alt="PyPI Version"></a>
</p>

A command-line tool to intelligently map and compile your project's source code into a single, context-optimized text
file for Large Language Models (LLMs).

---

## Why ProjectScriber?

When working with LLMs, providing the full context of a codebase is crucial for getting accurate analysis,
documentation, or refactoring suggestions. Manually copying and pasting files is tedious and error-prone. *
*ProjectScriber** automates this process. It scans your project, respects `.gitignore` rules, applies custom filters,
and bundles all relevant code into a clean, readable format perfect for any AI model.

## Key Features

* **🌳 Smart Project Mapping:** Generates a clear and intuitive tree view of your project's structure.
* **⚙️ Intelligent Filtering:** Automatically respects `.gitignore` rules and supports custom `include` and `exclude`
  patterns for fine-grained control.
* **📊 In-depth Code Analysis:** Provides a summary with total file size, estimated token count (using `cl100k_base`),
  and a language breakdown.
* **✨ Interactive Setup:** A simple `scriber init` command walks you through creating a configuration file tailored to
  your project.
* **📋 Clipboard Integration:** Use the `--copy` flag to automatically copy the entire output to your clipboard.
* **🔧 Flexible Configuration:** Manage settings in a `pyproject.toml` or a project-specific `.scriber.json` file.

---

## Getting Started

Install the package directly from the [Python Package Index (PyPI)](https://pypi.org/project/project-scriber/).

```shell
pip install project-scriber
````

-----

## Usage

#### 1\. Basic Scan

Run `scriber` in your project's root directory. It will generate a `scriber_output.txt` file.

```shell
scriber
```

To target a different directory:

```shell
scriber /path/to/your/project
```

#### 2\. First-Time Configuration

For a new project, run the interactive `init` command to create a `.scriber.json` configuration file.

```shell
scriber init
```

#### 3\. Advanced Example

Scan another project, specify a custom output file, and copy the result to the clipboard in one command.

```shell
scriber ../my-other-project --output custom_map.txt --copy
```

-----

## Commands and Options

| Command/Option        | Alias | Description                                                                  |
|:----------------------|:-----:|:-----------------------------------------------------------------------------|
| `scriber [path]`      |       | Targets a specific directory. Defaults to the current working directory.     |
| `init`                |       | Starts the interactive process to create a configuration file.               |
| `--help`              | `-h`  | Displays the help message.                                                   |
| `--version`           | `-v`  | Displays the current version of ProjectScriber.                              |
| `--output [filename]` | `-o`  | Specifies a custom name for the output file.                                 |
| `--copy`              | `-c`  | Copies the final output directly to the clipboard.                           |
| `--tree-only`         |       | Generates only the folder structure map, excluding all file contents.        |
| `--config [path]`     |       | Specifies a path to a custom `.json` or `pyproject.toml` configuration file. |

-----

## Configuration

ProjectScriber uses the following order of precedence for loading configurations:

1. **`--config [path]` flag**: Highest priority. If you provide a path to a `.json` or `pyproject.toml` file, its
   settings will be used.
2. **`.scriber.json`**: If no `--config` flag is used, Scriber looks for a `.scriber.json` file in the project's root.
   This file's settings will override any found in `pyproject.toml`.
3. **`pyproject.toml`**: If neither of the above is found, it looks for a `[tool.scriber]` section in a `pyproject.toml`
   file in the project's root.
4. **Default Config**: If no configuration is found, `scriber` will create a default `.scriber.json` on its first run in
   a directory.

**Example `.scriber.json`:**

```json
{
  "use_gitignore": true,
  "exclude": [
    "__pycache__",
    "node_modules",
    "*.log"
  ],
  "include": [
    "*.py",
    "*.js"
  ]
}
```

**Example `pyproject.toml`:**

```toml
[tool.scriber]
use_gitignore = true
exclude = [
    "__pycache__",
    "node_modules",
    "*.log"
]
include = [
    "*.py",
    "*.js"
]
```

-----

## For Developers

### Prerequisites

* Python 3.10 or higher.

### Development Installation

Clone the repository and install it in editable mode with all development dependencies.

```shell
git clone [https://github.com/SunneV/ProjectScriber.git](https://github.com/SunneV/ProjectScriber.git)
cd ProjectScriber
pip install -e .[dev]
```

### Running Tests

Run the test suite using `pytest`.

```shell
pytest
```

-----

## Contributing

Contributions are welcome\! If you have a suggestion or find a bug, please open an issue to discuss it.
