from __future__ import annotations

from pathlib import Path

from scriber.core.models import ScriberConfig
from scriber.native import is_native_available, require_native
from scriber.scanner.scan import scan_project as scan_rust
from scriber.scanner.scan_py import scan_project as scan_python


def test_native_module_available() -> None:
    assert is_native_available()
    native = require_native()
    assert native is not None


def test_native_read_write(tmp_path: Path) -> None:
    native = require_native()
    test_file = tmp_path / "test.txt"
    content = "Hello, native Rust world!\nWith some special characters: łóądźś\n"
    
    native.write_text(str(test_file), content)
    assert test_file.exists()
    
    read_back = native.read_text(str(test_file))
    assert read_back == content


def test_native_binary_check(tmp_path: Path) -> None:
    native = require_native()
    
    # Test text file
    txt_file = tmp_path / "normal.txt"
    txt_file.write_text("Hello world", encoding="utf-8")
    assert not native.is_probably_binary(str(txt_file))
    
    # Test binary file
    bin_file = tmp_path / "binary.bin"
    bin_file.write_bytes(b"Hello\x00world")
    assert native.is_probably_binary(str(bin_file))


def test_native_scan_matches_python_scan(tmp_path: Path) -> None:
    # Set up a mock project structure
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / "src" / "helper.py").write_text("import sys", encoding="utf-8")
    (tmp_path / "src" / "binary.dat").write_bytes(b"\x00\x01\x02")
    (tmp_path / "README.md").write_text("# Test Project", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[tool.scriber]\nversion='2'", encoding="utf-8")
    
    # Hidden dir and ignored patterns
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("git config", encoding="utf-8")
    
    config = ScriberConfig(
        use_gitignore=True,
        code_patterns=["**/*.py"],
        support_patterns=["pyproject.toml", "README.md", "requirements.txt"],
        hard_ignore_patterns=[".git/**", "**/binary.dat"],
    )
    
    # Create gitignore
    (tmp_path / ".gitignore").write_text("*.pyc\n", encoding="utf-8")

    rust_result = scan_rust(tmp_path, config)
    python_result = scan_python(tmp_path, config)

    # They should find the exact same relative paths
    assert set(rust_result.keys()) == set(python_result.keys())

    for path, rust_node in rust_result.items():
        py_node = python_result[path]
        
        # Verify fields match exactly
        assert rust_node.relative == py_node.relative
        assert rust_node.kind == py_node.kind
        assert rust_node.language == py_node.language
        assert rust_node.size_bytes == py_node.size_bytes
        assert rust_node.is_binary == py_node.is_binary
        assert rust_node.support_category == py_node.support_category
        assert rust_node.content_policy == py_node.content_policy


def test_native_no_support(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Test Project", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[tool.scriber]\nversion='2'", encoding="utf-8")

    config = ScriberConfig(
        support=False,
        code_patterns=["**/*.py"],
        support_patterns=["pyproject.toml", "README.md"],
    )

    rust_result = scan_rust(tmp_path, config)
    # Check that README.md and pyproject.toml are NOT in the result (they are support files)
    for path, node in rust_result.items():
        assert node.kind != "support"
    assert Path("README.md") not in rust_result
    assert Path("pyproject.toml") not in rust_result


def test_native_write_creates_parent_dirs(tmp_path: Path) -> None:
    native = require_native()
    path = tmp_path / "a" / "b" / "out.txt"

    native.write_text(str(path), "hello")

    assert path.read_text(encoding="utf-8") == "hello"


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_mixed_project(root: Path) -> None:
    write(root / "pyproject.toml", "[tool.scriber]\nversion='2'\n")
    write(root / "Cargo.toml", "[package]\nname='x'\n")
    write(root / "Cargo.lock", "# lock\n")
    write(root / "README.md", "# readme\n")
    write(root / "src/main.py", "from .auth import Auth\n")
    write(root / "src/auth.py", "class Auth: pass\n")
    write(root / "src/main.rs", "mod auth;\n")
    write(root / "src/auth.rs", "pub struct Auth;\n")
    write(root / "frontend/main.ts", "import './auth'\n")
    write(root / "frontend/auth.ts", "export const x = 1\n")
    write(root / "node_modules/pkg/index.js", "ignored\n")
    write(root / ".gitignore", "*.tmp\n")
    write(root / "ignored.tmp", "ignored\n")
    (root / "binary.bin").write_bytes(b"\x00\x01")


def make_config() -> ScriberConfig:
    return ScriberConfig(
        use_gitignore=True,
        code_patterns=["**/*.py", "**/*.rs", "**/*.ts"],
        support_patterns=["pyproject.toml", "README.md", "Cargo.toml", "Cargo.lock"],
        hard_ignore_patterns=["node_modules/**"],
    )


def test_native_scan_matches_python_scan_mixed_project(tmp_path: Path) -> None:
    make_mixed_project(tmp_path)
    config = make_config()

    rs = scan_rust(tmp_path, config)
    py = scan_python(tmp_path, config)

    assert set(rs.keys()) == set(py.keys())


def test_native_scan_support_false(tmp_path: Path) -> None:
    make_mixed_project(tmp_path)
    config = make_config()
    config.support = False

    rs = scan_rust(tmp_path, config)

    assert all(node.kind != "support" for node in rs.values())


def test_native_scan_gitignore(tmp_path: Path) -> None:
    make_mixed_project(tmp_path)
    config = make_config()
    config.use_gitignore = True

    rs = scan_rust(tmp_path, config)

    assert Path("ignored.tmp") not in rs


def test_native_graph_matches_python_graph_mixed_project(tmp_path: Path) -> None:
    make_mixed_project(tmp_path)
    config = make_config()

    python_files = scan_python(tmp_path, config)
    
    from scriber.graph.builder import build_graph as build_python_graph
    py_graph = build_python_graph(python_files, config)
    
    native = require_native()
    native_files = native.scan_project(
        str(tmp_path),
        config.use_gitignore,
        config.hard_ignore_patterns,
        config.code_patterns,
        config.support_patterns,
        config.support_content.full,
        config.support_content.tree_only,
        config.support_content.default,
        config.support
    )
    edges = native.build_import_graph(
        str(tmp_path),
        native_files,
        config.python.source_roots,
        config.python.module_init_files
    )

    rs_imports = {}
    for edge in edges:
        rs_imports.setdefault(Path(getattr(edge, "from")), set()).add(Path(edge.to))
    
    for path, targets in py_graph.imports.items():
        file = python_files[path]
        if file.language in {"python", "javascript", "typescript", "rust", "go", "c", "cpp"}:
            rs_targets = rs_imports.get(path, set())
            assert rs_targets == targets


def test_native_scoring_matches_python_for_focused_pack(tmp_path: Path) -> None:
    make_mixed_project(tmp_path)
    config = make_config()
    
    python_files = scan_python(tmp_path, config)
    from scriber.graph.builder import build_graph as build_python_graph
    py_graph = build_python_graph(python_files, config)
    
    from scriber.engine.scorer import score_candidates as score_python
    from scriber.core.models import SeedPath
    seed = SeedPath(
        original=Path("src/main.py"),
        absolute=(tmp_path / "src/main.py").resolve(),
        relative=Path("src/main.py"),
        is_dir=False,
        expanded_files=[Path("src/main.py")]
    )
    py_candidates = score_python(files=python_files, seeds=[seed], graph=py_graph, config=config, mode="focused")
    
    native = require_native()
    native_files = native.scan_project(
        str(tmp_path),
        config.use_gitignore,
        config.hard_ignore_patterns,
        config.code_patterns,
        config.support_patterns,
        config.support_content.full,
        config.support_content.tree_only,
        config.support_content.default,
        config.support
    )
    edges = native.build_import_graph(
        str(tmp_path),
        native_files,
        config.python.source_roots,
        config.python.module_init_files
    )
    
    scoring = config.modules_config.scoring
    opts = native.NativePackOptions(
        mode="focused",
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
        native_files,
        ["src/main.py"],
        edges,
        opts
    )
    
    py_map = {c.file.relative.as_posix(): c for c in py_candidates}
    rs_map = {c.path: c for c in rs_candidates}
    
    assert set(py_map.keys()) == set(rs_map.keys())
    for path, py_c in py_map.items():
        rs_c = rs_map[path]
        assert rs_c.kind == py_c.file.kind
        assert rs_c.score == py_c.score


def test_native_render_tree_matches_python() -> None:
    native = require_native()
    paths = [
        "src/main.py",
        "src/auth.py",
        "tests/test_auth.py",
        "pyproject.toml",
        "README.md",
    ]
    
    from scriber.rendering.renderer import render_tree as render_python_tree
    py_tree = render_python_tree([Path(p) for p in paths])
    
    rs_tree = native.render_tree(paths)
    
    assert rs_tree.strip() == py_tree.strip()


def test_default_toml_and_lock_support(tmp_path: Path) -> None:
    from scriber.core.config import load_config
    from scriber.scanner.scan import scan_project

    # Create dummy files
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[tool.scriber]\nversion='2'", encoding="utf-8")
    (tmp_path / "some_random_config.toml").write_text("a = 1", encoding="utf-8")
    (tmp_path / "some_random_lockfile.lock").write_text("lock", encoding="utf-8")

    # Load default config
    config = load_config(tmp_path / "pyproject.toml")
    config.use_gitignore = False
    
    # Assert that **/*.toml and **/*.lock are in support patterns
    assert "**/*.toml" in config.support_patterns
    assert "**/*.toml" in config.support_content.full
    assert "**/*.lock" in config.support_patterns
    assert "**/*.lock" in config.support_content.tree_only

    # Scan the project
    scanned = scan_project(tmp_path, config)

    # Check TOML classifications
    assert Path("some_random_config.toml") in scanned
    node = scanned[Path("some_random_config.toml")]
    assert node.kind == "support"
    assert node.support_category == "project config"
    assert node.content_policy == "full"

    # Check lockfile classifications
    assert Path("some_random_lockfile.lock") in scanned
    node = scanned[Path("some_random_lockfile.lock")]
    assert node.kind == "support"
    assert node.support_category == "dependency file"
    assert node.content_policy == "tree_only"


def test_native_import_complex_python(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("class A: pass", encoding="utf-8")
    (tmp_path / "src" / "b.py").write_text("class B: pass", encoding="utf-8")
    (tmp_path / "src" / "c.py").write_text("class C: pass", encoding="utf-8")
    (tmp_path / "src" / "d.py").write_text("class D: pass", encoding="utf-8")
    
    import_test_content = """
import os, sys
import math as m, json
from .a import A as AliasA
from .b import (
    B, # some comment here
    C as AliasC
)
from .c import D
"""
    (tmp_path / "src" / "main.py").write_text(import_test_content, encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[tool.scriber]\nversion='2'", encoding="utf-8")

    config = ScriberConfig(
        use_gitignore=False,
        code_patterns=["**/*.py"],
        support_patterns=["pyproject.toml"],
    )

    from scriber.scanner.scan import scan_project
    files = scan_project(tmp_path, config)
    
    native = require_native()
    native_files = native.scan_project(
        str(tmp_path),
        config.use_gitignore,
        config.hard_ignore_patterns,
        config.code_patterns,
        config.support_patterns,
        config.support_content.full,
        config.support_content.tree_only,
        config.support_content.default,
        config.support
    )
    edges = native.build_import_graph(
        str(tmp_path),
        native_files,
        config.python.source_roots,
        config.python.module_init_files
    )

    imports = {Path(getattr(edge, "from")): set() for edge in edges}
    for edge in edges:
        imports[Path(getattr(edge, "from"))].add(Path(edge.to))
        
    main_path = Path("src/main.py")
    assert main_path in imports
    
    expected_imports = {
        Path("src/a.py"),
        Path("src/b.py"),
        Path("src/c.py")
    }
    assert imports[main_path] == expected_imports



