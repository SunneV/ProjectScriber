# Introduction

<p align="center">
  <img src="https://raw.githubusercontent.com/SunneV/ProjectScriber/main/assets/scriber_logo.svg" alt="ProjectScriber Logo" width="420">
</p>
<p align="center">
  <img src="https://raw.githubusercontent.com/SunneV/ProjectScriber/main/assets/scriber_name.svg" alt="ProjectScriber Name" width="300">
</p>

A command-line tool to intelligently map and compile your entire project's source code into a single, context-optimized
text file for Large Language Models (LLMs).

ProjectScriber scans your project directory, respects `.gitignore` rules, applies custom filters, and bundles all
relevant code into a clean, readable format. It's the perfect way to provide a complete codebase to an AI for analysis,
documentation, or refactoring.

-----

## Key Features

- **🌳 Smart Project Mapping:** Generates a clear and intuitive tree view of your project's structure.
- **⚙️ Intelligent Filtering:** Automatically respects `.gitignore` rules and supports custom `include` and `exclude`
  patterns via a `.scriber.json` file for fine-grained control.
- **📊 In-depth Code Analysis:** Provides a summary with total file size, estimated token count (using `cl100k_base`),
  and a language breakdown for a quick overview of your codebase.
- **✨ Interactive Setup:** A simple `scriber init` command walks you through creating a configuration file tailored to
  your project.
- **📋 Clipboard Integration:** Use the `--copy` flag to automatically copy the entire consolidated output to your
  clipboard, ready to be pasted into any application.
- **🔧 Flexible Configuration:** Manage your settings globally in a `pyproject.toml` file or per-project with a
  `.scriber.json` file.

-----

## Getting Started

### Prerequisites

- Python 3.10 or higher.

### Installation

Install the package from the source using pip. For development, include the optional dependencies.

```shell
# Navigate to the project root directory
pip install .[dev]
```

This will install `ProjectScriber` and make the `scriber` command available in your terminal.

-----

## Usage

### 1\. Basic Scan

To run ProjectScriber on the current directory, simply execute the `scriber` command. This will generate a
`scriber_output.txt` file in the same directory.

```shell
scriber
```

To target a different project directory:

```shell
scriber /path/to/your/project
```

### 2\. First-Time Configuration

For a new project, run the interactive `init` command to create a `.scriber.json` configuration file. This will guide
you through setting up rules for ignoring files and respecting `.gitignore`.

```shell
scriber init
```

### 3\. Advanced Example

Scan a different project, specify a custom output file, and copy the result to the clipboard all in one command.

```shell
scriber ../my-other-project --output custom_map.txt --copy
```

-----

## Commands and Options

You can customize ProjectScriber's behavior with the following commands and options.

| Command/Option        | Alias | Description                                                                    |
|:----------------------|:-----:|:-------------------------------------------------------------------------------|
| `scriber [path]`      |       | Targets a specific directory. Defaults to the current working directory.       |
| `init`                |       | Starts the interactive process to create a `.scriber.json` configuration file. |
| `--output [filename]` | `-o`  | Specifies a custom name for the output file.                                   |
| `--copy`              | `-c`  | Copies the final output directly to the clipboard.                             |
| `--tree-only`         |       | Generates only the folder structure map, excluding all file contents.          |
| `--config [path]`     |       | Specifies the path to a custom configuration file.                             |

-----

## Configuration

You can control ProjectScriber's behavior by placing a `.scriber.json` file in your project's root, which can be easily
created with the `scriber init` command.

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
    "*.log",
]
include = [
    "*.py",
    "*.js",
]
```

- **`use_gitignore`**: If `true`, all patterns in your `.gitignore` file will be used for exclusion.
- **`exclude`**: A list of file or folder name patterns to explicitly ignore.
- **`include`**: If provided, *only* files matching these patterns will be included in the output, overriding other
  rules.

Settings can also be placed in your `pyproject.toml` file under the `[tool.scriber]` section. If a `.scriber.json` file
is present, it will take precedence over the `pyproject.toml` configuration.