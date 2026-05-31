from __future__ import annotations

from pathlib import Path

from scriber.core.matchers import match_pattern
from scriber.core.models import (
    Candidate,
    FileNode,
    ModuleGraph,
    ScriberConfig,
    SeedPath,
    RelationEdge,
)


def _score(config: ScriberConfig, key: str) -> int:
    return int(config.modules_config.scoring.get(key, 0))


def _add_reason(
    candidate: Candidate, kind: str, label: str, example: Path | None = None
) -> None:
    candidate.reason_counts[kind] = candidate.reason_counts.get(kind, 0) + 1
    if example is not None:
        if kind not in candidate.reason_examples:
            candidate.reason_examples[kind] = []
        if example not in candidate.reason_examples[kind]:
            candidate.reason_examples[kind].append(example)
    if label not in candidate.reasons:
        candidate.reasons.append(label)


def _build_reason_summary(candidate: Candidate) -> str:
    parts = []
    for kind, count in candidate.reason_counts.items():
        examples = candidate.reason_examples.get(kind, [])
        if kind == "seed_file":
            parts.append("seed file")
        elif kind == "seed_folder_file":
            parts.append("seed folder file")
        elif kind == "direct_dependency":
            if count > 1:
                parts.append(f"imports {count} included files")
            elif examples:
                parts.append(f"imports {examples[0].name}")
            else:
                parts.append("imports seed")
        elif kind == "reverse_dependency":
            if count > 1:
                parts.append(f"imported by {count} included files")
            elif examples:
                parts.append(f"imported by {examples[0].name}")
            else:
                parts.append("imported by seed")
        elif kind == "related_test":
            parts.append("related test")
        elif kind == "same_package":
            parts.append("same package")
        elif kind == "parent_entrypoint":
            parts.append("parent entrypoint")
        elif kind == "name_similarity":
            parts.append("name similarity")
        elif kind == "support_near_seed":
            parts.append("support file")
        elif kind == "project_support":
            parts.append("project support file")
        elif kind == "shared_dependency":
            parts.append("shared dependency bonus")
        elif kind == "entrypoint":
            parts.append("entrypoint file")
        elif kind == "test_file":
            parts.append("test file")
        elif kind == "code_file":
            parts.append("code file")
        elif kind == "other_file":
            parts.append("other file")
        else:
            parts.append(kind.replace("_", " "))
    return "; ".join(parts)


def _add(
    candidates: dict[Path, Candidate],
    files: dict[Path, FileNode],
    rel: Path,
    score: int,
    kind: str,
    label: str,
    *,
    seed: Path | None = None,
) -> None:
    file = files.get(rel)
    if file is None:
        return
    existing = candidates.get(rel)
    if existing is None:
        existing = Candidate(file=file, score=score)
        candidates[rel] = existing
    else:
        existing.score = max(existing.score, score)

    _add_reason(existing, kind, label, example=seed)
    if seed is not None:
        existing.seed_sources.add(seed)


def _is_test_file(rel: Path, config: ScriberConfig) -> bool:
    parts = rel.parts[:-1] if len(rel.parts) > 1 else ()
    name = rel.name.lower()
    if any(part in set(config.python.test_roots) for part in parts):
        return True
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith(".test.py")
    )


def _name_related(a: Path, b: Path) -> bool:
    a_stem = a.stem.lower().replace("test_", "").replace("_test", "")
    b_stem = b.stem.lower().replace("test_", "").replace("_test", "")
    if not a_stem or not b_stem:
        return False
    return a_stem in b_stem or b_stem in a_stem


def _walk_weighted_neighbors(
    edges: list[RelationEdge], start: Path, depth_limit: int, reverse: bool = False
) -> dict[Path, float]:
    import heapq

    adj: dict[Path, list[tuple[Path, RelationEdge]]] = {}
    for edge in edges:
        u = edge.target if reverse else edge.source
        v = edge.source if reverse else edge.target
        adj.setdefault(u, []).append((v, edge))

    queue = [(-1.0, 0, start)]
    max_strength: dict[Path, float] = {start: 1.0}
    best_at_state: dict[tuple[Path, int], float] = {(start, 0): 1.0}

    while queue:
        neg_str, depth, u = heapq.heappop(queue)
        u_str = -neg_str

        if u_str < best_at_state.get((u, depth), 0.0):
            continue

        if depth >= depth_limit:
            continue

        for neighbor, edge in adj.get(u, []):
            if edge.kind in {"import", "reexport"}:
                edge_str = 1.0 if depth == 0 else 0.88
            else:
                edge_str = edge.weight * edge.confidence

            next_str = u_str * edge_str
            next_depth = depth + 1

            if next_str > max_strength.get(neighbor, 0.0):
                max_strength[neighbor] = next_str

            if next_str > best_at_state.get((neighbor, next_depth), 0.0):
                best_at_state[(neighbor, next_depth)] = next_str
                heapq.heappush(queue, (-next_str, next_depth, neighbor))

    if start in max_strength:
        del max_strength[start]

    return max_strength


def _walk_neighbors(
    edges: dict[Path, set[Path]], start: Path, depth: int
) -> dict[Path, int]:
    found: dict[Path, int] = {}
    frontier = {start}
    visited = {start}
    for distance in range(1, max(1, depth) + 1):
        next_frontier: set[Path] = set()
        for item in frontier:
            for neighbor in edges.get(item, set()):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                found.setdefault(neighbor, distance)
                next_frontier.add(neighbor)
        frontier = next_frontier
        if not frontier:
            break
    return found


def _support_base_score(file: FileNode, config: ScriberConfig) -> int:
    category = file.support_category or "support file"
    if category == "project config":
        return _score(config, "project_config")
    if category == "dependency file":
        return _score(config, "dependency_file")
    if category in {
        "runtime support",
        "runtime config",
        "ci support",
        "tooling config",
    }:
        return _score(config, "runtime_support")
    if category == "documentation":
        return _score(config, "documentation")
    return _score(config, "documentation")


def _is_near_seed(support_file: Path, seed: Path) -> bool:
    if support_file.parent == Path("."):
        return True
    seed_parent = seed.parent
    return (
        support_file.parent == seed_parent
        or support_file.parent in seed_parent.parents
        or seed_parent in support_file.parent.parents
    )


def _matches_entrypoint(rel: Path, config: ScriberConfig) -> bool:
    return any(
        match_pattern(rel.name, pattern)
        for pattern in config.python.entrypoint_patterns
    )


def score_candidates_project_snapshot(
    *,
    files: dict[Path, FileNode],
    graph: ModuleGraph,
    config: ScriberConfig,
) -> list[Candidate]:
    candidates: dict[Path, Candidate] = {}

    for rel, file in files.items():
        if file.kind == "code":
            if _matches_entrypoint(rel, config):
                _add(
                    candidates,
                    files,
                    rel,
                    _score(config, "entrypoint_file"),
                    "entrypoint",
                    "entrypoint file",
                )
            elif _is_test_file(rel, config):
                _add(
                    candidates,
                    files,
                    rel,
                    _score(config, "test_file"),
                    "test_file",
                    "test file",
                )
            else:
                _add(
                    candidates,
                    files,
                    rel,
                    _score(config, "code_file"),
                    "code_file",
                    "code file",
                )
        elif file.kind == "support" and config.support:
            base = _support_base_score(file, config)
            category = file.support_category or "support file"
            _add(candidates, files, rel, base, "project_support", category)
        elif file.kind == "other":
            _add(
                candidates,
                files,
                rel,
                _score(config, "other_file"),
                "other_file",
                "other file",
            )

    for candidate in candidates.values():
        candidate.reason_summary = _build_reason_summary(candidate)

    filtered = [
        candidate
        for rel, candidate in candidates.items()
        if candidate.score >= config.min_score
        or candidate.score >= config.modules_config.tree_min_score
    ]
    filtered.sort(
        key=lambda item: (
            -item.score,
            item.file.kind != "code",
            item.file.relative.as_posix(),
        )
    )

    if config.max_files > 0 and len(filtered) > config.max_files:
        pinned = [
            c
            for c in filtered
            if c.file.relative.name in {"pyproject.toml", "README.md"}
        ]
        rest = [
            c
            for c in filtered
            if c.file.relative.name not in {"pyproject.toml", "README.md"}
        ]
        remaining = max(0, config.max_files - len(pinned))
        filtered = pinned + rest[:remaining]
        filtered.sort(
            key=lambda item: (
                -item.score,
                item.file.kind != "code",
                item.file.relative.as_posix(),
            )
        )

    return filtered


def score_candidates(
    *,
    files: dict[Path, FileNode],
    seeds: list[SeedPath],
    graph: ModuleGraph,
    config: ScriberConfig,
    mode: str = "focused",
) -> list[Candidate]:
    if mode == "project_snapshot":
        return score_candidates_project_snapshot(
            files=files, graph=graph, config=config
        )

    candidates: dict[Path, Candidate] = {}
    scoring = config.modules_config
    seed_files = [file for seed in seeds for file in seed.expanded_files]
    seed_set = set(seed_files)

    for seed in seeds:
        for rel in seed.expanded_files:
            key = "seed_folder_file" if seed.is_dir else "seed_file"
            reason = (
                f"file inside seed folder `{seed.relative.as_posix()}`"
                if seed.is_dir
                else "seed file"
            )
            _add(
                candidates,
                files,
                rel,
                _score(config, key),
                "seed_folder_file" if seed.is_dir else "seed_file",
                reason,
                seed=rel,
            )

    if config.modules and scoring.enabled:
        for seed_rel in seed_files:
            if scoring.include_direct_dependencies:
                for dep, strength in _walk_weighted_neighbors(
                    graph.edges, seed_rel, scoring.depth, reverse=False
                ).items():
                    score = max(
                        scoring.tree_min_score,
                        int(_score(config, "direct_dependency") * strength),
                    )
                    _add(
                        candidates,
                        files,
                        dep,
                        score,
                        "direct_dependency",
                        f"direct dependency of `{seed_rel.as_posix()}`",
                        seed=seed_rel,
                    )

            if scoring.include_reverse_dependencies:
                for dep, strength in _walk_weighted_neighbors(
                    graph.edges, seed_rel, scoring.depth, reverse=True
                ).items():
                    score = max(
                        scoring.tree_min_score,
                        int(_score(config, "reverse_dependency") * strength),
                    )
                    _add(
                        candidates,
                        files,
                        dep,
                        score,
                        "reverse_dependency",
                        f"imports seed `{seed_rel.as_posix()}`",
                        seed=seed_rel,
                    )

            if scoring.include_same_package:
                seed_parent = seed_rel.parent
                for rel, file in files.items():
                    if (
                        file.kind == "code"
                        and rel.parent == seed_parent
                        and rel not in seed_set
                    ):
                        _add(
                            candidates,
                            files,
                            rel,
                            _score(config, "same_package"),
                            "same_package",
                            f"same package as `{seed_rel.as_posix()}`",
                            seed=seed_rel,
                        )

            if scoring.include_parent_entrypoints:
                for rel, file in files.items():
                    if file.kind == "code" and _matches_entrypoint(rel, config):
                        if (
                            rel.parent == Path(".")
                            or rel.parent in seed_rel.parents
                            or seed_rel.parent in rel.parents
                        ):
                            _add(
                                candidates,
                                files,
                                rel,
                                _score(config, "parent_entrypoint"),
                                "parent_entrypoint",
                                f"parent/entrypoint near `{seed_rel.as_posix()}`",
                                seed=seed_rel,
                            )

            if scoring.include_tests:
                for rel, file in files.items():
                    if file.kind != "code" or not _is_test_file(rel, config):
                        continue
                    if _name_related(rel, seed_rel) or seed_rel in graph.imports.get(
                        rel, set()
                    ):
                        _add(
                            candidates,
                            files,
                            rel,
                            _score(config, "related_test"),
                            "related_test",
                            f"related test for `{seed_rel.as_posix()}`",
                            seed=seed_rel,
                        )

            for rel, file in files.items():
                if (
                    file.kind == "code"
                    and rel not in seed_set
                    and _name_related(rel, seed_rel)
                ):
                    _add(
                        candidates,
                        files,
                        rel,
                        _score(config, "name_similarity"),
                        "name_similarity",
                        f"name similarity with `{seed_rel.as_posix()}`",
                        seed=seed_rel,
                    )

        if config.support:
            for rel, file in files.items():
                if file.kind != "support":
                    continue
                base = _support_base_score(file, config)
                reason = file.support_category or "support file"
                if rel.name == "pyproject.toml":
                    _add(
                        candidates,
                        files,
                        rel,
                        _score(config, "project_config"),
                        "project_support",
                        "project config/root file",
                    )
                    continue
                added = False
                for seed_rel in seed_files:
                    if _is_near_seed(rel, seed_rel):
                        _add(
                            candidates,
                            files,
                            rel,
                            max(base, _score(config, "support_near_seed")),
                            "support_near_seed",
                            f"{reason} near `{seed_rel.as_posix()}`",
                            seed=seed_rel,
                        )
                        added = True
                if (
                    not added
                    and file.relative.parent == Path(".")
                    and scoring.include_project_configs
                ):
                    _add(candidates, files, rel, base, "project_support", reason)
    else:
        if config.support:
            pyproject = files.get(Path("pyproject.toml"))
            if pyproject:
                _add(
                    candidates,
                    files,
                    Path("pyproject.toml"),
                    _score(config, "project_config"),
                    "project_support",
                    "project config/root file",
                )

    for candidate in candidates.values():
        if len(candidate.seed_sources) > 1:
            candidate.score = min(
                100, candidate.score + _score(config, "shared_dependency_bonus")
            )
            _add_reason(candidate, "shared_dependency", "shared by multiple seed paths")

    for candidate in candidates.values():
        candidate.reason_summary = _build_reason_summary(candidate)

    required = set(seed_files)
    filtered = [
        candidate
        for rel, candidate in candidates.items()
        if rel in required
        or candidate.score >= config.min_score
        or candidate.score >= config.modules_config.tree_min_score
    ]
    filtered.sort(
        key=lambda item: (
            -item.score,
            item.file.kind != "code",
            item.file.relative.as_posix(),
        )
    )

    if config.max_files > 0 and len(filtered) > config.max_files:
        seeds_first = [
            candidate
            for candidate in filtered
            if candidate.file.relative in required
            or candidate.file.relative.name in {"pyproject.toml", "README.md"}
        ]
        rest = [
            candidate
            for candidate in filtered
            if candidate.file.relative not in required
            and candidate.file.relative.name not in {"pyproject.toml", "README.md"}
        ]
        remaining = max(0, config.max_files - len(seeds_first))
        filtered = seeds_first + rest[:remaining]
        filtered.sort(
            key=lambda item: (
                -item.score,
                item.file.kind != "code",
                item.file.relative.as_posix(),
            )
        )

    return filtered
