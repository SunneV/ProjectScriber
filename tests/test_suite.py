import json
from collections import Counter
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from src.scriber.cli import format_bytes
from src.scriber.cli import main as cli_main
from src.scriber.core import Scriber


# --- Test Core Scriber Functionality ---

class TestCore:
    """Groups tests for the Scriber core logic found in `src.scriber.core`."""

    def test_default_exclusion(self, tmp_path: Path):
        """Tests that default patterns like .git and __pycache__ are always excluded."""
        (tmp_path / ".git").mkdir()
        (tmp_path / "main.py").touch()
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "cache.pyc").touch()

        scriber = Scriber(root_path=tmp_path)
        scriber.map_project()

        paths = {p.name for p in scriber.mapped_files}
        assert "main.py" in paths
        assert ".git" not in paths
        assert "__pycache__" not in paths

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

        scriber = Scriber(root_path=tmp_path)
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
        assert actual_lines == expected_lines

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
    def test_cli_arguments_are_passed_correctly(self, mock_scriber, mocker):
        """Tests if CLI arguments are correctly parsed and passed to the Scriber class."""
        mock_instance = MagicMock()
        mock_instance.get_stats.return_value = {'total_files': 0, 'language_counts': Counter()}
        mock_instance.get_file_count.return_value = 0
        mock_scriber.return_value = mock_instance
        mocker.patch('pyperclip.copy')

        test_path = "/tmp/project"
        test_output = "output.txt"
        test_config = "/tmp/config.json"

        mocker.patch('sys.argv', [
            'scriber', test_path, '--output', test_output, '--config', test_config, '--tree-only'
        ])

        cli_main()

        mock_scriber.assert_called_with(Path(test_path).resolve(), config_path=Path(test_config))

        call = mock_instance.generate_output_file.call_args
        assert call.args[0] == test_output
        assert call.kwargs['tree_only'] is True

    @patch('src.scriber.cli.Confirm.ask')
    @patch('src.scriber.cli.Prompt.ask')
    def test_cli_init_command_creates_config(self, mock_prompt, mock_confirm, tmp_path: Path, mocker):
        """Tests the interactive 'init' command for config file creation."""
        mocker.patch('pathlib.Path.cwd', return_value=tmp_path)
        mock_confirm.return_value = False
        mock_prompt.side_effect = ["*.tmp, *.log", "*.py", "1"]

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
        mock_prompt.side_effect = ["*.log, .env", "*.py", "2"]

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

    @pytest.mark.parametrize("bytes_val, expected_str", [
        (500, "500 Bytes"),
        (2048, "2.00 KB"),
        (1500000, "1.43 MB"),
        (2 * 1024 * 1024, "2.00 MB"),
    ])
    def test_format_bytes_utility(self, bytes_val: int, expected_str: str):
        """Tests the byte formatting utility function."""
        assert format_bytes(bytes_val) == expected_str