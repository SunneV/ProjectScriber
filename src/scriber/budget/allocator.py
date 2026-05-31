from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from scriber.core.models import Candidate, ContentMode, PackItem, FileRole

@dataclass(slots=True)
class BudgetPolicy:
    target_tokens: int
    hard_limit_tokens: int
    mode: str = "full"
    header_budget_ratio: float = 0.12
    graph_budget_ratio: float = 0.08
    full_code_budget_ratio: float = 0.55
    outline_budget_ratio: float = 0.20
    reserve_ratio: float = 0.05

def allocate_budget(candidates: list[Candidate], policy: BudgetPolicy, explicit_seeds: set) -> list[PackItem]:
    items = []
    
    current_tokens = 0
    full_budget = int(policy.target_tokens * policy.full_code_budget_ratio)
    
    for i, c in enumerate(candidates):
        item_id = f"F{i+1:03d}"
        role = getattr(c, "role", "unknown")
        
        mode: ContentMode = "tree"
        
        is_seed = c.file.relative in explicit_seeds
        
        if is_seed:
            mode = "full"
        elif c.file.content_policy == "tree_only":
            mode = "tree"
        elif c.file.content_policy == "full" and policy.mode != "focused":
            mode = "full"
        elif c.token_estimate <= 1200 and c.score >= 80 and current_tokens < full_budget:
            mode = "full"
        elif c.score >= 85 and c.token_estimate <= 2400 and current_tokens < full_budget:
            mode = "full"
        elif c.score >= 75:
            mode = "excerpt"
        elif c.score >= 45:
            mode = "outline"
        else:
            mode = "tree"
            
        if mode == "full":
            current_tokens += c.token_estimate
            
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
            item_id=item_id
        )
        items.append(item)
        
    return items
