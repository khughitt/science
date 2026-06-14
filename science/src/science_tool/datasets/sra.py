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

    def _item_content(self, item: ET.Element) -> ET.Element:
        """Return a <root> element wrapping the item's content.

        Handles two forms:
        - Escaped XML string in item.text (real NCBI API response)
        - Literal child elements already parsed by ElementTree (test fixtures)
        """
        children = list(item)
        if children:
            # Children already parsed — wrap them in a synthetic root
            wrapper = ET.Element("root")
            for child in children:
                wrapper.append(child)
            return wrapper
        return self._fragment(item.text or "")

    def _parse_esummary(self, xml_text: str) -> list[DatasetResult]:
        root = ET.fromstring(xml_text)
        results: list[DatasetResult] = []
        for doc in root.findall("DocSum"):
            item_els = {it.get("Name", ""): it for it in doc.findall("Item")}
            exp = self._item_content(item_els["ExpXml"]) if "ExpXml" in item_els else ET.fromstring("<root/>")
            runs = self._item_content(item_els["Runs"]) if "Runs" in item_els else ET.fromstring("<root/>")
            run_accs = [acc for r in runs.findall(".//Run") if (acc := r.get("acc"))]
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
            exp_xml_raw = item_els.get("ExpXml")
            exp_xml_str = ET.tostring(exp_xml_raw, encoding="unicode") if exp_xml_raw is not None else ""
            controlled = "dbgap" in exp_xml_str.lower()
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
            item_els = {it.get("Name", ""): it for it in doc.findall("Item")}
            runs = self._item_content(item_els["Runs"]) if "Runs" in item_els else ET.fromstring("<root/>")
            accs.extend(acc for r in runs.findall(".//Run") if (acc := r.get("acc")))
        return accs
