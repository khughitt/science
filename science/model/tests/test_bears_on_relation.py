"""Tests that the core profile declares the bears_on relation kind."""

from __future__ import annotations

from science_model.profiles.core import CORE_PROFILE
from science_model.relations import relation_allows_kinds


def test_core_profile_declares_bears_on():
    names = {r.name for r in CORE_PROFILE.relation_kinds}
    assert "bears_on" in names


def test_bears_on_predicate():
    rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == "bears_on")
    assert rel.predicate == "sci:bearsOn"


def test_bears_on_sources_are_unrestricted():
    rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == "bears_on")
    # Empty source_kinds list = unrestricted, matching the has_participant pattern.
    assert rel.source_kinds == []


def test_bears_on_targets_match_target_kinds_exactly() -> None:
    # Phase 1 polish (t013 #5): the relation must enumerate every kind that
    # the freshness engine will treat as EPISTEMIC. Drift here is a silent
    # bug — assert exact equality with the closed list.
    bears_on = next(r for r in CORE_PROFILE.relation_kinds if r.name == "bears_on")
    expected = {
        "assumption",
        "chain-audit",
        "discussion",
        "finding",
        "hypothesis",
        "interpretation",
        "mechanism",
        "observation",
        "proposition",
        "question",
        "report",
        "story",
        "structural-chain",
        "theme",
        "validation-report",
    }
    assert set(bears_on.target_kinds) == expected


def test_bears_on_allows_structural_chain_as_target():
    bears_on = next(r for r in CORE_PROFILE.relation_kinds if r.name == "bears_on")
    assert relation_allows_kinds(bears_on, "mechanism", "structural-chain")
    assert relation_allows_kinds(bears_on, "finding", "structural-chain")


def test_bears_on_allows_chain_audit_as_target():
    bears_on = next(r for r in CORE_PROFILE.relation_kinds if r.name == "bears_on")
    assert relation_allows_kinds(bears_on, "structural-chain", "chain-audit")


def test_bears_on_still_rejects_dataset_target():
    # Regression: bears_on must not accept operational kinds.
    bears_on = next(r for r in CORE_PROFILE.relation_kinds if r.name == "bears_on")
    assert not relation_allows_kinds(bears_on, "interpretation", "dataset")
