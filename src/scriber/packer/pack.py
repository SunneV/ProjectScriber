from __future__ import annotations

from pathlib import Path
from typing import Callable

from scriber.core.config import apply_overrides, load_config
from scriber.core.errors import ScriberError
from scriber.core.models import Candidate, FileNode, ScriberPack, SeedPath
from scriber.core.root import (
    ensure_inside_root,
    project_root_from_config,
    rel_to_root,
    resolve_config_path,
)
from scriber.engine.scorer import score_candidates
from scriber.rendering.renderer import render_pack
from scriber.scanner.files import classify_file, is_text_readable
from scriber.tokens import estimate_tokens
from scriber.scanner.scan import scan_project
from scriber.core.models import LlmPack


def _resolve_input(
    path_value: str, root: Path, allow_external: bool, path_base: str = "cwd"
) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        if path_base == "project":
            path = (root / path).resolve(strict=False)
        else:
            path = (Path.cwd() / path).resolve(strict=False)
    else:
        path = path.resolve(strict=False)
    if not path.exists():
        # Try relative to project root as a convenience for programmatic calls.
        alt = (root / path_value).resolve(strict=False)
        if alt.exists():
            path = alt
    if not path.exists():
        raise ScriberError(f"Input path not found: {path_value}")
    ensure_inside_root(path, root, allow_external)
    return path.resolve()


def _ensure_seed_file(
    path: Path, root: Path, files: dict[Path, FileNode], config
) -> FileNode:
    rel = rel_to_root(path, root)
    existing = files.get(rel)
    if existing is not None:
        return existing
    node = classify_file(path, root, config)
    if node is not None:
        files[rel] = node
        return node
    # Explicit seed overrides hard-ignore classification if it is readable text.
    node = FileNode(
        absolute=path.resolve(),
        relative=rel,
        kind="other",
        language="text",
        size_bytes=path.stat().st_size,
        is_binary=not is_text_readable(path),
        support_category=None,
        content_policy="auto",
    )
    files[rel] = node
    return node


def _expand_seed(
    path: Path, root: Path, files: dict[Path, FileNode], config
) -> SeedPath:
    rel = rel_to_root(path, root)
    if path.is_file():
        node = _ensure_seed_file(path, root, files, config)
        return SeedPath(
            original=Path(path),
            absolute=path,
            relative=rel,
            is_dir=False,
            expanded_files=[node.relative],
        )

    expanded: list[Path] = []
    for file_rel, node in files.items():
        try:
            file_rel.relative_to(rel)
        except ValueError:
            continue
        if not node.is_binary:
            expanded.append(file_rel)
    expanded.sort(key=lambda item: item.as_posix())
    if not expanded:
        raise ScriberError(
            f"No readable project files found inside seed folder: {rel.as_posix()}"
        )
    return SeedPath(
        original=Path(path),
        absolute=path,
        relative=rel,
        is_dir=True,
        expanded_files=expanded,
    )


def _decide_content(
    candidate: Candidate,
    *,
    config,
    only_tree: bool,
    budget_left: int | None,
    is_seed: bool,
) -> tuple[bool, str | None, str | None, int]:
    if only_tree:
        return False, None, "only-tree mode", 0
    file = candidate.file
    if file.is_binary:
        return False, None, "binary file", 0

    should_include = False
    reason: str | None = None

    if is_seed:
        should_include = True
    elif file.kind == "code":
        should_include = candidate.score >= config.modules_config.content_min_score
        if not should_include:
            reason = f"score below content_min_score={config.modules_config.content_min_score}"
    elif file.kind == "support":
        if file.content_policy == "tree_only":
            should_include = False
            reason = "support content policy: tree_only"
        elif file.content_policy == "full":
            should_include = True
        else:
            should_include = file.size_bytes <= config.support_content.auto_max_bytes
            if not should_include:
                reason = f"support file larger than auto_max_bytes={config.support_content.auto_max_bytes}"
    else:
        should_include = is_seed
        if not should_include:
            reason = "other file not selected for content"

    if not should_include:
        return False, None, reason, 0

    try:
        content = file.read_text()
    except OSError as exc:
        return False, None, f"read error: {exc}", 0

    tokens = estimate_tokens(content, config.tokens)
    if budget_left is not None and tokens > budget_left and not is_seed:
        return False, None, "token budget exceeded", 0
    return True, content, None, tokens


def _apply_content_policy(pack: ScriberPack, config) -> None:
    if pack.mode == "focused":
        explicit_seed_files = {
            rel for seed in pack.seed_paths for rel in seed.expanded_files
        }
    else:
        explicit_seed_files = {
            rel
            for seed in pack.seed_paths
            if not seed.is_dir
            for rel in seed.expanded_files
        }
    budget_left = config.max_tokens if config.max_tokens > 0 else None
    total = 0
    for candidate in pack.candidates:
        is_explicit_seed = candidate.file.relative in explicit_seed_files
        include, content, omitted, tokens = _decide_content(
            candidate,
            config=config,
            only_tree=pack.only_tree,
            budget_left=budget_left,
            is_seed=is_explicit_seed,
        )
        candidate.include_content = include
        candidate.content = content
        candidate.omitted_reason = omitted
        candidate.token_estimate = tokens
        if include:
            total += tokens
            if budget_left is not None and not is_explicit_seed:
                budget_left = max(0, budget_left - tokens)
    pack.total_tokens = total


def _load_and_apply_config(
    paths,
    config_path,
    profile,
    output,
    output_format,
    only_tree,
    modules,
    support,
    max_files,
    max_tokens,
    min_score,
    support_content,
):
    resolved_config = resolve_config_path(paths, config_path)
    root = project_root_from_config(resolved_config)
    config = load_config(resolved_config)
    from scriber.core.profiles import apply_profile

    config = apply_profile(config, profile)
    config = apply_overrides(
        config,
        output=output,
        output_format=output_format,
        only_tree=only_tree,
        modules=modules,
        support=support,
        max_files=max_files,
        max_tokens=max_tokens,
        min_score=min_score,
        support_content=support_content,
    )
    return resolved_config, root, config


def _scan_files(paths, root, config, path_base, progress_callback):
    if progress_callback:
        progress_callback("Skanowanie plikow...")
    from scriber.native import is_native_available

    native_files = None
    if is_native_available():
        from scriber.scanner.scan import scan_project_with_native

        files, native_files = scan_project_with_native(root, config)
    else:
        files = scan_project(root, config)
    resolved_inputs = [
        _resolve_input(item, root, config.allow_external_paths, path_base)
        for item in paths
    ]
    seeds = [_expand_seed(path, root, files, config) for path in resolved_inputs]

    is_project_snapshot = False
    for path in resolved_inputs:
        if path == root:
            is_project_snapshot = True
            break

    return files, native_files, seeds, is_project_snapshot


def _build_graph_and_score(
    mode, files, seeds, native_files, root, config, progress_callback
):
    from time import perf_counter

    timings = {}
    stats = {}
    from scriber.native import is_native_available

    if is_native_available():
        from scriber.native import require_native

        native = require_native()

        t_graph = perf_counter()
        if progress_callback:
            progress_callback("Budowanie grafu modulow (natywnie)...")

        assert native_files is not None

        edges = native.build_relation_graph(
            str(root),
            native_files,
            config.python.source_roots,
            config.python.module_init_files,
        )

        from scriber.graph.analyzers import generate_cheap_relations

        edges.extend(
            generate_cheap_relations(files, native.NativeRelationEdge, is_native=True)
        )

        from scriber.cache import ScriberCache

        cache = ScriberCache(config, root)

        from scriber.core.models import ModuleGraph, RelationEdge

        graph = ModuleGraph()
        for edge in edges:
            from_path = Path(getattr(edge, "source"))
            to_path = Path(edge.target)
            py_edge = RelationEdge(
                source=from_path,
                target=to_path,
                kind=edge.kind,
                weight=edge.weight,
                confidence=edge.confidence,
                evidence=edge.evidence,
                line=edge.line,
                analyzer=edge.analyzer,
            )
            graph.add_edge(py_edge)
            if py_edge.kind in {"import", "reexport"}:
                cache.add_import_edge(from_path, to_path)

        cache.save(set(files.keys()))

        stats["graph_edges_built"] = len(edges)
        stats["graph_source"] = "native"
        stats["graph_cache_reads"] = cache.reads
        stats["graph_cache_hits"] = cache.hits
        stats["graph_cache_writes"] = cache.writes

        timings["graph_build"] = perf_counter() - t_graph

        t_score = perf_counter()
        if progress_callback:
            progress_callback("Ocenianie zaleznosci (natywnie)...")
        scoring = config.modules_config.scoring
        opts = native.NativePackOptions(
            mode=mode,
            max_files=config.max_files,
            min_score=config.min_score,
            tree_min_score=config.modules_config.tree_min_score,
            seed_file_score=scoring.get("seed_file", 100),
            seed_folder_file_score=scoring.get("seed_folder_file", 100),
            direct_dependency_score=scoring.get("direct_dependency", 90),
            reverse_dependency_score=scoring.get("reverse_dependency", 85),
            same_package_score=scoring.get("same_package", 65),
            parent_entrypoint_score=scoring.get("parent_entrypoint", 60),
            related_test_score=scoring.get("related_test", 80),
            name_similarity_score=scoring.get("name_similarity", 45),
            support_near_seed_score=scoring.get("support_near_seed", 60),
            project_config_score=scoring.get("project_config", 55),
            dependency_file_score=scoring.get("dependency_file", 52),
            runtime_support_score=scoring.get("runtime_support", 50),
            documentation_score=scoring.get("documentation", 45),
            shared_dependency_bonus=scoring.get("shared_dependency_bonus", 10),
            entrypoint_file_score=scoring.get("entrypoint_file", 90),
            code_file_score=scoring.get("code_file", 80),
            test_file_score=scoring.get("test_file", 60),
            other_file_score=scoring.get("other_file", 40),
            modules_enabled=config.modules,
            include_direct_dependencies=config.modules_config.include_direct_dependencies,
            include_reverse_dependencies=config.modules_config.include_reverse_dependencies,
            include_same_package=config.modules_config.include_same_package,
            include_parent_entrypoints=config.modules_config.include_parent_entrypoints,
            include_tests=config.modules_config.include_tests,
            include_project_configs=config.modules_config.include_project_configs,
            depth=config.modules_config.depth,
            support_enabled=config.support,
            entrypoint_patterns=config.python.entrypoint_patterns,
            test_roots=config.python.test_roots,
        )

        rs_candidates = native.score_candidates_native(
            native_files, [seed.relative.as_posix() for seed in seeds], edges, opts
        )

        candidates = []
        for rc in rs_candidates:
            rel = Path(rc.path)
            file_node = files.get(rel)
            if file_node:
                c = Candidate(
                    file=file_node,
                    score=rc.score,
                    reasons=rc.reasons,
                    reason_summary=rc.reason_summary,
                    include_content=rc.include_content,
                    omitted_reason=rc.omitted_reason,
                )
                candidates.append(c)
        timings["scoring"] = perf_counter() - t_score
    else:
        t_graph = perf_counter()
        if progress_callback:
            progress_callback("Budowanie grafu modulow...")
        from scriber.cache import ScriberCache

        cache = ScriberCache(config, root)
        from scriber.graph.builder import build_graph

        graph = build_graph(files, config, cache)

        from scriber.graph.analyzers import generate_cheap_relations
        from scriber.core.models import RelationEdge

        cheap_edges = generate_cheap_relations(files, RelationEdge, is_native=False)
        for edge in cheap_edges:
            graph.add_edge(edge)

        stats["graph_edges_built"] = len(graph.edges)
        stats["graph_source"] = "python"
        stats["graph_cache_reads"] = cache.reads
        stats["graph_cache_hits"] = cache.hits
        stats["graph_cache_writes"] = cache.writes

        timings["graph_build"] = perf_counter() - t_graph

        t_score = perf_counter()
        if progress_callback:
            progress_callback("Ocenianie zaleznosci...")
        candidates = score_candidates(
            files=files, seeds=seeds, graph=graph, config=config, mode=mode
        )
        timings["scoring"] = perf_counter() - t_score

    return candidates, graph, timings, stats


def build_pack(
    paths: list[str] | None = None,
    *,
    config_path: str | None = None,
    profile: str | None = None,
    output: str | None = None,
    output_format: str | None = None,
    only_tree: bool | None = None,
    modules: bool | None = None,
    support: bool | None = None,
    max_files: int | None = None,
    max_tokens: int | None = None,
    min_score: int | None = None,
    support_content: str | None = None,
    progress_callback: Callable[[str], None] | None = None,
    project: bool | None = None,
    path_base: str = "project",
) -> ScriberPack | LlmPack:
    from time import perf_counter

    t_start = perf_counter()
    paths = paths or ["."]
    resolved_config, root, config = _load_and_apply_config(
        paths,
        config_path,
        profile,
        output,
        output_format,
        only_tree,
        modules,
        support,
        max_files,
        max_tokens,
        min_score,
        support_content,
    )
    t_config_load = perf_counter() - t_start

    t_scan = perf_counter()
    files, native_files, seeds, is_project_snapshot = _scan_files(
        paths, root, config, path_base, progress_callback
    )
    t_scan_time = perf_counter() - t_scan

    mode = "project_snapshot" if (project or is_project_snapshot) else "focused"

    if profile == "full":
        mode = "project_snapshot"
    elif profile == "focused-gpt":
        mode = "focused"

    candidates, graph, sub_timings, stats = _build_graph_and_score(
        mode, files, seeds, native_files, root, config, progress_callback
    )

    if profile in {"gpt", "focused-gpt", "full"}:
        from scriber.engine.ranker import rank_context
        from scriber.budget.allocator import allocate_budget, BudgetPolicy
        from time import perf_counter

        t_rank = perf_counter()
        if progress_callback:
            progress_callback("Rankowanie kontekstu...")
        seed_paths = [seed for p in seeds for seed in p.expanded_files]
        new_candidates = rank_context(files, graph, seed_paths, config, mode)
        sub_timings["rank_context"] = perf_counter() - t_rank

        t_budget = perf_counter()
        if progress_callback:
            progress_callback("Alokacja budzetu...")
        policy = BudgetPolicy(
            target_tokens=config.max_tokens if config.max_tokens > 0 else 30000,
            hard_limit_tokens=config.max_tokens if config.max_tokens > 0 else 100000,
            mode=mode,
        )
        if mode == "focused":
            explicit_seeds = {seed for p in seeds for seed in p.expanded_files}
        else:
            explicit_seeds = {
                seed for p in seeds if not p.is_dir for seed in p.expanded_files
            }

        items = allocate_budget(new_candidates, policy, explicit_seeds)
        sub_timings["budget_allocation"] = perf_counter() - t_budget

        t_content = perf_counter()
        if progress_callback:
            progress_callback("Czytanie i outline...")
        from scriber.outline import generate_outline

        actual_tokens = 0
        for item in items:
            if item.content_mode == "full":
                try:
                    item.content = item.file.read_text()
                    actual_tokens += item.token_estimate
                except Exception:
                    item.content_mode = "tree"
            elif item.content_mode in ("outline", "excerpt"):
                try:
                    content = item.file.read_text()
                    item.outline = generate_outline(item.file, content)
                    has_outline_symbols = bool(
                        item.outline.classes
                        or item.outline.functions
                        or item.outline.constants
                        or item.outline.imports
                    )
                    if item.content_mode == "excerpt" and not has_outline_symbols:
                        if actual_tokens + item.token_estimate <= policy.target_tokens:
                            item.content_mode = "full"
                            item.content = content
                            actual_tokens += item.token_estimate
                        else:
                            item.content_mode = "tree"
                    else:
                        actual_tokens += item.outline.token_estimate
                except Exception:
                    item.content_mode = "tree"

        sub_timings["content_read"] = perf_counter() - t_content

        stats["input_paths"] = paths
        pack = LlmPack(
            project_root=root,
            config_path=resolved_config,
            profile=profile,
            mode=mode,
            goal=None,
            budget_target=policy.target_tokens,
            budget_actual=actual_tokens,
            items=items,
            graph=graph,
            stats=stats,
            warnings=[],
        )
        pack.timings = {
            "config_load": t_config_load,
            "scan": t_scan_time,
            **sub_timings,
        }
        return pack

    pack = ScriberPack(
        project_root=root,
        config_path=resolved_config,
        seed_paths=seeds,
        candidates=candidates,
        graph=graph,
        only_tree=config.only_tree,
        output_format=config.format,
        mode=mode,
        stats=stats,
    )

    t_content = perf_counter()
    if progress_callback:
        progress_callback("Aplikowanie regul zawartosci...")
    _apply_content_policy(pack, config)
    t_content_time = perf_counter() - t_content

    pack.timings = {
        "config_load": t_config_load,
        "scan": t_scan_time,
        "content_read": t_content_time,
        **sub_timings,
    }
    return pack


def build_and_write_pack(
    paths: list[str] | None = None, **kwargs
) -> tuple[Path | None, ScriberPack | LlmPack]:
    explain_selection = kwargs.pop("explain_selection", False)
    pack = build_pack(paths, **kwargs)
    config_path = resolve_config_path(paths or ["."], kwargs.get("config_path"))
    config = load_config(config_path)
    config = apply_overrides(
        config,
        output=kwargs.get("output"),
        output_format=kwargs.get("output_format"),
        only_tree=kwargs.get("only_tree"),
        modules=kwargs.get("modules"),
        support=kwargs.get("support"),
        max_files=kwargs.get("max_files"),
        max_tokens=kwargs.get("max_tokens"),
        min_score=kwargs.get("min_score"),
        support_content=kwargs.get("support_content"),
    )
    progress = kwargs.get("progress_callback")
    if progress:
        progress("Renderowanie Markdown...")

    if isinstance(pack, LlmPack):
        from scriber.renderer.llm_report import render_llm_report
        import io

        buf = io.StringIO()
        render_llm_report(pack, buf)
        rendered = buf.getvalue()
    else:
        rendered = render_pack(pack, explain_selection=explain_selection)

    output = config.output
    if str(output) == "-":
        import sys

        try:
            sys.stdout.buffer.write(rendered.encode("utf-8"))
            sys.stdout.flush()
        except (AttributeError, OSError):
            print(rendered)
        return None, pack
    if not output.is_absolute():
        output = pack.project_root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        from scriber.native import is_native_available, require_native

        if is_native_available():
            require_native().write_text(str(output), rendered)
        else:
            output.write_text(rendered, encoding="utf-8")
    except Exception:
        output.write_text(rendered, encoding="utf-8")

    return output, pack
