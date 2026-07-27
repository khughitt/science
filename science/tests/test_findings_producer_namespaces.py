"""Scope declarations for the producer namespaces.

**This file is NOT design test 29** (producer-namespace completeness), and does not
pretend to be. Test 29 requires comparing filesystem-discovered producers against
registered ones. Plan 1 registers ZERO producers, so that comparison would be
`set() == set()` — a guard that passes because there is nothing to check. A green
vacuous assertion is worse than an absent one: it reads as coverage it does not have,
which is the failure mode this repo has already been bitten by.

**Test 29 is therefore deferred to Plan 2**, where the first real producers exist and
the comparison can fail.

What this file does guard now is the precondition test 29 will need: every registered
namespace declares WHERE its producers live. A namespace whose scope nobody defined
cannot be walked, so Plan 2 could not write test 29 for it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.findings.producers import PRODUCER_NAMESPACES

SRC = Path(__file__).resolve().parents[1] / "src" / "science_tool"

#: Where each namespace's producer modules live, relative to `science_tool/`.
NAMESPACE_DIRS: dict[str, str] = {
    "health_checks": "graph/health_checks",
    "validate_checks": "validate/checks",
    "data_audit": "data_audit.py",
}


def test_every_namespace_declares_where_its_producers_live():
    missing = set(PRODUCER_NAMESPACES) - set(NAMESPACE_DIRS)
    assert not missing, (
        f"namespaces without a declared producer scope: {sorted(missing)}. "
        "A namespace whose scope is undefined cannot be guarded for completeness."
    )


def test_no_namespace_is_declared_without_being_registered():
    extra = set(NAMESPACE_DIRS) - set(PRODUCER_NAMESPACES)
    assert not extra, f"scope declared for unregistered namespaces: {sorted(extra)}"


@pytest.mark.parametrize("namespace", sorted(NAMESPACE_DIRS))
def test_each_declared_scope_exists_on_disk(namespace: str):
    target = SRC / NAMESPACE_DIRS[namespace]
    assert target.exists(), f"{namespace}: declared scope {target} does not exist"


def test_phase_boundary_ratchet_no_producers_are_registered_yet():
    """A PHASE-BOUNDARY RATCHET, not a placeholder.

    It states a fact that is true in Plan 1 and false the instant Plan 2 registers its
    first producer: at that moment the tree goes red, and the only correct way to make
    it green is to write design test 29 -- the real discovery-versus-registration
    comparison -- IN THE SAME COMMIT that registers the producer.

    Deleting it is not the correct response. Replacing it is. A commit that removes
    this and adds no equality guard has moved the codebase from "cannot check
    completeness" to "does not check completeness" while turning the tree green, which
    is the exact substitution this ratchet exists to make impossible.
    """
    from science_tool.findings.cli import _registry

    assert not _registry().producers_by_id, (
        "producers are now registered, so design test 29 (producer-namespace "
        "completeness) can and must be written: compare the modules discovered under "
        "each NAMESPACE_DIRS entry against the registered producers, and REPLACE this "
        "ratchet with that comparison in this same commit."
    )
