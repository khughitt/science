"""Lineage capability: ONE declaration, and the surfaces that must agree with it.

`EntityKind.supersedable` answers "can an entity of this kind be replaced as canonical by a newer
one?" It is DECLARED per kind, never inferred. The status vocabulary, the `sci:supersedes` endpoint
list, and the auto-stamping policy are all gated against it by EXACT equality in both directions --
so a stale exemption fails as loudly as a new gap.

This file used to carry a SUBSET ratchet over `_KNOWN_HALF_WIRED`, a frozen allowlist of twelve
half-wired kinds. That ratchet was right while the debt existed -- exact equality would have made
repairing any one of the twelve fail the suite. S2 rules all fifteen affected kinds, so there is no
debt left to freeze and the assertions became equalities. Restoring a subset assertion here would
re-open the hole by construction.
"""

from __future__ import annotations

import pytest

from science_model.profiles.core import CORE_PROFILE
from science_model.profiles.local import LOCAL_PROFILE
from science_model.profiles.schema import EntityKind, RelationKind
from science_model.relations import relation_allows_kinds  # THE authoritative admission rule

def _supersedes() -> RelationKind:
    return next(r for r in CORE_PROFILE.relation_kinds if r.name == "supersedes")


def test_supersedes_description_names_spec_replacement() -> None:
    # The descriptor prose is part of the contract: a reader of the relation must learn that spec
    # replacement is valid, not only that spec appears in the endpoint lists.
    assert "spec" in _supersedes().description.lower()


SHIPPED_KINDS: tuple[EntityKind, ...] = (*CORE_PROFILE.entity_kinds, *LOCAL_PROFILE.entity_kinds)

# The authored ruling. Kept here, beside the gate, so a reader sees the population the gate is
# about without opening the profile -- and so a silent edit to the profile fails HERE.
SUPERSEDABLE_KINDS: frozenset[str] = frozenset(
    {
        "decision", "discussion", "finding", "hypothesis", "inquiry", "interpretation",
        "mechanism", "method", "plan", "proposition", "report", "spec", "story",
        "synthesis", "theme", "topic", "validation-report", "workflow-step",
    }
)


def test_the_supersedes_TARGETS_agree_with_the_declaration() -> None:
    # The OBJECT is the thing superseded, so it must be able to reach the state. The SUBJECT is the
    # replacement and is deliberately NOT gated -- a non-supersedable kind replacing a supersedable
    # one is legitimate.
    targets = {pair.target_kind for pair in _supersedes().allowed_kind_pairs}
    supersedable = {k.name for k in SHIPPED_KINDS if k.supersedable}
    assert targets == supersedable, (
        f"admissible target but not supersedable: {sorted(targets - supersedable)}; "
        f"supersedable but never an admissible target: {sorted(supersedable - targets)}"
    )


def test_the_supersedes_pairs_are_exactly_the_ruling() -> None:
    # This population is intentionally HAND-AUTHORED here, rather than read from core.py: the
    # endpoint rule is twelve self-only pairs plus the conclusion-level Cartesian ruling. Deriving
    # either half from production would make this check agree with an illegal cross-pair.
    conclusion_kinds = {
        "interpretation",
        "finding",
        "discussion",
        "report",
        "validation-report",
        "story",
    }
    self_superseding = SUPERSEDABLE_KINDS - conclusion_kinds
    expected_pairs = {(kind, kind) for kind in self_superseding} | {
        (source_kind, target_kind)
        for source_kind in conclusion_kinds
        for target_kind in conclusion_kinds
    }
    actual_pairs = {(pair.source_kind, pair.target_kind) for pair in _supersedes().allowed_kind_pairs}
    assert actual_pairs == expected_pairs, (
        f"unexpected pairs: {sorted(actual_pairs - expected_pairs)}; "
        f"missing pairs: {sorted(expected_pairs - actual_pairs)}"
    )


@pytest.mark.parametrize("kind", sorted(SUPERSEDABLE_KINDS))
def test_every_supersedable_kind_can_author_the_CANONICAL_edge(kind: str) -> None:
    # Asked through the AUTHORITATIVE helper. `source_kinds & target_kinds` is NOT the admission
    # rule when `allowed_kind_pairs` is present -- the pairs are a non-Cartesian allow-list, and a
    # check on the flat lists would keep agreeing right up until it didn't.
    assert relation_allows_kinds(_supersedes(), kind, kind)


@pytest.mark.parametrize(
    "relation", [r for r in CORE_PROFILE.relation_kinds if r.allowed_kind_pairs], ids=lambda r: r.name
)
def test_the_flat_endpoint_lists_agree_with_the_pairs(relation: RelationKind) -> None:
    # `allowed_kind_pairs` decides admission, but `source_kinds`/`target_kinds` remain the fallback
    # rule for relations declaring no pairs -- and agents read them. Editing only the pairs leaves
    # the flat projections contradicting the surface that decides.
    sources = {pair.source_kind for pair in relation.allowed_kind_pairs}
    targets = {pair.target_kind for pair in relation.allowed_kind_pairs}
    assert set(relation.source_kinds or ()) == sources, (
        f"{relation.name} source_kinds disagrees with its pairs: "
        f"listed only: {sorted(set(relation.source_kinds or ()) - sources)}; "
        f"paired only: {sorted(sources - set(relation.source_kinds or ()))}"
    )
    assert set(relation.target_kinds or ()) == targets, (
        f"{relation.name} target_kinds disagrees with its pairs: "
        f"listed only: {sorted(set(relation.target_kinds or ()) - targets)}; "
        f"paired only: {sorted(targets - set(relation.target_kinds or ()))}"
    )


@pytest.mark.parametrize("kind", SHIPPED_KINDS, ids=lambda k: k.name)
def test_every_shipped_kind_DECLARES_supersedable(kind: EntityKind) -> None:
    # `model_fields_set` -- not the value. The field defaults to False so a project-authored
    # manifest kind stays inert, which means a shipped kind that simply FORGOT to declare would be
    # indistinguishable from one ruled non-supersedable. Presence is the only thing that separates
    # them, and kind 51 must not be able to arrive silently.
    assert "supersedable" in kind.model_fields_set, (
        f"{kind.name} does not declare `supersedable`; every shipped kind must rule explicitly"
    )


def test_the_declared_population_is_exactly_the_ruling() -> None:
    # Both directions. Adding a kind to the profile without ruling it, or leaving this manifest
    # naming a kind the profile no longer declares supersedable, both fail here.
    declared = {kind.name for kind in SHIPPED_KINDS if kind.supersedable}
    assert declared == SUPERSEDABLE_KINDS, (
        f"declared but not in the ruling: {sorted(declared - SUPERSEDABLE_KINDS)}; "
        f"ruled but not declared: {sorted(SUPERSEDABLE_KINDS - declared)}"
    )


def test_the_status_vocabulary_agrees_with_the_declaration() -> None:
    # The vocabulary is a HAND-AUTHORED declaration, not generated from `supersedable` -- which is
    # what makes this comparison non-vacuous. If `statuses` were derived, this test would be the
    # identity function.
    declares_status = {k.name for k in SHIPPED_KINDS if "superseded" in (k.statuses or ())}
    supersedable = {k.name for k in SHIPPED_KINDS if k.supersedable}
    assert declares_status == supersedable, (
        f"declares `superseded` but is not supersedable: {sorted(declares_status - supersedable)}; "
        f"supersedable but cannot reach the state: {sorted(supersedable - declares_status)}"
    )
