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
