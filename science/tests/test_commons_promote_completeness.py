"""Promote-time completeness gate for paper canonicals.

fb-2026-07-11-020. Promotion makes one project's paper summary THE canonical
entity every other project reads. A canonical that carries no Methods or
Limitations section leaves consumers unable to assess evidential strength. This
gate MEASURES the missing evidential-strength sections at promote time and
surfaces them; it decides nothing (mirroring `promote_body_loss`).

The report's other two asks — "warn when a project entity cites a claim absent
from the canonical body" and "consumer overlay contradicts its canonical" — are
semantic and cannot be honestly automated, so they are not attempted here.
"""
from __future__ import annotations

from science_tool.commons.promote_completeness import paper_completeness_gaps


def test_complete_paper_has_no_gaps() -> None:
    body = {"Methods": "we did X", "Limitations": "small n", "Key Findings": "y"}
    assert paper_completeness_gaps(body) == []


def test_missing_methods_and_limitations_both_reported() -> None:
    body = {"Key Findings": "y", "Summary": "z"}
    assert paper_completeness_gaps(body) == ["Methods", "Limitations"]


def test_missing_only_limitations() -> None:
    body = {"Methods": "we did X", "Key Findings": "y"}
    assert paper_completeness_gaps(body) == ["Limitations"]


def test_present_but_empty_section_counts_as_missing() -> None:
    body = {"Methods": "   \n", "Limitations": ""}
    assert paper_completeness_gaps(body) == ["Methods", "Limitations"]
