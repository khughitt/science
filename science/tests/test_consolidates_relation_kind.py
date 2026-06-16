"""consolidates RelationKind: registered, synthesis->any allowed (P4)."""
from __future__ import annotations

from science_model.profiles.core import CORE_PROFILE
from science_model.relations import build_relation_registry, relation_allows_kinds


def _consolidates():
    registry = build_relation_registry(CORE_PROFILE.relation_kinds)
    assert "consolidates" in registry
    return registry["consolidates"]


def test_consolidates_predicate_is_sci_consolidates() -> None:
    assert _consolidates().predicate == "sci:consolidates"


def test_consolidates_source_is_synthesis_target_unrestricted() -> None:
    rel = _consolidates()
    assert rel.source_kinds == ["synthesis"]
    assert rel.target_kinds == []  # empty == unrestricted target


def test_consolidates_allows_synthesis_to_any_member_kind() -> None:
    rel = _consolidates()
    assert relation_allows_kinds(rel, "synthesis", "finding") is True
    assert relation_allows_kinds(rel, "synthesis", "hypothesis") is True
    assert relation_allows_kinds(rel, "finding", "hypothesis") is False  # wrong source
