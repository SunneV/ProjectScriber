from __future__ import annotations

from pathlib import Path

from scriber.core.models import Candidate, ScriberPack


def _path(path: Path) -> str:
    return path.as_posix()


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _content_flag(candidate: Candidate) -> str:
    if candidate.include_content:
        return "yes"
    if candidate.omitted_reason:
        return f"no: {candidate.omitted_reason}"
    return "no"


def _table(candidates: list[Candidate], explain_selection: bool = False) -> str:
    if not candidates:
        return "_None._\n"
    lines = ["| Score | Content | Path | Reason |", "|---:|---|---|---|"]
    for candidate in candidates:
        reason = "; ".join(candidate.reasons) if explain_selection else candidate.reason_summary
        lines.append(
            f"| {candidate.score} | {_escape_table(_content_flag(candidate))} | `{_escape_table(_path(candidate.file.relative))}` | {_escape_table(reason)} |"
        )
    return "\n".join(lines) + "\n"


def render_tree(paths: list[Path]) -> str:
    tree: dict[str, dict] = {}
    for path in sorted(paths, key=lambda item: item.as_posix()):
        node = tree
        for part in path.parts:
            node = node.setdefault(part, {})

    def walk(node: dict[str, dict], prefix: str = "") -> list[str]:
        lines: list[str] = []
        items = sorted(node.items(), key=lambda item: item[0])
        for index, (name, child) in enumerate(items):
            is_last = index == len(items) - 1
            branch = "└── " if is_last else "├── "
            lines.append(f"{prefix}{branch}{name}")
            extension = "    " if is_last else "│   "
            lines.extend(walk(child, prefix + extension))
        return lines

    return ".\n" + "\n".join(walk(tree)) if tree else "."


def render_module_graph(pack: ScriberPack) -> str:
    included = set(pack.included_paths)
    lines: list[str] = []

    if pack.mode == "project_snapshot":
        import_counts = []
        imported_by_counts = []
        for path in included:
            imports = len(pack.graph.imports.get(path, set()) & included)
            if imports > 0:
                import_counts.append((path, imports))
            
            imported_by = len(pack.graph.imported_by.get(path, set()) & included)
            if imported_by > 0:
                imported_by_counts.append((path, imported_by))
                
        import_counts.sort(key=lambda x: (-x[1], x[0].as_posix()))
        imported_by_counts.sort(key=lambda x: (-x[1], x[0].as_posix()))
        
        lines.append("Top 5 files with most dependencies:")
        for path, count in import_counts[:5]:
            lines.append(f"- `{_path(path)}`: imports {count} included files")
            
        lines.append("")
        lines.append("Top 5 most imported files:")
        for path, count in imported_by_counts[:5]:
            lines.append(f"- `{_path(path)}`: imported by {count} included files")
            
        return "\n".join(lines).strip() or "No module graph available."

    for seed in pack.seed_paths:
        for seed_file in seed.expanded_files:
            lines.append(_path(seed_file))
            imports = sorted(pack.graph.imports.get(seed_file, set()) & included, key=lambda item: item.as_posix())
            imported_by = sorted(pack.graph.imported_by.get(seed_file, set()) & included, key=lambda item: item.as_posix())
            edges = [("imports", item) for item in imports] + [("imported by", item) for item in imported_by]
            for index, (kind, target) in enumerate(edges):
                branch = "└──" if index == len(edges) - 1 else "├──"
                lines.append(f"{branch} {kind} {_path(target)}")
            if not edges:
                lines.append("└── no included import edges")
            lines.append("")
    return "\n".join(lines).strip() or "No module graph available."


def _language_fence(language: str) -> str:
    if language in {"python", "rust", "javascript", "typescript", "go", "java", "kotlin", "c", "cpp", "toml", "yaml", "json", "markdown", "dockerfile", "ini"}:
        return language
    return "text"


def _fence_for(content: str) -> str:
    longest = 0
    current = 0
    for char in content:
        if char == "`":
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return "`" * max(3, longest + 1)


def render_summary(pack: ScriberPack) -> str:
    code_count = len([c for c in pack.candidates if c.file.kind == "code"])
    support_count = len([c for c in pack.candidates if c.file.kind == "support"])
    content_count = len([c for c in pack.candidates if c.include_content])
    tree_only_count = len([c for c in pack.candidates if not c.include_content])

    lines = [
        "## Pack summary",
        "",
        f"- Mode: `{pack.mode}`",
        f"- Seed paths: `{len(pack.seed_paths)}`",
        f"- Included code files: `{code_count}`",
        f"- Included support files: `{support_count}`",
        f"- Content files: `{content_count}`",
        f"- Tree-only files: `{tree_only_count}`",
        f"- Estimated tokens: `{pack.total_tokens}`",
        ""
    ]
    return "\n".join(lines)


def render_summary_text(pack: ScriberPack) -> str:
    code_count = len([c for c in pack.candidates if c.file.kind == "code"])
    support_count = len([c for c in pack.candidates if c.file.kind == "support"])
    content_count = len([c for c in pack.candidates if c.include_content])
    tree_only_count = len([c for c in pack.candidates if not c.include_content])

    lines = [
        "PACK SUMMARY",
        "------------",
        f"Mode: {pack.mode}",
        f"Seed paths: {len(pack.seed_paths)}",
        f"Included code files: {code_count}",
        f"Included support files: {support_count}",
        f"Content files: {content_count}",
        f"Tree-only files: {tree_only_count}",
        f"Estimated tokens: {pack.total_tokens}",
        ""
    ]
    return "\n".join(lines)


def render_markdown(pack: ScriberPack, explain_selection: bool = False) -> str:
    code = [candidate for candidate in pack.candidates if candidate.file.kind == "code"]
    support = [candidate for candidate in pack.candidates if candidate.file.kind == "support"]
    other = [candidate for candidate in pack.candidates if candidate.file.kind == "other"]

    lines: list[str] = []
    lines.append("# Scriber 2.0 Pack")
    lines.append("")
    lines.append(render_summary(pack).rstrip())
    lines.append("")
    lines.append("## Project")
    lines.append("")
    lines.append(f"Root: `{pack.project_root}`")
    lines.append(f"Config: `{pack.config_path.relative_to(pack.project_root).as_posix()}`")
    lines.append(f"Format: `{pack.output_format}`")
    lines.append(f"Only tree: `{str(pack.only_tree).lower()}`")
    lines.append("")
    lines.append("## Input paths")
    lines.append("")
    for seed in pack.seed_paths:
        lines.append(f"- `{_path(seed.relative)}`")
    lines.append("")
    lines.append("## Included code files")
    lines.append("")
    lines.append(_table(code, explain_selection).rstrip())
    lines.append("")
    lines.append("## Included support files")
    lines.append("")
    lines.append(_table(support, explain_selection).rstrip())
    if other:
        lines.append("")
        lines.append("## Included other files")
        lines.append("")
        lines.append(_table(other, explain_selection).rstrip())
    lines.append("")
    lines.append("## Module graph")
    lines.append("")
    lines.append("```text")
    lines.append(render_module_graph(pack))
    lines.append("```")
    lines.append("")
    lines.append("## Included project tree")
    lines.append("")
    lines.append("```text")
    lines.append(render_tree(pack.included_paths))
    lines.append("```")

    if not pack.only_tree:
        lines.append("")
        lines.append("## File contents")
        for candidate in pack.candidates:
            lines.append("")
            lines.append(f"### `{_path(candidate.file.relative)}`")
            lines.append("")
            if not candidate.include_content:
                lines.append(f"_Content omitted: {candidate.omitted_reason or 'not selected for content'}._")
                continue
            content = candidate.content or ""
            fence = _fence_for(content)
            language = _language_fence(candidate.file.language)
            lines.append(f"{fence}{language}")
            lines.append(content.rstrip("\n"))
            lines.append(fence)

    lines.append("")
    return "\n".join(lines)


def render_text(pack: ScriberPack, explain_selection: bool = False) -> str:
    lines: list[str] = []
    lines.append("SCRIBER 2.0 PACK")
    lines.append("================")
    lines.append("")
    lines.append(render_summary_text(pack).rstrip())
    lines.append("")
    lines.append(f"PROJECT ROOT: {pack.project_root}")
    lines.append(f"CONFIG: {pack.config_path.relative_to(pack.project_root).as_posix()}")
    lines.append(f"FORMAT: {pack.output_format}")
    lines.append(f"ONLY TREE: {str(pack.only_tree).lower()}")
    lines.append("")
    lines.append("INPUT PATHS")
    for seed in pack.seed_paths:
        lines.append(f"- {_path(seed.relative)}")
    lines.append("")
    lines.append("INCLUDED FILES")
    for candidate in pack.candidates:
        reason = "; ".join(candidate.reasons) if explain_selection else candidate.reason_summary
        lines.append(f"[{candidate.score:03d}] {_path(candidate.file.relative)}")
        lines.append(f"      kind: {candidate.file.kind}")
        lines.append(f"      content: {_content_flag(candidate)}")
        lines.append(f"      reason: {reason}")
    lines.append("")
    lines.append("MODULE GRAPH")
    lines.append(render_module_graph(pack))
    lines.append("")
    lines.append("INCLUDED PROJECT TREE")
    lines.append(render_tree(pack.included_paths))

    if not pack.only_tree:
        lines.append("")
        lines.append("FILE CONTENTS")
        lines.append("=============")
        for candidate in pack.candidates:
            lines.append("")
            lines.append(f"--- FILE: {_path(candidate.file.relative)} ---")
            if not candidate.include_content:
                lines.append(f"[content omitted: {candidate.omitted_reason or 'not selected for content'}]")
                continue
            lines.append(candidate.content or "")
    lines.append("")
    return "\n".join(lines)


def render_pack(pack: ScriberPack, explain_selection: bool = False) -> str:
    if pack.output_format == "txt":
        return render_text(pack, explain_selection=explain_selection)
    return render_markdown(pack, explain_selection=explain_selection)
