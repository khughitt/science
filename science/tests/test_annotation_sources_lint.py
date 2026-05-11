"""LintSource adapters: 3 instances, per-finding identity, dedupe shape."""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.annotation.model import Motivation
from science_tool.annotation.sources.lint import (
    DETECTOR_VERSIONS,
    LintSource,
    bare_author_year_source,
    numeric_anchor_source,
    short_form_ids_source,
    lint_source_name,
)

FX = Path(__file__).parent / "_fixtures" / "annotation" / "audit"


def test_lint_source_name_format() -> None:
    assert lint_source_name("bare-author-year") == \
        f"lint:bare-author-year-{DETECTOR_VERSIONS['bare-author-year']}"


def test_bare_author_year_source_emits_per_match_rows() -> None:
    rows = list(bare_author_year_source().scan(FX / "bare-author-year.md"))
    matches = sorted(r.match_text for r in rows)
    # Two mentions in one sentence + the standalone Brunton 2022.
    assert "Brunton 2022" in matches
    assert "Spivak 1999" in matches


def test_two_mentions_in_one_sentence_yield_two_rows() -> None:
    rows = list(bare_author_year_source().scan(FX / "bare-author-year.md"))
    # Find rows whose target.exact contains both names.
    multi = [
        r for r in rows
        if "Brunton 2022" in r.target.selector.exact
        and "Spivak 1999" in r.target.selector.exact
    ]
    matches = {r.match_text for r in multi}
    assert matches == {"Brunton 2022", "Spivak 1999"}


def test_short_form_ids_source_skips_canonical() -> None:
    rows = list(short_form_ids_source().scan(FX / "short-form-ids.md"))
    matches = [r.match_text for r in rows]
    assert "h04" in matches
    # The canonical hypothesis:h04-name occurrence must not be flagged.
    assert all(not r.target.selector.exact.startswith("Already canonical")
               or r.match_text == "h04" for r in rows)


def test_numeric_anchor_source_emits_unanchored_only() -> None:
    rows = list(numeric_anchor_source().scan(FX / "numeric-anchor.md"))
    matches = [r.match_text for r in rows]
    assert "42%" in matches
    assert "3.14" in matches


def test_lint_source_records_full_source_name() -> None:
    rows = list(bare_author_year_source().scan(FX / "bare-author-year.md"))
    assert all(
        r.source_name == lint_source_name("bare-author-year") for r in rows
    )


def test_lint_source_motivation_and_type() -> None:
    rows = list(bare_author_year_source().scan(FX / "bare-author-year.md"))
    for r in rows:
        assert r.motivation == Motivation.CLASSIFYING
        assert r.annotation_type == "bare-author-year"


def test_lint_source_lifted_from_is_none() -> None:
    rows = list(bare_author_year_source().scan(FX / "bare-author-year.md"))
    assert all(r.lifted_from is None for r in rows)


def test_lint_source_short_name_attribute() -> None:
    src = bare_author_year_source()
    assert src.short_name == "bare-author-year"
    assert isinstance(src, LintSource)
