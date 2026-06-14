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
        args, kwargs = mock_search.call_args
        assert args == ("rna-seq",)
        assert kwargs["sources"] == ["geo"]
        assert kwargs["max_per_source"] == 20
        assert callable(kwargs["on_error"])

    def test_search_reports_failed_source_without_aborting(self, runner: CliRunner) -> None:
        """A rate-limited source must surface a stderr warning, not abort (fb-2026-05-29-002)."""
        from science_tool.datasets import register, search_all

        class FlakyAdapter:
            name = "flaky"

            def search(self, query: str, *, max_results: int = 20) -> list[DatasetResult]:
                raise RuntimeError("429 Too Many Requests")

            def metadata(self, dataset_id: str) -> DatasetResult:  # pragma: no cover
                return DatasetResult(source="flaky", id=dataset_id, title="x")

            def files(self, dataset_id: str):  # pragma: no cover
                return []

            def download(self, file_info, dest_dir):  # pragma: no cover
                return dest_dir

        register("flaky", FlakyAdapter)
        # mix_stderr defaults so stderr is captured separately from stdout output
        result = runner.invoke(main, ["datasets", "search", "q", "--source", "flaky"])
        assert result.exit_code == 0
        combined = result.output + (result.stderr if result.stderr_bytes else "")
        assert "flaky" in combined and "429" in combined
        # search_all itself returns no rows (all sources failed) rather than raising
        assert search_all("q", sources=["flaky"], on_error=lambda *_: None) == []

    def test_search_empty_results(self, runner: CliRunner) -> None:
        with patch("science_tool.cli.search_all", return_value=[]):
            result = runner.invoke(main, ["datasets", "search", "nothing"])
        assert result.exit_code == 0
        assert "No datasets found" in result.output

    def test_search_json_includes_access(self, runner: CliRunner) -> None:
        mock_results = [
            DatasetResult(source="physionet", id="mmash", title="MMASH", access="public"),
        ]
        with patch("science_tool.cli.search_all", return_value=mock_results):
            result = runner.invoke(main, ["datasets", "search", "actigraphy", "--format", "json"])
        assert result.exit_code == 0
        import json

        data = json.loads(result.output)
        assert data["rows"][0]["access"] == "public"

    def test_metadata_json_includes_access(self, runner: CliRunner) -> None:
        from unittest.mock import MagicMock

        adapter = MagicMock()
        adapter.metadata.return_value = DatasetResult(
            source="sra", id="SRX111", title="RNA-seq", access="controlled"
        )
        with patch("science_tool.cli.get_adapter", return_value=adapter):
            result = runner.invoke(main, ["datasets", "metadata", "sra:SRX111", "--format", "json"])
        assert result.exit_code == 0
        import json

        rows = json.loads(result.output)["rows"]
        access_row = next(r for r in rows if r["field"] == "Access")
        assert access_row["value"] == "controlled"
