# Phase 4c: Operationalization — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add dataset discovery, acquisition, validation, and pipeline skills to complete Stage C of the Science research model.

**Architecture:** A `science_tool/datasets/` package with a protocol-based adapter system. Each adapter (Zenodo, Dryad, GEO, Semantic Scholar) implements `search`, `metadata`, `files`, `download`. A registry fans out searches across adapters. CLI commands expose these as `science-tool datasets *`. The `/science:find-datasets` command orchestrates LLM-driven discovery + adapter verification. Frictionless validation and pipeline skills round out the operationalization layer.

**Tech Stack:** Python 3.11+, httpx, pooch, frictionless, click, rich, pytest

**Design doc:** `docs/plans/2026-03-07-phase4c-operationalization-design.md`

**CLI prefix:** All commands use `uv run --frozen science-tool ...` from `science-tool/` directory.

**Test runner:** `cd science-tool && uv run --frozen pytest tests/<file>::<test> -v`

---

### Task 1: Adapter base types + registry + `[datasets]` extra

**Files:**
- Create: `science-tool/src/science_tool/datasets/__init__.py`
- Create: `science-tool/src/science_tool/datasets/_base.py`
- Modify: `science-tool/pyproject.toml`
- Test: `science-tool/tests/test_datasets.py`

**Step 1: Write the failing tests**

Create `science-tool/tests/test_datasets.py`:

```python
"""Tests for dataset adapter base types and registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from science_tool.datasets._base import DatasetAdapter, DatasetResult, FileInfo


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
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_datasets.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.datasets'`

**Step 3: Write the implementation**

Create `science-tool/src/science_tool/datasets/_base.py`:

```python
"""Base types for dataset adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class DatasetResult:
    """A dataset found by search."""

    source: str
    id: str
    title: str
    description: str = ""
    doi: str | None = None
    url: str | None = None
    year: int | None = None
    license: str | None = None
    keywords: list[str] = field(default_factory=list)
    organism: str | None = None
    modality: str | None = None
    sample_count: int | None = None
    file_count: int | None = None
    total_size_bytes: int | None = None


@dataclass(frozen=True)
class FileInfo:
    """A downloadable file within a dataset."""

    filename: str
    url: str
    size_bytes: int | None = None
    checksum: str | None = None
    format: str | None = None


@runtime_checkable
class DatasetAdapter(Protocol):
    """Common interface for dataset repository adapters."""

    name: str

    def search(self, query: str, *, max_results: int = 20) -> list[DatasetResult]: ...

    def metadata(self, dataset_id: str) -> DatasetResult: ...

    def files(self, dataset_id: str) -> list[FileInfo]: ...

    def download(self, file_info: FileInfo, dest_dir: Path) -> Path: ...
```

Create `science-tool/src/science_tool/datasets/__init__.py`:

```python
"""Dataset adapter registry and shared search interface."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from science_tool.datasets._base import DatasetAdapter, DatasetResult, FileInfo

__all__ = [
    "DatasetAdapter",
    "DatasetResult",
    "FileInfo",
    "available_adapters",
    "get_adapter",
    "register",
    "search_all",
]

_ADAPTERS: dict[str, type[Any]] = {}


def register(name: str, cls: type[Any]) -> None:
    """Register a dataset adapter class by name."""
    _ADAPTERS[name] = cls


def get_adapter(name: str) -> Any:
    """Instantiate a registered adapter by name. Raises KeyError if unknown."""
    if name not in _ADAPTERS:
        raise KeyError(f"Unknown dataset adapter: {name!r}. Available: {sorted(_ADAPTERS)}")
    return _ADAPTERS[name]()


def available_adapters() -> list[str]:
    """Return sorted list of registered adapter names."""
    return sorted(_ADAPTERS)


def search_all(
    query: str,
    *,
    sources: list[str] | None = None,
    max_per_source: int = 10,
) -> list[DatasetResult]:
    """Fan out search across multiple adapters, merge results."""
    targets = sources or list(_ADAPTERS)
    results: list[DatasetResult] = []
    for name in targets:
        adapter = get_adapter(name)
        results.extend(adapter.search(query, max_results=max_per_source))
    return results
```

**Step 4: Add `[datasets]` extra to pyproject.toml**

Add to `science-tool/pyproject.toml` under `[project.optional-dependencies]`:

```toml
datasets = [
    "httpx>=0.27",
    "pooch>=1.8",
]
```

**Step 5: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_datasets.py -v`
Expected: all 7 tests PASS

**Step 6: Commit**

```bash
git add science-tool/src/science_tool/datasets/ science-tool/tests/test_datasets.py science-tool/pyproject.toml
git commit -m "feat: add dataset adapter base types, protocol, and registry"
```

---

### Task 2: Zenodo adapter

**Files:**
- Create: `science-tool/src/science_tool/datasets/zenodo.py`
- Test: `science-tool/tests/test_datasets.py` (append)

**Step 1: Write the failing tests**

Append to `science-tool/tests/test_datasets.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_datasets.py::TestZenodoAdapter -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.datasets.zenodo'`

**Step 3: Write the implementation**

Create `science-tool/src/science_tool/datasets/zenodo.py`:

```python
"""Zenodo dataset adapter."""

from __future__ import annotations

from pathlib import Path

import httpx

from science_tool.datasets._base import DatasetResult, FileInfo

BASE_URL = "https://zenodo.org/api"


class ZenodoAdapter:
    """Search and download datasets from Zenodo."""

    name = "zenodo"

    def __init__(self) -> None:
        self._client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    def search(self, query: str, *, max_results: int = 20) -> list[DatasetResult]:
        resp = self._client.get(
            "/records",
            params={"q": query, "type": "dataset", "size": max_results, "sort": "mostrecent"},
        )
        resp.raise_for_status()
        return [self._parse_record(hit) for hit in resp.json()["hits"]["hits"]]

    def metadata(self, dataset_id: str) -> DatasetResult:
        resp = self._client.get(f"/records/{dataset_id}")
        resp.raise_for_status()
        return self._parse_record(resp.json())

    def files(self, dataset_id: str) -> list[FileInfo]:
        resp = self._client.get(f"/records/{dataset_id}")
        resp.raise_for_status()
        raw_files = resp.json().get("files", [])
        return [self._parse_file(f) for f in raw_files]

    def download(self, file_info: FileInfo, dest_dir: Path) -> Path:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / file_info.filename
        with self._client.stream("GET", file_info.url) as resp:
            resp.raise_for_status()
            with dest.open("wb") as f:
                for chunk in resp.iter_bytes(8192):
                    f.write(chunk)
        return dest

    def _parse_record(self, data: dict) -> DatasetResult:
        meta = data.get("metadata", {})
        files = data.get("files", [])
        pub_date = meta.get("publication_date", "")
        year = int(pub_date[:4]) if len(pub_date) >= 4 else None
        license_info = meta.get("license")
        license_id = license_info.get("id") if isinstance(license_info, dict) else None
        total_size = sum(f.get("size", 0) for f in files) if files else None

        return DatasetResult(
            source="zenodo",
            id=str(data["id"]),
            title=meta.get("title", ""),
            description=meta.get("description", ""),
            doi=meta.get("doi"),
            url=data.get("links", {}).get("self_html"),
            year=year,
            license=license_id,
            keywords=meta.get("keywords", []),
            file_count=len(files) if files else None,
            total_size_bytes=total_size,
        )

    def _parse_file(self, data: dict) -> FileInfo:
        links = data.get("links", {})
        url = links.get("self", "")
        ext = Path(data["key"]).suffix.lstrip(".")
        return FileInfo(
            filename=data["key"],
            url=url,
            size_bytes=data.get("size"),
            checksum=data.get("checksum"),
            format=ext or None,
        )
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_datasets.py::TestZenodoAdapter -v`
Expected: all 5 tests PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/datasets/zenodo.py science-tool/tests/test_datasets.py
git commit -m "feat: add Zenodo dataset adapter"
```

---

### Task 3: Dryad adapter

**Files:**
- Create: `science-tool/src/science_tool/datasets/dryad.py`
- Test: `science-tool/tests/test_datasets.py` (append)

**Step 1: Write the failing tests**

Append to `science-tool/tests/test_datasets.py`:

```python
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
        # First call: metadata to get version link
        meta_response = MagicMock()
        meta_response.status_code = 200
        meta_response.json.return_value = {
            "identifier": "doi:10.5061/dryad.abc123",
            "title": "T",
            "abstract": "",
            "publicationDate": "2024-01-01",
            "_links": {"stash:version": {"href": "/api/v2/versions/111"}},
        }

        # Second call: version files
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
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_datasets.py::TestDryadAdapter -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the implementation**

Create `science-tool/src/science_tool/datasets/dryad.py`:

```python
"""Dryad dataset adapter."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import httpx

from science_tool.datasets._base import DatasetResult, FileInfo

BASE_URL = "https://datadryad.org/api/v2"


class DryadAdapter:
    """Search and download datasets from Dryad."""

    name = "dryad"

    def __init__(self) -> None:
        self._client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    def search(self, query: str, *, max_results: int = 20) -> list[DatasetResult]:
        resp = self._client.get("/search", params={"q": query, "per_page": max_results})
        resp.raise_for_status()
        datasets = resp.json().get("_embedded", {}).get("stash:datasets", [])
        return [self._parse_dataset(d) for d in datasets]

    def metadata(self, dataset_id: str) -> DatasetResult:
        encoded = quote(dataset_id, safe="")
        resp = self._client.get(f"/datasets/{encoded}")
        resp.raise_for_status()
        return self._parse_dataset(resp.json())

    def files(self, dataset_id: str) -> list[FileInfo]:
        # Get dataset to find version link
        encoded = quote(dataset_id, safe="")
        meta_resp = self._client.get(f"/datasets/{encoded}")
        meta_resp.raise_for_status()
        version_href = meta_resp.json()["_links"]["stash:version"]["href"]

        files_resp = self._client.get(f"{version_href}/files")
        files_resp.raise_for_status()
        raw_files = files_resp.json().get("_embedded", {}).get("stash:files", [])
        return [self._parse_file(f) for f in raw_files]

    def download(self, file_info: FileInfo, dest_dir: Path) -> Path:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / file_info.filename
        with self._client.stream("GET", file_info.url) as resp:
            resp.raise_for_status()
            with dest.open("wb") as f:
                for chunk in resp.iter_bytes(8192):
                    f.write(chunk)
        return dest

    def _parse_dataset(self, data: dict) -> DatasetResult:
        doi = data.get("identifier", "")
        if doi.startswith("doi:"):
            doi = doi[4:]
        pub_date = data.get("publicationDate", "")
        year = int(pub_date[:4]) if len(pub_date) >= 4 else None
        lic = data.get("license", "")
        license_short = "CC0-1.0" if "zero" in lic.lower() else lic

        return DatasetResult(
            source="dryad",
            id=data.get("identifier", ""),
            title=data.get("title", ""),
            description=data.get("abstract", ""),
            doi=doi if doi else None,
            url=f"https://datadryad.org/stash/dataset/{quote(data.get('identifier', ''), safe=':')}",
            year=year,
            license=license_short,
            keywords=data.get("keywords", []),
        )

    def _parse_file(self, data: dict) -> FileInfo:
        dl_link = data.get("_links", {}).get("stash:download", {}).get("href", "")
        url = f"{BASE_URL}{dl_link}" if dl_link.startswith("/") else dl_link
        digest = data.get("digest")
        digest_type = data.get("digestType", "md5")
        checksum = f"{digest_type}:{digest}" if digest else None
        ext = Path(data.get("path", "")).suffix.lstrip(".")

        return FileInfo(
            filename=data.get("path", ""),
            url=url,
            size_bytes=data.get("size"),
            checksum=checksum,
            format=ext or None,
        )
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_datasets.py::TestDryadAdapter -v`
Expected: all 3 tests PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/datasets/dryad.py science-tool/tests/test_datasets.py
git commit -m "feat: add Dryad dataset adapter"
```

---

### Task 4: GEO adapter

**Files:**
- Create: `science-tool/src/science_tool/datasets/geo.py`
- Test: `science-tool/tests/test_datasets.py` (append)

**Step 1: Write the failing tests**

Append to `science-tool/tests/test_datasets.py`:

```python
import xml.etree.ElementTree as ET

from science_tool.datasets.geo import GEOAdapter


class TestGEOAdapter:
    def test_name(self) -> None:
        assert GEOAdapter().name == "geo"

    def test_parse_esummary_xml(self) -> None:
        """Test parsing of an E-utilities esummary XML response."""
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
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_datasets.py::TestGEOAdapter -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the implementation**

Create `science-tool/src/science_tool/datasets/geo.py`:

```python
"""NCBI GEO dataset adapter using E-utilities."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

from science_tool.datasets._base import DatasetResult, FileInfo

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
GEO_FTP_HTTPS = "https://ftp.ncbi.nlm.nih.gov/geo/series"


class GEOAdapter:
    """Search and access datasets from NCBI GEO."""

    name = "geo"

    def __init__(self) -> None:
        params: dict[str, str] = {}
        api_key = os.environ.get("NCBI_API_KEY")
        if api_key:
            params["api_key"] = api_key
        self._client = httpx.Client(base_url=EUTILS_BASE, timeout=30.0, params=params)

    def search(self, query: str, *, max_results: int = 20) -> list[DatasetResult]:
        # Step 1: esearch to get UIDs
        resp = self._client.get(
            "/esearch.fcgi",
            params={"db": "gds", "term": query, "retmax": max_results, "usehistory": "n"},
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        ids = [el.text for el in root.findall(".//IdList/Id") if el.text]
        if not ids:
            return []

        # Step 2: esummary for metadata
        resp = self._client.get(
            "/esummary.fcgi",
            params={"db": "gds", "id": ",".join(ids)},
        )
        resp.raise_for_status()
        return self._parse_esummary(resp.text)

    def metadata(self, dataset_id: str) -> DatasetResult:
        # Search by accession to get UID, then esummary
        resp = self._client.get(
            "/esearch.fcgi",
            params={"db": "gds", "term": f"{dataset_id}[Accession]", "retmax": 1},
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        ids = [el.text for el in root.findall(".//IdList/Id") if el.text]
        if not ids:
            raise ValueError(f"GEO accession not found: {dataset_id}")

        resp = self._client.get("/esummary.fcgi", params={"db": "gds", "id": ids[0]})
        resp.raise_for_status()
        results = self._parse_esummary(resp.text)
        if not results:
            raise ValueError(f"GEO accession not found: {dataset_id}")
        return results[0]

    def files(self, dataset_id: str) -> list[FileInfo]:
        return self._build_file_list(dataset_id)

    def download(self, file_info: FileInfo, dest_dir: Path) -> Path:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / file_info.filename
        with httpx.Client(timeout=120.0).stream("GET", file_info.url) as resp:
            resp.raise_for_status()
            with dest.open("wb") as f:
                for chunk in resp.iter_bytes(8192):
                    f.write(chunk)
        return dest

    def _parse_esummary(self, xml_text: str) -> list[DatasetResult]:
        root = ET.fromstring(xml_text)
        results: list[DatasetResult] = []
        for doc in root.findall("DocSum"):
            items = {item.get("Name", ""): item.text or "" for item in doc.findall("Item")}
            accession = items.get("Accession", "") or items.get("GSE", "")
            if not accession:
                continue

            pdat = items.get("PDAT", "")
            year = int(pdat[:4]) if len(pdat) >= 4 else None

            n_samples_str = items.get("n_samples", "")
            sample_count = int(n_samples_str) if n_samples_str.isdigit() else None

            results.append(
                DatasetResult(
                    source="geo",
                    id=accession,
                    title=items.get("title", ""),
                    description=items.get("summary", ""),
                    url=f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={accession}",
                    year=year,
                    organism=items.get("taxon") or None,
                    modality=items.get("gdsType") or None,
                    sample_count=sample_count,
                )
            )
        return results

    def _build_file_list(self, accession: str) -> list[FileInfo]:
        """Build standard GEO download URLs for a GSE accession."""
        if not accession.startswith("GSE"):
            return []
        # GEO FTP path: /geo/series/GSEnnn/GSEnnnn/
        prefix = accession[:len("GSE") + (len(accession) - 3 - 1) // 3 * 3]
        if len(accession) > 6:
            prefix = accession[:-3] + "nnn"
        else:
            prefix = accession[:3] + "nnn"

        base = f"{GEO_FTP_HTTPS}/{prefix}/{accession}"
        return [
            FileInfo(
                filename=f"{accession}_family.soft.gz",
                url=f"{base}/soft/{accession}_family.soft.gz",
                format="soft.gz",
            ),
            FileInfo(
                filename=f"{accession}_series_matrix.txt.gz",
                url=f"{base}/matrix/{accession}_series_matrix.txt.gz",
                format="txt.gz",
            ),
        ]
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_datasets.py::TestGEOAdapter -v`
Expected: all 5 tests PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/datasets/geo.py science-tool/tests/test_datasets.py
git commit -m "feat: add GEO dataset adapter (E-utilities + HTTPS)"
```

---

### Task 5: Semantic Scholar adapter

**Files:**
- Create: `science-tool/src/science_tool/datasets/semantic_scholar.py`
- Test: `science-tool/tests/test_datasets.py` (append)

**Step 1: Write the failing tests**

Append to `science-tool/tests/test_datasets.py`:

```python
from science_tool.datasets.semantic_scholar import SemanticScholarAdapter


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
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_datasets.py::TestSemanticScholarAdapter -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the implementation**

Create `science-tool/src/science_tool/datasets/semantic_scholar.py`:

```python
"""Semantic Scholar adapter for literature-linked dataset discovery."""

from __future__ import annotations

import os
from pathlib import Path

import httpx

from science_tool.datasets._base import DatasetResult, FileInfo

BASE_URL = "https://api.semanticscholar.org/graph/v1"

_FIELDS = "paperId,title,abstract,year,externalIds,url,openAccessPdf,fieldsOfStudy,citationCount"


class SemanticScholarAdapter:
    """Search papers via Semantic Scholar for dataset-linked literature."""

    name = "semantic_scholar"

    def __init__(self) -> None:
        headers: dict[str, str] = {}
        api_key = os.environ.get("S2_API_KEY")
        if api_key:
            headers["x-api-key"] = api_key
        self._client = httpx.Client(base_url=BASE_URL, timeout=30.0, headers=headers)

    def search(self, query: str, *, max_results: int = 20) -> list[DatasetResult]:
        resp = self._client.get(
            "/paper/search",
            params={"query": query, "limit": min(max_results, 100), "fields": _FIELDS},
        )
        resp.raise_for_status()
        return [self._parse_paper(p) for p in resp.json().get("data", [])]

    def metadata(self, dataset_id: str) -> DatasetResult:
        resp = self._client.get(f"/paper/{dataset_id}", params={"fields": _FIELDS})
        resp.raise_for_status()
        return self._parse_paper(resp.json())

    def files(self, dataset_id: str) -> list[FileInfo]:
        """Semantic Scholar doesn't host data files. Returns open access PDF if available."""
        result = self.metadata(dataset_id)
        # We stored the PDF URL in the url field if available
        # Re-fetch to get openAccessPdf
        resp = self._client.get(f"/paper/{dataset_id}", params={"fields": "openAccessPdf"})
        resp.raise_for_status()
        pdf = resp.json().get("openAccessPdf")
        if pdf and pdf.get("url"):
            return [FileInfo(filename=f"{dataset_id}.pdf", url=pdf["url"], format="pdf")]
        return []

    def download(self, file_info: FileInfo, dest_dir: Path) -> Path:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / file_info.filename
        with httpx.Client(timeout=60.0).stream("GET", file_info.url) as resp:
            resp.raise_for_status()
            with dest.open("wb") as f:
                for chunk in resp.iter_bytes(8192):
                    f.write(chunk)
        return dest

    def _parse_paper(self, data: dict) -> DatasetResult:
        ext_ids = data.get("externalIds") or {}
        return DatasetResult(
            source="semantic_scholar",
            id=data.get("paperId", ""),
            title=data.get("title", ""),
            description=data.get("abstract", "") or "",
            doi=ext_ids.get("DOI"),
            url=data.get("url"),
            year=data.get("year"),
            keywords=data.get("fieldsOfStudy") or [],
        )
```

**Step 4: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_datasets.py::TestSemanticScholarAdapter -v`
Expected: all 3 tests PASS

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/datasets/semantic_scholar.py science-tool/tests/test_datasets.py
git commit -m "feat: add Semantic Scholar dataset adapter"
```

---

### Task 6: Auto-registration + CLI `datasets` command group

**Files:**
- Modify: `science-tool/src/science_tool/datasets/__init__.py`
- Modify: `science-tool/src/science_tool/cli.py`
- Test: `science-tool/tests/test_datasets_cli.py` (new)

**Step 1: Write the failing tests**

Create `science-tool/tests/test_datasets_cli.py`:

```python
"""Tests for the datasets CLI command group."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from science_tool.cli import main
from science_tool.datasets._base import DatasetResult, FileInfo


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


import pytest


class TestDatasetsCLI:
    def test_sources_command(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["datasets", "sources"])
        assert result.exit_code == 0
        # At minimum we should see the registered adapters
        assert "zenodo" in result.output or "Available" in result.output

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
        assert "No datasets found" in result.output or result.output.strip() == ""
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_datasets_cli.py -v`
Expected: FAIL — no `datasets` command group on `main`

**Step 3: Add auto-registration to `__init__.py`**

Update `science-tool/src/science_tool/datasets/__init__.py` — add at the bottom:

```python
def _auto_register() -> None:
    """Register all built-in adapters. Called on import."""
    try:
        from science_tool.datasets.zenodo import ZenodoAdapter
        register("zenodo", ZenodoAdapter)
    except ImportError:
        pass
    try:
        from science_tool.datasets.dryad import DryadAdapter
        register("dryad", DryadAdapter)
    except ImportError:
        pass
    try:
        from science_tool.datasets.geo import GEOAdapter
        register("geo", GEOAdapter)
    except ImportError:
        pass
    try:
        from science_tool.datasets.semantic_scholar import SemanticScholarAdapter
        register("semantic_scholar", SemanticScholarAdapter)
    except ImportError:
        pass


_auto_register()
```

**Step 4: Add CLI command group to `cli.py`**

Add to `science-tool/src/science_tool/cli.py` (after existing imports):

```python
from science_tool.datasets import available_adapters, get_adapter, search_all
from science_tool.datasets._base import DatasetResult
```

Add the command group (after the `refs` group):

```python
@main.group()
def datasets() -> None:
    """Dataset discovery and download commands."""


@datasets.command("sources")
def datasets_sources() -> None:
    """List available dataset adapters."""
    adapters = available_adapters()
    if not adapters:
        click.echo("No dataset adapters available. Install with: uv add science-tool[datasets]")
        return
    click.echo("Available dataset sources:")
    for name in adapters:
        click.echo(f"  - {name}")


@datasets.command("search")
@click.argument("query")
@click.option("--source", default=None, help="Comma-separated list of sources (e.g. zenodo,geo)")
@click.option("--max", "max_results", default=20, show_default=True, help="Max results per source")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def datasets_search(query: str, source: str | None, max_results: int, output_format: str) -> None:
    """Search for datasets across repositories."""
    sources = source.split(",") if source else None
    results = search_all(query, sources=sources, max_per_source=max_results)
    if not results:
        click.echo("No datasets found.")
        return

    rows = [
        {
            "source": r.source,
            "id": r.id,
            "title": r.title[:80],
            "year": r.year or "",
            "doi": r.doi or "",
        }
        for r in results
    ]

    emit_query_rows(
        output_format=output_format,
        title=f"Dataset Search: {query}",
        columns=[
            ("source", "Source"),
            ("id", "ID"),
            ("title", "Title"),
            ("year", "Year"),
            ("doi", "DOI"),
        ],
        rows=rows,
    )


@datasets.command("metadata")
@click.argument("source_id", metavar="SOURCE:ID")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def datasets_metadata(source_id: str, output_format: str) -> None:
    """Show full metadata for a dataset. Use SOURCE:ID format (e.g. zenodo:12345)."""
    source, _, dataset_id = source_id.partition(":")
    if not dataset_id:
        raise click.ClickException("Use SOURCE:ID format, e.g. zenodo:12345 or geo:GSE12345")
    adapter = get_adapter(source)
    result = adapter.metadata(dataset_id)

    rows = [
        {"field": "Source", "value": result.source},
        {"field": "ID", "value": result.id},
        {"field": "Title", "value": result.title},
        {"field": "Description", "value": result.description[:200] if result.description else ""},
        {"field": "DOI", "value": result.doi or ""},
        {"field": "URL", "value": result.url or ""},
        {"field": "Year", "value": str(result.year) if result.year else ""},
        {"field": "License", "value": result.license or ""},
        {"field": "Keywords", "value": ", ".join(result.keywords) if result.keywords else ""},
        {"field": "Organism", "value": result.organism or ""},
        {"field": "Modality", "value": result.modality or ""},
        {"field": "Samples", "value": str(result.sample_count) if result.sample_count else ""},
        {"field": "Files", "value": str(result.file_count) if result.file_count else ""},
    ]

    emit_query_rows(
        output_format=output_format,
        title=f"Dataset: {result.title}",
        columns=[("field", "Field"), ("value", "Value")],
        rows=rows,
    )


@datasets.command("files")
@click.argument("source_id", metavar="SOURCE:ID")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def datasets_files(source_id: str, output_format: str) -> None:
    """List downloadable files in a dataset. Use SOURCE:ID format."""
    source, _, dataset_id = source_id.partition(":")
    if not dataset_id:
        raise click.ClickException("Use SOURCE:ID format, e.g. zenodo:12345")
    adapter = get_adapter(source)
    file_list = adapter.files(dataset_id)
    if not file_list:
        click.echo("No files found.")
        return

    rows = [
        {
            "filename": f.filename,
            "format": f.format or "",
            "size": _human_size(f.size_bytes) if f.size_bytes else "",
            "checksum": (f.checksum[:30] + "...") if f.checksum and len(f.checksum) > 30 else (f.checksum or ""),
        }
        for f in file_list
    ]

    emit_query_rows(
        output_format=output_format,
        title="Files",
        columns=[("filename", "Filename"), ("format", "Format"), ("size", "Size"), ("checksum", "Checksum")],
        rows=rows,
    )


@datasets.command("download")
@click.argument("source_id", metavar="SOURCE:ID")
@click.option("--file", "file_pattern", default=None, help="Download only files matching this pattern")
@click.option("--dest", "dest_dir", default="data/raw", show_default=True, type=click.Path(path_type=Path))
def datasets_download(source_id: str, file_pattern: str | None, dest_dir: Path) -> None:
    """Download dataset files. Use SOURCE:ID format."""
    import fnmatch

    source, _, dataset_id = source_id.partition(":")
    if not dataset_id:
        raise click.ClickException("Use SOURCE:ID format, e.g. zenodo:12345")
    adapter = get_adapter(source)
    file_list = adapter.files(dataset_id)
    if not file_list:
        click.echo("No files found.")
        return

    if file_pattern:
        file_list = [f for f in file_list if fnmatch.fnmatch(f.filename, file_pattern)]
        if not file_list:
            click.echo(f"No files matching pattern: {file_pattern}")
            return

    for fi in file_list:
        click.echo(f"Downloading {fi.filename}...")
        path = adapter.download(fi, dest_dir)
        click.echo(f"  Saved to {path}")


def _human_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes //= 1024
    return f"{size_bytes:.1f} TB"
```

**Step 5: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_datasets_cli.py -v`
Expected: all 5 tests PASS

Also run all dataset tests together:
Run: `cd science-tool && uv run --frozen pytest tests/test_datasets.py tests/test_datasets_cli.py -v`
Expected: all tests PASS

**Step 6: Commit**

```bash
git add science-tool/src/science_tool/datasets/__init__.py science-tool/src/science_tool/cli.py science-tool/tests/test_datasets_cli.py
git commit -m "feat: add datasets CLI command group with search, metadata, files, download"
```

---

### Task 7: `/science:find-datasets` command

**Files:**
- Create: `commands/find-datasets.md`

**Step 1: Write the command**

Create `commands/find-datasets.md`:

```markdown
---
description: Discover and document candidate datasets for research or tool demos. Uses LLM knowledge + dataset repository search to find, rank, and document relevant public datasets.
---

# Find Datasets

Find datasets for `$ARGUMENTS`.
If no argument is provided, derive candidate search terms from `specs/research-question.md`, active hypotheses, and inquiry variables, then ask the user to confirm the focus.

## Setup

Follow `references/command-preamble.md` (role: `research-assistant`).

Additionally:
1. Read `skills/data/SKILL.md` for data management conventions.
2. If present, read `skills/data/frictionless.md` for Data Package guidance.
3. Read `templates/dataset.md` for dataset documentation format.
4. Read project context:
   - `specs/research-question.md`
   - `specs/scope-boundaries.md`
   - `specs/hypotheses/`
   - Existing `doc/datasets/` (to avoid duplicating known datasets)
5. If an inquiry exists, check inquiry variables to understand what data the project needs:
   ```bash
   science-tool inquiry list --format json
   ```

## Tool invocation

All `science-tool` commands below use this pattern:

```bash
uv run --with ${CLAUDE_PLUGIN_ROOT}/science-tool science-tool <command>
```

For brevity, the examples below write just `science-tool <command>` — **always expand to the full `uv run --with ...` form when executing.**

## Workflow

### Step 1: Identify data needs

Based on project context:
- What variables does the project need data for?
- What modalities are relevant? (genomics, clinical, survey, imaging, etc.)
- What organisms or populations?
- What access constraints apply? (must be public, specific licenses, etc.)
- What formats are preferred?

Summarize needs concisely before searching.

### Step 2: LLM candidate generation

Using your knowledge of available datasets in the field:
- Suggest 5-10 candidate datasets with rationale
- Include known accessions, DOIs, or repository names where possible
- Explain why each is relevant to the project

### Step 3: Adapter-driven search

Use `science-tool datasets search` to find datasets across repositories:

```bash
# Broad search across all sources
science-tool datasets search "<query>" --format json

# Targeted search on specific sources
science-tool datasets search "<query>" --source zenodo,geo --format json
```

For each promising result, get full metadata:

```bash
science-tool datasets metadata <source>:<id> --format json
```

And list available files:

```bash
science-tool datasets files <source>:<id> --format json
```

Cross-reference LLM suggestions with search results. Note which candidates were verified and which remain unverified.

### Step 4: Rank candidates

Rank by:
1. **Relevance** — covers project variables, matches research question
2. **Quality** — sample size, known provenance, peer-reviewed origin
3. **Accessibility** — public access, permissive license, standard format
4. **Completeness** — covers multiple needed variables, adequate sample size
5. **Recency** — newer datasets may have better methods/standards

Label each as:
- `Use now` — download and integrate immediately
- `Evaluate next` — promising but needs closer inspection
- `Track` — potentially useful, defer

### Step 5: Document selected datasets

For each `Use now` or `Evaluate next` dataset, create a dataset note:

**File:** `doc/datasets/data-<slug>.md` using `templates/dataset.md`

Fill in all available fields. For fields you cannot verify, mark as `[UNVERIFIED]`.

### Step 6: Variable mapping (if inquiry exists)

If the project has an active inquiry, create a coverage matrix:
- List each inquiry variable
- Map which dataset(s) provide data for it
- Flag unmapped variables (data gaps)
- Flag variables with multiple dataset sources (potential for cross-validation)

Include this mapping in a `## Variable Coverage` section of the search output.

### Step 7: Update project files

1. Update `science.yaml` data_sources section with new entries.
2. Write machine-readable search results to `doc/searches/YYYY-MM-DD-datasets-<slug>.json`.
3. If appropriate, suggest download commands:
   ```bash
   science-tool datasets download <source>:<id> --dest data/raw/
   ```
4. Add follow-up tasks to `RESEARCH_PLAN.md`:
   - Download and inspect `Use now` datasets
   - Create `datapackage.json` for downloaded data
   - Map variables for pipeline planning

### Step 8: Suggest next steps

1. Download selected datasets
2. Create Frictionless Data Package descriptors
3. Run `/science:plan-pipeline` to build computational workflow
4. Run `/science:discuss` to evaluate dataset choices

## Output Summary

Present a concise summary table:

| Dataset | Source | Accession/DOI | Tier | Key Variables | Size |
|---|---|---|---|---|---|

Followed by any data gaps that need to be addressed.
```

**Step 2: Commit**

```bash
git add commands/find-datasets.md
git commit -m "feat: add /science:find-datasets command"
```

---

### Task 8: Frictionless skill

**Files:**
- Create: `skills/data/frictionless.md`

**Step 1: Write the skill**

Create `skills/data/frictionless.md`:

```markdown
---
name: data-frictionless
description: Frictionless Data Package creation and validation. Use when creating datapackage.json descriptors, validating data files against schemas, or connecting datasets to analysis pipelines. Also use when the user mentions data packages, data validation, or data schemas.
---

# Frictionless Data Packages

## When To Use

- After downloading raw data to `data/raw/`
- Before connecting data to a pipeline or notebook
- When validating data quality and schema conformance
- When documenting dataset structure for reproducibility

## Core Concepts

A **Data Package** is a `datapackage.json` file describing one or more data **resources** (files) with their schemas, formats, and metadata.

A **resource** describes a single data file: its path, format, schema (field names, types, constraints), and encoding.

## Creating a Data Package

### Option A: Auto-describe from existing files

```bash
# Generate descriptor from a CSV file
frictionless describe data/raw/observations.csv --json > data/raw/datapackage.json
```

Review and edit the generated descriptor — auto-detection may mis-type fields.

### Option B: Write manually

```json
{
  "name": "project-raw-data",
  "title": "Raw Data for <Project>",
  "description": "Downloaded from <source> on <date>",
  "licenses": [{"name": "CC-BY-4.0", "path": "https://creativecommons.org/licenses/by/4.0/"}],
  "resources": [
    {
      "name": "observations",
      "path": "observations.csv",
      "format": "csv",
      "encoding": "utf-8",
      "schema": {
        "fields": [
          {"name": "sample_id", "type": "string", "constraints": {"required": true}},
          {"name": "gene", "type": "string"},
          {"name": "expression", "type": "number"},
          {"name": "condition", "type": "string", "constraints": {"enum": ["control", "treated"]}}
        ],
        "primaryKey": "sample_id"
      }
    }
  ]
}
```

## Field Types

Use these Frictionless types:

| Type | Python equivalent | Use for |
|---|---|---|
| `string` | `str` | text, identifiers, categories |
| `number` | `float` | measurements, continuous values |
| `integer` | `int` | counts, indices |
| `boolean` | `bool` | flags |
| `date` | `datetime.date` | dates without time |
| `datetime` | `datetime.datetime` | timestamps |
| `array` | `list` | JSON arrays |
| `object` | `dict` | JSON objects |

## Validation

```bash
# Validate a data package
science-tool datasets validate --path data/raw/

# Or use frictionless directly
frictionless validate data/raw/datapackage.json
```

Common validation errors:
- **Missing values** in required fields — add `missingValues: ["", "NA", "N/A"]` to resource
- **Type errors** — check if auto-detected types are correct
- **Extra/missing columns** — update schema to match actual file

## Connecting to Inquiry Variables

When a `datapackage.json` exists and an inquiry is active:

1. Map resource fields to inquiry variables in `doc/datasets/data-<slug>.md`
2. Run coverage check: `science-tool datasets check-coverage <inquiry-slug>`
3. Document any transformations needed (unit conversions, normalization, filtering)

## Directory Conventions

```
data/
├── raw/                    # Immutable downloads
│   ├── datapackage.json    # Describes raw files
│   ├── observations.csv
│   └── metadata.csv
├── processed/              # Cleaned, transformed
│   ├── datapackage.json    # Describes processed files
│   └── normalized.csv
└── README.md               # Overview
```

**Rules:**
- Never modify files in `data/raw/` after download
- All transformations go to `data/processed/`
- Both directories get their own `datapackage.json`
- Record provenance: which script/pipeline produced each processed file

## Provenance in Data Packages

Add a `sources` field to track where data came from:

```json
{
  "name": "processed-data",
  "sources": [
    {"title": "GEO GSE12345", "path": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE12345"},
    {"title": "Downloaded via science-tool", "path": "science-tool datasets download geo:GSE12345"}
  ],
  "resources": [...]
}
```
```

**Step 2: Commit**

```bash
git add skills/data/frictionless.md
git commit -m "feat: add Frictionless Data Package skill"
```

---

### Task 9: Snakemake pipeline skill

**Files:**
- Create: `skills/pipelines/snakemake.md`

**Step 1: Write the skill**

Create `skills/pipelines/snakemake.md` (create `skills/pipelines/` directory first):

```markdown
---
name: pipeline-snakemake
description: Snakemake workflow construction and best practices. Use when creating computational pipelines, writing Snakefiles, connecting data acquisition to analysis, or the user mentions Snakemake, pipelines, workflows, or reproducible analysis.
---

# Snakemake Pipelines

## When To Use

- Building a reproducible analysis pipeline
- Connecting data download → preprocessing → analysis → output
- When a workflow has multiple steps with file dependencies
- When intermediate results should be cached and reusable

For interactive exploration, prefer marimo notebooks instead.

## Project Structure

```
code/pipelines/
├── Snakefile           # Main workflow definition
├── config.yaml         # Parameters (linked to inquiry AnnotatedParams)
├── envs/               # Conda environment specs per rule
│   ├── preprocessing.yaml
│   └── analysis.yaml
├── rules/              # Modular rule files (for complex pipelines)
│   ├── download.smk
│   ├── preprocess.smk
│   └── analyze.smk
└── scripts/            # Scripts called by rules
    ├── preprocess.py
    └── analyze.py
```

## Writing a Snakefile

### Minimal template

```python
configfile: "config.yaml"

rule all:
    input:
        "data/processed/results.csv"

rule download:
    output:
        "data/raw/{accession}_data.csv"
    shell:
        """
        uv run --with science-tool science-tool datasets download \
            {config[source]}:{wildcards.accession} --dest data/raw/
        """

rule preprocess:
    input:
        "data/raw/{accession}_data.csv"
    output:
        "data/processed/{accession}_clean.csv"
    script:
        "scripts/preprocess.py"

rule analyze:
    input:
        expand("data/processed/{acc}_clean.csv", acc=config["accessions"])
    output:
        "data/processed/results.csv"
    script:
        "scripts/analyze.py"
```

### Config file

```yaml
# config.yaml — linked to inquiry parameters
source: geo
accessions:
  - GSE12345
  - GSE67890
parameters:
  normalization: "quantile"
  min_samples: 3
```

## Best Practices

### Rule naming
- Use verb phrases: `download_data`, `normalize_counts`, `fit_model`
- Prefix with step number for clarity: `s01_download`, `s02_normalize`

### Wildcards
- Use wildcards for sample/accession variation
- Keep wildcard names descriptive: `{sample}`, `{accession}`, `{gene}`
- Constrain wildcards when needed: `wildcard_constraints: sample="[A-Za-z0-9]+"``

### Input/output
- All paths relative to Snakefile location
- Raw data: `data/raw/`
- Processed data: `data/processed/`
- Results: `results/` or `data/processed/`
- Use `temp()` for large intermediate files that can be deleted
- Use `protected()` for expensive-to-compute outputs

### Scripts vs shell
- **Shell:** simple commands, tool invocations
- **Scripts:** anything needing Python logic (access `snakemake.input`, `snakemake.output`, `snakemake.params`)

### Environments
- One conda env YAML per distinct tool set
- Pin versions for reproducibility

## Running

```bash
# Dry run (show what would execute)
snakemake -n

# Run with N cores
snakemake --cores 4

# Run specific target
snakemake data/processed/results.csv

# Generate DAG visualization
snakemake --dag | dot -Tpng > dag.png
```

## Connecting to Science Workflow

1. **Data acquisition rules** call `science-tool datasets download`
2. **Config parameters** map to inquiry `AnnotatedParam` values
3. **Validation rules** call `science-tool datasets validate`
4. **Output** goes to `data/processed/` with its own `datapackage.json`
5. Document each rule using `templates/pipeline-step.md`
```

**Step 2: Commit**

```bash
mkdir -p skills/pipelines
git add skills/pipelines/snakemake.md
git commit -m "feat: add Snakemake pipeline skill"
```

---

### Task 10: Marimo notebook skill

**Files:**
- Create: `skills/pipelines/marimo.md`

**Step 1: Write the skill**

Create `skills/pipelines/marimo.md`:

```markdown
---
name: pipeline-marimo
description: Marimo reactive notebook construction and best practices. Use when creating interactive analysis notebooks, exploratory data analysis, parameter exploration, or the user mentions marimo, notebooks, or interactive analysis.
---

# Marimo Notebooks

## When To Use

- Exploratory data analysis and visualization
- Interactive parameter exploration
- Prototyping analysis steps before encoding in Snakemake
- Presenting results with interactivity
- Quick one-off analyses that don't need pipeline formalization

For production pipelines with file dependencies, prefer Snakemake.

## Project Structure

```
code/notebooks/
├── viz.py              # Knowledge graph visualization (auto-generated)
├── explore-data.py     # Data exploration notebook
├── analyze-results.py  # Results analysis
└── parameter-sweep.py  # Interactive parameter testing
```

## Creating a Notebook

```bash
# Create and open a new notebook
uv run marimo edit code/notebooks/explore-data.py

# Run as a read-only app
uv run marimo run code/notebooks/explore-data.py
```

## Notebook Structure

### Standard sections

Organize notebooks with clear cell progression:

1. **Setup** — imports, configuration, data paths
2. **Data loading** — read from `data/raw/` or `data/processed/`
3. **Processing** — transformations, filtering, normalization
4. **Visualization** — charts, tables, summary statistics
5. **Export** — save results to `data/processed/` with provenance

### Example notebook

```python
import marimo

app = marimo.App(width="medium")


@app.cell
def setup():
    import marimo as mo
    import polars as pl
    import altair as alt
    return mo, pl, alt


@app.cell
def load_data(pl):
    data = pl.read_csv("../../data/processed/normalized.csv")
    data.head()
    return (data,)


@app.cell
def explore(mo, data, alt):
    # Interactive column selector
    column = mo.ui.dropdown(
        options=data.columns,
        value=data.columns[0],
        label="Select column",
    )
    column
    return (column,)


@app.cell
def visualize(data, alt, column):
    chart = alt.Chart(data.to_pandas()).mark_bar().encode(
        x=alt.X(column.value, bin=True),
        y="count()",
    ).properties(width=600, height=400)
    chart
    return (chart,)


@app.cell
def export(data, pl):
    # Export filtered/processed results
    output_path = "../../data/processed/explored_subset.csv"
    data.write_csv(output_path)
    print(f"Exported to {output_path}")
    return ()
```

## Best Practices

### Data access
- Use relative paths from notebook location: `../../data/raw/`
- Load data with polars (preferred) or pandas
- For large datasets, use lazy evaluation: `pl.scan_csv()`

### Interactive elements
- `mo.ui.slider()` — numeric parameter exploration
- `mo.ui.dropdown()` — categorical selection
- `mo.ui.checkbox()` — toggle options
- `mo.ui.text()` — free-form input
- `mo.ui.table()` — interactive data tables

### Visualization
- Prefer Altair for declarative charts (integrates well with marimo)
- Use `mo.ui.altair_chart()` for interactive selection
- For specialized plots, seaborn is acceptable

### Reactivity
- Marimo cells are reactive: changing a cell re-runs dependents
- Name return values explicitly to create dependencies
- Avoid side effects in cells (file writes should be in dedicated export cells)

### Connecting to Science workflow
- Read inquiry variables from graph: `science-tool inquiry show <slug> --format json`
- Load `datapackage.json` to understand available fields
- Export results with provenance metadata
- Document findings in `doc/` after exploration
```

**Step 2: Commit**

```bash
git add skills/pipelines/marimo.md
git commit -m "feat: add Marimo notebook skill"
```

---

### Task 11: Pipeline and experiment templates

**Files:**
- Create: `templates/pipeline-step.md`
- Create: `templates/experiment.md`

**Step 1: Write the templates**

Create `templates/pipeline-step.md`:

```markdown
---
id: "step:<slug>"
type: "pipeline-step"
title: "<Step Name>"
status: "planned"
tags: []
inquiry: "<inquiry-slug>"
rule_name: "<snakemake-rule-name>"
created: "<YYYY-MM-DD>"
updated: "<YYYY-MM-DD>"
---

# <Step Name>

## Purpose

<What this step does and why it exists in the pipeline.>

## Input / Output

- **Input:** `<path/to/input>`
- **Output:** `<path/to/output>`
- **Format:** <input format> → <output format>

## Tool / Library

- <tool name and version>
- <relevant function or command>

## Parameters

| Parameter | Value | Source | Notes |
|---|---|---|---|
| <param> | <value> | inquiry AnnotatedParam / config.yaml | <why this value> |

## Validation

- [ ] Output file exists and is non-empty
- [ ] <domain-specific check>
- [ ] <statistical check if applicable>

## Runtime

- Estimated time: <estimate>
- Resource needs: <memory, CPU, GPU>

## Related

- Inquiry: `<inquiry-slug>`
- Upstream step: `<step-slug>`
- Downstream step: `<step-slug>`
```

Create `templates/experiment.md`:

```markdown
---
id: "experiment:<slug>"
type: "experiment"
title: "<Experiment Name>"
status: "planned"
tags: []
inquiry: "<inquiry-slug>"
hypothesis: "<hypothesis-id>"
created: "<YYYY-MM-DD>"
updated: "<YYYY-MM-DD>"
---

# <Experiment Name>

## Hypothesis

<Which hypothesis is being tested and what the expected outcome is.>

## Design

- **Independent variable(s):** <what is being varied>
- **Dependent variable(s):** <what is being measured>
- **Controls:** <baseline comparisons>
- **Sample size:** <N>

## Pipeline Steps

1. <step-slug> — <brief description>
2. <step-slug> — <brief description>

## Expected Results

<What a positive result looks like. What a negative result looks like.>

## Actual Results

<Fill in after running.>

## Interpretation

<What the results mean for the hypothesis. Limitations. Next steps.>

## Related

- Hypothesis: `specs/hypotheses/<hypothesis-id>.md`
- Pipeline: `doc/plans/<pipeline-plan>.md`
- Data: `data/processed/<output>`
```

**Step 2: Commit**

```bash
git add templates/pipeline-step.md templates/experiment.md
git commit -m "feat: add pipeline-step and experiment templates"
```

---

### Task 12: Data validation CLI commands

**Files:**
- Modify: `science-tool/src/science_tool/cli.py`
- Create: `science-tool/src/science_tool/datasets/validate.py`
- Test: `science-tool/tests/test_datasets_validate.py` (new)

**Step 1: Write the failing tests**

Create `science-tool/tests/test_datasets_validate.py`:

```python
"""Tests for dataset validation commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from science_tool.datasets.validate import validate_data_packages


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create a minimal data directory with a data package."""
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)

    # Create a simple CSV
    csv_path = raw / "observations.csv"
    csv_path.write_text("sample_id,gene,expression\nS1,TP53,12.5\nS2,BRCA1,8.3\n")

    # Create a valid datapackage.json
    pkg = {
        "name": "test-data",
        "resources": [
            {
                "name": "observations",
                "path": "observations.csv",
                "format": "csv",
                "schema": {
                    "fields": [
                        {"name": "sample_id", "type": "string"},
                        {"name": "gene", "type": "string"},
                        {"name": "expression", "type": "number"},
                    ]
                },
            }
        ],
    }
    (raw / "datapackage.json").write_text(json.dumps(pkg))
    return tmp_path / "data"


@pytest.fixture
def bad_data_dir(tmp_path: Path) -> Path:
    """Create a data directory with validation issues."""
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)

    # CSV with type mismatch
    csv_path = raw / "bad.csv"
    csv_path.write_text("id,count\nA,not_a_number\n")

    pkg = {
        "name": "bad-data",
        "resources": [
            {
                "name": "bad",
                "path": "bad.csv",
                "format": "csv",
                "schema": {
                    "fields": [
                        {"name": "id", "type": "string"},
                        {"name": "count", "type": "integer"},
                    ]
                },
            }
        ],
    }
    (raw / "datapackage.json").write_text(json.dumps(pkg))
    return tmp_path / "data"


class TestValidateDataPackages:
    def test_valid_package_passes(self, data_dir: Path) -> None:
        results = validate_data_packages(data_dir)
        failures = [r for r in results if r["status"] == "fail"]
        assert len(failures) == 0

    def test_missing_datapackage_warns(self, tmp_path: Path) -> None:
        raw = tmp_path / "data" / "raw"
        raw.mkdir(parents=True)
        results = validate_data_packages(tmp_path / "data")
        statuses = [r["status"] for r in results]
        assert "warn" in statuses or "fail" in statuses

    def test_schema_presence_check(self, data_dir: Path) -> None:
        results = validate_data_packages(data_dir)
        check_names = [r["check"] for r in results]
        assert any("schema" in c.lower() or "datapackage" in c.lower() for c in check_names)

    def test_bad_data_reports_errors(self, bad_data_dir: Path) -> None:
        results = validate_data_packages(bad_data_dir)
        failures = [r for r in results if r["status"] == "fail"]
        assert len(failures) > 0
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_datasets_validate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.datasets.validate'`

**Step 3: Write the implementation**

Create `science-tool/src/science_tool/datasets/validate.py`:

```python
"""Data package validation using Frictionless."""

from __future__ import annotations

import json
from pathlib import Path


def validate_data_packages(data_dir: Path) -> list[dict[str, str]]:
    """Validate datapackage.json files in raw/ and processed/ subdirectories.

    Returns a list of check results with keys: check, status, details.
    Status is one of: pass, fail, warn.
    """
    results: list[dict[str, str]] = []

    for subdir_name in ("raw", "processed"):
        subdir = data_dir / subdir_name
        pkg_path = subdir / "datapackage.json"

        if not subdir.exists():
            continue

        # Check 1: datapackage.json presence
        if not pkg_path.exists():
            results.append({
                "check": f"{subdir_name}/datapackage.json presence",
                "status": "warn",
                "details": f"No datapackage.json in {subdir_name}/",
            })
            continue

        results.append({
            "check": f"{subdir_name}/datapackage.json presence",
            "status": "pass",
            "details": f"Found {pkg_path}",
        })

        # Check 2: valid JSON
        try:
            with pkg_path.open() as f:
                pkg = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            results.append({
                "check": f"{subdir_name}/datapackage.json valid JSON",
                "status": "fail",
                "details": str(e),
            })
            continue

        results.append({
            "check": f"{subdir_name}/datapackage.json valid JSON",
            "status": "pass",
            "details": "Valid JSON",
        })

        # Check 3: has resources
        resources = pkg.get("resources", [])
        if not resources:
            results.append({
                "check": f"{subdir_name} resources defined",
                "status": "warn",
                "details": "No resources defined in datapackage.json",
            })
            continue

        # Check 4: each resource file exists and schema validates
        for res in resources:
            res_name = res.get("name", res.get("path", "unknown"))
            res_path = subdir / res.get("path", "")

            if not res_path.exists():
                results.append({
                    "check": f"{subdir_name}/{res_name} file exists",
                    "status": "fail",
                    "details": f"File not found: {res_path}",
                })
                continue

            results.append({
                "check": f"{subdir_name}/{res_name} file exists",
                "status": "pass",
                "details": str(res_path),
            })

            # Check 5: schema validation (if frictionless is available)
            schema = res.get("schema")
            if schema:
                schema_results = _validate_resource_schema(res_path, schema, f"{subdir_name}/{res_name}")
                results.extend(schema_results)

    if not results:
        results.append({
            "check": "data directory structure",
            "status": "warn",
            "details": "No raw/ or processed/ subdirectories found",
        })

    return results


def _validate_resource_schema(
    file_path: Path, schema: dict, prefix: str
) -> list[dict[str, str]]:
    """Validate a CSV file against a Frictionless-style schema."""
    results: list[dict[str, str]] = []

    try:
        import csv

        with file_path.open(newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                results.append({
                    "check": f"{prefix} schema validation",
                    "status": "fail",
                    "details": "Could not read CSV headers",
                })
                return results

            # Check field names match
            expected_fields = [f["name"] for f in schema.get("fields", [])]
            actual_fields = list(reader.fieldnames)
            missing = set(expected_fields) - set(actual_fields)
            extra = set(actual_fields) - set(expected_fields)

            if missing:
                results.append({
                    "check": f"{prefix} field presence",
                    "status": "fail",
                    "details": f"Missing fields: {sorted(missing)}",
                })
            elif extra:
                results.append({
                    "check": f"{prefix} field presence",
                    "status": "warn",
                    "details": f"Extra fields not in schema: {sorted(extra)}",
                })
            else:
                results.append({
                    "check": f"{prefix} field presence",
                    "status": "pass",
                    "details": f"All {len(expected_fields)} fields present",
                })

            # Check type conformance for a sample of rows
            field_types = {f["name"]: f.get("type", "string") for f in schema.get("fields", [])}
            type_errors: list[str] = []
            for row_num, row in enumerate(reader, start=2):
                if row_num > 100:  # Sample first 100 rows
                    break
                for fname, ftype in field_types.items():
                    value = row.get(fname, "")
                    if value == "" or value is None:
                        continue
                    if not _check_type(value, ftype):
                        type_errors.append(f"Row {row_num}, {fname}: {value!r} is not {ftype}")

            if type_errors:
                results.append({
                    "check": f"{prefix} type conformance",
                    "status": "fail",
                    "details": f"{len(type_errors)} type error(s): {type_errors[0]}"
                    + (f" (and {len(type_errors) - 1} more)" if len(type_errors) > 1 else ""),
                })
            else:
                results.append({
                    "check": f"{prefix} type conformance",
                    "status": "pass",
                    "details": "All sampled values match declared types",
                })

    except Exception as e:
        results.append({
            "check": f"{prefix} schema validation",
            "status": "fail",
            "details": f"Validation error: {e}",
        })

    return results


def _check_type(value: str, declared_type: str) -> bool:
    """Check if a string value is compatible with a Frictionless field type."""
    if declared_type in ("string",):
        return True
    if declared_type in ("integer",):
        try:
            int(value)
            return True
        except ValueError:
            return False
    if declared_type in ("number",):
        try:
            float(value)
            return True
        except ValueError:
            return False
    if declared_type in ("boolean",):
        return value.lower() in ("true", "false", "1", "0")
    # For other types (date, datetime, etc.), accept anything for now
    return True
```

**Step 4: Add CLI command for validation**

Add to the `datasets` group in `science-tool/src/science_tool/cli.py`:

```python
from science_tool.datasets.validate import validate_data_packages

@datasets.command("validate")
@click.option("--path", "data_path", default="data", show_default=True, type=click.Path(path_type=Path))
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def datasets_validate(data_path: Path, output_format: str) -> None:
    """Validate Frictionless Data Packages in raw/ and processed/ directories."""
    results = validate_data_packages(data_path)
    emit_query_rows(
        output_format=output_format,
        title="Data Validation",
        columns=[("check", "Check"), ("status", "Status"), ("details", "Details")],
        rows=results,
    )
    if any(r["status"] == "fail" for r in results):
        raise click.exceptions.Exit(1)
```

**Step 5: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_datasets_validate.py -v`
Expected: all 4 tests PASS

**Step 6: Commit**

```bash
git add science-tool/src/science_tool/datasets/validate.py science-tool/tests/test_datasets_validate.py science-tool/src/science_tool/cli.py
git commit -m "feat: add data package validation with schema and type checks"
```

---

### Task 13: Update plan.md with Phase 4c progress

**Files:**
- Modify: `docs/plan.md`

**Step 1: Update Phase 4c deliverables and commands**

In `docs/plan.md`:

1. Move `/science:find-datasets` from "Commands Planned for Later Phases" to a new "Implemented Commands (Phase 4c)" section.
2. Check off the Phase 4c deliverables list items.
3. Add the new skills to the "Implemented Skills" section.
4. Add the new templates to the Templates table.
5. Update "Immediate Next Steps" to reflect Phase 4c completion and Phase 5 as next.

**Step 2: Commit**

```bash
git add docs/plan.md
git commit -m "docs: mark Phase 4c deliverables as complete in plan.md"
```

---

### Task 14: Run full test suite + lint

**Step 1: Run all tests**

Run: `cd science-tool && uv run --frozen pytest tests/ -v`
Expected: all tests PASS

**Step 2: Run linter**

Run: `cd science-tool && uv run --frozen ruff check .`
Expected: no errors

**Step 3: Run formatter**

Run: `cd science-tool && uv run --frozen ruff format .`

**Step 4: Run type checker**

Run: `cd science-tool && uv run --frozen pyright`
Expected: no errors (or only pre-existing ones)

**Step 5: Fix any issues found, then commit**

```bash
git add -A
git commit -m "chore: fix lint and type issues from Phase 4c"
```
