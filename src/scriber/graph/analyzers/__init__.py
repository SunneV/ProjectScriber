from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from scriber.graph.indexes import GraphIndexes
from scriber.graph.analyzers.tests import TestsAnalyzer
from scriber.graph.analyzers.package import PackageAnalyzer
from scriber.graph.analyzers.env import EnvAnalyzer
from scriber.graph.analyzers.config_refs import ConfigRefsAnalyzer
from scriber.graph.analyzers.docs import DocsAnalyzer


def generate_cheap_relations(
    files: dict[Path, Any], edge_cls: Any, is_native: bool = False
) -> list[Any]:
    indexes = GraphIndexes.build(files)
    config = None  # Passed as None for these simple analyzers

    analyzers = [
        TestsAnalyzer(),
        PackageAnalyzer(),
        EnvAnalyzer(),
        ConfigRefsAnalyzer(),
        DocsAnalyzer(),
    ]

    # Audit finding #6: run analyzers concurrently. They are I/O-bound (each
    # reads file contents) and share the read-only ``indexes``/``files`` maps
    # during analysis, so a thread pool yields a speedup without correctness
    # risk. Falls back to sequential execution on any error.
    try:
        results: list[Any] = []
        with ThreadPoolExecutor(max_workers=min(len(analyzers), 5)) as pool:
            futures = [
                pool.submit(
                    analyzer.analyze, files, indexes, config, edge_cls, is_native
                )
                for analyzer in analyzers
            ]
            for fut in futures:
                results.extend(fut.result())
        return results
    except Exception:
        # Defensive fallback to the original sequential path.
        edges: list[Any] = []
        for analyzer in analyzers:
            edges.extend(analyzer.analyze(files, indexes, config, edge_cls, is_native))
        return edges
