from __future__ import annotations
from pathlib import Path
import math
from collections import deque, defaultdict
from scriber.core.models import FileNode, RelationGraph, ScriberConfig, Candidate
from scriber.engine.roles import classify_file_role, ROLE_SCORE

RELATION_WEIGHT = {
    "import": 90,
    "reexport": 80,
    "test_of": 78,
    "entrypoint_to_module": 75,
    "config_refs_code": 58,
    "env_key": 52,
    "doc_mentions_code": 42,
    "git_cochange": 40,
    "same_package": 28,
    "same_dir": 20,
    "name_similarity": 18,
    "semantic_similarity": 15,
}

def rank_context(files: dict[Path, FileNode], graph: RelationGraph, seeds: list[Path], config: ScriberConfig, mode: str) -> list[Candidate]:
    candidates = []
    
    explicit_seeds = {s for s in seeds}

    distances = {}
    if mode == "focused":
        adj_out = defaultdict(list)
        adj_in = defaultdict(list)
        for edge in graph.edges:
            adj_out[edge.source].append(edge.target)
            adj_in[edge.target].append(edge.source)
            
        q_out = deque()
        q_in = deque()
        dist_out = {}
        dist_in = {}
        
        for s in explicit_seeds:
            if s in files:
                dist_out[s] = 0
                dist_in[s] = 0
                q_out.append(s)
                q_in.append(s)
                
        while q_out:
            curr = q_out.popleft()
            d = dist_out[curr]
            for nbr in adj_out[curr]:
                if nbr not in dist_out:
                    dist_out[nbr] = d + 1
                    q_out.append(nbr)
                    
        while q_in:
            curr = q_in.popleft()
            d = dist_in[curr]
            for nbr in adj_in[curr]:
                if nbr not in dist_in:
                    dist_in[nbr] = d + 1
                    q_in.append(nbr)
                    
        for rel in files.keys():
            d_out = dist_out.get(rel, 999)
            d_in = dist_in.get(rel, 999)
            distances[rel] = min(d_out, d_in)

    for rel, node in files.items():
        role = classify_file_role(node, graph)
        role_score = ROLE_SCORE.get(role, 20)
        
        relation_score = 0.0
        incoming = graph.incoming.get(rel, [])
        for edge in incoming:
            weight = RELATION_WEIGHT.get(edge.kind, 10) * edge.weight * edge.confidence
            relation_score += weight
            
        centrality_bonus = 0
        evidence_bonus = len(incoming) * 2
        noise_penalty = 0
        
        if node.language in {"json", "lock", "svg"}:
            noise_penalty += 50

        if mode == "focused":
            dist = distances.get(rel, 999)
            if dist == 0:
                decay = 1.0
                seed_bonus = 100
                max_score = 100
            elif dist == 1:
                decay = 1.0
                seed_bonus = 0
                max_score = 79
            elif dist == 2:
                decay = 0.5
                seed_bonus = 0
                max_score = 74
            else:
                decay = 0.1
                seed_bonus = 0
                max_score = 44
        else:
            decay = 1.0
            seed_bonus = 100 if rel in explicit_seeds else 0
            max_score = 100
            
        if mode == "focused" and role == "test" and rel not in explicit_seeds:
            noise_penalty += 80
            max_score = min(max_score, 44) # Force test files to tree mode unless specifically targeted
            
        raw_score = (role_score + relation_score + seed_bonus + centrality_bonus + evidence_bonus - noise_penalty) * decay
        
        token_estimate = node.size_bytes // 4
        utility = raw_score / math.sqrt(token_estimate + 200)
        
        c = Candidate(
            file=node,
            score=int(min(max_score, max(0, raw_score))), # clamp to distance-based max_score
            reasons=[f"Role {role}: {role_score}", f"Relations: {relation_score:.1f}"],
            include_content=False,
            token_estimate=token_estimate
        )
        
        object.__setattr__(c, "utility", utility)
        object.__setattr__(c, "raw_score", raw_score)
        object.__setattr__(c, "role", role)
        
        candidates.append(c)
        
    # Primary sort by utility, then score
    candidates.sort(key=lambda c: (getattr(c, "utility", 0), c.score), reverse=True)
    return candidates
