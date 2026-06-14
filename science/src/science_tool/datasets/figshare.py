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
        if not file_info.url:
            raise ValueError(f"figshare file has no download URL: {file_info.filename}")
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / file_info.filename
        with self._client.stream("GET", file_info.url) as resp:
            resp.raise_for_status()
            with dest.open("wb") as f:
                for chunk in resp.iter_bytes(8192):
                    f.write(chunk)
        return dest

    def _year(self, published: str) -> int | None:
        if not published or len(published) < 4:
            return None
        try:
            return int(published[:4])
        except ValueError:
            return None

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
        total_size = sum(f.get("size") or 0 for f in files) if files else None
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
