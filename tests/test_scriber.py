from __future__ import annotations

from pathlib import Path

from scriber.pack import build_pack
from scriber.render import render_markdown


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_project(tmp_path: Path) -> Path:
    write(
        tmp_path / "pyproject.toml",
        """
[tool.scriber]
version = "2"
format = "md"
output = ".scriber/out.md"
use_gitignore = false
max_files = 50
max_tokens = 100000
min_score = 30

[tool.scriber.code_files]
patterns = ["**/*.py"]

[tool.scriber.support_files]
enabled = true
patterns = ["pyproject.toml", "README.md", "requirements.txt", "poetry.lock", "Dockerfile"]

[tool.scriber.support_files.content]
default = "auto"
full = ["pyproject.toml", "README.md", "requirements.txt", "Dockerfile"]
tree_only = ["poetry.lock"]

[tool.scriber.modules]
enabled = true
depth = 2
include_direct_dependencies = true
include_reverse_dependencies = true
include_tests = true
include_same_package = true
include_parent_entrypoints = true
include_project_configs = true
content_min_score = 50
tree_min_score = 30

[tool.scriber.python]
source_roots = ["src", "."]
test_roots = ["tests"]
entrypoint_patterns = ["main.py", "routes.py"]

[tool.scriber.hard_ignore]
patterns = [".git/**"]
""".strip()
        + "\n",
    )
    write(tmp_path / "README.md", "# Example\n")
    write(tmp_path / "requirements.txt", "fastapi\n")
    write(tmp_path / "poetry.lock", "very large lock in real life\n")
    write(tmp_path / "Dockerfile", "FROM python:3.12\n")
    write(tmp_path / "src/app/__init__.py", "")
    write(
        tmp_path / "src/app/auth.py",
        "from .session import Session\nfrom .config import SETTINGS\n\nclass Auth: pass\n",
    )
    write(tmp_path / "src/app/session.py", "class Session: pass\n")
    write(tmp_path / "src/app/config.py", "SETTINGS = {}\n")
    write(tmp_path / "src/app/main.py", "from app.auth import Auth\n")
    write(tmp_path / "src/api/routes.py", "from app.auth import Auth\n")
    write(
        tmp_path / "tests/test_auth.py",
        "from app.auth import Auth\n\ndef test_auth():\n    assert Auth\n",
    )
    write(tmp_path / "src/app/unrelated.py", "VALUE = 1\n")
    return tmp_path


def test_build_pack_includes_seed_dependencies_reverse_tests_and_support(
    tmp_path: Path, monkeypatch
) -> None:
    project = make_project(tmp_path)
    monkeypatch.chdir(project)

    pack = build_pack(["src/app/auth.py"], config_path="pyproject.toml")
    paths = [path.as_posix() for path in pack.included_paths]

    assert "src/app/auth.py" in paths
    assert "src/app/session.py" in paths
    assert "src/app/config.py" in paths
    assert "src/api/routes.py" in paths
    assert "tests/test_auth.py" in paths
    assert "pyproject.toml" in paths
    assert "README.md" in paths
    assert "requirements.txt" in paths
    assert "poetry.lock" in paths

    by_path = {
        candidate.file.relative.as_posix(): candidate for candidate in pack.candidates
    }
    assert by_path["src/app/auth.py"].score == 100
    assert by_path["src/app/session.py"].score >= 80
    assert by_path["src/api/routes.py"].score >= 80
    assert by_path["tests/test_auth.py"].score >= 80
    assert by_path["poetry.lock"].include_content is False
    assert "tree_only" in (by_path["poetry.lock"].omitted_reason or "")


def test_only_tree_omits_contents(tmp_path: Path, monkeypatch) -> None:
    project = make_project(tmp_path)
    monkeypatch.chdir(project)

    pack = build_pack(["src/app/auth.py"], config_path="pyproject.toml", only_tree=True)
    assert pack.only_tree is True
    assert all(candidate.include_content is False for candidate in pack.candidates)

    rendered = render_markdown(pack)
    assert "## Pack summary" in rendered
    assert "Mode: `focused`" in rendered
    assert "## File contents" not in rendered
    assert "## Module graph" in rendered


def test_multiple_paths_promote_shared_dependency(tmp_path: Path, monkeypatch) -> None:
    project = make_project(tmp_path)
    write(tmp_path / "src/app/billing.py", "from .config import SETTINGS\n")
    monkeypatch.chdir(project)

    pack = build_pack(
        ["src/app/auth.py", "src/app/billing.py"], config_path="pyproject.toml"
    )
    by_path = {
        candidate.file.relative.as_posix(): candidate for candidate in pack.candidates
    }
    assert "src/app/config.py" in by_path
    assert by_path["src/app/config.py"].score == 100
    assert any(
        "shared by multiple seed paths" in reason
        for reason in by_path["src/app/config.py"].reasons
    )


def test_no_modules_keeps_seed_and_pyproject(tmp_path: Path, monkeypatch) -> None:
    project = make_project(tmp_path)
    monkeypatch.chdir(project)

    pack = build_pack(["src/app/auth.py"], config_path="pyproject.toml", modules=False)
    paths = [path.as_posix() for path in pack.included_paths]
    assert "src/app/auth.py" in paths
    assert "pyproject.toml" in paths
    assert "src/app/session.py" not in paths


def test_folder_seed_expands_files(tmp_path: Path, monkeypatch) -> None:
    project = make_project(tmp_path)
    monkeypatch.chdir(project)

    pack = build_pack(["src/app"], config_path="pyproject.toml", modules=False)
    paths = [path.as_posix() for path in pack.included_paths]
    assert "src/app/auth.py" in paths
    assert "src/app/session.py" in paths
    assert "src/app/config.py" in paths


def test_project_snapshot_mode(tmp_path: Path, monkeypatch) -> None:
    project = make_project(tmp_path)
    monkeypatch.chdir(project)

    pack = build_pack(["."], config_path="pyproject.toml")
    assert pack.mode == "project_snapshot"

    by_path = {
        candidate.file.relative.as_posix(): candidate for candidate in pack.candidates
    }

    # Entrypoint (e.g., src/app/main.py matches main.py pattern)
    assert by_path["src/app/main.py"].score == 90
    assert by_path["src/app/main.py"].reason_summary == "entrypoint file"

    # Test file (tests/test_auth.py)
    assert by_path["tests/test_auth.py"].score == 60
    assert by_path["tests/test_auth.py"].reason_summary == "test file"

    # Regular code file
    assert by_path["src/app/auth.py"].score == 80
    assert by_path["src/app/auth.py"].reason_summary == "code file"

    # Support files
    assert by_path["README.md"].score == 45
    assert by_path["README.md"].reason_summary == "project support file"

    # Ensure no near-seed duplication in project snapshot mode
    assert "near" not in by_path["README.md"].reason_summary
    assert "shared by multiple seed paths" not in by_path["README.md"].reasons


def test_dry_run_and_open_cli(tmp_path: Path, monkeypatch) -> None:
    from scriber.cli.main import main

    project = make_project(tmp_path)
    monkeypatch.chdir(project)

    # Test dry run
    code = main(["src/app/auth.py", "--dry-run"])
    assert code == 0

    # Ensure no output file was created under .scriber/out.md if it didn't exist
    assert not (tmp_path / ".scriber/out.md").exists()

    # Test open flag by mocking open_path to verify it gets called
    called_with = None

    def mock_open_path(path: Path) -> None:
        nonlocal called_with
        called_with = path

    monkeypatch.setattr("scriber.core.open_file.open_path", mock_open_path)
    code = main(["src/app/auth.py", "--open"])
    assert code == 0
    assert called_with == (tmp_path / ".scriber/out.md").resolve()


def test_no_support_excludes_support_files_project_snapshot(tmp_path: Path) -> None:
    project = make_project(tmp_path)

    pack = build_pack(["."], config_path=str(project / "pyproject.toml"), support=False)

    assert all(c.file.kind != "support" for c in pack.candidates)


def test_no_support_excludes_support_files_folder_seed(tmp_path: Path) -> None:
    project = make_project(tmp_path)

    pack = build_pack(["."], config_path=str(project / "pyproject.toml"), support=False)

    paths = {c.file.relative.as_posix() for c in pack.candidates}
    assert "README.md" not in paths
    assert "pyproject.toml" not in paths
