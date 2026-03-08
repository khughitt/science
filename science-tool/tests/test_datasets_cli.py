"""Tests for the datasets CLI command group."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from science_tool.cli import main
from science_tool.datasets._base import DatasetResult


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestDatasetsCLI:
    def test_sources_command(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["datasets", "sources"])
        assert result.exit_code == 0
        assert "zenodo" in result.output

    def test_search_table_format(self, runner: CliRunner) -> None:
        mock_results = [
            DatasetResult(source="zenodo", id="123", title="Test Dataset", year=2024, doi="10.5281/zenodo.123"),
        ]
        with patch("science_tool.cli.search_all", return_value=mock_results):
            result = runner.invoke(main, ["datasets", "search", "test query"])
        assert result.exit_code == 0
        assert "Test Dataset" in result.output

    def test_search_json_format(self, runner: CliRunner) -> None:
        mock_results = [
            DatasetResult(source="zenodo", id="123", title="Test Dataset", year=2024),
        ]
        with patch("science_tool.cli.search_all", return_value=mock_results):
            result = runner.invoke(main, ["datasets", "search", "test query", "--format", "json"])
        assert result.exit_code == 0
        import json

        data = json.loads(result.output)
        assert len(data["rows"]) == 1
        assert data["rows"][0]["title"] == "Test Dataset"

    def test_search_with_source_filter(self, runner: CliRunner) -> None:
        mock_results = [
            DatasetResult(source="geo", id="GSE12345", title="GEO Dataset"),
        ]
        with patch("science_tool.cli.search_all", return_value=mock_results) as mock_search:
            result = runner.invoke(main, ["datasets", "search", "rna-seq", "--source", "geo"])
        assert result.exit_code == 0
        mock_search.assert_called_once_with("rna-seq", sources=["geo"], max_per_source=20)

    def test_search_empty_results(self, runner: CliRunner) -> None:
        with patch("science_tool.cli.search_all", return_value=[]):
            result = runner.invoke(main, ["datasets", "search", "nothing"])
        assert result.exit_code == 0
        assert "No datasets found" in result.output
