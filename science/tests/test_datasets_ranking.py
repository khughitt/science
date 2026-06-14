"""Tests for dataset result ranking and dedup (datasets/_ranking.py)."""

from __future__ import annotations

from science_tool.datasets._base import DatasetResult
from science_tool.datasets._ranking import _normalize_doi


class TestNormalizeDoi:
    def test_strips_https_prefix(self) -> None:
        assert _normalize_doi("https://doi.org/10.5281/ZENODO.123") == "10.5281/zenodo.123"

    def test_strips_dx_and_doi_scheme(self) -> None:
        assert _normalize_doi("http://dx.doi.org/10.1/x") == "10.1/x"
        assert _normalize_doi("doi:10.1/x") == "10.1/x"

    def test_bare_doi_lowercased_and_trimmed(self) -> None:
        assert _normalize_doi("  10.1/ABC  ") == "10.1/abc"

    def test_none_and_empty_return_none(self) -> None:
        assert _normalize_doi(None) is None
        assert _normalize_doi("") is None
        assert _normalize_doi("   ") is None
