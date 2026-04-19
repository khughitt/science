from __future__ import annotations

from science_model.aspects import KNOWN_ASPECTS, matches_aspect_filter, resolve_entity_aspects


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
