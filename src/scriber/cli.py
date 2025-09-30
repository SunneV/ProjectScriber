import argparse
import io
import json
import os
import re
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

import pyperclip
import tomlkit
from dotenv import load_dotenv

from .core import DEFAULT_CONFIG, Scriber

try:
    import rich.box
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
    from rich.prompt import Confirm, Prompt
    from rich.table import Table
    from rich.text import Text

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

load_dotenv()


class SimpleConsole:
    """A fallback console that mimics rich.Console with simple print statements."""

    def print(self, message: Any = "") -> None:
        """Strips rich markup and prints the message, handling potential Unicode errors.

        This method attempts to print the message directly. If a UnicodeEncodeError
        occurs, it falls back to encoding the message using the system's stdout
        encoding, replacing any unsupported characters to prevent crashes.

        Args:
            message: The object or text to print.
        """
        message_str = str(message)
        cleaned_message = re.sub(r'\[/?[a-zA-Z\s=]+\]', '', message_str)
        try:
            print(cleaned_message)
        except UnicodeEncodeError:
            safe_message = cleaned_message.encode(
                sys.stdout.encoding, errors='replace'
            ).decode(sys.stdout.encoding)
            print(safe_message)


def format_bytes(byte_count: int) -> str:
    """Formats a byte count into a human-readable string (KB, MB).

    Args:
        byte_count: The number of bytes.

    Returns:
        A formatted string representing the size.
    """
    if byte_count > 1024 * 1024:
        return f"{byte_count / (1024 * 1024):.2f} MB"
    if byte_count > 1024:
        return f"{byte_count / 1024:.2f} KB"
    return f"{byte_count} Bytes"


def save_to_json(console: Any, config: dict[str, Any]):
    """Saves configuration to a .scriber.json file.

    Args:
        console: The console instance for printing output.
        config: The configuration dictionary to save.
    """
    config_path = Path.cwd() / ".scriber.json"
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        console.print(f"\n✅ [bold green]Configuration saved to:[/] {config_path}")
    except IOError as e:
        console.print(f"\n❌ [bold red]Error saving config file:[/] {e}")


def save_to_toml(console: Any, config: dict[str, Any]):
    """Saves configuration to the pyproject.toml file.

    Args:
        console: The console instance for printing output.
        config: The configuration dictionary to save.
    """
    toml_path = Path.cwd() / "pyproject.toml"
    if not toml_path.exists():
        console.print(f"\n❌ [bold red]Error: `pyproject.toml` not found in the current directory.[/]")
        return

    try:
        with open(toml_path, "r+", encoding="utf-8") as f:
            doc = tomlkit.parse(f.read())

            tool_table = doc.setdefault("tool", tomlkit.table())
            scriber_table = tool_table.setdefault("scriber", tomlkit.table())
            scriber_table.update(config)

            f.seek(0)
            f.truncate()
            f.write(tomlkit.dumps(doc))

        console.print(f"\n✅ [bold green]Configuration saved to:[/] {toml_path}")
    except Exception as e:
        console.print(f"\n❌ [bold red]Error updating `pyproject.toml`:[/] {e}")


def handle_init(args: argparse.Namespace, console: Any, rich_available: bool):
    """Handles the interactive initialization of a config file.

    Args:
        args: The parsed command-line arguments.
        console: The console instance for printing output.
        rich_available: A boolean indicating if the 'rich' library is installed.
    """
    if rich_available:
        console.print(Panel("[bold cyan]Scriber Configuration Setup[/]", expand=False))
    else:
        console.print("--- Scriber Configuration Setup ---")
    console.print("This utility will help you create a configuration file.\n")

    config: dict[str, Any] = {}

    if rich_available:
        config["use_gitignore"] = Confirm.ask("✨ Would you like to respect `.gitignore` rules?", default=True)
        default_exclude = ", ".join(DEFAULT_CONFIG.exclude)
        exclude_str = Prompt.ask("📂 Enter patterns to exclude (comma-separated)", default=default_exclude)
        include_str = Prompt.ask("📄 Enter patterns to include (optional, comma-separated)", default="")
        hidden_str = Prompt.ask("🙈 Enter patterns to hide content for (e.g., lock files, optional, comma-separated)",
                                default="")
        config["single_process"] = Confirm.ask("⚙️ Run in a single process? (for Celery or similar environments)",
                                               default=False)
    else:
        answer = input("✨ Would you like to respect `.gitignore` rules? (Y/n) ").strip().lower()
        config["use_gitignore"] = answer not in ['n', 'no']
        default_exclude = ", ".join(DEFAULT_CONFIG.exclude)
        exclude_str = input(
            f"📂 Enter patterns to exclude (comma-separated, default: {default_exclude}): ") or default_exclude
        include_str = input("📄 Enter patterns to include (optional, comma-separated): ")
        hidden_str = input("🙈 Enter patterns to hide content for (e.g., lock files, optional, comma-separated): ")
        answer = input("⚙️ Run in a single process? (for Celery or similar environments) (y/N) ").strip().lower()
        config["single_process"] = answer in ['y', 'yes']

    config["exclude"] = [item.strip() for item in exclude_str.split(',') if item.strip()]
    include_patterns = [item.strip() for item in include_str.split(',') if item.strip()]
    if include_patterns:
        config["include"] = include_patterns
    hidden_patterns = [item.strip() for item in hidden_str.split(",") if item.strip()]
    if hidden_patterns:
        config["hidden"] = hidden_patterns

    console.print("\n[bold]Choose a save location:[/bold]")
    console.print("  [cyan]1[/]: Save to `.scriber.json` (project-specific override)")
    console.print("  [cyan]2[/]: Save to `pyproject.toml` (project default)")

    if rich_available:
        save_target = Prompt.ask("Enter your choice", choices=["1", "2"], default="1")
    else:
        save_target = input("Enter your choice (1/2, default: 1): ") or "1"

    if save_target == '1':
        save_to_json(console, config)
    elif save_target == '2':
        save_to_toml(console, config)


def run_scriber(args: argparse.Namespace, console: Any, version: str, rich_available: bool):
    """Handles the main logic of mapping and generating the project output.

    Args:
        args: The parsed command-line arguments.
        console: The console instance for printing output.
        version: The current version of the application.
        rich_available: A boolean indicating if the 'rich' library is installed.
    """
    if rich_available:
        title_text = Text(f"Scriber v{version}", justify="center", style="bold magenta")
        subtitle_text = Text("An intelligent tool to map, analyze, and compile project source code for LLM context.",
                             justify="center", style="cyan")
        console.print(Panel(Text.assemble(title_text, "\n", subtitle_text), expand=False, border_style="blue"))
    else:
        console.print(f"--- Scriber v{version} ---")

    scriber = Scriber(args.root_path.resolve(), config_path=args.config)
    if args.single_process:
        scriber.single_process = True

    scriber.map_project()

    progress = None
    task_id = None
    if rich_available:
        progress_manager = Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                                    BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                                    console=console, transient=True)
        total_files = scriber.get_file_count()
        if total_files > 0 and not args.tree_only:
            task_id = progress_manager.add_task("[green]Processing files...", total=total_files)
        progress = progress_manager
    else:
        console.print("Processing files...")

    output_content = ""
    if progress:
        with progress:
            output_content = scriber.get_output_as_string(tree_only=args.tree_only, progress=progress, task_id=task_id)
    else:
        output_content = scriber.get_output_as_string(tree_only=args.tree_only)

    stats = scriber.get_stats()
    config_file_display = str(scriber.config_path_used) if scriber.config_path_used else "Defaults"

    if rich_available:
        summary_table = Table(box=rich.box.ROUNDED, show_header=False, title="[bold]Run Summary[/]",
                              title_justify="left")
        summary_table.add_column("Parameter", style="cyan", no_wrap=True)
        summary_table.add_column("Value", style="magenta")
        summary_table.add_row("Project Path", str(args.root_path.resolve()))
        summary_table.add_row("Config File", config_file_display)
        if not args.copy_only:
            summary_table.add_row("Output File", args.output or scriber.config.output)
        console.print(summary_table)
    else:
        console.print("\n--- Run Summary ---")
        console.print(f"Project Path: {str(args.root_path.resolve())}")
        console.print(f"Config File: {config_file_display}")
        if not args.copy_only:
            console.print(f"Output File: {args.output or scriber.config.output}")

    if stats['total_files'] > 0:
        if rich_available:
            results_table = Table(box=rich.box.ROUNDED, show_header=False, title="[bold]📊 Analysis Results[/]",
                                  title_justify="left")
            results_table.add_column("Metric", style="cyan", no_wrap=True)
            results_table.add_column("Value", style="magenta", justify="right")
            results_table.add_row("Files Mapped", str(stats['total_files']))
            if stats.get('skipped_binary') > 0:
                results_table.add_row("Binary Skipped", str(stats['skipped_binary']))
            results_table.add_section()
            results_table.add_row("Total Size", format_bytes(stats['total_size_bytes']))
            results_table.add_row("Est. Tokens (cl100k)", f"{stats['total_tokens']:,}")
            results_table.add_section()
            results_table.add_row("[bold]Language Breakdown[/]", "")
            for lang, count in stats['language_counts'].most_common():
                results_table.add_row(f"  {lang.capitalize()}", str(count))
            console.print(results_table)
        else:
            console.print("\n--- Analysis Results ---")
            console.print(f"Files Mapped: {stats['total_files']}")
            if stats.get('skipped_binary') > 0:
                console.print(f"Binary Skipped: {stats['skipped_binary']}")
            console.print(f"Total Size: {format_bytes(stats['total_size_bytes'])}")
            console.print(f"Est. Tokens (cl100k): {stats['total_tokens']:,}")
            console.print("Language Breakdown:")
            for lang, count in stats['language_counts'].most_common():
                console.print(f"  {lang.capitalize()}: {count}")
    else:
        if rich_available:
            console.print(Panel("[yellow]No files were mapped based on the current configuration.[/]", expand=False))
        else:
            console.print("No files were mapped based on the current configuration.")

    if not args.copy_only:
        output_filename = args.output or scriber.config.output
        output_location = Path(args.root_path).resolve() / output_filename
        try:
            with open(output_location, 'w', encoding='utf-8') as f:
                f.write(output_content)
            console.print("\n✅ [green]Success! Output saved to:[/green]")
            console.print(str(output_location))
        except IOError as e:
            console.print(f"\n❌ [bold red]Error saving output file:[/] {e}")

    if args.copy or args.copy_only:
        try:
            pyperclip.copy(output_content)
            if args.copy_only:
                console.print("\n✅ [green]Success! Output copied to clipboard.[/green]")
            else:
                console.print("📋 [green]Content copied to clipboard.[/green]")
        except Exception as e:
            console.print(f"❌ [bold red]Could not copy to clipboard: {e}[/bold red]")


def main() -> None:
    """Parses arguments and runs the appropriate command."""
    if RICH_AVAILABLE:
        # On Windows, the default console (cmd.exe) often doesn't support Unicode
        # emojis. We detect this environment and disable emojis to prevent crashes,
        # unless we are in a modern terminal like Windows Terminal.
        is_legacy_windows = (
            sys.platform == "win32"
            and not os.environ.get("WT_SESSION")
            and not os.environ.get("TERMINUS_SUCKS")
            and sys.stdout.encoding != "utf-8"
        )
        console = Console(emoji=not is_legacy_windows)
    else:
        console = SimpleConsole()

    try:
        version = metadata.version("project-scriber")
    except metadata.PackageNotFoundError:
        version = "1.0.0 (local)"

    parser = argparse.ArgumentParser(
        description="Scriber: An intelligent tool to map, analyze, and compile project source code for LLM context.")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s v{version}",
                        help="Show the version number and exit.")
    subparsers = parser.add_subparsers(dest="command", title="Commands")

    init_parser = subparsers.add_parser("init", help="Create a new configuration file interactively.")
    init_parser.set_defaults(func=lambda args: handle_init(args, console, RICH_AVAILABLE))

    run_parser = subparsers.add_parser("run", help="Map the project structure (default command).")
    exec_mode = os.environ.get('SCRIBER_EXEC_MODE')
    default_path = Path.cwd().parent if exec_mode == 'RUN_PY' else Path.cwd()
    if exec_mode == 'RUN_PY':
        del os.environ['SCRIBER_EXEC_MODE']

    run_parser.add_argument("root_path", nargs="?", default=os.environ.get("PROJECT_SCRIBER_ROOT", default_path),
                            type=Path,
                            help="The root directory of the project to map. Defaults to the current directory.")
    run_parser.add_argument("-o", "--output", help="The name of the output file. Overrides config file settings.")
    run_parser.add_argument("--config", default=os.environ.get("PROJECT_SCRIBER_CONFIG"), type=Path,
                            help="Path to a custom configuration file.")
    run_parser.add_argument("-c", "--copy", action="store_true", help="Copy the final output to the clipboard.")
    run_parser.add_argument("--copy-only", action="store_true",
                            help="Generate the output and copy it to the clipboard without saving to a file.")
    run_parser.add_argument("--tree-only", action="store_true",
                            help="Generate only the file tree structure without file content.")
    run_parser.add_argument("--single-process", action="store_true",
                            help="Run in a single process to avoid issues in daemonic environments.")
    run_parser.set_defaults(func=lambda args: run_scriber(args, console, version, RICH_AVAILABLE))

    args_to_parse = sys.argv[1:]
    global_flags = ['-h', '--help', '-v', '--version']

    if not args_to_parse or args_to_parse[0] not in list(subparsers.choices) + global_flags:
        args_to_parse.insert(0, 'run')

    args = parser.parse_args(args_to_parse)

    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()