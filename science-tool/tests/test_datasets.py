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


# ---------------------------------------------------------------------------
# Zenodo adapter tests
# ---------------------------------------------------------------------------
from unittest.mock import MagicMock, patch

from science_tool.datasets.zenodo import ZenodoAdapter


class TestZenodoAdapter:
    def test_name(self) -> None:
        adapter = ZenodoAdapter()
        assert adapter.name == "zenodo"

    def test_search_parses_response(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "hits": {
                "hits": [
                    {
                        "id": 12345,
                        "metadata": {
                            "title": "Test Dataset",
                            "description": "A test",
                            "doi": "10.5281/zenodo.12345",
                            "publication_date": "2024-01-15",
                            "license": {"id": "cc-by-4.0"},
                            "keywords": ["test", "data"],
                        },
                        "links": {"self_html": "https://zenodo.org/records/12345"},
                        "files": [
                            {"key": "data.csv", "size": 1024},
                        ],
                    }
                ]
            }
        }

        adapter = ZenodoAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.return_value = mock_response
            results = adapter.search("test query", max_results=10)

        assert len(results) == 1
        r = results[0]
        assert r.source == "zenodo"
        assert r.id == "12345"
        assert r.title == "Test Dataset"
        assert r.doi == "10.5281/zenodo.12345"
        assert r.year == 2024
        assert r.file_count == 1
        assert r.total_size_bytes == 1024

    def test_metadata_parses_record(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 99999,
            "metadata": {
                "title": "Specific Record",
                "description": "Details",
                "doi": "10.5281/zenodo.99999",
                "publication_date": "2023-06-01",
                "license": {"id": "cc0-1.0"},
                "keywords": [],
            },
            "links": {"self_html": "https://zenodo.org/records/99999"},
            "files": [],
        }

        adapter = ZenodoAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.return_value = mock_response
            result = adapter.metadata("99999")

        assert result.id == "99999"
        assert result.title == "Specific Record"
        assert result.license == "cc0-1.0"

    def test_files_parses_list(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 12345,
            "metadata": {"title": "T", "description": "", "publication_date": "2024-01-01"},
            "links": {},
            "files": [
                {
                    "key": "data.csv",
                    "size": 2048,
                    "checksum": "md5:abc123def456",
                    "links": {"self": "https://zenodo.org/api/records/12345/files/data.csv/content"},
                },
                {
                    "key": "readme.txt",
                    "size": 256,
                    "checksum": "md5:789xyz",
                    "links": {"self": "https://zenodo.org/api/records/12345/files/readme.txt/content"},
                },
            ],
        }

        adapter = ZenodoAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.return_value = mock_response
            files = adapter.files("12345")

        assert len(files) == 2
        assert files[0].filename == "data.csv"
        assert files[0].size_bytes == 2048
        assert files[0].checksum == "md5:abc123def456"
        assert files[1].filename == "readme.txt"

    def test_search_empty_results(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"hits": {"hits": []}}

        adapter = ZenodoAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.return_value = mock_response
            results = adapter.search("nonexistent gibberish query")

        assert results == []


# ---------------------------------------------------------------------------
# Dryad adapter tests
# ---------------------------------------------------------------------------
from science_tool.datasets.dryad import DryadAdapter


class TestDryadAdapter:
    def test_name(self) -> None:
        assert DryadAdapter().name == "dryad"

    def test_search_parses_response(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "_embedded": {
                "stash:datasets": [
                    {
                        "identifier": "doi:10.5061/dryad.abc123",
                        "title": "Dryad Test Dataset",
                        "abstract": "A curated dataset",
                        "publicationDate": "2024-03-15",
                        "license": "https://creativecommons.org/publicdomain/zero/1.0/",
                        "keywords": ["ecology", "birds"],
                        "_links": {"stash:version": {"href": "/api/v2/versions/111"}},
                    }
                ]
            },
            "total": 1,
        }

        adapter = DryadAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.return_value = mock_response
            results = adapter.search("ecology birds")

        assert len(results) == 1
        r = results[0]
        assert r.source == "dryad"
        assert r.doi == "10.5061/dryad.abc123"
        assert r.year == 2024
        assert "ecology" in r.keywords

    def test_files_parses_list(self) -> None:
        meta_response = MagicMock()
        meta_response.status_code = 200
        meta_response.json.return_value = {
            "identifier": "doi:10.5061/dryad.abc123",
            "title": "T",
            "abstract": "",
            "publicationDate": "2024-01-01",
            "_links": {"stash:version": {"href": "/api/v2/versions/111"}},
        }

        files_response = MagicMock()
        files_response.status_code = 200
        files_response.json.return_value = {
            "_embedded": {
                "stash:files": [
                    {
                        "path": "observations.csv",
                        "size": 4096,
                        "digestType": "md5",
                        "digest": "aabbcc",
                        "_links": {"stash:download": {"href": "/api/v2/files/222/download"}},
                    }
                ]
            }
        }

        adapter = DryadAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.side_effect = [meta_response, files_response]
            files = adapter.files("doi:10.5061/dryad.abc123")

        assert len(files) == 1
        assert files[0].filename == "observations.csv"
        assert files[0].size_bytes == 4096

    def test_search_empty(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"_embedded": {"stash:datasets": []}, "total": 0}

        adapter = DryadAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.return_value = mock_response
            results = adapter.search("zzzzz nonexistent")

        assert results == []


# ---------------------------------------------------------------------------
# GEO adapter tests
# ---------------------------------------------------------------------------
from science_tool.datasets.geo import GEOAdapter


class TestGEOAdapter:
    def test_name(self) -> None:
        assert GEOAdapter().name == "geo"

    def test_parse_esummary_xml(self) -> None:
        xml_text = """<?xml version="1.0" encoding="UTF-8"?>
        <eSummaryResult>
            <DocSum>
                <Id>200012345</Id>
                <Item Name="Accession" Type="String">GSE12345</Item>
                <Item Name="title" Type="String">RNA-seq of human brain</Item>
                <Item Name="summary" Type="String">Transcriptome profiling</Item>
                <Item Name="GPL" Type="String">GPL16791</Item>
                <Item Name="GSE" Type="String">GSE12345</Item>
                <Item Name="taxon" Type="String">Homo sapiens</Item>
                <Item Name="gdsType" Type="String">Expression profiling by high throughput sequencing</Item>
                <Item Name="PDAT" Type="String">2024/01/15</Item>
                <Item Name="n_samples" Type="Integer">48</Item>
                <Item Name="PubMedIds" Type="List">
                    <Item Name="int" Type="Integer">38000001</Item>
                </Item>
            </DocSum>
        </eSummaryResult>"""

        adapter = GEOAdapter()
        results = adapter._parse_esummary(xml_text)
        assert len(results) == 1
        r = results[0]
        assert r.source == "geo"
        assert r.id == "GSE12345"
        assert r.title == "RNA-seq of human brain"
        assert r.organism == "Homo sapiens"
        assert r.modality == "Expression profiling by high throughput sequencing"
        assert r.year == 2024
        assert r.sample_count == 48

    def test_search_calls_esearch_then_esummary(self) -> None:
        esearch_resp = MagicMock()
        esearch_resp.status_code = 200
        esearch_resp.text = """<?xml version="1.0"?>
        <eSearchResult>
            <Count>1</Count>
            <IdList><Id>200099999</Id></IdList>
        </eSearchResult>"""

        esummary_resp = MagicMock()
        esummary_resp.status_code = 200
        esummary_resp.text = """<?xml version="1.0"?>
        <eSummaryResult>
            <DocSum>
                <Id>200099999</Id>
                <Item Name="Accession" Type="String">GSE99999</Item>
                <Item Name="title" Type="String">Test GEO</Item>
                <Item Name="summary" Type="String">Test</Item>
                <Item Name="taxon" Type="String">Mus musculus</Item>
                <Item Name="gdsType" Type="String">Expression profiling by array</Item>
                <Item Name="PDAT" Type="String">2023/06/01</Item>
                <Item Name="n_samples" Type="Integer">12</Item>
            </DocSum>
        </eSummaryResult>"""

        adapter = GEOAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.side_effect = [esearch_resp, esummary_resp]
            results = adapter.search("test query", max_results=5)

        assert len(results) == 1
        assert results[0].id == "GSE99999"
        assert results[0].organism == "Mus musculus"

    def test_files_returns_standard_geo_urls(self) -> None:
        adapter = GEOAdapter()
        files = adapter._build_file_list("GSE12345")
        filenames = [f.filename for f in files]
        assert any("soft" in fn.lower() or "SOFT" in fn for fn in filenames)
        assert any("matrix" in fn.lower() for fn in filenames)
        assert all(f.url.startswith("https://") for f in files)

    def test_search_empty(self) -> None:
        esearch_resp = MagicMock()
        esearch_resp.status_code = 200
        esearch_resp.text = """<?xml version="1.0"?>
        <eSearchResult><Count>0</Count><IdList></IdList></eSearchResult>"""

        adapter = GEOAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.return_value = esearch_resp
            results = adapter.search("zzzzz nothing")

        assert results == []
