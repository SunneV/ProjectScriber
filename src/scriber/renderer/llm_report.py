from __future__ import annotations
from typing import TextIO
from pathlib import Path
from collections import defaultdict
import json

from scriber.core.models import LlmPack, PackItem, FileOutline
from scriber.graph.model import RelationEdge

def render_llm_report(pack: LlmPack, out: TextIO) -> None:
    out.write("# Scriber Pack v3\n\n")
    
    out.write("<scriber_instructions>\n")
    out.write("You are reading a generated codebase context pack.\n")
    out.write("Prefer facts from <manifest>, <relations>, and <file> blocks.\n")
    out.write("If a file is tree_only or omitted, do not infer its contents.\n")
    out.write("When proposing patches, cite file IDs and line ranges.\n")
    out.write("</scriber_instructions>\n\n")
    
    out.write("<manifest format=\"yaml\">\n")
    out.write("project:\n")
    out.write(f"  mode: {pack.mode}\n")
    out.write(f"  goal: {pack.goal or 'null'}\n")
    out.write(f"  target_tokens: {pack.budget_target}\n")
    out.write(f"  actual_tokens: {pack.budget_actual}\n")
    
    input_paths = pack.stats.get("input_paths", [])
    if input_paths:
        out.write("  analyzed_targets:\n")
        for p in input_paths:
            out.write(f"    - {p}\n")
    out.write("\n")
    
    out.write("read_order:\n")
    for item in pack.items:
        if item.content_mode not in ("tree", "omit"):
            out.write(f"  - {item.item_id}  # {item.file.relative.as_posix()}\n")
            
    out.write("\nfiles:\n")
    for item in pack.items:
        if item.content_mode in ("omit",):
            continue
        out.write(f"  {item.item_id}:\n")
        out.write(f"    path: {item.file.relative.as_posix()}\n")
        out.write(f"    role: {item.role}\n")
        out.write(f"    mode: {item.content_mode}\n")
        out.write(f"    score: {item.score}\n")
        out.write(f"    utility: {item.utility:.2f}\n")
        out.write(f"    tokens: {item.token_estimate}\n")
        if item.outline and item.outline.purpose:
            out.write(f"    purpose: {item.outline.purpose}\n")
    out.write("</manifest>\n\n")

    out.write("## Architecture map\n")
    out.write("```\n")
    _render_tree(pack.items, out)
    out.write("```\n\n")

    out.write("<relations>\n")
    _render_graph(pack, out)
    out.write("</relations>\n\n")
    
    warnings = _generate_warnings(pack)
    if warnings:
        out.write("## Pack quality warnings\n\n")
        for w in warnings:
            out.write(f"- {w}\n")
        out.write("\n")

    out.write("## Files Content\n\n")
    
    for item in pack.items:
        if item.content_mode in ("tree", "omit"):
            continue
            
        out.write(f'<file id="{item.item_id}" path="{item.file.relative.as_posix()}" role="{item.role}" mode="{item.content_mode}">\n')
        
        if item.outline and item.outline.purpose:
            out.write("<purpose>\n")
            out.write(f"{item.outline.purpose}\n")
            out.write("</purpose>\n\n")
            
        if item.outline:
            _render_symbols_manifest(item.outline, out)

        if item.content_mode == "full" and item.content:
            out.write(f"```{item.file.language} linenums=\"1\"\n")
            out.write(_add_line_numbers(item.content, item.file.relative.as_posix(), item.file.language))
            if not item.content.endswith("\n"):
                out.write("\n")
            out.write("```\n")
            
        elif item.content_mode == "excerpt":
            if item.excerpts:
                for excerpt in item.excerpts:
                    out.write(f"```{item.file.language}\n")
                    out.write(excerpt)
                    out.write("\n```\n\n")
            elif item.outline:
                _render_outline_fallback(item, out)
            else:
                out.write("_Excerpt unavailable; falling back to metadata only._\n\n")
                
        elif item.content_mode == "outline" and item.outline:
            _render_outline_fallback(item, out)
            
        out.write("</file>\n\n")

import re

def _add_line_numbers(content: str, path: str, language: str) -> str:
    lines = content.splitlines()
    out = []
    out.append(f"# file: {path}")
    out.append(f"# lines: 1-{len(lines)}")
    for i, line in enumerate(lines, 1):
        if language in ("python", "py"):
            m = re.match(r'^(\s*)(class|def|async def)\s+([a-zA-Z0-9_]+)', line)
            if m:
                indent, _, name = m.groups()
                out.append(f"{i:04d} {indent}# <anchor id=\"{name}\">")
        out.append(f"{i:04d} {line}")
    return "\n".join(out)

def _render_symbols_manifest(outline: FileOutline, out: TextIO) -> None:
    symbols = []
    if outline.classes:
        symbols.extend(outline.classes)
    if outline.functions:
        symbols.extend(outline.functions)
    if not symbols:
        return
        
    out.write("<symbols>\n")
    for sym in symbols:
        out.write(f"- {sym}\n")
    out.write("</symbols>\n\n")

def _render_outline_fallback(item: PackItem, out: TextIO) -> None:
    out.write("```python\n") 
    out.write(f"# Outline for {item.file.relative.name}\n")
    if item.outline.classes:
        out.write("Classes: " + ", ".join(item.outline.classes) + "\n")
    if item.outline.functions:
        out.write("Functions: " + ", ".join(item.outline.functions) + "\n")
    if item.outline.imports:
        out.write("Imports: " + ", ".join(item.outline.imports) + "\n")
    out.write("```\n\n")

def _generate_warnings(pack: LlmPack) -> list[str]:
    warnings = []
    empty_excerpts = sum(1 for i in pack.items if i.content_mode == "excerpt" and not i.excerpts)
    if empty_excerpts > 0:
        warnings.append(f"{empty_excerpts} files are marked excerpt but have no excerpts (falling back to outline).")
    
    unknown_roles = sum(1 for i in pack.items if i.role == "unknown")
    if unknown_roles > 0:
        warnings.append(f"{unknown_roles} files have role=unknown.")
        
    return warnings

def _render_tree(items: list[PackItem], out: TextIO) -> None:
    tree = {}
    item_map = {item.file.relative.as_posix(): item for item in items}
    
    for item in items:
        parts = item.file.relative.parts
        curr = tree
        for part in parts:
            if part not in curr:
                curr[part] = {}
            curr = curr[part]
            
    def print_node(path_parts, current_dict, prefix=""):
        keys = sorted(current_dict.keys())
        for i, k in enumerate(keys):
            is_last = i == len(keys) - 1
            child_prefix = prefix + ("    " if is_last else "│   ")
            connector = "└── " if is_last else "├── "
            
            full_path = "/".join(path_parts + (k,))
            item = item_map.get(full_path)
            
            if item:
                badge = f"[{item.item_id} {item.role} {item.content_mode} score={item.score}]"
                name_str = f"{prefix}{connector}{k}"
                out.write(f"{name_str:<50} {badge}\n")
            else:
                out.write(f"{prefix}{connector}{k}/\n")
                print_node(path_parts + (k,), current_dict[k], child_prefix)
                
    out.write(".\n")
    print_node((), tree, "")

def _render_graph(pack: LlmPack, out: TextIO) -> None:
    included_paths = {item.file.relative for item in pack.items}
    item_id_map = {item.file.relative: item.item_id for item in pack.items}
    
    groups = defaultdict(list)
    for edge in pack.graph.edges:
        if edge.source in included_paths and edge.target in included_paths:
            key = (edge.source, edge.target, edge.kind)
            groups[key].append(edge)
            
    sorted_groups = sorted(groups.items(), key=lambda x: (x[0][0].as_posix(), x[0][1].as_posix()))
    
    for (source, target, kind), edges in sorted_groups:
        count = len(edges)
        max_conf = max(e.confidence for e in edges)
        analyzers = sorted({e.analyzer for e in edges})
        
        s_id = item_id_map[source]
        t_id = item_id_map[target]
        
        analyzer_str = ",".join(analyzers)
        out.write(f"{s_id} -> {t_id} [{kind}] x{count} (analyzers=[{analyzer_str}], conf={max_conf:.2f})\n")
