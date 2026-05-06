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
            params={"q": query, "type": "dataset", "size": max_results, "sort": "bestmatch"},
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

    def _parse_record(self, data: dict) -> DatasetResult:  # type: ignore[type-arg]
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

    def _parse_file(self, data: dict) -> FileInfo:  # type: ignore[type-arg]
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
