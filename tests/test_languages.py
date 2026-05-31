from __future__ import annotations

from pathlib import Path
from scriber.core.models import FileNode, ScriberConfig
from scriber.graph.builder import build_graph


def test_javascript_typescript_graph(tmp_path: Path) -> None:
    config = ScriberConfig()

    auth_path = tmp_path / "src/auth.ts"
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    auth_path.write_text("export class Auth {}", encoding="utf-8")

    main_path = tmp_path / "src/main.ts"
    main_path.write_text(
        "import { Auth } from './auth';\nimport 'lodash';", encoding="utf-8"
    )

    files = {
        Path("src/auth.ts"): FileNode(
            absolute=auth_path.resolve(),
            relative=Path("src/auth.ts"),
            kind="code",
            language="typescript",
            size_bytes=auth_path.stat().st_size,
        ),
        Path("src/main.ts"): FileNode(
            absolute=main_path.resolve(),
            relative=Path("src/main.ts"),
            kind="code",
            language="typescript",
            size_bytes=main_path.stat().st_size,
        ),
    }

    graph = build_graph(files, config)
    assert Path("src/auth.ts") in graph.imports[Path("src/main.ts")]
    assert Path("src/main.ts") in graph.imported_by[Path("src/auth.ts")]


def test_rust_graph(tmp_path: Path) -> None:
    config = ScriberConfig()

    cargo_toml = tmp_path / "Cargo.toml"
    cargo_toml.write_text("[package]\nname = 'test'", encoding="utf-8")

    auth_path = tmp_path / "src/auth.rs"
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    auth_path.write_text("pub struct Auth;", encoding="utf-8")

    main_path = tmp_path / "src/main.rs"
    main_path.write_text(
        "mod auth;\nuse crate::auth::Auth;\nuse super::unrelated;", encoding="utf-8"
    )

    files = {
        Path("src/auth.rs"): FileNode(
            absolute=auth_path.resolve(),
            relative=Path("src/auth.rs"),
            kind="code",
            language="rust",
            size_bytes=auth_path.stat().st_size,
        ),
        Path("src/main.rs"): FileNode(
            absolute=main_path.resolve(),
            relative=Path("src/main.rs"),
            kind="code",
            language="rust",
            size_bytes=main_path.stat().st_size,
        ),
    }

    graph = build_graph(files, config)
    assert Path("src/auth.rs") in graph.imports[Path("src/main.rs")]
    assert Path("src/main.rs") in graph.imported_by[Path("src/auth.rs")]


def test_go_graph(tmp_path: Path) -> None:
    config = ScriberConfig()

    go_mod = tmp_path / "go.mod"
    go_mod.write_text("module github.com/user/project\n", encoding="utf-8")

    db_path = tmp_path / "pkg/db/db.go"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_text("package db\n", encoding="utf-8")

    main_path = tmp_path / "cmd/main.go"
    main_path.parent.mkdir(parents=True, exist_ok=True)
    main_path.write_text(
        'package main\nimport "github.com/user/project/pkg/db"\n', encoding="utf-8"
    )

    files = {
        Path("pkg/db/db.go"): FileNode(
            absolute=db_path.resolve(),
            relative=Path("pkg/db/db.go"),
            kind="code",
            language="go",
            size_bytes=db_path.stat().st_size,
        ),
        Path("cmd/main.go"): FileNode(
            absolute=main_path.resolve(),
            relative=Path("cmd/main.go"),
            kind="code",
            language="go",
            size_bytes=main_path.stat().st_size,
        ),
    }

    graph = build_graph(files, config)
    assert Path("pkg/db/db.go") in graph.imports[Path("cmd/main.go")]
    assert Path("cmd/main.go") in graph.imported_by[Path("pkg/db/db.go")]


def test_cpp_graph(tmp_path: Path) -> None:
    config = ScriberConfig()

    header_path = tmp_path / "src/auth.h"
    header_path.parent.mkdir(parents=True, exist_ok=True)
    header_path.write_text("class Auth {};", encoding="utf-8")

    main_path = tmp_path / "src/main.cpp"
    main_path.write_text(
        '#include "auth.h"\n#include <vector>\n#include "utils/helper.hpp"',
        encoding="utf-8",
    )

    helper_path = tmp_path / "src/utils/helper.hpp"
    helper_path.parent.mkdir(parents=True, exist_ok=True)
    helper_path.write_text("void helper();", encoding="utf-8")

    files = {
        Path("src/auth.h"): FileNode(
            absolute=header_path.resolve(),
            relative=Path("src/auth.h"),
            kind="code",
            language="c",
            size_bytes=header_path.stat().st_size,
        ),
        Path("src/main.cpp"): FileNode(
            absolute=main_path.resolve(),
            relative=Path("src/main.cpp"),
            kind="code",
            language="cpp",
            size_bytes=main_path.stat().st_size,
        ),
        Path("src/utils/helper.hpp"): FileNode(
            absolute=helper_path.resolve(),
            relative=Path("src/utils/helper.hpp"),
            kind="code",
            language="cpp",
            size_bytes=helper_path.stat().st_size,
        ),
    }

    graph = build_graph(files, config)
    assert Path("src/auth.h") in graph.imports[Path("src/main.cpp")]
    assert Path("src/main.cpp") in graph.imported_by[Path("src/auth.h")]
    assert Path("src/utils/helper.hpp") in graph.imports[Path("src/main.cpp")]
    assert Path("src/main.cpp") in graph.imported_by[Path("src/utils/helper.hpp")]
