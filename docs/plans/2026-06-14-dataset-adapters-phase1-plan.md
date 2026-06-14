# Dataset Adapters Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add four domain dataset adapters (`figshare`, `arrayexpress`, `physionet`, `sra`) to `science_tool.datasets`, plus a canonical `access` tier surfaced through the CLI, so rhythm-relevant repositories are discoverable via `science datasets search`.

**Architecture:** Each adapter is a self-contained class implementing the existing `DatasetAdapter` protocol (`search`/`metadata`/`files`/`download`), constructed with its own `httpx.Client`, registered in `datasets/__init__.py::_auto_register()`. One additive `access` field on `DatasetResult` carries a canonical tier (`public`/`restricted`/`controlled`/`None`); the CLI `search` and `metadata` commands are extended to surface it. No new CLI commands.

**Tech Stack:** Python 3.13, `httpx`, `xml.etree.ElementTree` (for NCBI E-utilities), `pytest`, `unittest.mock` (`MagicMock` + `patch.object`), `click.testing.CliRunner`.

**Reference patterns (read before starting):**
- `science/src/science_tool/datasets/zenodo.py` — REST adapter template (figshare, arrayexpress, physionet)
- `science/src/science_tool/datasets/geo.py` — NCBI E-utilities template (sra)
- `science/tests/test_datasets.py` — adapter test style (`MagicMock` response + `patch.object(adapter, "_client")`)
- `science/tests/test_datasets_cli.py` — CLI test style (`CliRunner`, `patch("science_tool.cli.search_all"/"get_adapter")`)
- Design spec: `docs/plans/2026-06-14-dataset-adapters-phase1-design.md`

**Conventions:** All commands run from `~/d/science`. Tests use **no live network** — every HTTP call is mocked. Run a single test with `uv run pytest <path>::<name> -v`.

---

## File Structure

**Create:**
- `science/src/science_tool/datasets/figshare.py` — figshare REST adapter
- `science/src/science_tool/datasets/arrayexpress.py` — EBI BioStudies/ArrayExpress REST adapter
- `science/src/science_tool/datasets/physionet.py` — PhysioNet JSON API adapter
- `science/src/science_tool/datasets/sra.py` — NCBI SRA E-utilities adapter

**Modify:**
- `science/src/science_tool/datasets/_base.py` — add `access` field to `DatasetResult`
- `science/src/science_tool/datasets/__init__.py` — register the four adapters
- `science/src/science_tool/cli.py` — surface `access` in `datasets search` + `datasets metadata`
- `science/commands/find-datasets.md` — adapter list, access caveats, access crosswalk
- `science/codex-skills/science-find-datasets/SKILL.md` — mirror adapter-list change if it duplicates the list

**Test:**
- `science/tests/test_datasets.py` — adapter unit tests + registry assertions
- `science/tests/test_datasets_cli.py` — CLI `access` output

---

## Task 1: Add `access` field to `DatasetResult`

**Files:**
- Modify: `science/src/science_tool/datasets/_base.py`
- Test: `science/tests/test_datasets.py`

- [ ] **Step 1: Write the failing test**

Add to the `TestDatasetResult` class in `science/tests/test_datasets.py`:

```python
    def test_access_defaults_none_and_accepts_canonical(self) -> None:
        assert DatasetResult(source="s", id="1", title="T").access is None
        r = DatasetResult(source="s", id="1", title="T", access="restricted")
        assert r.access == "restricted"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest science/tests/test_datasets.py::TestDatasetResult::test_access_defaults_none_and_accepts_canonical -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'access'`

- [ ] **Step 3: Add the field**

In `science/src/science_tool/datasets/_base.py`, add `access` to the `DatasetResult` dataclass, immediately after the `modality` field:

```python
    modality: str | None = None
    access: str | None = None  # canonical: "public" | "restricted" | "controlled" | None
    sample_count: int | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest science/tests/test_datasets.py::TestDatasetResult -v`
Expected: PASS (all `TestDatasetResult` tests)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets/_base.py science/tests/test_datasets.py
git commit -m "feat(datasets): add canonical access tier field to DatasetResult"
```

---

## Task 2: `figshare` adapter

**Files:**
- Create: `science/src/science_tool/datasets/figshare.py`
- Test: `science/tests/test_datasets.py`

figshare API: `POST /articles/search` returns a JSON **array** of lean article summaries (`id`, `title`, `doi`, `published_date`, `url_public_html`). `GET /articles/{id}` returns the full article (`description`, `license.name`, `tags`, `files[]`). Files carry `name`, `download_url`, `size`, `computed_md5`.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_datasets.py` (add `from science_tool.datasets.figshare import FigshareAdapter` to the imports at the top of the file first):

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest science/tests/test_datasets.py::TestFigshareAdapter -v`
Expected: FAIL — `ImportError`/`ModuleNotFoundError: science_tool.datasets.figshare`

- [ ] **Step 3: Write the adapter**

Create `science/src/science_tool/datasets/figshare.py`:

```python
"""figshare dataset adapter."""

from __future__ import annotations

from pathlib import Path

import httpx

from science_tool.datasets._base import DatasetResult, FileInfo

BASE_URL = "https://api.figshare.com/v2"
ITEM_TYPE_DATASET = 3


class FigshareAdapter:
    """Search and download datasets from figshare."""

    name = "figshare"

    def __init__(self) -> None:
        self._client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    def search(self, query: str, *, max_results: int = 20) -> list[DatasetResult]:
        resp = self._client.post(
            "/articles/search",
            json={"search_for": query, "item_type": ITEM_TYPE_DATASET, "page_size": max_results},
        )
        resp.raise_for_status()
        return [self._parse_summary(hit) for hit in resp.json()]

    def metadata(self, dataset_id: str) -> DatasetResult:
        resp = self._client.get(f"/articles/{dataset_id}")
        resp.raise_for_status()
        return self._parse_article(resp.json())

    def files(self, dataset_id: str) -> list[FileInfo]:
        resp = self._client.get(f"/articles/{dataset_id}")
        resp.raise_for_status()
        return [self._parse_file(f) for f in resp.json().get("files", [])]

    def download(self, file_info: FileInfo, dest_dir: Path) -> Path:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / file_info.filename
        with self._client.stream("GET", file_info.url) as resp:
            resp.raise_for_status()
            with dest.open("wb") as f:
                for chunk in resp.iter_bytes(8192):
                    f.write(chunk)
        return dest

    def _year(self, published: str) -> int | None:
        return int(published[:4]) if published and len(published) >= 4 else None

    def _parse_summary(self, data: dict) -> DatasetResult:  # type: ignore[type-arg]
        return DatasetResult(
            source="figshare",
            id=str(data["id"]),
            title=data.get("title", ""),
            doi=data.get("doi") or None,
            url=data.get("url_public_html"),
            year=self._year(data.get("published_date", "")),
            access="public",
        )

    def _parse_article(self, data: dict) -> DatasetResult:  # type: ignore[type-arg]
        files = data.get("files", [])
        license_info = data.get("license")
        license_name = license_info.get("name") if isinstance(license_info, dict) else None
        total_size = sum(f.get("size", 0) for f in files) if files else None
        return DatasetResult(
            source="figshare",
            id=str(data["id"]),
            title=data.get("title", ""),
            description=data.get("description", ""),
            doi=data.get("doi") or None,
            url=data.get("url_public_html"),
            year=self._year(data.get("published_date", "")),
            license=license_name,
            keywords=data.get("tags", []),
            file_count=len(files) if files else None,
            total_size_bytes=total_size,
            access="public",
        )

    def _parse_file(self, data: dict) -> FileInfo:  # type: ignore[type-arg]
        name = data["name"]
        ext = Path(name).suffix.lstrip(".")
        return FileInfo(
            filename=name,
            url=data.get("download_url", ""),
            size_bytes=data.get("size"),
            checksum=data.get("computed_md5"),
            format=ext or None,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest science/tests/test_datasets.py::TestFigshareAdapter -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets/figshare.py science/tests/test_datasets.py
git commit -m "feat(datasets): add figshare adapter"
```

---

## Task 3: `arrayexpress` adapter

**Files:**
- Create: `science/src/science_tool/datasets/arrayexpress.py`
- Test: `science/tests/test_datasets.py`

EBI BioStudies API scoped to the ArrayExpress collection. `GET /arrayexpress/search?query=&pageSize=` returns `{"hits": [{accession, title, release_date}, ...]}`. `GET /studies/{accession}` returns `{accession, section: {attributes: [{name, value}], files: [...]}}`. Section `files` may be nested lists; flatten them. Attribute lookup is case-insensitive. File download URL: `https://www.ebi.ac.uk/biostudies/files/{accession}/{path}`.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_datasets.py` (add `from science_tool.datasets.arrayexpress import ArrayExpressAdapter` to the top imports):

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest science/tests/test_datasets.py::TestArrayExpressAdapter -v`
Expected: FAIL — `ModuleNotFoundError: science_tool.datasets.arrayexpress`

- [ ] **Step 3: Write the adapter**

Create `science/src/science_tool/datasets/arrayexpress.py`:

```python
"""ArrayExpress dataset adapter via the EBI BioStudies API."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import httpx

from science_tool.datasets._base import DatasetResult, FileInfo

BASE_URL = "https://www.ebi.ac.uk/biostudies/api/v1"
FILES_BASE = "https://www.ebi.ac.uk/biostudies/files"
STUDY_HTML = "https://www.ebi.ac.uk/biostudies/arrayexpress/studies"


class ArrayExpressAdapter:
    """Search and access ArrayExpress studies (EBI BioStudies collection)."""

    name = "arrayexpress"

    def __init__(self) -> None:
        self._client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    def search(self, query: str, *, max_results: int = 20) -> list[DatasetResult]:
        resp = self._client.get(
            "/arrayexpress/search", params={"query": query, "pageSize": max_results}
        )
        resp.raise_for_status()
        return [self._parse_hit(hit) for hit in resp.json().get("hits", [])]

    def metadata(self, dataset_id: str) -> DatasetResult:
        resp = self._client.get(f"/studies/{dataset_id}")
        resp.raise_for_status()
        return self._parse_study(resp.json())

    def files(self, dataset_id: str) -> list[FileInfo]:
        resp = self._client.get(f"/studies/{dataset_id}")
        resp.raise_for_status()
        section = resp.json().get("section", {})
        return [self._parse_file(f, dataset_id) for f in self._iter_files(section.get("files", []))]

    def download(self, file_info: FileInfo, dest_dir: Path) -> Path:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / Path(file_info.filename).name
        with self._client.stream("GET", file_info.url) as resp:
            resp.raise_for_status()
            with dest.open("wb") as f:
                for chunk in resp.iter_bytes(8192):
                    f.write(chunk)
        return dest

    def _parse_hit(self, data: dict) -> DatasetResult:  # type: ignore[type-arg]
        release = data.get("release_date", "") or ""
        year = int(release[:4]) if len(release) >= 4 else None
        accession = data.get("accession", "")
        return DatasetResult(
            source="arrayexpress",
            id=accession,
            title=data.get("title", ""),
            url=f"{STUDY_HTML}/{accession}",
            year=year,
            access="public",
        )

    def _attrs(self, attributes: list) -> dict:  # type: ignore[type-arg]
        return {a.get("name", "").lower(): a.get("value", "") for a in attributes}

    def _parse_study(self, data: dict) -> DatasetResult:  # type: ignore[type-arg]
        accession = data.get("accession", "")
        section = data.get("section", {})
        attrs = self._attrs(section.get("attributes", []))
        files = list(self._iter_files(section.get("files", [])))
        return DatasetResult(
            source="arrayexpress",
            id=accession,
            title=attrs.get("title", ""),
            description=attrs.get("description", ""),
            url=f"{STUDY_HTML}/{accession}",
            organism=attrs.get("organism") or None,
            modality=attrs.get("study type") or attrs.get("aeexperimenttype") or None,
            file_count=len(files) if files else None,
            access="public",
        )

    def _iter_files(self, files: list) -> Iterator[dict]:  # type: ignore[type-arg]
        for entry in files:
            if isinstance(entry, list):
                yield from self._iter_files(entry)
            elif isinstance(entry, dict):
                yield entry

    def _parse_file(self, data: dict, accession: str) -> FileInfo:  # type: ignore[type-arg]
        path = data.get("path", "")
        ext = Path(path).suffix.lstrip(".")
        return FileInfo(
            filename=path,
            url=f"{FILES_BASE}/{accession}/{path}",
            size_bytes=data.get("size"),
            format=ext or None,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest science/tests/test_datasets.py::TestArrayExpressAdapter -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets/arrayexpress.py science/tests/test_datasets.py
git commit -m "feat(datasets): add arrayexpress adapter"
```

---

## Task 4: `physionet` adapter

**Files:**
- Create: `science/src/science_tool/datasets/physionet.py`
- Test: `science/tests/test_datasets.py`

PhysioNet JSON API v1. `GET /projects/search/?search_term=` returns a JSON **array** of projects: `slug`, `version`, `title`, `abstract`, `short_description`, `version_doi`/`core_doi`, `publish_date`, `license.name`, `access_policy` (`Open`/`Restricted`/`Credentialed`), `topics`, `main_storage_size`, `source_url`. `GET /projects/{slug}/versions/` lists versions; `GET /projects/{slug}/versions/{version}/` is detail. `GET /projects/published/{slug}/{version}/sha256sums/` returns text (`<sha256>␠␠<path>` per line) — **checksums + paths only, no byte sizes**, so `FileInfo.size_bytes` is `None`. Access map: `Open`→`public`, `Restricted`→`restricted`, `Credentialed`→`controlled`. A `401`/`403` on download means credentialed access → raise `PermissionError`.

`dataset_id` is the project `slug`, optionally `slug/version`; when no version is given, `metadata`/`files` resolve the latest version.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_datasets.py` (add `import httpx` and `from science_tool.datasets.physionet import PhysioNetAdapter` to the top imports):

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest science/tests/test_datasets.py::TestPhysioNetAdapter -v`
Expected: FAIL — `ModuleNotFoundError: science_tool.datasets.physionet`

- [ ] **Step 3: Write the adapter**

Create `science/src/science_tool/datasets/physionet.py`:

```python
"""PhysioNet dataset adapter (JSON API v1)."""

from __future__ import annotations

from pathlib import Path

import httpx

from science_tool.datasets._base import DatasetResult, FileInfo

BASE_URL = "https://physionet.org/api/v1"
FILES_BASE = "https://physionet.org/files"

_ACCESS_MAP = {"open": "public", "restricted": "restricted", "credentialed": "controlled"}


class PhysioNetAdapter:
    """Search and access PhysioNet projects via the JSON API."""

    name = "physionet"

    def __init__(self) -> None:
        self._client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    def search(self, query: str, *, max_results: int = 20) -> list[DatasetResult]:
        resp = self._client.get("/projects/search/", params={"search_term": query})
        resp.raise_for_status()
        return [self._parse_project(p) for p in resp.json()[:max_results]]

    def metadata(self, dataset_id: str) -> DatasetResult:
        slug, version = self._resolve_version(dataset_id)
        resp = self._client.get(f"/projects/{slug}/versions/{version}/")
        resp.raise_for_status()
        return self._parse_project(resp.json())

    def files(self, dataset_id: str) -> list[FileInfo]:
        slug, version = self._resolve_version(dataset_id)
        resp = self._client.get(f"/projects/published/{slug}/{version}/sha256sums/")
        resp.raise_for_status()
        return self._parse_sha256sums(resp.text, slug, version)

    def download(self, file_info: FileInfo, dest_dir: Path) -> Path:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / Path(file_info.filename).name
        try:
            with self._client.stream("GET", file_info.url) as resp:
                resp.raise_for_status()
                with dest.open("wb") as f:
                    for chunk in resp.iter_bytes(8192):
                        f.write(chunk)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403):
                raise PermissionError(
                    f"PhysioNet file requires credentialed/restricted access: {file_info.url}"
                ) from exc
            raise
        return dest

    def _resolve_version(self, dataset_id: str) -> tuple[str, str]:
        if "/" in dataset_id:
            slug, version = dataset_id.split("/", 1)
            return slug, version
        resp = self._client.get(f"/projects/{dataset_id}/versions/")
        resp.raise_for_status()
        versions = resp.json()
        latest = next((v for v in versions if v.get("is_latest_version")), versions[-1])
        return dataset_id, latest["version"]

    def _parse_project(self, data: dict) -> DatasetResult:  # type: ignore[type-arg]
        publish = data.get("publish_date", "") or ""
        year = int(publish[:4]) if len(publish) >= 4 else None
        license_info = data.get("license")
        license_name = license_info.get("name") if isinstance(license_info, dict) else None
        policy = (data.get("access_policy") or "").lower()
        size = data.get("main_storage_size")
        topics = data.get("topics", []) or []
        keywords = [t if isinstance(t, str) else t.get("description", "") for t in topics]
        return DatasetResult(
            source="physionet",
            id=data.get("slug", ""),
            title=data.get("title", ""),
            description=data.get("short_description") or data.get("abstract", "") or "",
            doi=data.get("version_doi") or data.get("core_doi") or None,
            url=data.get("source_url"),
            year=year,
            license=license_name,
            keywords=[k for k in keywords if k],
            total_size_bytes=size if isinstance(size, int) else None,
            access=_ACCESS_MAP.get(policy),
        )

    def _parse_sha256sums(self, text: str, slug: str, version: str) -> list[FileInfo]:
        files: list[FileInfo] = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            checksum, _, path = line.partition(" ")
            path = path.strip()
            if not path:
                continue
            ext = Path(path).suffix.lstrip(".")
            files.append(
                FileInfo(
                    filename=path,
                    url=f"{FILES_BASE}/{slug}/{version}/{path}",
                    size_bytes=None,
                    checksum=checksum,
                    format=ext or None,
                )
            )
        return files
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest science/tests/test_datasets.py::TestPhysioNetAdapter -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets/physionet.py science/tests/test_datasets.py
git commit -m "feat(datasets): add physionet adapter (JSON API)"
```

---

## Task 5: `sra` adapter

**Files:**
- Create: `science/src/science_tool/datasets/sra.py`
- Test: `science/tests/test_datasets.py`

NCBI SRA via E-utilities, mirroring `geo.py` (including `NCBI_API_KEY` handling). `esearch.fcgi?db=sra&term=` → UIDs → `esummary.fcgi?db=sra&id=`. Each `DocSum` carries an `ExpXml` item (an XML fragment with `<Title>`, `<Platform>`, `<Organism>`, `<LIBRARY_STRATEGY>`, `<Experiment acc="SRX...">`) and a `Runs` item (`<Run acc="SRR..."/>`). Both fragments are wrapped in `<root>…</root>` before parsing. `files()` builds per-run `.sra` URLs at `https://sra-pub-run-odp.s3.amazonaws.com/sra/{SRR}/{SRR}`. `access` is `controlled` when the fragment mentions dbGaP, else `public`.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_datasets.py` (add `from science_tool.datasets.sra import SRAAdapter` to the top imports):

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest science/tests/test_datasets.py::TestSRAAdapter -v`
Expected: FAIL — `ModuleNotFoundError: science_tool.datasets.sra`

- [ ] **Step 3: Write the adapter**

Create `science/src/science_tool/datasets/sra.py`:

```python
"""NCBI SRA dataset adapter using E-utilities."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

from science_tool.datasets._base import DatasetResult, FileInfo

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
SRA_RUN_BASE = "https://sra-pub-run-odp.s3.amazonaws.com/sra"


class SRAAdapter:
    """Search and access datasets from NCBI SRA."""

    name = "sra"

    def __init__(self) -> None:
        params: dict[str, str] = {}
        api_key = os.environ.get("NCBI_API_KEY")
        if api_key:
            params["api_key"] = api_key
        self._client = httpx.Client(base_url=EUTILS_BASE, timeout=30.0, params=params)

    def search(self, query: str, *, max_results: int = 20) -> list[DatasetResult]:
        resp = self._client.get(
            "/esearch.fcgi",
            params={"db": "sra", "term": query, "retmax": max_results, "usehistory": "n"},
        )
        resp.raise_for_status()
        ids = self._ids(resp.text)
        if not ids:
            return []
        resp = self._client.get("/esummary.fcgi", params={"db": "sra", "id": ",".join(ids)})
        resp.raise_for_status()
        return self._parse_esummary(resp.text)

    def metadata(self, dataset_id: str) -> DatasetResult:
        results = self._parse_esummary(self._esummary_for(dataset_id))
        if not results:
            raise ValueError(f"SRA accession not found: {dataset_id}")
        return results[0]

    def files(self, dataset_id: str) -> list[FileInfo]:
        runs = self._run_accessions(self._esummary_for(dataset_id))
        return [
            FileInfo(filename=f"{run}.sra", url=f"{SRA_RUN_BASE}/{run}/{run}", format="sra")
            for run in runs
        ]

    def download(self, file_info: FileInfo, dest_dir: Path) -> Path:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / file_info.filename
        with httpx.Client(timeout=120.0).stream("GET", file_info.url) as resp:
            resp.raise_for_status()
            with dest.open("wb") as f:
                for chunk in resp.iter_bytes(8192):
                    f.write(chunk)
        return dest

    def _ids(self, esearch_xml: str) -> list[str]:
        root = ET.fromstring(esearch_xml)
        return [el.text for el in root.findall(".//IdList/Id") if el.text]

    def _esummary_for(self, accession: str) -> str:
        resp = self._client.get(
            "/esearch.fcgi",
            params={"db": "sra", "term": f"{accession}[Accession]", "retmax": 1},
        )
        resp.raise_for_status()
        ids = self._ids(resp.text)
        if not ids:
            raise ValueError(f"SRA accession not found: {accession}")
        resp = self._client.get("/esummary.fcgi", params={"db": "sra", "id": ids[0]})
        resp.raise_for_status()
        return resp.text

    def _fragment(self, text: str) -> ET.Element:
        if not text.strip():
            return ET.fromstring("<root/>")
        try:
            return ET.fromstring(f"<root>{text}</root>")
        except ET.ParseError:
            return ET.fromstring("<root/>")

    def _parse_esummary(self, xml_text: str) -> list[DatasetResult]:
        root = ET.fromstring(xml_text)
        results: list[DatasetResult] = []
        for doc in root.findall("DocSum"):
            items = {it.get("Name", ""): it.text or "" for it in doc.findall("Item")}
            exp = self._fragment(items.get("ExpXml", ""))
            runs = self._fragment(items.get("Runs", ""))
            run_accs = [r.get("acc") for r in runs.findall(".//Run") if r.get("acc")]
            exp_el = exp.find(".//Experiment")
            accession = (exp_el.get("acc") if exp_el is not None else "") or (
                run_accs[0] if run_accs else ""
            )
            if not accession:
                continue
            org_el = exp.find(".//Organism")
            organism = None
            if org_el is not None:
                organism = org_el.get("ScientificName") or (org_el.text or None)
            strategy = exp.findtext(".//LIBRARY_STRATEGY", default="")
            platform_el = exp.find(".//Platform")
            modality = strategy or (platform_el.text if platform_el is not None else None)
            controlled = "dbgap" in items.get("ExpXml", "").lower()
            results.append(
                DatasetResult(
                    source="sra",
                    id=accession,
                    title=exp.findtext(".//Title", default=""),
                    url=f"https://www.ncbi.nlm.nih.gov/sra/{accession}",
                    organism=organism,
                    modality=modality or None,
                    access="controlled" if controlled else "public",
                )
            )
        return results

    def _run_accessions(self, xml_text: str) -> list[str]:
        root = ET.fromstring(xml_text)
        accs: list[str] = []
        for doc in root.findall("DocSum"):
            items = {it.get("Name", ""): it.text or "" for it in doc.findall("Item")}
            runs = self._fragment(items.get("Runs", ""))
            accs.extend(r.get("acc") for r in runs.findall(".//Run") if r.get("acc"))
        return accs
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest science/tests/test_datasets.py::TestSRAAdapter -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets/sra.py science/tests/test_datasets.py
git commit -m "feat(datasets): add sra adapter (E-utilities)"
```

---

## Task 6: Register the four adapters

**Files:**
- Modify: `science/src/science_tool/datasets/__init__.py`
- Test: `science/tests/test_datasets.py`

- [ ] **Step 1: Write the failing test**

Add this test to `science/tests/test_datasets.py` (top-level function near the other registry tests):

```python
def test_domain_adapters_registered() -> None:
    from science_tool.datasets import available_adapters

    names = available_adapters()
    for name in ("figshare", "arrayexpress", "physionet", "sra"):
        assert name in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest science/tests/test_datasets.py::test_domain_adapters_registered -v`
Expected: FAIL — assertion error (names not yet registered)

- [ ] **Step 3: Register the adapters**

In `science/src/science_tool/datasets/__init__.py`, inside `_auto_register()`, append four blocks after the existing `cbioportal` block (before the function ends):

```python
    try:
        from science_tool.datasets.figshare import FigshareAdapter

        register("figshare", FigshareAdapter)
    except ImportError:
        pass
    try:
        from science_tool.datasets.arrayexpress import ArrayExpressAdapter

        register("arrayexpress", ArrayExpressAdapter)
    except ImportError:
        pass
    try:
        from science_tool.datasets.physionet import PhysioNetAdapter

        register("physionet", PhysioNetAdapter)
    except ImportError:
        pass
    try:
        from science_tool.datasets.sra import SRAAdapter

        register("sra", SRAAdapter)
    except ImportError:
        pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest science/tests/test_datasets.py::test_domain_adapters_registered -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets/__init__.py science/tests/test_datasets.py
git commit -m "feat(datasets): register figshare/arrayexpress/physionet/sra adapters"
```

---

## Task 7: Surface `access` in the CLI

**Files:**
- Modify: `science/src/science_tool/cli.py` (`datasets_search` ~line 2974, `datasets_metadata` ~line 3010)
- Test: `science/tests/test_datasets_cli.py`

- [ ] **Step 1: Write the failing tests**

Append to the `TestDatasetsCLI` class in `science/tests/test_datasets_cli.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest science/tests/test_datasets_cli.py::TestDatasetsCLI::test_search_json_includes_access science/tests/test_datasets_cli.py::TestDatasetsCLI::test_metadata_json_includes_access -v`
Expected: FAIL — `KeyError: 'access'` (search) and `StopIteration` (metadata: no "Access" row)

- [ ] **Step 3a: Add `access` to the search rows/columns**

In `science/src/science_tool/cli.py`, in `datasets_search`, add `"access"` to each row dict and an `("access", "Access")` column. The row builder becomes:

```python
    rows = [
        {
            "source": r.source,
            "id": r.id,
            "title": r.title[:80],
            "year": r.year or "",
            "access": r.access or "",
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
            ("access", "Access"),
            ("doi", "DOI"),
        ],
        rows=rows,
    )
```

- [ ] **Step 3b: Add the `Access` row to metadata**

In `datasets_metadata`, add an `Access` row to the `rows` list, immediately after the `License` row:

```python
        {"field": "License", "value": result.license or ""},
        {"field": "Access", "value": result.access or ""},
        {"field": "Keywords", "value": ", ".join(result.keywords) if result.keywords else ""},
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest science/tests/test_datasets_cli.py -v`
Expected: PASS (existing tests + the two new ones)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/cli.py science/tests/test_datasets_cli.py
git commit -m "feat(datasets): surface access tier in search and metadata CLI output"
```

---

## Task 8: Update documentation

**Files:**
- Modify: `science/commands/find-datasets.md`
- Modify: `science/codex-skills/science-find-datasets/SKILL.md` (only if it duplicates the adapter list)

- [ ] **Step 1: Update the adapter-coverage line in `find-datasets.md`**

Find the sentence (~line 73): `Adapters cover Zenodo, NCBI GEO, Dryad, Semantic Scholar, and the public cBioPortal study catalog.` Replace with:

```markdown
Adapters cover Zenodo, NCBI GEO, Dryad, Semantic Scholar, the public cBioPortal
study catalog, figshare, ArrayExpress (EBI BioStudies), PhysioNet, and NCBI SRA.

**Access tiers:** PhysioNet and SRA report an access tier on each result —
`public` (freely downloadable), `restricted` (self-serve DUA/login), or
`controlled` (application/approval required). PhysioNet `restricted`/`credentialed`
files raise on download until access is granted; SRA `.sra` files need
`fasterq-dump` conversion downstream.
```

- [ ] **Step 2: Add the access crosswalk near the `access` entity-field guidance**

In `find-datasets.md`, find the `access` field guidance (~line 119: `access — one of public, controlled, mixed`). Append this note directly beneath that bullet:

```markdown
  When mapping an adapter result's `access` tier to the entity `access.level`,
  apply: `public → public`, `restricted → controlled`, `controlled → controlled`.
  `mixed` is set only when sibling artefacts differ in level (see emission rules).
```

- [ ] **Step 3: Mirror into the codex skill if needed**

Run: `grep -n "Adapters cover\|Zenodo, NCBI GEO\|cBioPortal" science/codex-skills/science-find-datasets/SKILL.md`

If a matching adapter-list sentence exists, apply the same replacement as Step 1. If `grep` returns nothing, skip this step (no duplicate list to update).

- [ ] **Step 4: Commit**

```bash
git add science/commands/find-datasets.md science/codex-skills/science-find-datasets/SKILL.md
git commit -m "docs(datasets): document four new adapters and access crosswalk"
```

---

## Final Validation

- [ ] **Run the full datasets test suite**

Run: `uv run pytest science/tests/test_datasets.py science/tests/test_datasets_cli.py -v`
Expected: PASS (all tests, including the 5 existing adapters' tests — no regressions)

- [ ] **Lint**

Run: `uv run ruff check science/src/science_tool/datasets science/src/science_tool/cli.py`
Expected: no errors

- [ ] **Smoke-check the adapters register**

Run: `uv run science datasets sources`
Expected output includes: `arrayexpress`, `cbioportal`, `dryad`, `figshare`, `geo`, `physionet`, `semantic_scholar`, `sra`, `zenodo`

---

## Self-Review Notes (author checklist — done at plan-writing time)

- **Spec coverage:** §2.1 access field → Task 1; §2.2 CLI → Task 7; §3.1–3.4 four adapters → Tasks 2–5; §4 registration → Task 6; §5 testing → tests embedded per task + `test_access_tier`/gated-download in Task 4 and registry in Task 6; §6 docs → Task 8; §7 validation → Final Validation. No uncovered spec section.
- **Type consistency:** all adapters return `DatasetResult`/`FileInfo` from `_base`; `access` values restricted to `public`/`restricted`/`controlled`/`None`; method names match the `DatasetAdapter` protocol exactly.
- **Known caveats carried from design:** PhysioNet `size_bytes` is always `None` (sha256sums lacks sizes); SRA `ExpXml` fragments may contain unescaped `&` — `_fragment()` degrades to an empty element on `ParseError` rather than crashing the whole summary parse.
