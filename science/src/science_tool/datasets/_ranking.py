"""Relevance ranking and cross-source dedup for merged dataset search results.

Pure functions over already-normalized DatasetResult lists — no I/O, no network.
Applied by search_all after the per-source fan-out (datasets/__init__.py).
"""

from __future__ import annotations

import re  # noqa: F401

from science_tool.datasets._base import DatasetResult  # noqa: F401

_DOI_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi:",
)


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
