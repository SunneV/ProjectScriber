def test_top_dependencies_limits_graph_traversal():
    from pathlib import Path
    from scriber.core.models import RelationEdge
    from scriber.engine.scorer import _walk_weighted_neighbors

    start = Path("app.py")
    edges = []
    # Create 15 outgoing edges with varying strengths
    for i in range(15):
        target = Path(f"dep_{i}.py")
        edges.append(
            RelationEdge(
                source=start,
                target=target,
                kind="import",
                weight=1.0,
                confidence=0.1 * i,  # Higher i = higher confidence
                evidence=[],
                line=i,
                analyzer="test",
            )
        )

    # Unlimited dependencies (0)
    result_unlimited = _walk_weighted_neighbors(
        edges, start, depth_limit=1, top_dependencies=0
    )
    assert len(result_unlimited) == 15

    # Top 5 dependencies
    result_top5 = _walk_weighted_neighbors(
        edges, start, depth_limit=1, top_dependencies=5
    )
    assert len(result_top5) == 5

    # Verify the ones with highest confidence were picked
    # The edges have confidence 0.0 to 1.4. The top 5 should be from 1.0 to 1.4 (dep_10 to dep_14)
    expected_deps = {Path(f"dep_{i}.py") for i in range(10, 15)}
    assert set(result_top5.keys()) == expected_deps
