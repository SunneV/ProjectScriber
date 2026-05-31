from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from scriber.core.config import (
    load_raw_pyproject,
    load_config,
    validate_config,
    validate_raw_config,
)
from scriber.core.errors import ScriberError
from scriber.core.init_config import init_project
from scriber.core.root import resolve_config_path
from scriber.packer.pack import build_and_write_pack


def handle_introspection(args, pack) -> None:
    import json

    # 1. Export Graph JSON if requested
    if args.graph_json:
        edges_data = []
        for edge in pack.graph.edges:
            edges_data.append(
                {
                    "source": str(edge.source),
                    "target": str(edge.target),
                    "kind": edge.kind,
                    "weight": edge.weight,
                    "confidence": edge.confidence,
                    "evidence": edge.evidence,
                    "line": edge.line,
                    "analyzer": edge.analyzer,
                }
            )

        graph_data = {"edges": edges_data}
        json_path = Path(args.graph_json)
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(graph_data, f, indent=2)
            print(f"Exported relation graph to {json_path}", file=sys.stderr)
        except Exception as e:
            print(f"Error exporting relation graph to JSON: {e}", file=sys.stderr)

    # 2. Explain Graph
    if args.explain_graph:
        edges = pack.graph.edges
        total_edges = len(edges)

        # Group by kind
        kind_counts = {}
        for edge in edges:
            kind_counts[edge.kind] = kind_counts.get(edge.kind, 0) + 1

        # Get unique nodes
        nodes = set()
        for edge in edges:
            nodes.add(edge.source)
            nodes.add(edge.target)
        unique_nodes = len(nodes)
        avg_degree = (total_edges * 2.0 / unique_nodes) if unique_nodes > 0 else 0.0

        print("\n========================================", file=sys.stderr)
        print("SCRIBER RELATION GRAPH EXPLANATION", file=sys.stderr)
        print("========================================", file=sys.stderr)
        print(f"Total Edges: {total_edges}", file=sys.stderr)
        print("Edges by Kind:", file=sys.stderr)
        for kind, count in sorted(
            kind_counts.items(), key=lambda x: x[1], reverse=True
        ):
            print(f" - {kind.ljust(20)}: {count}", file=sys.stderr)
        print(f"Unique Nodes: {unique_nodes}", file=sys.stderr)
        print(f"Average Degree: {avg_degree:.2f}", file=sys.stderr)
        print("========================================\n", file=sys.stderr)

    # 3. Why <file>
    if args.why:
        why_target = args.why.replace("\\", "/").lower()
        target_c = None

        candidates_or_items = getattr(pack, "candidates", getattr(pack, "items", []))
        for c in candidates_or_items:
            rel_str = c.file.relative.as_posix().lower()
            abs_str = c.file.absolute.as_posix().lower()
            if why_target in rel_str or why_target in abs_str:
                target_c = c
                break

        if not target_c:
            print(
                f"\nCould not find file matching '{args.why}' in the analyzed candidates.",
                file=sys.stderr,
            )
            return

        print("\n========================================", file=sys.stderr)
        print(f"WHY WAS '{target_c.file.relative}' INCLUDED?", file=sys.stderr)
        print("========================================", file=sys.stderr)
        print(f"Score: {target_c.score}", file=sys.stderr)
        if hasattr(target_c, "role"):
            print(f"Role: {target_c.role}", file=sys.stderr)
        if hasattr(target_c, "token_estimate"):
            print(f"Token Cost: {target_c.token_estimate}", file=sys.stderr)
        if hasattr(target_c, "content_mode"):
            print(f"Content Mode: {target_c.content_mode}", file=sys.stderr)
        if hasattr(target_c, "omitted_reason") and target_c.omitted_reason:
            print(f"Omitted Reason: {target_c.omitted_reason}", file=sys.stderr)

        reasons = getattr(target_c, "reasons", [])
        if reasons:
            print("Selection Reasons:", file=sys.stderr)
            for r in reasons:
                print(f" - {r}", file=sys.stderr)
        else:
            reason_summary = getattr(
                target_c, "reason_summary", getattr(target_c, "reason", "None")
            )
            print(f"Selection Reasons: {reason_summary}", file=sys.stderr)

        incoming = []
        for edge in pack.graph.edges:
            if edge.target == target_c.file.relative:
                incoming.append(edge)

        if incoming:
            print("\nIncoming Relation Edges:", file=sys.stderr)
            for edge in sorted(incoming, key=lambda e: (e.kind, str(e.source))):
                ev = f" ({edge.evidence})" if edge.evidence else ""
                print(
                    f" - {edge.source} -> [this file] (kind: {edge.kind}, weight: {edge.weight}, confidence: {edge.confidence}){ev}",
                    file=sys.stderr,
                )
        else:
            print("\nNo incoming relation edges found in graph.", file=sys.stderr)
        print("========================================\n", file=sys.stderr)


def _progress(msg: str) -> None:
    # Use carriage return and padding to avoid external dependencies like rich
    sys.stderr.write(f"\r[Scriber] {msg}".ljust(80))
    sys.stderr.flush()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scriber",
        description="Scriber 2.0: build an intelligent code pack from one or more project paths.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Project file/folder paths used as seeds. Defaults to current directory.",
    )
    parser.add_argument(
        "--profile",
        choices=["default", "audit", "debug", "refactor", "docs"],
        default="default",
        help="Preset configuration profile.",
    )
    parser.add_argument(
        "--config",
        help="Path to pyproject.toml. Its parent directory becomes the project root.",
    )
    parser.add_argument(
        "--path-base",
        choices=["project", "cwd"],
        default="project",
        help="Base directory for relative paths when --config is used.",
    )
    parser.add_argument(
        "--format", choices=["md", "txt"], dest="output_format", help="Output format."
    )
    parser.add_argument(
        "--output",
        help="Output file path, relative to project root unless absolute. Use '-' for stdout.",
    )
    parser.add_argument(
        "--only-tree",
        action="store_true",
        help="Render only scored tree/map, without file contents.",
    )
    parser.add_argument(
        "--modules",
        dest="modules",
        action="store_true",
        help="Enable automatic related module selection.",
    )
    parser.add_argument(
        "--no-modules",
        dest="modules",
        action="store_false",
        help="Disable automatic related module selection.",
    )
    parser.set_defaults(modules=None)
    parser.add_argument(
        "--support", dest="support", action="store_true", help="Enable support files."
    )
    parser.add_argument(
        "--no-support",
        dest="support",
        action="store_false",
        help="Disable support files.",
    )
    parser.set_defaults(support=None)
    parser.add_argument(
        "--support-content",
        choices=["full", "auto", "tree_only"],
        help="Override default support file content policy.",
    )
    parser.add_argument(
        "--max-files", type=int, help="Maximum number of files in the pack."
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        help="Approximate token budget for included file contents. 0 disables budget.",
    )
    parser.add_argument(
        "--min-score", type=int, help="Minimum score for non-seed files."
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Append a default [tool.scriber] config to pyproject.toml and exit.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow --init to append even if [tool.scriber] already exists.",
    )
    parser.add_argument(
        "--project", action="store_true", help="Force project snapshot mode."
    )
    parser.add_argument(
        "--explain",
        "--explain-selection",
        dest="explain_selection",
        action="store_true",
        help="Explain reason for file selection in detail.",
    )
    parser.add_argument(
        "--explain-graph",
        action="store_true",
        help="Print relation graph statistics and relations.",
    )
    parser.add_argument(
        "--why",
        help="Print exactly which rules/edges pulled the specified file into the pack.",
    )
    parser.add_argument(
        "--graph-json",
        help="Export the RelationGraph as a JSON file to the specified path.",
    )
    parser.add_argument(
        "--validate-config",
        action="store_true",
        help="Validate pyproject.toml scriber config.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without saving the pack file.",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the output file automatically after creation.",
    )
    parser.add_argument(
        "--timings", action="store_true", help="Show execution timings for each phase."
    )
    parser.add_argument(
        "--version", action="store_true", help="Show version information and exit."
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.version:
            from scriber import __version__

            print(f"scriber {__version__}")
            from scriber.native import is_native_available, require_native

            if is_native_available():
                native = require_native()
                if hasattr(native, "build_info"):
                    api_ver = (
                        native.native_api_version()
                        if hasattr(native, "native_api_version")
                        else "unknown"
                    )
                    print(f"native {native.build_info()} (API v{api_ver})")
            return 0

        if args.validate_config:
            config_path = resolve_config_path(args.paths or ["."], args.config)
            if not config_path.exists():
                print(f"Error: Config file not found at {config_path}", file=sys.stderr)
                return 1
            try:
                raw_data = load_raw_pyproject(config_path)
                raw_issues = validate_raw_config(raw_data)
                if raw_issues:
                    issues = raw_issues
                else:
                    config = load_config(config_path)
                    issues = validate_config(config, raw_data, config_path)

                if not issues:
                    print("Scriber config is valid.", file=sys.stderr)
                    return 0
                else:
                    errors = 0
                    warnings = 0
                    for issue in issues:
                        severity = issue.severity.upper()
                        if severity == "ERROR":
                            errors += 1
                        else:
                            warnings += 1
                        print(f"[{severity}] {issue.message}", file=sys.stderr)
                    print(
                        f"\nValidation completed: {errors} error(s), {warnings} warning(s)",
                        file=sys.stderr,
                    )
                    return 1 if errors > 0 else 0
            except Exception as exc:
                print(f"Error: Failed to parse pyproject.toml: {exc}", file=sys.stderr)
                return 1

        if args.init:
            path = init_project(args.config, args.force)
            print(f"Scriber config written to: {path}")
            return 0

        if args.dry_run:
            from scriber.packer.pack import build_pack
            from scriber.core.config import apply_overrides

            pack = build_pack(
                args.paths or ["."],
                config_path=args.config,
                profile=args.profile,
                output=args.output,
                output_format=args.output_format,
                only_tree=True if args.only_tree else None,
                modules=args.modules,
                support=args.support,
                max_files=args.max_files,
                max_tokens=args.max_tokens,
                min_score=args.min_score,
                support_content=args.support_content,
                progress_callback=_progress,
                project=args.project,
                path_base=args.path_base,
            )
            sys.stderr.write("\r".ljust(80) + "\r")
            sys.stderr.flush()

            is_llm_pack = hasattr(pack, "items")
            items = getattr(pack, "items", getattr(pack, "candidates", []))
            if is_llm_pack:
                code_count = len(
                    [
                        c
                        for c in items
                        if c.file.kind == "code" and c.content_mode != "tree"
                    ]
                )
                support_count = len(
                    [
                        c
                        for c in items
                        if c.file.kind == "support" and c.content_mode != "tree"
                    ]
                )
                total_count = len([c for c in items if c.content_mode != "tree"])
            else:
                code_count = len(
                    [c for c in items if c.file.kind == "code" and c.include_content]
                )
                support_count = len(
                    [c for c in items if c.file.kind == "support" and c.include_content]
                )
                total_count = len([c for c in items if c.include_content])

            print("Scriber dry-run completed.", file=sys.stderr)
            print("----------------------------------------", file=sys.stderr)
            print(f" Mode:                   {pack.mode}", file=sys.stderr)
            print(f" Code files selected:    {code_count}", file=sys.stderr)
            print(f" Support files selected: {support_count}", file=sys.stderr)
            print(f" Total files in pack:    {total_count}", file=sys.stderr)
            total_tokens = getattr(
                pack, "budget_actual", getattr(pack, "total_tokens", 0)
            )
            print(f" Estimated tokens:       {total_tokens}", file=sys.stderr)
            if args.timings:
                if pack.stats:
                    print("----------------------------------------", file=sys.stderr)
                    print("Stats:", file=sys.stderr)
                    if "graph_edges_built" in pack.stats:
                        print(
                            f"  Graph edges built:  {pack.stats['graph_edges_built']}",
                            file=sys.stderr,
                        )
                        print(
                            f"  Graph cache reads:  {pack.stats['graph_cache_reads']}",
                            file=sys.stderr,
                        )
                        print(
                            f"  Graph cache hits:   {pack.stats['graph_cache_hits']}",
                            file=sys.stderr,
                        )
                        print(
                            f"  Graph cache writes: {pack.stats['graph_cache_writes']}",
                            file=sys.stderr,
                        )
                        print(
                            f"  Graph source:       {pack.stats['graph_source']}",
                            file=sys.stderr,
                        )
                if pack.timings:
                    print("----------------------------------------", file=sys.stderr)
                    print("Timings:", file=sys.stderr)
                    for phase, duration in pack.timings.items():
                        print(
                            f"  {phase.replace('_', ' ').ljust(15)}: {duration:.4f}s",
                            file=sys.stderr,
                        )
                    print(
                        f"  total:           {sum(pack.timings.values()):.4f}s",
                        file=sys.stderr,
                    )

            config = load_config(pack.config_path)
            config = apply_overrides(config, output=args.output)
            output_path = config.output
            if not output_path.is_absolute():
                output_path = pack.project_root / output_path
            print(f" Proposed output path:   {output_path}", file=sys.stderr)
            print("----------------------------------------", file=sys.stderr)
            if args.explain_graph or args.why or args.graph_json:
                handle_introspection(args, pack)
            return 0

        output, pack = build_and_write_pack(
            args.paths or ["."],
            config_path=args.config,
            profile=args.profile,
            output=args.output,
            output_format=args.output_format,
            only_tree=True if args.only_tree else None,
            modules=args.modules,
            support=args.support,
            max_files=args.max_files,
            max_tokens=args.max_tokens,
            min_score=args.min_score,
            support_content=args.support_content,
            progress_callback=_progress,
            project=args.project,
            explain_selection=args.explain_selection,
            path_base=args.path_base,
        )

        sys.stderr.write("\r".ljust(80) + "\r")
        sys.stderr.flush()

        is_llm_pack = hasattr(pack, "items")
        items = getattr(pack, "items", getattr(pack, "candidates", []))

        code_count = 0
        support_count = 0
        omitted_count = 0

        for cand in items:
            if is_llm_pack:
                if cand.content_mode != "tree":
                    if cand.file.kind == "code":
                        code_count += 1
                    elif cand.file.kind == "support":
                        support_count += 1
                else:
                    omitted_count += 1
            else:
                if cand.include_content:
                    if cand.file.kind == "code":
                        code_count += 1
                    elif cand.file.kind == "support":
                        support_count += 1
                else:
                    omitted_count += 1

        sys.stderr.write("Scriber build completed.\n")
        sys.stderr.write("----------------------------------------\n")
        sys.stderr.write(f" Code files included:    {code_count}\n")
        sys.stderr.write(f" Support files included: {support_count}\n")
        sys.stderr.write(f" Files omitted/skipped:  {omitted_count}\n")
        total_tokens = getattr(pack, "budget_actual", getattr(pack, "total_tokens", 0))
        sys.stderr.write(f" Estimated tokens:       {total_tokens}\n")
        sys.stderr.write("----------------------------------------\n")
        if args.timings:
            if pack.stats:
                sys.stderr.write("Stats:\n")
                if "graph_edges_built" in pack.stats:
                    sys.stderr.write(
                        f" - Graph edges built:  {pack.stats['graph_edges_built']}\n"
                    )
                    sys.stderr.write(
                        f" - Graph cache reads:  {pack.stats['graph_cache_reads']}\n"
                    )
                    sys.stderr.write(
                        f" - Graph cache hits:   {pack.stats['graph_cache_hits']}\n"
                    )
                    sys.stderr.write(
                        f" - Graph cache writes: {pack.stats['graph_cache_writes']}\n"
                    )
                    sys.stderr.write(
                        f" - Graph source:       {pack.stats['graph_source']}\n"
                    )
                sys.stderr.write("----------------------------------------\n")
            if pack.timings:
                sys.stderr.write("Timings:\n")
                for phase, duration in pack.timings.items():
                    sys.stderr.write(
                        f" - {phase.replace('_', ' ').ljust(15)}: {duration:.4f}s\n"
                    )
                sys.stderr.write(
                    f" - total:           {sum(pack.timings.values()):.4f}s\n"
                )
                sys.stderr.write("----------------------------------------\n")

        if args.explain_graph or args.why or args.graph_json:
            handle_introspection(args, pack)

        if output is not None:
            print(f"Scriber pack written to: {output}")
            if args.open:
                from scriber.core.open_file import open_path

                open_path(output)
        return 0
    except ScriberError as exc:
        parser.exit(2, f"scriber: error: {exc}\n")
    except KeyboardInterrupt:
        parser.exit(130, "scriber: interrupted\n")


if __name__ == "__main__":
    raise SystemExit(main())
