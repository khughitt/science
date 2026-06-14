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
        year = int(release[:4]) if len(release) >= 4 and release[:4].isdigit() else None
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
