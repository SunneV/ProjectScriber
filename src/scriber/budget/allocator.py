from __future__ import annotations
from dataclasses import dataclass
from scriber.core.models import Candidate, ContentMode, PackItem


@dataclass(slots=True)
class BudgetPolicy:
    target_tokens: int
    hard_limit_tokens: int
    mode: str = "full"


# Token weight per content mode (audit finding #28). Every mode now consumes the
# budget counter — previously only "full" did, making the budget gate symbolic.
# Weights reflect how much of the file actually lands in the output.
MODE_TOKEN_WEIGHT: dict[ContentMode, float] = {
    "full": 1.0,
    "excerpt": 0.25,
    "outline": 0.12,
    "tree": 0.02,
    "omit": 0.0,
}


def allocate_budget(
    candidates: list[Candidate], policy: BudgetPolicy, explicit_seeds: set
) -> list[PackItem]:
    items = []

    current_tokens = 0
    # Reserve a slice for graph/header/outline framing so full-code content
    # cannot starve structural sections (audit #28).
    full_budget = int(policy.target_tokens * 0.85)
    hard_limit = policy.hard_limit_tokens

    def within_budget(token_estimate: int, mode: ContentMode) -> bool:
        """True if adding this item (in given mode) stays under hard limit."""
        if hard_limit <= 0:
            return True  # unlimited
        cost = int(token_estimate * MODE_TOKEN_WEIGHT[mode])
        return current_tokens + cost <= hard_limit

    for i, c in enumerate(candidates):
        item_id = f"F{i + 1:03d}"
        role = getattr(c, "role", "unknown")

        mode: ContentMode = "tree"
        is_seed = c.file.relative in explicit_seeds

        # Seed files are always full, regardless of budget (explicit user intent).
        if is_seed:
            mode = "full"
        elif c.file.content_policy == "tree_only":
            mode = "tree"
        elif c.file.content_policy == "full" and policy.mode != "focused":
            mode = "full"
        elif (
            c.token_estimate <= 1200
            and c.score >= 80
            and within_budget(c.token_estimate, "full")
        ):
            mode = "full"
        elif (
            c.score >= 85
            and c.token_estimate <= 2400
            and within_budget(c.token_estimate, "full")
            and current_tokens < full_budget
        ):
            mode = "full"
        elif c.score >= 75 and within_budget(c.token_estimate, "excerpt"):
            mode = "excerpt"
        elif c.score >= 45 and within_budget(c.token_estimate, "outline"):
            mode = "outline"
        else:
            # Fallback: degrade gracefully rather than exceeding hard limit.
            if within_budget(c.token_estimate, "outline"):
                mode = "outline"
            else:
                mode = "tree"

        # Every mode now contributes to the budget counter (audit #28).
        current_tokens += int(c.token_estimate * MODE_TOKEN_WEIGHT[mode])

        item = PackItem(
            file=c.file,
            score=c.score,
            role=role,
            content_mode=mode,
            reason=c.reason_summary,
            reasons=c.reasons,
            relation_evidence=[],
            token_estimate=c.token_estimate,
            utility=c.utility,
            raw_score=c.raw_score,
            item_id=item_id,
        )
        items.append(item)

    return items
