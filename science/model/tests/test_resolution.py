"""The cross-record layer: does a lineage reference resolve to a real, LIVE, other entity?

The schema validates one record in isolation, so it cannot answer this. A PRESENT but DANGLING
`superseded_by:` satisfies the schema, closes the entity, and records no real reason for closing --
the hole in a subtler dress.

RESOLVE, then CHECK. Raw string membership (`ref not in known_ids`) is the wrong question and fails
in BOTH directions; the two ☠️ tests below are the two directions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from science_model.entity_schema.resolution import check_resolution


@dataclass(frozen=True)
class _Res:
    status: str
    canonical_id: str | None = None
    candidates: tuple[str, ...] = field(default_factory=tuple)


class _Targets:
    """A stand-in with ReferenceResolver's EXACT semantics: alias -> canonical, else unresolved.

    The real wiring passes the real `ReferenceResolver`. This exists so the unit tests can state
    each alias case in one line -- NOT so they can invent a different resolution rule. If the two
    ever disagree, the wiring test (`test_resolution_wiring.py`, real resolver, real corpus) is the
    authority.
    """

    def __init__(self, aliases: dict[str, str]) -> None:
        self._aliases = aliases

    def resolve(self, raw: str) -> _Res:
        canonical = self._aliases.get(raw)
        if canonical is None:
            return _Res(status="unresolved")
        return _Res(status="resolved", canonical_id=canonical)


# `0009` is an ALIAS of the live `0009-successor`; `0003-gone` resolves but is ARCHIVED.
TARGETS = _Targets(
    {
        "hypothesis:0001-x": "hypothesis:0001-x",
        "hypothesis:0002-y": "hypothesis:0002-y",
        "hypothesis:0009": "hypothesis:0009-successor",  # <- the alias
        "hypothesis:0009-successor": "hypothesis:0009-successor",
        "hypothesis:0003-gone": "hypothesis:0003-gone",  # <- resolves, but NOT live
        "hypothesis:x-alias": "hypothesis:0001-x",  # <- an alias OF the entity itself
    }
)
LIVE = {"hypothesis:0001-x", "hypothesis:0002-y", "hypothesis:0009-successor"}


def _check(entity: dict[str, object]):
    return check_resolution(entity, targets=TARGETS, live_hypotheses=LIVE)


def test_dangling_successor_is_caught() -> None:
    # The whole reason this module exists: the schema is satisfied, the entity is closed,
    # and the reason it closed does not exist.
    #
    # NOTE the assertions are on FIELDS. `check_resolution` returns `list[ResolutionViolation]`,
    # and `"9999-nope" in v[0]` is not a substring test on a Pydantic model: `__iter__` yields
    # (field_name, value) PAIRS, so the expression is simply False and the test would fail against a
    # CORRECT implementation. That is the cost of a typed carrier, and it is the point of one: the
    # violation's parts are addressable instead of buried in a sentence.
    v = _check(
        {"id": "hypothesis:0001-x", "status": "superseded", "superseded_by": "hypothesis:9999-nope"}
    )
    assert len(v) == 1
    assert v[0].entity_id == "hypothesis:0001-x"
    assert v[0].field == "superseded_by"
    assert v[0].ref == "hypothesis:9999-nope"


def test_resolving_successor_passes() -> None:
    assert (
        _check(
            {
                "id": "hypothesis:0001-x",
                "status": "superseded",
                "superseded_by": "hypothesis:0002-y",
            }
        )
        == []
    )


def test_a_LIVE_ALIAS_resolves_and_is_CLEAN() -> None:
    # ☠️ The case raw membership BLOCKS. `hypothesis:0009` is an alias of the live
    # `hypothesis:0009-successor`; it is a perfectly good successor, and `ref not in known_ids`
    # would have called it dangling and refused a CORRECT corpus.
    assert (
        _check(
            {"id": "hypothesis:0001-x", "status": "superseded", "superseded_by": "hypothesis:0009"}
        )
        == []
    )


def test_a_SELF_ALIAS_is_caught() -> None:
    # ☠️ The case raw `ref == entity_id` MISSES. `hypothesis:x-alias` is an alias OF
    # `hypothesis:0001-x`, so as a STRING it differs from the entity's id, resolves cleanly, and
    # sails through as a valid successor -- a closed loop, wearing the check's green.
    # Identity must be decided AFTER resolution, on canonical ids, on both sides.
    v = _check(
        {
            "id": "hypothesis:0001-x",
            "status": "superseded",
            "superseded_by": "hypothesis:x-alias",
        }
    )
    assert len(v) == 1
    assert "itself" in v[0].message


def test_an_ARCHIVED_target_RESOLVES_and_is_still_a_violation() -> None:
    # Resolution and liveness are TWO questions. `0003-gone` resolves perfectly -- and naming a
    # dead entity as the reason you closed is not a reason.
    v = _check(
        {
            "id": "hypothesis:0001-x",
            "status": "superseded",
            "superseded_by": "hypothesis:0003-gone",
        }
    )
    assert len(v) == 1
    assert "not a live hypothesis" in v[0].message


def test_resynthesized_into_is_a_LIST_and_every_member_must_resolve() -> None:
    # One good member does not discharge the list. A resolver that returned on first success --
    # or that reported the FIELD rather than the REF -- passes a suite that only counts findings.
    # The typed carrier is what lets this assert WHICH member dangled.
    v = _check(
        {
            "id": "hypothesis:0001-x",
            "status": "superseded",
            "resynthesized_into": ["hypothesis:0002-y", "hypothesis:9999-nope"],
        }
    )
    assert len(v) == 1
    assert v[0].field == "resynthesized_into"
    assert v[0].ref == "hypothesis:9999-nope"  # the BAD member, not the good one


def test_self_supersession_is_caught() -> None:
    # The literal spelling. Kept BESIDE the alias case above, not replaced by it: they fail
    # differently, and a check that catches one is not a check that catches the other.
    v = _check(
        {
            "id": "hypothesis:0002-y",
            "status": "superseded",
            "superseded_by": "hypothesis:0002-y",
        }
    )
    assert len(v) == 1
    assert v[0].entity_id == "hypothesis:0002-y"
    assert "itself" in v[0].message


def test_an_ARCHIVED_entity_has_NOTHING_to_resolve() -> None:
    # `archived` is NOT in `_TERMINALS_WITH_STRUCTURE` (design §7.4, corrected): the archive index
    # mints no record id, so there is nothing a ref could point at. It is discharged by
    # `closure_basis` -- which is SHAPE, and shape is the schema's. This module must not restate it.
    assert (
        _check(
            {
                "id": "hypothesis:0001-x",
                "status": "archived",
                "closure_basis": "folded into h5",
            }
        )
        == []
    )


def test_a_basis_closed_entity_needs_no_structure() -> None:
    assert (
        _check(
            {
                "id": "hypothesis:0001-x",
                "status": "superseded",
                "closure_basis": "folded into h5",
            }
        )
        == []
    )


def test_a_live_entity_is_not_checked() -> None:
    assert (
        check_resolution(
            {"id": "hypothesis:0001-x", "status": "active"}, targets=TARGETS, live_hypotheses=set()
        )
        == []
    )
