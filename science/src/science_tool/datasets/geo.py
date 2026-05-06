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
        resp = self._client.get(
            "/esearch.fcgi",
            params={"db": "gds", "term": query, "retmax": max_results, "usehistory": "n"},
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        ids = [el.text for el in root.findall(".//IdList/Id") if el.text]
        if not ids:
            return []

        resp = self._client.get(
            "/esummary.fcgi",
            params={"db": "gds", "id": ",".join(ids)},
        )
        resp.raise_for_status()
        return self._parse_esummary(resp.text)

    def metadata(self, dataset_id: str) -> DatasetResult:
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
        if not accession.startswith("GSE"):
            return []
        nnn = accession[:-3] + "nnn" if len(accession) > 6 else accession[:3] + "nnn"
        base = f"{GEO_FTP_HTTPS}/{nnn}/{accession}"
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
