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

    def _parse_dataset(self, data: dict) -> DatasetResult:  # type: ignore[type-arg]
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

    def _parse_file(self, data: dict) -> FileInfo:  # type: ignore[type-arg]
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
