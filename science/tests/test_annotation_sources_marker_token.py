"""MarkerTokenSource scanning, mirror vs remove selector text."""

from __future__ import annotations

from pathlib import Path


from science_tool.annotation.model import Motivation
from science_tool.annotation.sources.marker_token import (
    TOKEN_SOURCE_NAME,
    TOKEN_TYPE_MAP,
    MarkerTokenSource,
)

FIXTURE = (
    Path(__file__).parent
    / "_fixtures" / "annotation" / "audit" / "mixed-tokens.md"
)


def test_token_source_name_constant() -> None:
    assert TOKEN_SOURCE_NAME == "marker-scanner:phase-2"


def test_scan_finds_four_unique_tokens() -> None:
    src = MarkerTokenSource()
    rows = list(src.scan(FIXTURE))
    types = sorted(r.annotation_type for r in rows)
    assert types == ["inaccessible", "missing-citation", "speculation", "unverified"]


def test_scan_skips_documentation_and_fenced() -> None:
    src = MarkerTokenSource()
    rows = list(src.scan(FIXTURE))
    # Only 4 hits — backticked + fenced occurrences excluded.
    assert len(rows) == 4


def test_scan_sets_lifted_from_and_match_text() -> None:
    src = MarkerTokenSource()
    rows = list(src.scan(FIXTURE))
    for row in rows:
        assert row.lifted_from is not None
        assert row.lifted_from == row.match_text
        assert row.lifted_from.startswith("[") and row.lifted_from.endswith("]")
        assert row.source_name == TOKEN_SOURCE_NAME
        assert row.motivation == Motivation.CLASSIFYING


def test_scan_text_uses_provided_text_directly() -> None:
    """scan_text accepts pre-computed text (used by lift-tokens --remove)."""
    src = MarkerTokenSource()
    text = "Sentence with [UNVERIFIED] inline.\n"
    rows = list(src.scan_text(Path("synthetic.md"), text))
    assert len(rows) == 1
    assert rows[0].match_text == "[UNVERIFIED]"
    assert "[UNVERIFIED]" in rows[0].target.selector.exact


def test_scan_text_zero_hits_when_tokens_already_stripped() -> None:
    src = MarkerTokenSource()
    text = "Sentence with  inline.\n"  # tokens already removed
    rows = list(src.scan_text(Path("synthetic.md"), text))
    assert rows == []


def test_token_type_map_covers_all_four_canonical_tokens() -> None:
    assert set(TOKEN_TYPE_MAP) == {
        "UNVERIFIED", "MISSING_CITATION", "SPECULATION", "INACCESSIBLE",
    }
