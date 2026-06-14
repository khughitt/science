"""Relevance ranking and cross-source dedup for merged dataset search results.

Pure functions over already-normalized DatasetResult lists — no I/O, no network.
Applied by search_all after the per-source fan-out (datasets/__init__.py).
"""

from __future__ import annotations

import re

from science_tool.datasets._base import DatasetResult

_DOI_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi:",
)

_TOKEN_RE = re.compile(r"\w+")

# Field weights for lexical scoring (design §2.1).
_TITLE_WEIGHT = 3
_KEYWORDS_WEIGHT = 2
_ENTITY_WEIGHT = 1  # organism, modality (each)
_DESCRIPTION_WEIGHT = 1


def _normalize_doi(doi: str | None) -> str | None:
    """Canonical DOI key for dedup: lowercased, prefix-stripped, or None."""
    if doi is None:
        return None
    value = doi.strip().lower()
    for prefix in _DOI_PREFIXES:
        if value.startswith(prefix):
            value = value[len(prefix):]
            break
    value = value.strip()
    return value or None


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def score_result(query: str, result: DatasetResult) -> float:
    """Field-weighted count of distinct query tokens matched in a result."""
    query_tokens = _tokens(query)
    if not query_tokens:
        return 0.0
    fields: list[tuple[str, int]] = [
        (result.title, _TITLE_WEIGHT),
        (" ".join(result.keywords), _KEYWORDS_WEIGHT),
        (result.organism or "", _ENTITY_WEIGHT),
        (result.modality or "", _ENTITY_WEIGHT),
        (result.description, _DESCRIPTION_WEIGHT),
    ]
    score = 0.0
    for text, weight in fields:
        if not text:
            continue
        score += weight * len(query_tokens & _tokens(text))
    return score


def _richness(result: DatasetResult) -> int:
    """Count of populated optional metadata fields (dedup representative tiebreak).

    `doi` is excluded: it is the dedup group key, identical within a group.
    """
    optional = (
        result.description,
        result.url,
        result.year,
        result.license,
        result.keywords,
        result.organism,
        result.modality,
        result.access,
        result.sample_count,
        result.file_count,
        result.total_size_bytes,
    )
    return sum(1 for value in optional if value)


def dedupe_results(query: str, results: list[DatasetResult]) -> list[DatasetResult]:
    """Collapse same-DOI records, keeping the best representative.

    Groups by normalized DOI. Within a group the representative maximizes
    ``(score_result(query, r), _richness(r))`` — relevance first, metadata
    completeness as tiebreak. None-DOI records are never grouped. A group's
    output position is fixed by its first appearance in fan-out order.
    """
    groups: dict[str, list[DatasetResult]] = {}
    slots: list[DatasetResult | str] = []
    for r in results:
        key = _normalize_doi(r.doi)
        if key is None:
            slots.append(r)
        elif key in groups:
            groups[key].append(r)
        else:
            groups[key] = [r]
            slots.append(key)

    out: list[DatasetResult] = []
    for slot in slots:
        if isinstance(slot, str):
            group = groups[slot]
            out.append(max(group, key=lambda r: (score_result(query, r), _richness(r))))
        else:
            out.append(slot)
    return out


def rank_results(query: str, results: list[DatasetResult]) -> list[DatasetResult]:
    """Stable sort by descending lexical score (equal scores keep input order)."""
    return sorted(results, key=lambda r: score_result(query, r), reverse=True)
