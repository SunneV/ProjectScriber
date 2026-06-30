from __future__ import annotations
from copy import deepcopy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scriber.core.models import ScriberConfig

PROFILE_CHOICES = (
    "default",
    "audit",
    "debug",
    "refactor",
    "docs",
    "gpt",
    "focused-gpt",
    "full",
)


def apply_profile(config: ScriberConfig, profile: str) -> ScriberConfig:
    if profile == "default" or not profile:
        return config

    cfg = deepcopy(config)
    scoring = cfg.modules_config.scoring

    if profile == "audit":
        scoring["test_file"] = 80
        scoring["project_config"] = 90
        scoring["dependency_file"] = 90
        scoring["runtime_support"] = 85
        scoring["documentation"] = 70

    elif profile == "debug":
        scoring["direct_dependency"] = 90
        scoring["reverse_dependency"] = 80
        scoring["test_file"] = 70
        scoring["runtime_support"] = 80
        scoring["support_near_seed"] = 80

    elif profile == "refactor":
        scoring["same_package"] = 80
        scoring["related_test"] = 90
        scoring["test_file"] = 75
        scoring["direct_dependency"] = 60

    elif profile == "docs":
        scoring["documentation"] = 95
        scoring["project_config"] = 50
        scoring["dependency_file"] = 30
        scoring["test_file"] = 10
        scoring["code_file"] = 30
        cfg.support_content.default = "tree_only"

    # LLM-optimized profiles (audit finding #19) — these previously triggered
    # the LlmPack path in packer/pack.py but were absent from --profile choices,
    # making them undiscoverable from the CLI.
    elif profile in {"gpt", "focused-gpt", "full"}:
        # No scoring overrides needed: these profiles are handled downstream
        # by rank_context + render_llm_report. Exposed here for discoverability.
        pass

    return cfg
