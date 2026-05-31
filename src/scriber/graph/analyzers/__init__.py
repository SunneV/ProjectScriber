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

    edges = []
    for analyzer in analyzers:
        edges.extend(analyzer.analyze(files, indexes, config, edge_cls, is_native))

    return edges
