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
        year = int(publish[:4]) if len(publish) >= 4 and publish[:4].isdigit() else None
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
