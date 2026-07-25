from __future__ import annotations

import pytest

from science_tool.graph.health_projection import (
    COUNTS_AS_ISSUE_SECTIONS,
    SEVERITY_SECTIONS,
    UNFILTERED_SECTIONS,
    meets_threshold,
)


def test_entity_identity_is_severity_bearing() -> None:
    assert "entity_identity" in SEVERITY_SECTIONS


def test_cross_paper_evidence_is_severity_bearing_not_counts_as_issue() -> None:
    assert "cross_paper_evidence" in SEVERITY_SECTIONS
    assert "cross_paper_evidence" not in COUNTS_AS_ISSUE_SECTIONS


def test_prose_epistemics_filters_on_severity() -> None:
    assert "prose_epistemics" in SEVERITY_SECTIONS


def test_managed_artifacts_is_counts_as_issue_only() -> None:
    assert "managed_artifacts" in COUNTS_AS_ISSUE_SECTIONS
    assert "managed_artifacts" not in SEVERITY_SECTIONS


def test_unwired_checks_is_never_filtered() -> None:
    assert "unwired_checks" in UNFILTERED_SECTIONS


def test_classifications_are_disjoint() -> None:
    assert not (SEVERITY_SECTIONS & COUNTS_AS_ISSUE_SECTIONS)
    assert not (SEVERITY_SECTIONS & UNFILTERED_SECTIONS)
    assert not (COUNTS_AS_ISSUE_SECTIONS & UNFILTERED_SECTIONS)


@pytest.mark.parametrize(
    ("severity", "threshold", "expected"),
    [
        ("warning", "warn", True),
        ("error", "warn", True),
        ("info", "warn", False),
        ("error", "error", True),
        ("warning", "error", False),
        ("info", "all", True),
        ("warning", "all", True),
    ],
)
def test_threshold_semantics(severity: str, threshold: str, expected: bool) -> None:
    assert meets_threshold({"severity": severity}, threshold) is expected


def test_counts_as_issue_never_filters_display() -> None:
    """A warning that counts as an issue is still hidden at --severity error."""
    assert meets_threshold({"severity": "warning", "counts_as_issue": True}, "error") is False


def test_row_without_severity_survives_every_threshold() -> None:
    assert meets_threshold({"code": "x"}, "error") is True


def test_unknown_severity_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown health severity"):
        meets_threshold({"severity": "critical"}, "warn")


def test_explicit_none_severity_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown health severity"):
        meets_threshold({"severity": None}, "warn")
