# science/tests/test_annotation_selector.py
"""Unit tests for science_tool.annotation.selector."""
from science_tool.annotation import TextQuoteSelector
from science_tool.annotation.selector import (
    ResolutionStatus,
    _fuzzy_unique_match,
    resolve_selector,
)


def _sel(exact: str, prefix: str = "", suffix: str = "") -> TextQuoteSelector:
    return TextQuoteSelector(exact=exact, prefix=prefix, suffix=suffix)


def test_anchored_exact_unique_match() -> None:
    text = "alpha beta gamma delta"
    sel = _sel(exact="beta", prefix="alpha ", suffix=" gamma")
    r = resolve_selector(text, sel)
    assert r.status is ResolutionStatus.RESOLVED
    assert text[r.start:r.end] == "beta"


def test_bare_exact_unique_match_when_anchored_misses() -> None:
    # prefix/suffix don't match (the surrounding context drifted)
    # but exact appears uniquely.
    text = "alpha beta gamma delta"
    sel = _sel(exact="beta", prefix="WRONG", suffix="WRONG")
    r = resolve_selector(text, sel)
    assert r.status is ResolutionStatus.DEGRADED
    assert text[r.start:r.end] == "beta"


def test_bare_exact_ambiguous_falls_through_to_prefix_disambiguation() -> None:
    # exact appears twice; prefix uniquely identifies the first occurrence.
    text = "alpha foo, then alpha foo again"
    sel = _sel(exact="foo", prefix="alpha ", suffix=", then")
    r = resolve_selector(text, sel)
    assert r.status is ResolutionStatus.RESOLVED  # prefix+exact+suffix wins
    # The first "foo" in "alpha foo,"
    assert text.index("foo") == r.start


def test_bare_exact_ambiguous_with_prefix_only() -> None:
    text = "x foo y; z foo w"
    sel = _sel(exact="foo", prefix="x ", suffix="WRONG")
    r = resolve_selector(text, sel)
    assert r.status is ResolutionStatus.DEGRADED
    assert text[r.start:r.end] == "foo"
    assert r.start == text.index("foo")  # the "x foo" occurrence


def test_fuzzy_match_with_clear_margin() -> None:
    # Source text has a single 1-char-substituted version of exact.
    # exact = "quick brawn fox" (15 chars); source contains "quick brown fox".
    # Distance: 1 substitution (a↔o). max_distance = max(1, int(15*0.05)) = 1.
    # Within threshold; only one candidate → margin trivially satisfied.
    text = "the quick brown fox jumps over the lazy dog"
    sel = _sel(exact="quick brawn fox", prefix="WRONG", suffix="WRONG")
    r = resolve_selector(text, sel)
    assert r.status is ResolutionStatus.FUZZY
    matched = text[r.start:r.end]
    assert "brown" in matched


def test_fuzzy_guard_skips_pathological_inputs() -> None:
    # A stale selector against a large source must not trigger a whole-document
    # fuzzy scan (fb-2026-06-28-013): the cost guard returns no match so the
    # caller treats it as SUPERSEDED instead of hanging.
    source = "lorem ipsum dolor sit amet consectetur " * 30000  # ~1.2M chars
    exact = "this selector text is stale and totally absent here xyz"
    assert _fuzzy_unique_match(source, exact) is None
    sel = _sel(exact=exact)
    assert resolve_selector(source, sel).status is ResolutionStatus.SUPERSEDED


def test_fuzzy_still_recovers_on_normal_sized_source() -> None:
    # The guard must not disable legitimate fuzzy recovery on ordinary text:
    # a unique 1-substitution match in a several-KB source still resolves.
    source = "filler text. " * 500 + "the quick brown fox jumps. " + "more. " * 500
    sel = _sel(exact="quick brawn fox", prefix="WRONG", suffix="WRONG")
    r = resolve_selector(source, sel)
    assert r.status is ResolutionStatus.FUZZY
    assert "brown" in source[r.start:r.end]


def test_fuzzy_match_rejected_without_margin() -> None:
    # Two distinct windows in the source, each one substitution from exact.
    # Both are equally good fuzzy candidates → reject (margin requirement).
    text = "abcdy   ;   abcdz"
    sel = _sel(exact="abcdx", prefix="WRONG", suffix="WRONG")
    r = resolve_selector(text, sel)
    assert r.status is ResolutionStatus.SUPERSEDED


def test_ambiguous_exact_returns_superseded_without_attempting_fuzzy() -> None:
    # exact appears multiple times and one-sided anchors don't help.
    # Algorithm MUST NOT fall through to fuzzy (which would silently
    # attribute to the first occurrence with distance-0 ties).
    text = "alpha foo bar; alpha foo bar"
    sel = _sel(exact="foo", prefix="WRONG", suffix="WRONG")
    r = resolve_selector(text, sel)
    assert r.status is ResolutionStatus.SUPERSEDED


def test_no_match_returns_superseded() -> None:
    text = "completely different content"
    sel = _sel(exact="missing string", prefix="WRONG", suffix="WRONG")
    r = resolve_selector(text, sel)
    assert r.status is ResolutionStatus.SUPERSEDED
    assert r.start is None
    assert r.end is None
