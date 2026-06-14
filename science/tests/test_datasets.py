"""Tests for dataset adapter base types and registry."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from science_tool.datasets._base import DatasetResult, FileInfo
import httpx

from science_tool.datasets.arrayexpress import ArrayExpressAdapter
from science_tool.datasets.dryad import DryadAdapter
from science_tool.datasets.figshare import FigshareAdapter
from science_tool.datasets.geo import GEOAdapter
from science_tool.datasets.physionet import PhysioNetAdapter
from science_tool.datasets.semantic_scholar import SemanticScholarAdapter
from science_tool.datasets.sra import SRAAdapter
from science_tool.datasets.zenodo import ZenodoAdapter


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

    def test_access_defaults_none_and_accepts_canonical(self) -> None:
        assert DatasetResult(source="s", id="1", title="T").access is None
        r = DatasetResult(source="s", id="1", title="T", access="restricted")
        assert r.access == "restricted"


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

    def test_search_all_degrades_when_one_adapter_fails(self) -> None:
        """A single failing adapter must not abort the whole fan-out.

        Regression for fb-2026-05-29-002: a semantic_scholar 429 killed the
        entire 'datasets search', hiding GEO/zenodo/dryad results. search_all
        should skip the failing source, return partial results, and report the
        error via on_error rather than raising.
        """
        from science_tool.datasets import register, search_all

        class GoodAdapter:
            name = "good"

            def search(self, query: str, *, max_results: int = 20) -> list[DatasetResult]:
                return [DatasetResult(source="good", id="1", title=query)]

            def metadata(self, dataset_id: str) -> DatasetResult:
                return DatasetResult(source="good", id=dataset_id, title="Good")

            def files(self, dataset_id: str) -> list[FileInfo]:
                return []

            def download(self, file_info: FileInfo, dest_dir: Path) -> Path:
                return dest_dir / file_info.filename

        class RateLimitedAdapter(GoodAdapter):
            name = "ratelimited"

            def search(self, query: str, *, max_results: int = 20) -> list[DatasetResult]:
                raise RuntimeError("429 Too Many Requests")

        register("good", GoodAdapter)
        register("ratelimited", RateLimitedAdapter)

        errors: list[tuple[str, Exception]] = []
        results = search_all(
            "q",
            sources=["ratelimited", "good"],
            on_error=lambda name, exc: errors.append((name, exc)),
        )

        assert [r.source for r in results] == ["good"]
        assert len(errors) == 1
        assert errors[0][0] == "ratelimited"
        assert isinstance(errors[0][1], RuntimeError)

    def test_search_all_dedupes_by_doi(self) -> None:
        """The same DOI from two sources collapses to one ranked result."""
        from science_tool.datasets import register, search_all

        class ZenodoLike:
            name = "zlike"

            def search(self, query: str, *, max_results: int = 20) -> list[DatasetResult]:
                return [DatasetResult(source="zlike", id="1", title="shared", doi="10.1/dup")]

            def metadata(self, dataset_id: str) -> DatasetResult:  # pragma: no cover
                return DatasetResult(source="zlike", id=dataset_id, title="x")

            def files(self, dataset_id: str) -> list[FileInfo]:  # pragma: no cover
                return []

            def download(self, file_info: FileInfo, dest_dir: Path) -> Path:  # pragma: no cover
                return dest_dir

        class FigshareLike(ZenodoLike):
            name = "flike"

            def search(self, query: str, *, max_results: int = 20) -> list[DatasetResult]:
                return [DatasetResult(source="flike", id="2", title="shared", doi="10.1/dup", organism="mouse")]

        register("zlike", ZenodoLike)
        register("flike", FigshareLike)
        results = search_all("shared", sources=["zlike", "flike"])
        assert len(results) == 1
        # richer (organism-bearing) figshare record is the representative
        assert results[0].source == "flike"

    def test_search_all_ranks_by_relevance(self) -> None:
        """More query-relevant results sort first."""
        from science_tool.datasets import register, search_all

        class TwoHits:
            name = "twohits"

            def search(self, query: str, *, max_results: int = 20) -> list[DatasetResult]:
                return [
                    DatasetResult(source="twohits", id="1", title="unrelated record"),
                    DatasetResult(source="twohits", id="2", title="circadian rhythm record"),
                ]

            def metadata(self, dataset_id: str) -> DatasetResult:  # pragma: no cover
                return DatasetResult(source="twohits", id=dataset_id, title="x")

            def files(self, dataset_id: str) -> list[FileInfo]:  # pragma: no cover
                return []

            def download(self, file_info: FileInfo, dest_dir: Path) -> Path:  # pragma: no cover
                return dest_dir

        register("twohits", TwoHits)
        results = search_all("circadian rhythm", sources=["twohits"])
        assert [r.id for r in results] == ["2", "1"]

    def test_search_all_rank_false_preserves_concatenation(self) -> None:
        """rank=False returns the raw fan-out order and count (no dedup/rank)."""
        from science_tool.datasets import register, search_all

        class DupSource:
            name = "dupsource"

            def search(self, query: str, *, max_results: int = 20) -> list[DatasetResult]:
                return [
                    DatasetResult(source="dupsource", id="1", title="unrelated", doi="10.1/dup"),
                    DatasetResult(source="dupsource", id="2", title="circadian", doi="10.1/dup"),
                ]

            def metadata(self, dataset_id: str) -> DatasetResult:  # pragma: no cover
                return DatasetResult(source="dupsource", id=dataset_id, title="x")

            def files(self, dataset_id: str) -> list[FileInfo]:  # pragma: no cover
                return []

            def download(self, file_info: FileInfo, dest_dir: Path) -> Path:  # pragma: no cover
                return dest_dir

        register("dupsource", DupSource)
        results = search_all("circadian", sources=["dupsource"], rank=False)
        assert [r.id for r in results] == ["1", "2"]

    def test_get_unknown_adapter_raises(self) -> None:
        from science_tool.datasets import get_adapter

        with pytest.raises(KeyError):
            get_adapter("nonexistent_adapter_xyz")


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


class TestSemanticScholarAdapter:
    def test_name(self) -> None:
        assert SemanticScholarAdapter().name == "semantic_scholar"

    def test_search_parses_response(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total": 1,
            "data": [
                {
                    "paperId": "abc123",
                    "title": "A study on datasets",
                    "abstract": "We present a new dataset...",
                    "year": 2024,
                    "externalIds": {"DOI": "10.1234/test.5678", "PMID": "38000001"},
                    "url": "https://www.semanticscholar.org/paper/abc123",
                    "openAccessPdf": {"url": "https://example.com/paper.pdf"},
                    "fieldsOfStudy": ["Biology", "Computer Science"],
                    "citationCount": 42,
                }
            ],
        }

        adapter = SemanticScholarAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.return_value = mock_response
            results = adapter.search("datasets biology")

        assert len(results) == 1
        r = results[0]
        assert r.source == "semantic_scholar"
        assert r.id == "abc123"
        assert r.doi == "10.1234/test.5678"
        assert r.year == 2024
        assert "Biology" in r.keywords

    def test_metadata_by_doi(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "paperId": "xyz789",
            "title": "Specific Paper",
            "abstract": "Details",
            "year": 2023,
            "externalIds": {"DOI": "10.1234/specific"},
            "url": "https://www.semanticscholar.org/paper/xyz789",
            "fieldsOfStudy": [],
            "citationCount": 10,
        }

        adapter = SemanticScholarAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.return_value = mock_response
            result = adapter.metadata("DOI:10.1234/specific")

        assert result.id == "xyz789"
        assert result.title == "Specific Paper"

    def test_search_empty(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"total": 0, "data": []}

        adapter = SemanticScholarAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.return_value = mock_response
            results = adapter.search("nonexistent")

        assert results == []


class TestCBioPortalAdapter:
    # Sample of the public cbioportal.org /api/studies SUMMARY projection.
    _CATALOG = [
        {
            "studyId": "gbm_cptac_2021",
            "name": "Glioblastoma (CPTAC, Cell 2021)",
            "description": "CPTAC <A HREF=\"x\">Glioblastoma</A> proteogenomics.",
            "cancerTypeId": "gbm",
            "allSampleCount": 99,
            "publicStudy": True,
        },
        {
            "studyId": "brca_tcga_pub2015",
            "name": "Breast Invasive Carcinoma (TCGA, Cell 2015)",
            "description": "TCGA breast cohort.",
            "cancerTypeId": "brca",
            "allSampleCount": 816,
            "publicStudy": True,
        },
    ]

    def _catalog_response(self) -> MagicMock:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = self._CATALOG
        return resp

    def test_name(self) -> None:
        from science_tool.datasets.cbioportal import CBioPortalAdapter

        assert CBioPortalAdapter().name == "cbioportal"

    def test_search_matches_case_insensitively(self) -> None:
        # The public API's `keyword` filter is case-sensitive; the adapter must
        # match a lowercase query against title-cased study names so oncology
        # cohorts are actually reachable (fb-2026-05-30-013/014).
        from science_tool.datasets.cbioportal import CBioPortalAdapter

        adapter = CBioPortalAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.return_value = self._catalog_response()
            results = adapter.search("glioblastoma", max_results=10)

        assert len(results) == 1
        r = results[0]
        assert r.source == "cbioportal"
        assert r.id == "gbm_cptac_2021"
        assert r.title == "Glioblastoma (CPTAC, Cell 2021)"
        assert r.year == 2021
        # allSampleCount is a placeholder (1) in the list endpoint, so search
        # results deliberately do not report a sample count.
        assert r.sample_count is None
        assert "https://www.cbioportal.org/study/summary?id=gbm_cptac_2021" == r.url
        # HTML tags stripped from the description.
        assert "<A" not in r.description

    def test_metadata_fetches_real_sample_count(self) -> None:
        # The study object reports allSampleCount=1 (placeholder); the real count
        # comes only from the dedicated /samples listing.
        from science_tool.datasets.cbioportal import CBioPortalAdapter

        study_resp = MagicMock()
        study_resp.status_code = 200
        study_resp.json.return_value = {
            "studyId": "gbm_tcga_pub2013",
            "name": "Glioblastoma (TCGA, Cell 2013)",
            "description": "TCGA GBM.",
            "cancerTypeId": "gbm",
            "allSampleCount": 1,
        }
        samples_resp = MagicMock()
        samples_resp.status_code = 200
        samples_resp.json.return_value = [{"sampleId": f"s{i}"} for i in range(577)]

        adapter = CBioPortalAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.side_effect = [study_resp, samples_resp]
            result = adapter.metadata("gbm_tcga_pub2013")

        assert result.id == "gbm_tcga_pub2013"
        assert result.sample_count == 577
        assert result.year == 2013

    def test_search_requires_all_tokens(self) -> None:
        from science_tool.datasets.cbioportal import CBioPortalAdapter

        adapter = CBioPortalAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.return_value = self._catalog_response()
            results = adapter.search("breast tcga", max_results=10)

        assert [r.id for r in results] == ["brca_tcga_pub2015"]

    def test_search_empty_when_no_match(self) -> None:
        from science_tool.datasets.cbioportal import CBioPortalAdapter

        adapter = CBioPortalAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.return_value = self._catalog_response()
            results = adapter.search("pancreatic xenograft", max_results=10)

        assert results == []

    def test_files_returns_public_datahub_tarball(self) -> None:
        from science_tool.datasets.cbioportal import CBioPortalAdapter

        files = CBioPortalAdapter().files("gbm_cptac_2021")
        assert len(files) == 1
        assert files[0].url == (
            "https://cbioportal-datahub.s3.amazonaws.com/gbm_cptac_2021.tar.gz"
        )
        assert files[0].filename == "gbm_cptac_2021.tar.gz"

    def test_registered_in_adapter_registry(self) -> None:
        from science_tool.datasets import available_adapters

        assert "cbioportal" in available_adapters()


def test_domain_adapters_registered() -> None:
    from science_tool.datasets import available_adapters

    names = available_adapters()
    for name in ("figshare", "arrayexpress", "physionet", "sra"):
        assert name in names


class TestFigshareAdapter:
    def test_name(self) -> None:
        assert FigshareAdapter().name == "figshare"

    def test_search_parses_summary_list(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": 123,
                "title": "CGM dataset",
                "doi": "10.6084/m9.figshare.123",
                "published_date": "2023-05-01T00:00:00Z",
                "url_public_html": "https://figshare.com/articles/123",
            }
        ]
        adapter = FigshareAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.post.return_value = mock_response
            results = adapter.search("glucose", max_results=5)
        assert len(results) == 1
        r = results[0]
        assert r.source == "figshare"
        assert r.id == "123"
        assert r.title == "CGM dataset"
        assert r.doi == "10.6084/m9.figshare.123"
        assert r.year == 2023
        assert r.access == "public"

    def test_metadata_parses_article(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": 123,
            "title": "CGM dataset",
            "description": "Continuous glucose monitoring",
            "doi": "10.6084/m9.figshare.123",
            "published_date": "2023-05-01T00:00:00Z",
            "url_public_html": "https://figshare.com/articles/123",
            "license": {"name": "CC BY 4.0"},
            "tags": ["glucose", "cgm"],
            "files": [{"name": "data.csv", "size": 2048}],
        }
        adapter = FigshareAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.return_value = mock_response
            r = adapter.metadata("123")
        assert r.license == "CC BY 4.0"
        assert r.keywords == ["glucose", "cgm"]
        assert r.file_count == 1
        assert r.total_size_bytes == 2048
        assert r.description == "Continuous glucose monitoring"
        assert r.doi == "10.6084/m9.figshare.123"
        assert r.year == 2023
        assert r.url == "https://figshare.com/articles/123"

    def test_files_parses_download_urls(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": 123,
            "files": [
                {"name": "data.csv", "download_url": "https://ndownloader.figshare.com/files/1", "size": 2048, "computed_md5": "abc"},
            ],
        }
        adapter = FigshareAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.return_value = mock_response
            files = adapter.files("123")
        assert len(files) == 1
        assert files[0].filename == "data.csv"
        assert files[0].url == "https://ndownloader.figshare.com/files/1"
        assert files[0].checksum == "abc"
        assert files[0].format == "csv"

    def test_year_handles_malformed_date(self) -> None:
        adapter = FigshareAdapter()
        assert adapter._year("N/A ") is None
        assert adapter._year("") is None

    def test_metadata_tolerates_null_file_size(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": 1,
            "title": "T",
            "published_date": "2024-01-01T00:00:00Z",
            "files": [{"name": "a.csv", "size": None}, {"name": "b.csv", "size": 10}],
        }
        adapter = FigshareAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.return_value = mock_response
            r = adapter.metadata("1")
        assert r.total_size_bytes == 10
        assert r.file_count == 2

    def test_download_without_url_raises(self) -> None:
        from pathlib import Path

        adapter = FigshareAdapter()
        with pytest.raises(ValueError):
            adapter.download(FileInfo(filename="x.csv", url=""), Path("/tmp/figshare-test"))


class TestArrayExpressAdapter:
    def test_name(self) -> None:
        assert ArrayExpressAdapter().name == "arrayexpress"

    def test_search_parses_hits(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "hits": [
                {"accession": "E-MTAB-1724", "title": "Circadian blood", "release_date": "2015-03-10"},
            ]
        }
        adapter = ArrayExpressAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.return_value = mock_response
            results = adapter.search("circadian", max_results=5)
        assert len(results) == 1
        r = results[0]
        assert r.source == "arrayexpress"
        assert r.id == "E-MTAB-1724"
        assert r.title == "Circadian blood"
        assert r.year == 2015
        assert r.access == "public"

    def test_metadata_parses_section_attributes(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "accession": "E-MTAB-1724",
            "section": {
                "attributes": [
                    {"name": "Title", "value": "Circadian blood"},
                    {"name": "Organism", "value": "Homo sapiens"},
                    {"name": "Study type", "value": "transcription profiling by array"},
                ],
                "files": [{"path": "data.txt", "size": 100}],
            },
        }
        adapter = ArrayExpressAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.return_value = mock_response
            r = adapter.metadata("E-MTAB-1724")
        assert r.title == "Circadian blood"
        assert r.organism == "Homo sapiens"
        assert r.modality == "transcription profiling by array"
        assert r.file_count == 1

    def test_files_flattens_nested_lists(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "accession": "E-MTAB-1724",
            "section": {
                "files": [
                    {"path": "a.txt", "size": 10},
                    [{"path": "sub/b.cel", "size": 20}],
                ]
            },
        }
        adapter = ArrayExpressAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.return_value = mock_response
            files = adapter.files("E-MTAB-1724")
        assert {f.filename for f in files} == {"a.txt", "sub/b.cel"}
        b = next(f for f in files if f.filename == "sub/b.cel")
        assert b.url == "https://www.ebi.ac.uk/biostudies/files/E-MTAB-1724/sub/b.cel"
        assert b.format == "cel"


class TestPhysioNetAdapter:
    def test_name(self) -> None:
        assert PhysioNetAdapter().name == "physionet"

    def test_search_parses_projects_and_access(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "slug": "mmash",
                "version": "1.0.0",
                "title": "MMASH",
                "short_description": "Actigraphy and saliva",
                "abstract": "Long abstract",
                "version_doi": "10.13026/mmash",
                "publish_date": "2020-07-01",
                "license": {"name": "ODC-By 1.0"},
                "access_policy": "Open",
                "topics": ["actigraphy", "circadian"],
                "main_storage_size": 12345,
                "source_url": "https://physionet.org/content/mmash/",
            },
            {"slug": "secret", "version": "1.0.0", "title": "Secret", "access_policy": "Credentialed", "topics": []},
        ]
        adapter = PhysioNetAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.return_value = mock_response
            results = adapter.search("actigraphy", max_results=10)
        assert len(results) == 2
        r = results[0]
        assert r.id == "mmash"
        assert r.title == "MMASH"
        assert r.description == "Actigraphy and saliva"
        assert r.doi == "10.13026/mmash"
        assert r.year == 2020
        assert r.license == "ODC-By 1.0"
        assert r.keywords == ["actigraphy", "circadian"]
        assert r.total_size_bytes == 12345
        assert r.access == "public"
        assert results[1].access == "controlled"

    def test_access_tier_mapping(self) -> None:
        adapter = PhysioNetAdapter()
        assert adapter._parse_project({"slug": "a", "access_policy": "Open"}).access == "public"
        assert adapter._parse_project({"slug": "b", "access_policy": "Restricted"}).access == "restricted"
        assert adapter._parse_project({"slug": "c", "access_policy": "Credentialed"}).access == "controlled"
        assert adapter._parse_project({"slug": "d"}).access is None

    def test_files_parses_sha256sums(self) -> None:
        mock_response = MagicMock()
        mock_response.text = (
            "aaaa1111  records/data.csv\n"
            "bbbb2222  notes.txt\n"
            "\n"
        )
        adapter = PhysioNetAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.return_value = mock_response
            files = adapter.files("mmash/1.0.0")
        assert len(files) == 2
        csv = files[0]
        assert csv.filename == "records/data.csv"
        assert csv.url == "https://physionet.org/files/mmash/1.0.0/records/data.csv"
        assert csv.checksum == "aaaa1111"
        assert csv.format == "csv"
        assert csv.size_bytes is None

    def test_resolve_version_empty_list_raises_valueerror(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = []
        adapter = PhysioNetAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.return_value = mock_response
            with pytest.raises(ValueError):
                adapter.metadata("draft-only-project")

    def test_keywords_from_dict_topics(self) -> None:
        adapter = PhysioNetAdapter()
        r = adapter._parse_project(
            {"slug": "x", "topics": [{"description": "sleep"}, {"description": "ecg"}]}
        )
        assert r.keywords == ["sleep", "ecg"]

    def test_download_gated_raises_permission_error(self) -> None:
        adapter = PhysioNetAdapter()
        file_info = FileInfo(filename="x.dat", url="https://physionet.org/files/secret/1.0.0/x.dat")
        request = httpx.Request("GET", file_info.url)
        response = httpx.Response(403, request=request)
        ctx = MagicMock()
        ctx.__enter__.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403", request=request, response=response
        )
        adapter._client = MagicMock()
        adapter._client.stream.return_value = ctx
        with pytest.raises(PermissionError):
            adapter.download(file_info, Path("/tmp/pn-test"))


class TestSRAAdapter:
    _ESUMMARY = (
        '<eSummaryResult><DocSum><Id>1</Id>'
        '<Item Name="ExpXml" Type="String">'
        '<Summary><Title>Time-series RNA-seq of liver</Title>'
        '<Platform instrument_model="Illumina">ILLUMINA</Platform></Summary>'
        '<Organism ScientificName="Mus musculus"/>'
        '<Library_descriptor><LIBRARY_STRATEGY>RNA-Seq</LIBRARY_STRATEGY></Library_descriptor>'
        '<Experiment acc="SRX111"/>'
        '</Item>'
        '<Item Name="Runs" Type="String"><Run acc="SRR111"/><Run acc="SRR112"/></Item>'
        '</DocSum></eSummaryResult>'
    )

    def test_name(self) -> None:
        assert SRAAdapter().name == "sra"

    def test_search_parses_esummary(self) -> None:
        esearch = MagicMock()
        esearch.text = "<eSearchResult><IdList><Id>1</Id></IdList></eSearchResult>"
        esummary = MagicMock()
        esummary.text = self._ESUMMARY
        adapter = SRAAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.side_effect = [esearch, esummary]
            results = adapter.search("circadian liver rna-seq", max_results=5)
        assert len(results) == 1
        r = results[0]
        assert r.source == "sra"
        assert r.id == "SRX111"
        assert r.title == "Time-series RNA-seq of liver"
        assert r.organism == "Mus musculus"
        assert r.modality == "RNA-Seq"
        assert r.access == "public"

    def test_search_empty_when_no_ids(self) -> None:
        esearch = MagicMock()
        esearch.text = "<eSearchResult><IdList></IdList></eSearchResult>"
        adapter = SRAAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.return_value = esearch
            assert adapter.search("nothing") == []

    def test_files_builds_run_urls(self) -> None:
        esearch = MagicMock()
        esearch.text = "<eSearchResult><IdList><Id>1</Id></IdList></eSearchResult>"
        esummary = MagicMock()
        esummary.text = self._ESUMMARY
        adapter = SRAAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.side_effect = [esearch, esummary]
            files = adapter.files("SRX111")
        assert [f.filename for f in files] == ["SRR111.sra", "SRR112.sra"]
        assert files[0].url == "https://sra-pub-run-odp.s3.amazonaws.com/sra/SRR111/SRR111"
        assert files[0].format == "sra"

    _ESUMMARY_ESCAPED = (
        '<eSummaryResult><DocSum><Id>2</Id>'
        '<Item Name="ExpXml" Type="String">'
        '&lt;Summary&gt;&lt;Title&gt;Escaped RNA-seq&lt;/Title&gt;'
        '&lt;Platform&gt;ILLUMINA&lt;/Platform&gt;&lt;/Summary&gt;'
        '&lt;Organism ScientificName="Homo sapiens"/&gt;'
        '&lt;Library_descriptor&gt;&lt;LIBRARY_STRATEGY&gt;ATAC-seq&lt;/LIBRARY_STRATEGY&gt;&lt;/Library_descriptor&gt;'
        '&lt;Experiment acc="SRX999"/&gt;'
        '</Item>'
        '<Item Name="Runs" Type="String">&lt;Run acc="SRR999"/&gt;</Item>'
        '</DocSum></eSummaryResult>'
    )

    def test_search_flags_dbgap_controlled(self) -> None:
        esearch = MagicMock()
        esearch.text = "<eSearchResult><IdList><Id>9</Id></IdList></eSearchResult>"
        esummary = MagicMock()
        esummary.text = (
            '<eSummaryResult><DocSum><Id>9</Id>'
            '<Item Name="ExpXml" Type="String">'
            '<Summary><Title>Controlled human study (dbGaP)</Title></Summary>'
            '<Experiment acc="SRX900"/>'
            '</Item>'
            '<Item Name="Runs" Type="String"><Run acc="SRR900"/></Item>'
            '</DocSum></eSummaryResult>'
        )
        adapter = SRAAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.side_effect = [esearch, esummary]
            results = adapter.search("controlled", max_results=5)
        assert len(results) == 1
        assert results[0].access == "controlled"

    def test_search_parses_escaped_text_expxml(self) -> None:
        esearch = MagicMock()
        esearch.text = "<eSearchResult><IdList><Id>2</Id></IdList></eSearchResult>"
        esummary = MagicMock()
        esummary.text = self._ESUMMARY_ESCAPED
        adapter = SRAAdapter()
        with patch.object(adapter, "_client") as mock_client:
            mock_client.get.side_effect = [esearch, esummary]
            results = adapter.search("atac", max_results=5)
        assert len(results) == 1
        r = results[0]
        assert r.id == "SRX999"
        assert r.title == "Escaped RNA-seq"
        assert r.organism == "Homo sapiens"
        assert r.modality == "ATAC-seq"
