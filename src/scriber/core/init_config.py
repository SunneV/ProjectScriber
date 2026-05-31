from __future__ import annotations

from pathlib import Path
from scriber.core.errors import ScriberError
from scriber.core.config import DEFAULT_CONFIG_BLOCK


def replace_existing_tool_scriber_block(content: str, default_block: str) -> str:
    lines = content.splitlines()
    new_lines = []
    in_scriber = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            header = stripped[1:-1].strip()
            if header == "tool.scriber" or header.startswith("tool.scriber."):
                in_scriber = True
                continue
            else:
                in_scriber = False

        if not in_scriber:
            new_lines.append(line)

    cleaned = "\n".join(new_lines).strip()
    if cleaned:
        return cleaned + "\n\n" + default_block + "\n"
    return default_block + "\n"


def init_project(config_path: str | None = None, force: bool = False) -> Path:
    path = Path(config_path or "pyproject.toml")
    if path.is_dir():
        path = path / "pyproject.toml"
    if not path.is_absolute():
        path = Path.cwd() / path

    if path.exists():
        content = path.read_text(encoding="utf-8")
        has_scriber = "[tool.scriber]" in content

        if has_scriber and not force:
            raise ScriberError(
                "Scriber config already exists. Use --force to replace it."
            )

        if has_scriber:
            new_content = replace_existing_tool_scriber_block(
                content, DEFAULT_CONFIG_BLOCK
            )
        else:
            if content and not content.endswith("\n"):
                content += "\n"
            new_content = content + "\n" + DEFAULT_CONFIG_BLOCK + "\n"

        path.write_text(new_content, encoding="utf-8")
    else:
        path.write_text(DEFAULT_CONFIG_BLOCK + "\n", encoding="utf-8")

    return path
