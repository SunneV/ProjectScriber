from __future__ import annotations

import pytest
from pathlib import Path
from scriber.core.errors import ScriberError
from scriber.core.init_config import init_project, replace_existing_tool_scriber_block


def test_replace_existing_block() -> None:
    content = """
[build-system]
requires = ["setuptools>=61"]

[tool.scriber]
version = "1"

[tool.scriber.code_files]
patterns = ["*.py"]

[tool.pytest.ini_options]
addopts = "-q"
""".strip()

    default_block = """
[tool.scriber]
version = "2"
""".strip()

    expected = (
        """
[build-system]
requires = ["setuptools>=61"]

[tool.pytest.ini_options]
addopts = "-q"

[tool.scriber]
version = "2"
""".strip()
        + "\n"
    )

    res = replace_existing_tool_scriber_block(content, default_block)
    assert res == expected


def test_init_project_file_missing(tmp_path: Path) -> None:
    config_path = tmp_path / "pyproject.toml"
    assert not config_path.exists()

    path = init_project(str(config_path))
    assert path == config_path.resolve()
    assert config_path.exists()
    assert "[tool.scriber]" in config_path.read_text(encoding="utf-8")


def test_init_project_exists_no_scriber(tmp_path: Path) -> None:
    config_path = tmp_path / "pyproject.toml"
    config_path.write_text("[build-system]\n", encoding="utf-8")

    init_project(str(config_path))
    content = config_path.read_text(encoding="utf-8")
    assert "[build-system]" in content
    assert "[tool.scriber]" in content


def test_init_project_exists_with_scriber_raises(tmp_path: Path) -> None:
    config_path = tmp_path / "pyproject.toml"
    config_path.write_text("[tool.scriber]\nversion = '1'\n", encoding="utf-8")

    with pytest.raises(ScriberError, match="Scriber config already exists"):
        init_project(str(config_path))


def test_init_project_exists_with_scriber_force(tmp_path: Path) -> None:
    config_path = tmp_path / "pyproject.toml"
    config_path.write_text(
        """
[build-system]
requires = ["setuptools>=61"]

[tool.scriber]
version = '1'
""".strip()
        + "\n",
        encoding="utf-8",
    )

    init_project(str(config_path), force=True)
    content = config_path.read_text(encoding="utf-8")
    assert "[build-system]" in content
    assert "[tool.scriber]" in content
    assert "version = '1'" not in content  # must be replaced with the default block

    # Ensure there is exactly one [tool.scriber] header in pyproject.toml
    assert content.count("[tool.scriber]") == 1
