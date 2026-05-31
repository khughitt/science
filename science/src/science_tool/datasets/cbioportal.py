"""cBioPortal dataset adapter (public www.cbioportal.org REST API).

Surfaces the public cBioPortal study catalog (TCGA, CPTAC, MSK, and other
oncology cohorts) to ``datasets search`` (fb-2026-05-30-013/014). The public
API's ``keyword`` filter is case-sensitive substring matching against
title-cased study names, which made it effectively unusable for free-text
queries. This adapter instead fetches the bounded study catalog once and filters
client-side with case-insensitive, all-tokens-must-match semantics.

Scope: this covers the public www.cbioportal.org instance only. DUA-gated or
separately hosted cohorts (e.g. AACR GENIE BPC on Synapse / genie.cbioportal.org)
are not reachable here.
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import httpx

from science_tool.datasets._base import DatasetResult, FileInfo

BASE_URL = "https://www.cbioportal.org/api"
DATAHUB_TARBALL = "https://cbioportal-datahub.s3.amazonaws.com/{study_id}.tar.gz"
STUDY_SUMMARY_URL = "https://www.cbioportal.org/study/summary?id={study_id}"

# The public catalog is a few hundred studies; one full SUMMARY fetch is cheap
# and lets us filter case-insensitively client-side.
_CATALOG_PAGE_SIZE = 10000
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


class CBioPortalAdapter:
    """Search and access public studies from cBioPortal."""

    name = "cbioportal"

    def __init__(self) -> None:
        self._client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    def search(self, query: str, *, max_results: int = 20) -> list[DatasetResult]:
        resp = self._client.get(
            "/studies",
            params={
                "projection": "SUMMARY",
                "pageSize": _CATALOG_PAGE_SIZE,
                "pageNumber": 0,
                "direction": "ASC",
            },
        )
        resp.raise_for_status()
        tokens = [tok for tok in query.lower().split() if tok]
        if not tokens:
            return []

        scored: list[tuple[int, str, dict]] = []
        for study in resp.json():
            haystack = self._haystack(study)
            if all(tok in haystack for tok in tokens):
                score = sum(haystack.count(tok) for tok in tokens)
                scored.append((score, str(study.get("studyId", "")), study))
        # Highest match-count first; studyId tiebreak keeps ordering deterministic.
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [self._parse_study(study) for _, _, study in scored[:max_results]]

    def metadata(self, dataset_id: str) -> DatasetResult:
        resp = self._client.get(f"/studies/{dataset_id}")
        resp.raise_for_status()
        result = self._parse_study(resp.json())
        # The study object's allSampleCount is a placeholder (1); the real count
        # only comes from the dedicated samples listing. Worth one extra request
        # for a single known study (but not for every catalog hit in search()).
        samples = self._client.get(
            f"/studies/{dataset_id}/samples", params={"projection": "ID"}
        )
        samples.raise_for_status()
        return replace(result, sample_count=len(samples.json()))

    def files(self, dataset_id: str) -> list[FileInfo]:
        # Public studies are distributed as a single datahub tarball. Not every
        # study is mirrored there, so this is a best-effort canonical URL.
        return [
            FileInfo(
                filename=f"{dataset_id}.tar.gz",
                url=DATAHUB_TARBALL.format(study_id=dataset_id),
                format="tar.gz",
            )
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

    def _haystack(self, study: dict) -> str:  # type: ignore[type-arg]
        parts = [
            str(study.get(key, ""))
            for key in ("name", "description", "studyId", "cancerTypeId")
        ]
        return " ".join(parts).lower()

    def _parse_study(self, study: dict) -> DatasetResult:  # type: ignore[type-arg]
        study_id = str(study.get("studyId", ""))
        name = study.get("name", "")
        description = _HTML_TAG_RE.sub("", study.get("description", "")).strip()
        cancer_type = study.get("cancerTypeId") or None

        # Publication year is encoded in the study name (e.g. "(TCGA, Cell 2015)")
        # or citation; importDate is the load date, not publication, so avoid it.
        year_match = _YEAR_RE.search(name) or _YEAR_RE.search(str(study.get("citation", "")))
        year = int(year_match.group(0)) if year_match else None

        return DatasetResult(
            source="cbioportal",
            id=study_id,
            title=name,
            description=description,
            url=STUDY_SUMMARY_URL.format(study_id=study_id),
            year=year,
            organism="Homo sapiens",
            keywords=[cancer_type] if cancer_type else [],
        )
