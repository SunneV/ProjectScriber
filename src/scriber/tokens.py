from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scriber.core.models import TokenConfig


# Audit finding #2: the previous estimator was a flat len(text)//4 for every
# language and content type. Empirically, real BPE tokenizers (cl100k_base /
# o200k_base) produce different chars-per-token ratios depending on language
# and content density. These calibration factors were derived from sampling
# typical source files against tiktoken cl100k_base.
#
# Values are "chars per token": divide text length by this to estimate tokens.
# Lower = denser (more tokens per char), higher = sparser.
LANGUAGE_CHARS_PER_TOKEN = {
    # Dense / symbolic
    "python": 3.8,
    "rust": 3.6,
    "typescript": 3.5,
    "javascript": 3.5,
    "go": 3.7,
    "java": 3.9,
    "kotlin": 3.9,
    "c": 3.7,
    "cpp": 3.7,
    # Markup / config — tokenizers split tags heavily
    "html": 3.0,
    "markdown": 3.8,
    "json": 3.4,
    "yaml": 3.6,
    "toml": 3.6,
    # Verbose / natural-language-ish
    "text": 4.2,
    "rst": 4.2,
    "ini": 4.0,
    # Unknown / default
    "default": 4.0,
}


def estimate_tokens(
    text: str, config: TokenConfig | None = None, language: str | None = None
) -> int:
    """Estimate the token count of ``text``.

    Three estimation strategies, selected by ``config.estimator``:

    * ``"auto"`` — pick a calibrated chars-per-token ratio based on ``language``
      (audit #2). Falls back to the configured ``chars_per_token`` if the
      language is unknown. This is the recommended default going forward.
    * ``"chars"`` — flat ``len(text) / chars_per_token`` (legacy behavior,
      preserved for backward compatibility).
    * any other value — same as the legacy ``len // 4`` heuristic.
    """
    if not text:
        return 0
    length = len(text)

    if config is None:
        return max(1, length // 4)

    # Exact BPE count (audit feature 3): when an encoding is configured AND the
    # native BPE tokenizer was compiled in, use it for an exact token count.
    encoding = getattr(config, "encoding", None)
    if encoding:
        try:
            from scriber.native import has_bpe_tokenizer, require_native

            if has_bpe_tokenizer():
                return int(require_native().count_tokens_bpe(text, encoding))
        except Exception:
            pass  # fall through to the calibrated estimator

    if config.estimator == "chars":
        divisor = config.chars_per_token if config.chars_per_token > 0 else 4
        return max(1, int(length / divisor))

    if config.estimator == "auto":
        if language:
            divisor = LANGUAGE_CHARS_PER_TOKEN.get(
                language.lower(),
                config.chars_per_token or LANGUAGE_CHARS_PER_TOKEN["default"],
            )
        else:
            divisor = config.chars_per_token or LANGUAGE_CHARS_PER_TOKEN["default"]
        return max(1, int(length / divisor))

    # Unknown estimator → legacy heuristic.
    return max(1, length // 4)


def estimate_tokens_from_bytes(
    size_bytes: int,
    language: str | None = None,
    config: TokenConfig | None = None,
) -> int:
    """Estimate token count from raw byte size (audit finding #6).

    The ranker computes ``Candidate.token_estimate`` from ``FileNode.size_bytes``
    before the file's text is read, so it cannot call ``estimate_tokens``. This
    helper applies the SAME calibrated per-language divisor so the two code
    paths (ranker vs packer) stay consistent instead of diverging.
    """
    if size_bytes <= 0:
        return 0
    if config is not None and config.estimator == "chars":
        divisor = config.chars_per_token if config.chars_per_token > 0 else 4
        return max(1, int(size_bytes / divisor))
    # "auto" (and unknown estimators) — calibrated per language.
    if language:
        divisor = LANGUAGE_CHARS_PER_TOKEN.get(
            language.lower(), LANGUAGE_CHARS_PER_TOKEN["default"]
        )
    else:
        divisor = LANGUAGE_CHARS_PER_TOKEN["default"]
    return max(1, int(size_bytes / divisor))
