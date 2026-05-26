from __future__ import annotations

import pytest

from science_tool.commons.member import (
    MemberOf,
    ResolutionState,
    evaluate_key_resolution,
    parse_member_of,
)


def test_parse_member_of_extracts_parent_and_key() -> None:
    entity = {
        "origin": "derived",
        "derivation": {
            "kind": "member_of",
            "parent_dataset": "dataset:reactome-v89",
            "member_key": "R-HSA-12345",
        },
    }
    assert parse_member_of(entity) == MemberOf(
        parent_dataset="dataset:reactome-v89", member_key="R-HSA-12345"
    )


def test_parse_member_of_returns_none_for_workflow_derivation() -> None:
    entity = {"origin": "derived", "derivation": {"workflow_recipe": "r", "inputs": []}}
    assert parse_member_of(entity) is None


def test_parse_member_of_returns_none_when_no_derivation() -> None:
    assert parse_member_of({"origin": "external"}) is None


def test_evaluate_key_resolution_resolved_when_key_present() -> None:
    state = evaluate_key_resolution(
        key="R-HSA-12345", available_keys={"R-HSA-12345", "R-HSA-2"}, declared_status=None
    )
    assert state is ResolutionState.RESOLVED


def test_evaluate_key_resolution_unresolved_when_key_absent() -> None:
    state = evaluate_key_resolution(
        key="R-HSA-999", available_keys={"R-HSA-1"}, declared_status=None
    )
    assert state is ResolutionState.UNRESOLVED


def test_evaluate_key_resolution_declared_unresolved_is_first_class() -> None:
    # An explicit declared_unresolved is honoured even with no key index available.
    state = evaluate_key_resolution(
        key="X", available_keys=None, declared_status="declared_unresolved"
    )
    assert state is ResolutionState.DECLARED_UNRESOLVED


def test_evaluate_key_resolution_unknown_when_no_index_and_no_declaration() -> None:
    # No key index to check against and no explicit declaration: the contract is
    # unverifiable here, reported as UNKNOWN (the check decides severity).
    state = evaluate_key_resolution(key="X", available_keys=None, declared_status=None)
    assert state is ResolutionState.UNKNOWN


def test_evaluate_key_resolution_rejects_unknown_declared_status() -> None:
    with pytest.raises(ValueError, match="resolution_status"):
        evaluate_key_resolution(key="X", available_keys=None, declared_status="bogus")
