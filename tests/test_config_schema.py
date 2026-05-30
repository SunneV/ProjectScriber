from __future__ import annotations

from pathlib import Path
from scriber.core.config import load_config


def test_config_schema_parsing(tmp_path: Path) -> None:
    config_file = tmp_path / "pyproject.toml"
    config_file.write_text("""
[tool.scriber]
format = "txt"
max_tokens = 50000
max_files = 30
only_tree = true
allow_external_paths = true

[tool.scriber.modules]
enabled = false
content_min_score = 40

[tool.scriber.code_files]
patterns = ["**/*.py", "**/*.rs"]

[tool.scriber.support_files]
enabled = true
patterns = ["pyproject.toml", "Dockerfile"]

[tool.scriber.support_files.content]
default = "tree_only"
auto_max_bytes = 20000
full = ["pyproject.toml"]
tree_only = ["Dockerfile"]

[tool.scriber.hard_ignore]
patterns = [".git/**", "node_modules/**"]
""".strip(), encoding="utf-8")

    config = load_config(config_file)
    
    assert config.format == "txt"
    assert config.max_tokens == 50000
    assert config.max_files == 30
    assert config.only_tree is True
    assert config.allow_external_paths is True
    
    assert config.modules is False
    assert config.modules_config.enabled is False
    assert config.modules_config.content_min_score == 40
    
    assert config.code_patterns == ["**/*.py", "**/*.rs"]
    
    assert config.support is True
    assert config.support_patterns == ["pyproject.toml", "Dockerfile"]
    
    assert config.support_content.default == "tree_only"
    assert config.support_content.auto_max_bytes == 20000
    assert config.support_content.full == ["pyproject.toml"]
    assert config.support_content.tree_only == ["Dockerfile"]
    
    assert config.hard_ignore_patterns == [".git/**", "node_modules/**"]


def test_validate_config_cli(tmp_path: Path, monkeypatch) -> None:
    from scriber.cli.main import main

    # 1. Valid config
    config_file = tmp_path / "pyproject.toml"
    config_file.write_text("[tool.scriber]\nformat = 'md'\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    code = main(["--validate-config"])
    assert code == 0

    # 2. Invalid config format
    config_file.write_text("[tool.scriber]\nformat = 'invalid'\n", encoding="utf-8")
    code = main(["--validate-config"])
    assert code == 1
