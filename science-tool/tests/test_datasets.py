"""Tests for dataset adapter base types and registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.datasets._base import DatasetResult, FileInfo


class TestDatasetResult:
    def test_creation_minimal(self) -> None:
        r = DatasetResult(source="test", id="123", title="Test Dataset")
        assert r.source == "test"
        assert r.id == "123"
        assert r.title == "Test Dataset"
        assert r.doi is None
        assert r.keywords == []

    def test_creation_full(self) -> None:
        r = DatasetResult(
            source="zenodo",
            id="12345",
            title="RNA-seq of mouse liver",
            description="Bulk RNA-seq from 20 samples",
            doi="10.5281/zenodo.12345",
            url="https://zenodo.org/records/12345",
            year=2024,
            license="CC-BY-4.0",
            keywords=["RNA-seq", "mouse", "liver"],
            organism="Mus musculus",
            modality="RNA-seq",
            sample_count=20,
            file_count=3,
            total_size_bytes=1_000_000,
        )
        assert r.doi == "10.5281/zenodo.12345"
        assert r.organism == "Mus musculus"
        assert r.sample_count == 20

    def test_frozen(self) -> None:
        r = DatasetResult(source="test", id="1", title="T")
        with pytest.raises(AttributeError):
            r.title = "changed"  # type: ignore[misc]


class TestFileInfo:
    def test_creation(self) -> None:
        f = FileInfo(
            filename="data.csv",
            url="https://example.com/data.csv",
            size_bytes=1024,
            checksum="sha256:abc123",
            format="csv",
        )
        assert f.filename == "data.csv"
        assert f.format == "csv"

    def test_minimal(self) -> None:
        f = FileInfo(filename="data.csv", url="https://example.com/data.csv")
        assert f.size_bytes is None
        assert f.checksum is None


class TestRegistry:
    def test_register_and_get(self) -> None:
        from science_tool.datasets import available_adapters, get_adapter, register

        class FakeAdapter:
            name = "fake"

            def search(self, query: str, *, max_results: int = 20) -> list[DatasetResult]:
                return [DatasetResult(source="fake", id="1", title=query)]

            def metadata(self, dataset_id: str) -> DatasetResult:
                return DatasetResult(source="fake", id=dataset_id, title="Fake")

            def files(self, dataset_id: str) -> list[FileInfo]:
                return []

            def download(self, file_info: FileInfo, dest_dir: Path) -> Path:
                return dest_dir / file_info.filename

        register("fake", FakeAdapter)
        assert "fake" in available_adapters()
        adapter = get_adapter("fake")
        assert adapter.name == "fake"
        results = adapter.search("test query")
        assert len(results) == 1
        assert results[0].title == "test query"

    def test_search_all(self) -> None:
        from science_tool.datasets import search_all

        # Uses whatever adapters are registered (at least "fake" from above)
        results = search_all("test", sources=["fake"], max_per_source=5)
        assert len(results) >= 1

    def test_get_unknown_adapter_raises(self) -> None:
        from science_tool.datasets import get_adapter

        with pytest.raises(KeyError):
            get_adapter("nonexistent_adapter_xyz")
