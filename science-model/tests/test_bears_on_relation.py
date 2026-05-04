"""Tests that the core profile declares the bears_on relation kind."""

from __future__ import annotations

from science_model.profiles.core import CORE_PROFILE


EPISTEMIC_KINDS = {
    "hypothesis",
    "question",
    "proposition",
    "observation",
    "finding",
    "interpretation",
    "discussion",
    "story",
    "mechanism",
}


def test_core_profile_declares_bears_on():
    names = {r.name for r in CORE_PROFILE.relation_kinds}
    assert "bears_on" in names


def test_bears_on_predicate():
    rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == "bears_on")
    assert rel.predicate == "sci:bearsOn"


def test_bears_on_targets_are_epistemic_only():
    rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == "bears_on")
    declared = set(rel.target_kinds)
    # Every declared target is in the epistemic set.
    assert declared.issubset(EPISTEMIC_KINDS), f"non-epistemic targets: {declared - EPISTEMIC_KINDS}"
    # Core epistemic kinds are all declared as valid targets.
    assert EPISTEMIC_KINDS.issubset(declared), f"missing epistemic targets: {EPISTEMIC_KINDS - declared}"


def test_bears_on_sources_are_unrestricted():
    rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == "bears_on")
    # Empty source_kinds list = unrestricted, matching the has_participant pattern.
    assert rel.source_kinds == []
