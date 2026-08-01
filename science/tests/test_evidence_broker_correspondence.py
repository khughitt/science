from __future__ import annotations

import pytest
from science_model.audit import LocationEvidence, Span

from science_tool.evidence_broker.correspondence import (
    Absent,
    Full,
    Lines,
    PathOnly,
    _corresponds,
    _line_count,
    _merge_coverage,
)


@pytest.mark.parametrize(
    "left,right,expected",
    [
        (Full(8), Full(5), Full(5)),
        (Full(8), Lines(frozenset({9})), Full(8)),
        (Full(8), PathOnly(), Full(8)),
        (Full(8), Absent(), Full(8)),
        (Lines(frozenset({1})), Lines(frozenset({3})), Lines(frozenset({1, 3}))),
        (Lines(frozenset({1})), PathOnly(), Lines(frozenset({1}))),
        (PathOnly(), PathOnly(), PathOnly()),
        (PathOnly(), Absent(), Absent()),
        (Absent(), Absent(), Absent()),
    ],
)
def test_merge_coverage_is_total_over_reachable_pairs(left, right, expected) -> None:
    assert _merge_coverage(left, right) == expected
    assert _merge_coverage(right, left) == expected


def test_lines_and_absent_is_rejected_as_unreachable() -> None:
    with pytest.raises(ValueError, match="both matched and absent"):
        _merge_coverage(Lines(frozenset({1})), Absent())


@pytest.mark.parametrize(
    "payload,expected",
    [(b"", 0), (b"a\n", 1), (b"a", 1), (b"a\nb", 2), (b"a\rb\n", 1)],
)
def test_line_count_uses_lf_only(payload: bytes, expected: int) -> None:
    assert _line_count(payload) == expected


def test_full_bounds_lines_but_allows_a_pointer() -> None:
    assert _corresponds(LocationEvidence(path="a", line=2), Full(2))
    assert not _corresponds(LocationEvidence(path="a", line=3), Full(2))
    assert _corresponds(LocationEvidence(path="a", pointer="heading"), Full(0))


def test_lines_requires_every_line_of_a_span_and_forbids_a_pointer() -> None:
    coverage = Lines(frozenset({2, 3, 4}))
    assert _corresponds(LocationEvidence(path="a", span=Span(start_line=2, end_line=4)), coverage)
    endpoints_only = Lines(frozenset({2, 4}))
    assert not _corresponds(LocationEvidence(path="a", span=Span(start_line=2, end_line=4)), endpoints_only)
    assert not _corresponds(LocationEvidence(path="a", pointer="heading"), coverage)


@pytest.mark.parametrize("coverage", [PathOnly(), Absent()])
def test_path_only_coverages_accept_only_a_bare_path(coverage) -> None:
    assert _corresponds(LocationEvidence(path="a"), coverage)
    assert not _corresponds(LocationEvidence(path="a", line=1), coverage)
    assert not _corresponds(LocationEvidence(path="a", pointer="heading"), coverage)
