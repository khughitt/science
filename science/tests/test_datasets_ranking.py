"""Tests for dataset result ranking and dedup (datasets/_ranking.py)."""

from __future__ import annotations

from science_tool.datasets._base import DatasetResult
from science_tool.datasets._ranking import _normalize_doi, _richness, score_result


def _r(**kw) -> DatasetResult:
    base = dict(source="s", id="i", title="")
    base.update(kw)
    return DatasetResult(**base)


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


class TestScoreResult:
    def test_title_hit_outscores_description_hit(self) -> None:
        in_title = _r(title="circadian rhythm", description="unrelated")
        in_desc = _r(title="unrelated", description="circadian rhythm")
        assert score_result("circadian", in_title) > score_result("circadian", in_desc)

    def test_token_counts_once_per_field(self) -> None:
        # "rhythm" appears twice in the title but the query token scores once.
        r = _r(title="rhythm rhythm")
        assert score_result("rhythm", r) == 3.0  # title weight

    def test_multiple_fields_accumulate(self) -> None:
        r = _r(title="sleep", keywords=["sleep"], description="sleep")
        # title 3 + keywords 2 + description 1
        assert score_result("sleep", r) == 6.0

    def test_organism_and_modality_each_weight_one(self) -> None:
        r = _r(title="x", organism="mouse", modality="mouse")
        assert score_result("mouse", r) == 2.0

    def test_empty_query_scores_zero(self) -> None:
        assert score_result("", _r(title="anything")) == 0.0

    def test_no_match_scores_zero(self) -> None:
        assert score_result("zzz", _r(title="abc")) == 0.0


class TestRichness:
    def test_counts_populated_optional_fields(self) -> None:
        bare = _r(title="t")
        rich = _r(title="t", organism="mouse", modality="rna-seq", keywords=["a"], year=2024)
        assert _richness(rich) > _richness(bare)

    def test_bare_result_is_zero(self) -> None:
        assert _richness(_r(title="t")) == 0

    def test_empty_keywords_not_counted(self) -> None:
        # default keywords=[] is falsy and must not count toward richness
        assert _richness(_r(title="t", keywords=[])) == 0

    def test_doi_not_counted(self) -> None:
        # doi is the group key in dedup, constant within a group, so excluded
        assert _richness(_r(title="t", doi="10.1/x")) == 0
