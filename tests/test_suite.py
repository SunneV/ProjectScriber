"""
Tests for the main Scriber application, covering both core logic and the CLI.
"""
import io
import json
from collections import Counter
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import tiktoken

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from src.scriber.cli import format_bytes
from src.scriber.cli import main as cli_main
from src.scriber.config import ScriberConfig
from src.scriber.core import Scriber


def test_direct_import():
    """Tests that the Scriber class can be imported directly from the package."""
    try:
        from src.scriber import Scriber
    except ImportError:
        pytest.fail("Could not import Scriber from src.scriber")
    assert callable(Scriber)


# --- Test Core Scriber Functionality ---

class TestCore:
    """Groups tests for the Scriber core logic found in `src.scriber.core`."""

    def test_default_exclusion(self, tmp_path: Path):
        """Tests that default patterns like .git/ and __pycache__/ are excluded."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").touch()
        (tmp_path / "main.py").touch()
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "cache.pyc").touch()
        (tmp_path / "build").mkdir()
        (tmp_path / "build" / "app").touch()

        scriber = Scriber(root_path=tmp_path)
        scriber.map_project()

        paths = {p.relative_to(tmp_path).as_posix() for p in scriber.mapped_files}
        assert "main.py" in paths
        assert not any(p.startswith('.git/') for p in paths)
        assert not any(p.startswith('__pycache__/') for p in paths)
        assert not any(p.startswith('build/') for p in paths)

    def test_directory_only_exclusion(self, tmp_path: Path):
        """Tests that a pattern with a trailing slash only excludes the directory."""
        (tmp_path / "my_app").mkdir()
        (tmp_path / "my_app" / "code.py").touch()
        (tmp_path / "my_app_file").touch()

        config = ScriberConfig(exclude=["my_app/"], include=[])

        scriber = Scriber(root_path=tmp_path, config=config)
        scriber.map_project()
        paths = {p.name for p in scriber.mapped_files}

        assert "my_app_file" in paths
        assert "code.py" not in paths
        assert len(paths) == 1

    def test_root_anchored_exclusion(self, tmp_path: Path):
        """Tests that a pattern with a leading slash only excludes at the root."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "config.yml").touch()
        (tmp_path / "config.yml").touch()
        config = ScriberConfig(exclude=["/config.yml"], include=[])

        scriber = Scriber(root_path=tmp_path, config=config)
        scriber.map_project()
        paths = {p.relative_to(tmp_path).as_posix() for p in scriber.mapped_files}

        assert "src/config.yml" in paths
        assert "config.yml" not in paths

    def test_unanchored_exclusion(self, tmp_path: Path):
        """Tests that a pattern without slashes excludes files/dirs anywhere."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "temp.log").touch()
        (tmp_path / "temp.log").touch()
        config = ScriberConfig(exclude=["temp.log"], include=[])

        scriber = Scriber(root_path=tmp_path, config=config)
        scriber.map_project()

        assert not scriber.mapped_files

    def test_gitignore_handling(self, tmp_path: Path):
        """Ensures .gitignore rules are correctly applied when enabled."""
        (tmp_path / "main.py").touch()
        (tmp_path / "ignored.log").touch()
        (tmp_path / ".gitignore").write_text("*.log")

        scriber = Scriber(root_path=tmp_path)
        scriber.map_project()

        paths = {p.name for p in scriber.mapped_files}
        assert "main.py" in paths
        assert "ignored.log" not in paths

    def test_disable_gitignore(self, tmp_path: Path):
        """Ensures .gitignore is ignored when `use_gitignore` is false in the config."""
        (tmp_path / "main.py").touch()
        (tmp_path / "not_ignored.log").touch()
        (tmp_path / ".gitignore").write_text("*.log")
        config = {"use_gitignore": False, "exclude": []}
        (tmp_path / ".scriber.json").write_text(json.dumps(config))

        scriber = Scriber(root_path=tmp_path)
        scriber.map_project()

        paths = {p.name for p in scriber.mapped_files}
        assert "main.py" in paths
        assert "not_ignored.log" in paths

    def test_binary_file_skipping(self, tmp_path: Path):
        """Tests that binary files are detected and correctly skipped."""
        (tmp_path / "app.exe").write_bytes(b"\x4d\x5a\x90\x00\x03\x00\x00\x00")

        config = ScriberConfig(include=["app.exe"], exclude=[])
        scriber = Scriber(root_path=tmp_path, config=config)
        scriber.map_project()

        assert len(scriber.mapped_files) == 0
        assert scriber.get_stats()['skipped_binary'] == 1

    def test_include_patterns(self, tmp_path: Path):
        """Tests that 'include' patterns correctly filter files when provided."""
        (tmp_path / "main.py").touch()
        (tmp_path / "script.js").touch()
        (tmp_path / "style.css").touch()
        (tmp_path / ".scriber.json").write_text(json.dumps({"include": ["*.py", "*.js"]}))

        scriber = Scriber(root_path=tmp_path)
        scriber.map_project()

        paths = {p.name for p in scriber.mapped_files}
        assert paths == {"main.py", "script.js"}

    def test_exclude_map_dictionary(self, tmp_path: Path):
        """Tests that the exclude_map dictionary filter works as intended."""
        (tmp_path / "app.py").touch()
        (tmp_path / "utils_test.py").touch()
        (tmp_path / "script.js").touch()
        (tmp_path / "archive.log").touch()
        (tmp_path / "README.md").touch()

        config = ScriberConfig(
            exclude_map={
                "python": ["*_test.py"],
                "global": ["*.log"]
            },
            exclude=[],
            include=[]
        )
        scriber = Scriber(root_path=tmp_path, config=config)
        files = scriber.get_mapped_files()
        mapped_names = {p.name for p in files}

        assert "app.py" in mapped_names
        assert "script.js" in mapped_names
        assert "README.md" in mapped_names
        assert "utils_test.py" not in mapped_names
        assert "archive.log" not in mapped_names
        assert len(mapped_names) == 3

    def test_hidden_files_are_in_tree_but_content_is_skipped(self, tmp_path: Path):
        """Tests that hidden files appear in the tree but their content is not in the output."""
        (tmp_path / "main.py").write_text("print('hello')")
        lock_content = "some-lock-file-content"
        (tmp_path / "poetry.lock").write_text(lock_content)
        config = {"hidden": ["poetry.lock"], "exclude": []}
        (tmp_path / ".scriber.json").write_text(json.dumps(config))

        scriber = Scriber(root_path=tmp_path)
        scriber.map_project()

        output_buffer = io.StringIO()
        scriber._write_output(output_buffer, tree_only=False, progress=None, task_id=None)
        output = output_buffer.getvalue()

        assert "poetry.lock" in output
        assert "[Content hidden based on configuration]" in output
        assert lock_content not in output
        assert "print('hello')" in output

    def test_hidden_files_are_excluded_from_token_count(self, tmp_path: Path):
        """Tests that hidden files contribute to size but not token count."""
        main_py_content = "def main(): pass"
        (tmp_path / "main.py").write_text(main_py_content)
        (tmp_path / "poetry.lock").write_text("some-lock-file-content")
        config = {"hidden": ["poetry.lock"], "exclude": [".scriber.json"]}
        (tmp_path / ".scriber.json").write_text(json.dumps(config))

        scriber = Scriber(root_path=tmp_path)
        scriber.map_project()
        stats = scriber.get_stats()

        tokenizer = tiktoken.get_encoding("cl100k_base")
        expected_tokens = len(tokenizer.encode(main_py_content))

        assert stats["total_files"] == 2
        assert stats["total_tokens"] == expected_tokens
        assert stats["total_size_bytes"] == (
            (tmp_path / "main.py").stat().st_size +
            (tmp_path / "poetry.lock").stat().st_size
        )

    def test_init_with_direct_config_object(self, tmp_path: Path):
        """Tests that Scriber can be configured directly with a ScriberConfig object."""
        (tmp_path / "app.py").touch()
        (tmp_path / "data.json").touch()
        direct_config = ScriberConfig(include=["*.py"], exclude=[])

        scriber = Scriber(root_path=tmp_path, config=direct_config)
        files = scriber.get_mapped_files()

        paths = {p.name for p in files}
        assert paths == {"app.py"}
        assert scriber.config_path_used is None

    def test_get_output_as_string(self, tmp_path: Path):
        """Tests that the full project map can be retrieved as a string."""
        (tmp_path / "main.py").write_text("print('test')")
        scriber = Scriber(root_path=tmp_path)
        output_str = scriber.get_output_as_string()

        assert isinstance(output_str, str)
        assert "Mapped Folder Structure" in output_str
        assert "main.py" in output_str
        assert "print('test')" in output_str

    def test_getters_trigger_map_project_automatically(self, tmp_path: Path):
        """Tests that getter methods automatically call map_project if not already run."""
        (tmp_path / "test.txt").touch()
        scriber = Scriber(root_path=tmp_path)

        assert not scriber.mapped_files
        stats = scriber.get_stats()
        assert len(scriber.mapped_files) == 1
        assert stats["total_files"] == 1

    def test_core_loads_external_toml_config(self, tmp_path: Path):
        """Tests core logic loads config from an external pyproject.toml via config_path."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        toml_path = config_dir / "pyproject.toml"
        toml_path.write_text("[tool.scriber]\ninclude = ['*.py']")

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "app.py").touch()
        (project_dir / "data.json").touch()

        scriber = Scriber(root_path=project_dir, config_path=toml_path)
        scriber.map_project()

        paths = {p.name for p in scriber.mapped_files}
        assert paths == {"app.py"}
        assert scriber.config_path_used == toml_path

    def test_core_handles_nonexistent_config_path(self, tmp_path: Path, capsys):
        """Tests that a warning is printed for a non-existent --config path."""
        non_existent_path = tmp_path / "nonexistent.json"
        Scriber(root_path=tmp_path, config_path=non_existent_path)
        captured = capsys.readouterr()
        assert "Warning: Config file specified by --config not found" in captured.err

    def test_tree_representation(self, tmp_path: Path):
        """Checks if the folder tree string is formatted correctly."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").touch()
        (tmp_path / "README.md").touch()

        scriber = Scriber(root_path=tmp_path)
        scriber.map_project()
        tree_str = scriber._get_tree_representation()

        expected_lines = [
            tmp_path.name,
            "├── README.md",
            "└── src",
            "    └── main.py",
        ]
        actual_lines = tree_str.split('\n')
        # The tree formatting can have subtle whitespace differences, so we check line by line
        assert actual_lines[0] == expected_lines[0]
        assert "README.md" in actual_lines[1]
        assert "src" in actual_lines[2]
        assert "main.py" in actual_lines[3]


    @pytest.mark.parametrize("filename, expected_lang", [
        ("test.py", "python"),
        ("script.js", "javascript"),
        ("style.css", "css"),
        ("Dockerfile", "dockerfile"),
        ("unknown.xyz", ""),
    ])
    def test_language_detection(self, tmp_path: Path, filename: str, expected_lang: str):
        """Tests the language mapping utility for various file types."""
        scriber = Scriber(root_path=tmp_path)
        lang = scriber._get_language(Path(filename))
        assert lang == expected_lang

    def test_multi_root_collection(self, tmp_path: Path):
        """Tests that files from multiple root directories are collected."""
        project_a = tmp_path / "project_a"
        project_a.mkdir()
        (project_a / "a.py").touch()

        project_b = tmp_path / "project_b"
        project_b.mkdir()
        (project_b / "b.js").touch()

        scriber = Scriber(root_path=[project_a, project_b])
        scriber.map_project()
        mapped_names = {p.name for p in scriber.mapped_files}

        assert mapped_names == {"a.py", "b.js"}
        assert len(scriber.mapped_files) == 2

    def test_multi_root_tree_and_output(self, tmp_path: Path):
        """Tests tree and output format for multiple roots."""
        project_a = tmp_path / "project_a"
        project_a.mkdir()
        (project_a / "a.py").write_text("print('a')")

        project_b = tmp_path / "project_b"
        project_b.mkdir()
        (project_b / "b.js").write_text("console.log('b')")

        scriber = Scriber(root_path=[project_a, project_b])
        output = scriber.get_output_as_string()

        assert "project_a\n└── a.py" in output
        assert "project_b\n└── b.js" in output
        assert f"File: project_a/a.py" in output
        assert f"File: project_b/b.js" in output

# --- Test CLI Functionality ---

class TestCli:
    """Groups tests for the command-line interface in `src.scriber.cli`."""

    @patch('src.scriber.cli.run_scriber')
    def test_cli_run_command_is_default(self, mock_run_scriber, mocker):
        """Tests that the 'run' command is triggered by default with no subcommand."""
        mocker.patch('sys.argv', ['scriber'])
        cli_main()
        mock_run_scriber.assert_called_once()

    @patch('src.scriber.cli.Scriber')
    def test_cli_arguments_are_passed_correctly(self, mock_scriber, mocker, tmp_path: Path):
        """Tests if CLI arguments are correctly parsed and passed to the Scriber class."""
        mock_instance = MagicMock()
        mock_instance.get_output_as_string.return_value = "Mocked Output"
        mock_instance.config = ScriberConfig(output="default_name.txt")
        mock_instance.get_stats.return_value = {'total_files': 0, 'language_counts': Counter()}
        mock_instance.get_file_count.return_value = 0
        mock_scriber.return_value = mock_instance
        mocker.patch('pyperclip.copy')

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        config_file = tmp_path / "config.json"
        config_file.touch()

        test_path_str = str(project_dir)
        test_output = "output.txt"
        test_config_str = str(config_file)

        mocker.patch('sys.argv', [
            'scriber', 'run', test_path_str, '--output', test_output, '--config', test_config_str, '--tree-only'
        ])

        cli_main()

        mock_scriber.assert_called_with(Path(test_path_str).resolve(), config_path=Path(test_config_str))

        mock_instance.get_output_as_string.assert_called_once()
        call_kwargs = mock_instance.get_output_as_string.call_args.kwargs
        assert call_kwargs['tree_only'] is True

        output_file = project_dir / test_output
        assert output_file.is_file()
        assert output_file.read_text() == "Mocked Output"

    @patch('src.scriber.cli.Confirm.ask')
    @patch('src.scriber.cli.Prompt.ask')
    def test_cli_init_command_creates_config(self, mock_prompt, mock_confirm, tmp_path: Path, mocker):
        """Tests the interactive 'init' command for config file creation."""
        mocker.patch('pathlib.Path.cwd', return_value=tmp_path)
        mock_confirm.return_value = False
        mock_prompt.side_effect = ["*.tmp, *.log", "*.py", "", "1"]

        mocker.patch('sys.argv', ['scriber', 'init'])
        cli_main()

        config_path = tmp_path / ".scriber.json"
        assert config_path.exists()

        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert not data['use_gitignore']
        assert data['exclude'] == ['*.tmp', '*.log']
        assert data['include'] == ['*.py']

    @patch('src.scriber.cli.Confirm.ask')
    @patch('src.scriber.cli.Prompt.ask')
    def test_cli_init_command_creates_config_in_toml(self, mock_prompt, mock_confirm, tmp_path: Path, mocker):
        """Tests the interactive 'init' command for saving config to pyproject.toml."""
        mocker.patch('pathlib.Path.cwd', return_value=tmp_path)

        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text("[project]\nname = 'test-project'")

        mock_confirm.return_value = True
        mock_prompt.side_effect = ["*.log, .env", "*.py", "*.lock", "2"]

        mocker.patch('sys.argv', ['scriber', 'init'])
        cli_main()

        assert pyproject_path.exists()

        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        assert "tool" in data
        assert "scriber" in data["tool"]
        scriber_config = data["tool"]["scriber"]
        assert scriber_config['use_gitignore'] is True
        assert scriber_config['exclude'] == ['*.log', '.env']
        assert scriber_config['include'] == ['*.py']
        assert scriber_config['hidden'] == ['*.lock']

    @pytest.mark.parametrize("bytes_val, expected_str", [
        (500, "500 Bytes"),
        (2048, "2.00 KB"),
        (1500000, "1.43 MB"),
        (2 * 1024 * 1024, "2.00 MB"),
    ])
    def test_format_bytes_utility(self, bytes_val: int, expected_str: str):
        """Tests the byte formatting utility function."""
        assert format_bytes(bytes_val) == expected_str