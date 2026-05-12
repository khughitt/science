"""text_segmentation: sentence boundaries + selector building."""

from __future__ import annotations

import pytest

from science_tool.annotation.model import TextQuoteSelector
from science_tool.annotation.text_segmentation import (
    build_quote_selector,
    sentence_range_at,
    sentence_range_containing_literal,
    split_sentences_with_offsets,
)


# ---- split_sentences_with_offsets -------------------------------------

def test_split_sentences_simple() -> None:
    text = "First sentence. Second sentence. Third."
    ranges = split_sentences_with_offsets(text)
    assert len(ranges) == 3
    assert text[ranges[0][0] : ranges[0][1]] == "First sentence."
    assert text[ranges[1][0] : ranges[1][1]] == "Second sentence."
    assert text[ranges[2][0] : ranges[2][1]] == "Third."


def test_split_sentences_empty_text() -> None:
    assert split_sentences_with_offsets("") == []


def test_split_sentences_no_terminator() -> None:
    text = "Just a fragment with no period"
    ranges = split_sentences_with_offsets(text)
    assert ranges == [(0, len(text))]


def test_split_sentences_across_lines() -> None:
    text = "Line one ends.\nLine two ends.\nLine three."
    ranges = split_sentences_with_offsets(text)
    assert len(ranges) == 3


# ---- sentence_range_at (col REQUIRED) ---------------------------------

def test_sentence_range_at_picks_correct_sentence_on_multi_sent_line() -> None:
    text = "First. Second. Third."
    rng = sentence_range_at(text, line=1, col=8)
    assert rng is not None
    assert text[rng[0] : rng[1]] == "Second."


def test_sentence_range_at_picks_first_when_col_inside_first() -> None:
    text = "First sentence here. Second sentence."
    rng = sentence_range_at(text, line=1, col=3)
    assert rng is not None
    assert text[rng[0] : rng[1]] == "First sentence here."


def test_sentence_range_at_inter_sentence_whitespace_falls_back() -> None:
    text = "First.  Second."
    rng = sentence_range_at(text, line=1, col=7)
    assert rng is not None
    assert text[rng[0] : rng[1]] == "First."


def test_sentence_range_at_line_out_of_range_returns_none() -> None:
    text = "One sentence."
    assert sentence_range_at(text, line=99, col=1) is None


# ---- sentence_range_containing_literal --------------------------------

def test_sentence_range_containing_literal_picks_second_sentence() -> None:
    """Regression for marker-token mis-anchoring on multi-sentence lines."""
    text = "Some text. A claim [UNVERIFIED] sits here. Trailing text."
    rng = sentence_range_containing_literal(text, line=1, literal="[UNVERIFIED]")
    assert rng is not None
    assert text[rng[0] : rng[1]] == "A claim [UNVERIFIED] sits here."


def test_sentence_range_containing_literal_picks_first_sentence() -> None:
    text = "[UNVERIFIED] starts the line. Next sentence here."
    rng = sentence_range_containing_literal(text, line=1, literal="[UNVERIFIED]")
    assert rng is not None
    assert text[rng[0] : rng[1]] == "[UNVERIFIED] starts the line."


def test_sentence_range_containing_literal_not_on_line() -> None:
    text = "Line one has nothing.\nLine two has [UNVERIFIED]."
    assert sentence_range_containing_literal(
        text, line=1, literal="[UNVERIFIED]",
    ) is None


def test_sentence_range_containing_literal_finds_on_correct_line() -> None:
    text = "Line one has nothing.\nLine two has [UNVERIFIED]."
    rng = sentence_range_containing_literal(
        text, line=2, literal="[UNVERIFIED]",
    )
    assert rng is not None
    assert text[rng[0] : rng[1]] == "Line two has [UNVERIFIED]."


# ---- build_quote_selector ---------------------------------------------

def test_build_quote_selector_full_window_in_middle() -> None:
    text = "x" * 100 + "Target sentence." + "y" * 100
    sent_start = 100
    sent_end = sent_start + len("Target sentence.")
    sel = build_quote_selector(text, sent_start, sent_end, context=60)
    assert isinstance(sel, TextQuoteSelector)
    assert sel.exact == "Target sentence."
    assert sel.prefix == "x" * 60
    assert sel.suffix == "y" * 60


def test_build_quote_selector_truncates_prefix_near_start() -> None:
    text = "Pre " + "Target sentence." + "y" * 100
    sent_start = 4
    sent_end = sent_start + len("Target sentence.")
    sel = build_quote_selector(text, sent_start, sent_end, context=60)
    assert sel.exact == "Target sentence."
    assert sel.prefix == "Pre "
    assert sel.suffix == "y" * 60


def test_build_quote_selector_truncates_suffix_near_eof() -> None:
    text = "x" * 100 + "Target sentence." + " End"
    sent_start = 100
    sent_end = sent_start + len("Target sentence.")
    sel = build_quote_selector(text, sent_start, sent_end, context=60)
    assert sel.exact == "Target sentence."
    assert sel.prefix == "x" * 60
    assert sel.suffix == " End"


def test_sentence_range_at_requires_col_no_default() -> None:
    """`col` MUST be required; defaulting silently mis-anchors markers."""
    with pytest.raises(TypeError):
        sentence_range_at("x.", line=1)  # type: ignore[call-arg]
