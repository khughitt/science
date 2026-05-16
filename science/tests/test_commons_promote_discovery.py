"""Tests for science_tool.commons.promote — discovery + module surface."""

from __future__ import annotations

import pytest


def test_promote_module_imports() -> None:
    from science_tool.commons import promote  # noqa: F401


def test_dataclass_surface_is_frozen() -> None:
    from science_tool.commons.promote import (
        ConflictResolution,
        DiscoveryResult,
        FailedCandidate,
        FieldConflict,
        OverlayRewrite,
        PromoteCandidate,
        PromoteDecision,
        PromotePlan,
        PromoteResult,
    )

    for cls in (
        PromoteCandidate,
        FieldConflict,
        ConflictResolution,
        OverlayRewrite,
        PromoteDecision,
        FailedCandidate,
        DiscoveryResult,
        PromotePlan,
        PromoteResult,
    ):
        # frozen=True is the authoritative flag on the dataclass params
        assert cls.__dataclass_params__.frozen, f"{cls.__name__} must be frozen"


def test_normalize_bibkey_for_match_casefolds() -> None:
    from science_tool.commons.promote import _normalize_bibkey_for_match
    assert _normalize_bibkey_for_match("Huh2024") == "huh2024"
    assert _normalize_bibkey_for_match("ADAMS2025") == "adams2025"
    assert _normalize_bibkey_for_match("Adams2025.md") == "adams2025"


def test_normalize_bibkey_for_match_rejects_empty() -> None:
    from science_tool.commons.promote import _normalize_bibkey_for_match
    from science_tool.commons.errors import PromoteCandidateError
    with pytest.raises(PromoteCandidateError):
        _normalize_bibkey_for_match("")
    with pytest.raises(PromoteCandidateError):
        _normalize_bibkey_for_match("   ")


def test_normalize_bibkey_for_match_rejects_regex_failing() -> None:
    from science_tool.commons.promote import _normalize_bibkey_for_match
    from science_tool.commons.errors import PromoteCandidateError
    with pytest.raises(PromoteCandidateError):
        _normalize_bibkey_for_match("1leading-digit")
    with pytest.raises(PromoteCandidateError):
        _normalize_bibkey_for_match("has space")


def test_classify_paper_file_kind_explicit_paper() -> None:
    from science_tool.commons.promote import _classify_paper_file_kind
    assert _classify_paper_file_kind({"kind": "paper"}) == "paper"
    assert _classify_paper_file_kind({"type": "paper"}) == "paper"


def test_classify_paper_file_kind_explicit_other_kind() -> None:
    from science_tool.commons.promote import _classify_paper_file_kind
    assert _classify_paper_file_kind({"kind": "review-article"}) == "skip-other-kind"
    assert _classify_paper_file_kind({"type": "dataset"}) == "skip-other-kind"


def test_classify_paper_file_kind_no_kind_inferred_as_paper() -> None:
    from science_tool.commons.promote import _classify_paper_file_kind
    assert _classify_paper_file_kind({"title": "Foo"}) == "paper"
    assert _classify_paper_file_kind({}) == "paper"


def test_classify_paper_file_kind_non_paper_id_prefix() -> None:
    from science_tool.commons.promote import _classify_paper_file_kind
    assert _classify_paper_file_kind({"id": "dataset:foo"}) == "skip-other-id"
    assert _classify_paper_file_kind({"id": "paper:Adams2025"}) == "paper"


def test_classify_paper_file_kind_explicit_kind_overrides_contradictory_id() -> None:
    """Rule ordering: explicit `kind: paper` wins over a non-paper `id:` prefix
    (the id check is defense-in-depth against directory-inference, not
    against an explicit kind declaration)."""
    from science_tool.commons.promote import _classify_paper_file_kind
    assert _classify_paper_file_kind({"id": "dataset:foo", "kind": "paper"}) == "paper"
    assert _classify_paper_file_kind({"id": "paper:Adams2025", "kind": "dataset"}) == "skip-other-kind"
