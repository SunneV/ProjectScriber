from __future__ import annotations

from pathlib import Path
from scriber.tokens import estimate_tokens
from scriber.core.models import TokenConfig
from scriber.core.config import load_config


def test_token_estimation_default() -> None:
    text = "hello world"
    # default chars_per_token is 4, len("hello world") == 11, 11 // 4 == 2
    assert estimate_tokens(text) == 2


def test_token_estimation_custom_config() -> None:
    text = "hello world"
    config = TokenConfig(estimator="chars", chars_per_token=2)
    # len("hello world") == 11, 11 // 2 == 5
    assert estimate_tokens(text, config) == 5


def test_token_estimation_parsing_from_config(tmp_path: Path) -> None:
    config_file = tmp_path / "pyproject.toml"
    config_file.write_text(
        """
[tool.scriber.tokens]
estimator = "chars"
chars_per_token = 5
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_file)
    assert config.tokens.estimator == "chars"
    assert config.tokens.chars_per_token == 5

    text = "hello world"
    # len("hello world") == 11, 11 // 5 == 2
    assert estimate_tokens(text, config.tokens) == 2
