import argparse
import sys
import re
from pathlib import Path

# Must be run from project root, or specify path
try:
    import tomli
except ImportError:
    import tomllib as tomli


def get_version(root: Path) -> str:
    with open(root / "pyproject.toml", "rb") as f:
        data = tomli.load(f)
    return data["project"]["version"]


def generate_cli_options() -> str:
    # We must import scriber to build the parser
    # Assume we run it inside the environment
    from scriber.cli.main import build_parser

    parser = build_parser()

    lines = ["| Option | Description |", "|:---|:---|"]
    for action in parser._actions:
        if action.dest == "help":
            continue

        flags = ", ".join(action.option_strings)
        if not flags:
            flags = action.dest

        help_text = action.help or ""
        lines.append(f"| `{flags}` | {help_text} |")

    return "\n".join(lines)


def generate_profiles() -> str:
    from scriber.core.profiles import PROFILE_CHOICES

    lines = [
        "### Profiles",
        "",
        "ProjectScriber comes with several preset profiles to quickly bias the file scoring and inclusion criteria:",
        "",
        "| Profile | Description |",
        "|:---|:---|",
    ]

    descriptions = {
        "default": "Standard scoring behavior.",
        "audit": "Boosts tests, config files, CI environments, and dependency files. Assumes full support content inclusion.",
        "debug": "Boosts direct/reverse dependencies, tests, runtime support, and files close to the seed path.",
        "refactor": "Boosts files within the same package, related tests, and direct dependencies.",
        "docs": "Heavily boosts documentation files while suppressing test and code file scores. Assumes tree_only support content by default.",
    }

    for p in PROFILE_CHOICES:
        lines.append(f"| `{p}` | {descriptions.get(p, '')} |")

    return "\n".join(lines)


def sync_readme(root: Path, write: bool = False) -> bool:
    readme_path = root / "README.md"
    content = readme_path.read_text(encoding="utf-8")
    original_content = content

    version = get_version(root)

    # 1. Update Version tags
    version_pattern = re.compile(
        r"<!-- BEGIN SCRIBER:VERSION -->.*?<!-- END SCRIBER:VERSION -->", re.DOTALL
    )
    content = version_pattern.sub(
        f"<!-- BEGIN SCRIBER:VERSION -->{version}<!-- END SCRIBER:VERSION -->", content
    )

    # 2. Update CLI Options
    cli_options = generate_cli_options()
    cli_pattern = re.compile(
        r"<!-- BEGIN SCRIBER:CLI_OPTIONS -->.*?<!-- END SCRIBER:CLI_OPTIONS -->",
        re.DOTALL,
    )
    content = cli_pattern.sub(
        f"<!-- BEGIN SCRIBER:CLI_OPTIONS -->\n{cli_options}\n<!-- END SCRIBER:CLI_OPTIONS -->",
        content,
    )

    # 3. Update Profiles
    profiles = generate_profiles()
    profiles_pattern = re.compile(
        r"<!-- BEGIN SCRIBER:PROFILES -->.*?<!-- END SCRIBER:PROFILES -->", re.DOTALL
    )
    content = profiles_pattern.sub(
        f"<!-- BEGIN SCRIBER:PROFILES -->\n{profiles}\n<!-- END SCRIBER:PROFILES -->",
        content,
    )

    # Also enforce 2.x references
    content = re.sub(
        r"\*\*Version 2\.\d+(\.\d+)?\*\*", f"**Version {version}**", content
    )
    content = re.sub(
        r"ProjectScriber 2\.\d+(\.\d+)?", f"ProjectScriber {version}", content
    )
    content = re.sub(r"Scriber 2\.\d+(\.\d+)?", f"Scriber {version}", content)

    if content == original_content:
        print("README.md is up to date.")
        return True

    if write:
        readme_path.write_text(content, encoding="utf-8")
        print("README.md has been updated.")
        return True
    else:
        print(
            "Error: README.md is stale. Run 'python scripts/sync_readme.py --write' to update."
        )
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write", action="store_true", help="Write changes to README.md"
    )
    parser.add_argument(
        "--check", action="store_true", help="Check if README.md is up to date"
    )
    args = parser.parse_args()

    root = Path(__file__).parent.parent
    if args.write:
        sys.exit(0 if sync_readme(root, write=True) else 1)
    elif args.check:
        sys.exit(0 if sync_readme(root, write=False) else 1)
    else:
        parser.print_help()
