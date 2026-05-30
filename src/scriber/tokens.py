from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scriber.core.models import TokenConfig


def estimate_tokens(text: str, config: TokenConfig | None = None) -> int:
    if config is None:
        return max(1, len(text) // 4)
    if config.estimator == "chars":
        return max(1, len(text) // config.chars_per_token)
    return max(1, len(text) // 4)
