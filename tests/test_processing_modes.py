"""
Tests for single-process and multi-process execution modes in Scriber.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.scriber.core import Scriber


def test_single_process_mode_avoids_process_pool(tmp_path: Path):
    """
    Verifies that ProcessPoolExecutor is not used when single_process is True.
    """
    (tmp_path / "test.txt").write_text("hello world")

    with patch('src.scriber.core.ProcessPoolExecutor') as mock_executor:
        config = {"single_process": True, "exclude": []}
        scriber = Scriber(root_path=tmp_path, config=config)
        scriber.map_project()

    mock_executor.assert_not_called()
    stats = scriber.get_stats()
    assert stats['total_files'] == 1
    assert stats['total_tokens'] > 0


def test_multi_process_mode_uses_process_pool(tmp_path: Path):
    """
    Verifies that ProcessPoolExecutor is used by default (single_process is False).

    This test uses a more advanced mock to simulate the return of futures
    and ensure the statistics are correctly aggregated from the mocked results.
    """
    (tmp_path / "test.txt").write_text("hello world")
    expected_stats = {"size": 11, "tokens": 2, "lang": "text"}

    with patch('src.scriber.core.ProcessPoolExecutor') as MockProcessPoolExecutor, \
            patch('src.scriber.core.as_completed') as mock_as_completed:
        mock_future = MagicMock()
        mock_future.result.return_value = expected_stats
        mock_as_completed.return_value = [mock_future]

        mock_executor_instance = MockProcessPoolExecutor.return_value.__enter__.return_value

        config = {"single_process": False, "exclude": []}
        scriber = Scriber(root_path=tmp_path, config=config)
        scriber.map_project()

    MockProcessPoolExecutor.assert_called_once()
    assert mock_executor_instance.submit.called
    mock_as_completed.assert_called_once()

    stats = scriber.get_stats()
    assert stats['total_files'] == 1
    assert stats['total_size_bytes'] == expected_stats['size']
    assert stats['total_tokens'] == expected_stats['tokens']