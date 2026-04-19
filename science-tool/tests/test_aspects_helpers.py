from __future__ import annotations

import pytest

from science_model.aspects import (
    KNOWN_ASPECTS,
    AspectValidationError,
    load_project_aspects,
    matches_aspect_filter,
    resolve_entity_aspects,
    validate_entity_aspects,
)


def test_known_aspects_matches_science_yaml_schema() -> None:
    assert KNOWN_ASPECTS == frozenset(
        {
            "causal-modeling",
            "hypothesis-testing",
            "computational-analysis",
            "software-development",
        }
    )


def test_resolve_returns_entity_aspects_when_explicit() -> None:
    resolved = resolve_entity_aspects(
        entity_aspects=["software-development"],
        project_aspects=["hypothesis-testing", "software-development"],
    )
    assert resolved == ["software-development"]


def test_resolve_inherits_project_when_entity_is_none() -> None:
    resolved = resolve_entity_aspects(
        entity_aspects=None,
        project_aspects=["hypothesis-testing", "computational-analysis"],
    )
    assert resolved == ["hypothesis-testing", "computational-analysis"]


def test_resolve_preserves_order_of_explicit_entity_aspects() -> None:
    resolved = resolve_entity_aspects(
        entity_aspects=["computational-analysis", "hypothesis-testing"],
        project_aspects=["hypothesis-testing", "computational-analysis"],
    )
    assert resolved == ["computational-analysis", "hypothesis-testing"]


def test_matches_when_intersection_is_nonempty() -> None:
    assert matches_aspect_filter(
        resolved=["hypothesis-testing", "computational-analysis"],
        filter_set={"hypothesis-testing"},
    )


def test_does_not_match_when_disjoint() -> None:
    assert not matches_aspect_filter(
        resolved=["software-development"],
        filter_set={"hypothesis-testing", "computational-analysis"},
    )


def test_does_not_match_on_empty_resolved() -> None:
    assert not matches_aspect_filter(resolved=[], filter_set={"hypothesis-testing"})


def test_does_not_match_on_empty_filter_set() -> None:
    assert not matches_aspect_filter(
        resolved=["hypothesis-testing"], filter_set=set()
    )


PROJECT = ["causal-modeling", "hypothesis-testing", "software-development"]


def test_validate_accepts_subset_of_project() -> None:
    assert validate_entity_aspects(["hypothesis-testing"], PROJECT) == [
        "hypothesis-testing"
    ]


def test_validate_returns_canonical_order() -> None:
    # Caller supplied in a non-project order; helper normalizes to project order.
    assert validate_entity_aspects(
        ["software-development", "causal-modeling"], PROJECT
    ) == ["causal-modeling", "software-development"]


def test_validate_rejects_empty_list() -> None:
    with pytest.raises(AspectValidationError, match="empty"):
        validate_entity_aspects([], PROJECT)


def test_validate_rejects_duplicates() -> None:
    with pytest.raises(AspectValidationError, match="duplicate"):
        validate_entity_aspects(["hypothesis-testing", "hypothesis-testing"], PROJECT)


def test_validate_rejects_aspect_not_in_project() -> None:
    with pytest.raises(AspectValidationError, match="not declared"):
        validate_entity_aspects(["computational-analysis"], PROJECT)


def test_validate_rejects_aspect_not_in_vocabulary() -> None:
    with pytest.raises(AspectValidationError, match="vocabulary"):
        validate_entity_aspects(["typo-aspect"], PROJECT + ["typo-aspect"])


def test_load_reads_aspects_field(tmp_path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\naspects:\n  - hypothesis-testing\n"
        "  - computational-analysis\n"
    )
    assert load_project_aspects(tmp_path) == [
        "hypothesis-testing",
        "computational-analysis",
    ]


def test_load_returns_empty_list_when_aspects_absent(tmp_path) -> None:
    (tmp_path / "science.yaml").write_text("name: demo\nprofile: research\n")
    assert load_project_aspects(tmp_path) == []


def test_load_raises_when_yaml_missing(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        load_project_aspects(tmp_path)
