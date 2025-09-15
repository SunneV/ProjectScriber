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

An intelligent tool to map, analyze, and compile project source code into a single, context-optimized text file for
Large Language Models (LLMs), available as both a powerful CLI and a flexible Python library.

-----

## 📖 Table of Contents

- [🤔 Why ProjectScriber?](#-why-projectscriber)
- [✨ Key Features](#-key-features)
- [🚀 Quick Start](#-quick-start)
- [💾 Installation](#-installation)
- [🖥️ Command-Line Usage](#️-command-line-usage)
- [📚 Library Usage (API)](#-library-usage-api)
- [⚙️ Configuration](#️-configuration)
- [🤝 Contributing & Development](#-contributing--development)

-----

## 🤔 Why ProjectScriber?

When working with Large Language Models, providing the full context of a codebase is crucial for getting accurate
analysis, documentation, or refactoring suggestions. Manually copying and pasting files is tedious, error-prone, and
unsustainable for projects of any real size. **ProjectScriber automates this entire process.** It intelligently scans
your project, respects your existing
`.gitignore` rules, applies custom filters, and bundles all relevant code into a single, clean, and readable format
perfect for any AI model.

<p align="center">
    📁 <b>Your Codebase</b> → 📦 <b>ProjectScriber</b> → 📋 <b>LLM-Ready Context</b>
</p>

-----

## ✨ Key Features

|Feature                        |Description                                                                                                                                                    |
|:-------------------------------|:--------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **🌳 Smart Project Mapping** | Generates a clear and intuitive tree view of your project's structure.                                                                                        |
| **⚙️ Intelligent Filtering** | Automatically respects `.gitignore` and supports custom `include`, `exclude`, and `hidden` patterns using `.gitignore`-style syntax for precise control. |
| **📊 In-depth Code Analysis** | Provides a summary with total file size, estimated token count (using `cl100k_base`), and a language breakdown.                                               |
| **🐍 Flexible Python Library** | Import and use the `Scriber` class directly in your Python projects for full programmatic control.                                                            |
| **✨ Interactive CLI** | A simple `scriber init` command walks you through creating a configuration file for your project.                                                                     |
| **📋 Clipboard Integration** | Use the `--copy` or `--copy-only` flags to automatically send the entire output to your clipboard, ready for pasting.                                          |
| **💨 Lightweight & Fast** | The default installation is minimal, and file analysis is multi-threaded for improved performance. A single-process mode is available for compatibility.    |

-----

## 🚀 Quick Start

1. **Install Scriber:**

    ```shell
    pip install project-scriber

    ````

2. **Navigate to your project's root and run:**

   ```shell
   scriber
   ```

3. **That's it\!** A `scriber_output.txt` file is now in your directory. It will look something like this:

   ````text
   ===
    Mapped Folder Structure
   ===

   ProjectScriber
   ├── .github
   │   └── workflows
   │       ├── ci.yml
   │       └── release.yml
   ├── README.md
   └── src
       └── scriber
           ├── __init__.py
           └── core.py

   ---
   File: .github/workflows/ci.yml
   Size: 512 bytes
   ---
   ```yaml
   name: Continuous Integration

   on:
     push:
       branches:
         - develop

   jobs:
     run_tests:
   ...
   ````

-----

## 💾 Installation

You have two options for installation.

#### Standard Installation

This provides the core functionality with a minimal, text-based interface.

```shell
pip install project-scriber
```

#### With Rich UI ✨

For an enhanced terminal experience with colors, tables, and progress bars, install the `rich` extra:

```shell
pip install project-scriber[rich]
```

-----

## 🖥️ Command-Line Usage

### Basic Commands

- **Scan the current directory**:
  ```shell
  scriber
  ```
- **Scan a different directory**:
  ```shell
  scriber /path/to/your/project
  ```
- **Interactive Setup**: Create a configuration file (`.scriber.json` or `pyproject.toml`) for your project.
  ```shell
  scriber init
  ```

### CLI Options

|Option             | Alias | Description                                                                                             |
|:------------------|:------|:--------------------------------------------------------------------------------------------------------|
| `root_path`       |       | The project directory to map. Defaults to the current directory.                                        |
| `--output [file]` | `-o`  | Set a custom name for the output file.                                                                  |
| `--config [path]` |       | Path to a custom config file (e.g., a `pyproject.toml` in a monorepo).                                  |
| `--copy`          | `-c`  | Copy the final output to the clipboard in addition to saving it.                                        |
| `--copy-only`     |       | Generate the output and copy it to the clipboard without saving to a file.                              |
| `--tree-only`     |       | Generate only the file tree structure, without any file content.                                        |
| `--single-process`|       | Run file analysis in a single process. Recommended for use in environments like Celery.                 |
| `--version`       | `-v`  | Show the installed version of ProjectScriber.                                                           |
| `--help`          | `-h`  | Display the help message.                                                                               |

### Advanced Example

Scan another project, save the output to `custom_map.txt`, and copy the result to the clipboard in one go:

```shell
scriber ../my-other-project --output custom_map.txt --copy
```

-----

## 📚 Library Usage (API)

Use `ProjectScriber` directly in your Python code for maximum flexibility and automation.

### Basic Example: Get Context as a String

Initialize `Scriber`, and it will automatically handle mapping and analysis.

```python
from pathlib import Path
from scriber import Scriber  # The class is exposed for direct import

# 1. Initialize Scriber for the current directory
scriber = Scriber(root_path=Path('.'))

# 2. Get the complete output directly as a string
project_context = scriber.get_output_as_string()

# 3. Use the context for your application
print(f"Generated context of {len(project_context)} characters.")

# 4. Access the calculated statistics
stats = scriber.get_stats()
print(f"Total files mapped: {stats['total_files']}")
print(f"Estimated tokens: {stats['total_tokens']:,}")
```

### Advanced Configuration via ScriberConfig

Bypass all on-disk configuration files by passing a `ScriberConfig` object directly to the constructor. This is perfect
for dynamic or controlled environments.

```python
from pathlib import Path
from scriber import Scriber, ScriberConfig

# 1. Create a config object and customize it
config = ScriberConfig()
config.single_process = True
config.exclude.append("tests/")
config.exclude.append("assets/scriber_*")

# 2. Initialize Scriber with the root path and config object
current_directory = Path('.').resolve()
scriber = Scriber(root_path=current_directory, config=config)

# 3. Get the output
project_context = scriber.get_output_as_string()
print(project_context)
```

### Scanning Multiple Directories

You can pass a list of paths to the `Scriber` constructor to map multiple directories into a single output. The first
path in the list is treated as the "primary root" for loading configurations (`.gitignore`, `pyproject.toml`, etc.).

```python
from pathlib import Path
from scriber import Scriber

# Example: Scan both a 'backend' and a 'frontend' directory
backend_path = Path('./my_backend_project')
frontend_path = Path('./my_frontend_project')

# Create dummy directories and files for the example
backend_path.mkdir(exist_ok=True)
(backend_path / "main.py").write_text("print('hello from backend')")
frontend_path.mkdir(exist_ok=True)
(frontend_path / "app.js").write_text("console.log('hello from frontend')")

# Initialize with a list of paths. `backend_path` is the primary root.
scriber = Scriber(root_path=[backend_path, frontend_path])

# Get the combined context as a single string
combined_context = scriber.get_output_as_string()
print(combined_context)

# The output will contain two separate trees and file content blocks,
# with file paths prefixed by their root folder's name.
```

### Accessing Intermediate Data

You can also access the generated file tree and the list of mapped files before the final output is compiled.

```python
from pathlib import Path
from scriber import Scriber

scriber = Scriber(root_path=Path('.'))

# Get just the formatted file tree
tree_representation = scriber.get_tree()
print("--- Project Tree ---")
print(tree_representation)

# Get a list of all mapped file paths
print("\n--- Mapped Files ---")
file_paths = scriber.get_mapped_files()
for path in file_paths:
    print(path.relative_to(scriber.primary_root))
```

### Practical Example: Preparing Context for an LLM

Here's a small function demonstrating how you can use ProjectScriber to generate a complete, well-formatted prompt for
an LLM.

```python
from pathlib import Path
from scriber import Scriber


def get_llm_context(project_path: Path, task: str) -> str:
    '''
    Generates a complete project context string ready for an LLM.

    Args:
        project_path: The root directory of the project.
        task: The specific task you want the LLM to perform.

    Returns:
        A formatted string to be used as a prompt for an LLM.
    '''
    # Initialize Scriber and get the project map
    scriber = Scriber(root_path=project_path)
    project_map = scriber.get_output_as_string()

    # Get some stats for the context header
    stats = scriber.get_stats()
    token_count = stats.get("total_tokens", 0)

    # Assemble the final prompt for the LLM
    prompt = (
        f"Please perform the following task: {task}\n\n"
        f"Here is the full context of the project codebase. "
        f"It includes a file tree and the content of all relevant files.\n"
        f"Estimated Token Count: {token_count:,}\n\n"
        "--- PROJECT CONTEXT BEGINS ---\n"
        f"{project_map}"
        "--- PROJECT CONTEXT ENDS ---"
    )

    return prompt


# --- Usage ---
if __name__ == "__main__":
    my_project_path = Path('.')
    user_task = "Analyze the code for potential bugs and suggest improvements."
    llm_prompt = get_llm_context(my_project_path, user_task)

    print(llm_prompt)

    # Now you can send `llm_prompt` to your favorite LLM API.
```

-----

## ⚙️ Configuration

ProjectScriber is configured via a file in your project's root. It searches for configurations in the following order of
precedence:

1. **Direct `config` object/dictionary** (Library mode only).
2. **`--config [path]` flag** (CLI mode only).
3. **`.scriber.json`** in the project root.
4. **`[tool.scriber]`** section in `pyproject.toml`.
5. **Default Behavior**: If no file is found, a default configuration is used, and a `.scriber.json` may be created to
   guide you.

### Configuration Keys

|Key             |Type    |Default                |Description                                                                                                                                      |
|:----------------|:--------|:-----------------------|:------------------------------------------------------------------------------------------------------------------------------------------------|
| `use_gitignore` | boolean | `true`                 |If `true`, all patterns in the `.gitignore` file will be used for exclusion.                                                                     |
| `exclude`       |list    |See `config.py`        |A list of file/folder names or `.gitignore`-style patterns to exclude globally (e.g., `"node_modules"`, `"*.log"`, `build/`).                          |
| `include`       |list    |`[]`                   |If not empty, **only** files matching these `.gitignore`-style patterns will be included.                                                           |
| `hidden`        |list    |`[]`                   |Files matching these patterns will appear in the tree but their content will be replaced with a placeholder. Useful for large lock files.          |
| `exclude_map`   |object  |`{}`                   |A dictionary for language-specific and global exclusion patterns. See example below.                                                              |
| `output`        |string  |`"scriber_output.txt"` |The default name for the output file.                                                                                                            |
| `single_process`|boolean |`false`                |If `true`, runs file analysis in a single process. This is slower but required for environments like Celery that do not allow child processes. |

### Example `pyproject.toml` Configuration

Here is an example of a well-configured `[tool.scriber]` section in your `pyproject.toml` file:

```toml
[tool.scriber]
# Respect the project's .gitignore file
use_gitignore = true

# Globally exclude common folders and file types using gitignore-style patterns
exclude = [
    "__pycache__/",
    "node_modules/",
    "dist/",
    "build/",
    ".venv/",
]

# Only include files with these extensions
include = [
    "*.py",
    "*.js",
    "*.css",
    "*.md"
]

# Show these files in the tree, but hide their content
hidden = [
    "poetry.lock"
]

# Run in a single process to prevent issues in certain environments
single_process = false

# Language-specific and global exclusion rules
[tool.scriber.exclude_map]
# Exclude these patterns from all files
global = ["*.log", "*.tmp"]
# In Python files, exclude tests and setup scripts
python = ["*_test.py", "setup.py"]
# In JavaScript files, exclude spec files
javascript = ["*.spec.js"]
```

> **💡 Note on Pattern Matching:** The `exclude` and `include` options support `.gitignore`-style pattern matching. This
allows for more precise rules, such as matching directories only (e.g., `build/`), root-level files (e.g.,
`/config.yaml`), or standard wildcards (`*.log`).

-----

## 🤝 Contributing & Development

Contributions are welcome\! If you have a suggestion or find a bug, please open an issue to discuss it first.

### Development Setup

1. **Prerequisites**:

    * Python 3.10 or higher.

2. **Clone the Repository**:

   ```shell
   git clone https://github.com/SunneV/ProjectScriber.git
   ```

3. **Navigate to the Project Directory**:

   ```shell
   cd ProjectScriber
   ```

4. **Install Dependencies**:
   Choose one of the following methods to install the project in editable mode with all development dependencies.

    * **Using `pip`**:

      ```shell
      pip install -e .[dev]
      ```

    * **Using `uv`** (Recommended):

      ```shell
      uv pip install -e .[dev]
      ```

### Running Tests

Run the test suite using `pytest`:

```shell
pytest
```