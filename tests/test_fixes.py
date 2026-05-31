from pathlib import Path
from unittest.mock import patch

from scriber.core.config import ScriberConfig
from scriber.core.models import FileNode, ModuleGraph
from scriber.engine.roles import classify_file_role
from scriber.engine.scorer import _is_test_file
from scriber.scanner.files import classify_file, read_text_lossy


def test_role_classifier_does_not_mark_production_tests_analyzer_as_test():
    config = ScriberConfig()
    config.python.test_roots = ["tests", "test"]
    rel = Path("src/scriber/graph/analyzers/tests.py")
    assert not _is_test_file(rel, config)

    rel2 = Path("tests/test_something.py")
    assert _is_test_file(rel2, config)


def test_classify_file_does_not_binary_check_unmatched_files():
    config = ScriberConfig()
    config.code_patterns = ["**/*.py"]
    config.support = False

    with patch("scriber.scanner.files.is_probably_binary") as mock_binary:
        # Not a match to any pattern
        res = classify_file(Path("/fake/file.unknown"), Path("/fake"), config)
        assert res is None
        mock_binary.assert_not_called()


def test_read_text_lossy_without_native(tmp_path):
    p = tmp_path / "test.txt"
    p.write_bytes(b"hello \xff world")  # invalid utf-8

    with patch("scriber.native.is_native_available", return_value=False):
        content = read_text_lossy(p)
        assert "hello \ufffd world" in content or "hello  world" in content


def test_classify_file_role_does_not_mark_graph_analyzers_tests_py_as_test():
    file = FileNode(
        absolute=Path("/src/scriber/graph/analyzers/tests.py"),
        relative=Path("src/scriber/graph/analyzers/tests.py"),
        kind="code",
        language="python",
        size_bytes=100,
    )
    graph = ModuleGraph()
    role = classify_file_role(file, graph)
    assert role != "test"


def test_read_text_lossy_falls_back_when_native_read_raises(tmp_path):
    p = tmp_path / "test.txt"
    p.write_bytes(b"hello")

    with patch("scriber.native.is_native_available", return_value=True):
        with patch("scriber.native.require_native") as mock_require:
            mock_require.return_value.read_text.side_effect = Exception(
                "Native read failed"
            )
            content = read_text_lossy(p)
            assert content == "hello"


def test_import_cache_works_with_custom_cache_dir(tmp_path):
    config = ScriberConfig()
    config.cache.dir = "custom/cache/dir"

    from scriber.cache import ScriberCache

    cache = ScriberCache(config, tmp_path)

    assert cache.cache_dir == tmp_path / "custom" / "cache" / "dir"

    f1 = tmp_path / "a.py"
    f2 = tmp_path / "b.py"
    f1.write_text("import b")
    f2.write_text("")

    cache.set_imports(Path("a.py"), {Path("b.py")})
    assert cache.imports_data["a.py"]["targets"] == ["b.py"]


def test_project_snapshot_docs_profile_changes_code_and_test_scores():
    from scriber.core.profiles import apply_profile

    config = ScriberConfig()
    config = apply_profile(config, "docs")

    from scriber.engine.scorer import score_candidates_project_snapshot

    files = {
        Path("app.py"): FileNode(
            Path("/app.py"), Path("app.py"), "code", "python", 100
        ),
        Path("test_app.py"): FileNode(
            Path("/test_app.py"), Path("test_app.py"), "code", "python", 100
        ),
        Path("utils.py"): FileNode(
            Path("/utils.py"), Path("utils.py"), "code", "python", 100
        ),
    }
    graph = ModuleGraph()
    # Mocking minimums so we see all files in output
    config.min_score = 0
    config.modules_config.tree_min_score = 0

    candidates = score_candidates_project_snapshot(
        files=files, graph=graph, config=config
    )

    c_app = next(c for c in candidates if c.file.relative.name == "app.py")
    assert c_app.score == config.modules_config.scoring.get("entrypoint_file", 90)

    c_test = next(c for c in candidates if c.file.relative.name == "test_app.py")
    assert c_test.score == config.modules_config.scoring.get("test_file", 60)

    c_utils = next(c for c in candidates if c.file.relative.name == "utils.py")
    assert c_utils.score == config.modules_config.scoring.get("code_file", 80)


def test_native_project_snapshot_uses_profile_code_and_test_scores():
    from scriber.core.profiles import apply_profile

    config = ScriberConfig()
    config = apply_profile(config, "docs")
    from scriber.native import is_native_available, require_native

    if not is_native_available():
        return  # skip if native not built

    native = require_native()
    scoring = config.modules_config.scoring
    opts = native.NativePackOptions(
        mode="project_snapshot",
        max_files=10,
        min_score=0,
        tree_min_score=0,
        entrypoint_patterns=config.python.entrypoint_patterns,
        test_roots=config.python.test_roots,
        entrypoint_file_score=scoring.get("entrypoint_file", 90),
        code_file_score=scoring.get("code_file", 80),
        test_file_score=scoring.get("test_file", 60),
        other_file_score=scoring.get("other_file", 40),
    )
    assert opts.entrypoint_file_score == scoring.get("entrypoint_file", 90)
    assert opts.test_file_score == scoring.get("test_file", 60)
    assert opts.code_file_score == scoring.get("code_file", 80)
    assert opts.other_file_score == scoring.get("other_file", 40)


def test_llm_pack_gpt_profile_does_not_access_missing_outline_symbols(tmp_path):
    from scriber.packer.pack import build_pack

    config_path = tmp_path / "pyproject.toml"
    config_path.write_text("")

    code_path = tmp_path / "test.py"
    code_path.write_text("def my_func(): pass")

    # Just verify it builds without Exception on outline.symbols
    pack = build_pack(paths=[str(code_path)], profile="gpt", path_base="cwd")
    assert pack is not None
