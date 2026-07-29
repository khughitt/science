"""Which profiles have a probe battery, and which are debt.

Task 2 established that hypothesis is value-reconciled at BOTH generations by running its battery
against each. This file states which kinds have a battery at all, so a newly declared mixin cannot
arrive with no probe values and no failing test.

☠️ The declaration is `VALUE_RECONCILED_KINDS` -- a set of KINDS. The pending PROFILE set is
derived from it. Declaring profiles directly would restate membership the profile table already
determines, and a hand-written declaration is only appropriate where it records a judgment that
cannot be derived.
"""

from __future__ import annotations

from science_model.entity_schema.profile import _MIXIN_VERSION_BY_GENERATION

# Kinds with an authored probe battery. `hypothesis` is `test_hypothesis_entity.py`, whose
# `_BATTERY` covers all 27 of its shared fields and runs against every hypothesis profile;
# `concept` is `test_concept_entity.py`, 13 shared fields against both profiles.
# S1b adds the four COMMONS kinds below; each addition is ~20-27 fields of hand-authored probe
# values, and a name may only be added here once that file exists and passes.
#
# `concept` was not one of S1b's four. A schema-closure slice declares a new project mixin, so
# it owes its battery in the same branch that arms the kind -- deferring it would put a closed
# kind in `PENDING_PROFILES`, which is the debt list for mixins that exist but enforce nothing.
# `method` is the second schema-closure slice, same rule: `test_method_entity.py`, 17 shared
# fields against both profiles. It is the only one of these whose shared surface is computed
# against a TYPED subclass (`MethodEntity`) rather than the generic `ProjectEntity`.
VALUE_RECONCILED_KINDS = frozenset({"hypothesis", "concept", "method"})

# The exact remainder, frozen. This is a RATCHET, not a target: it must SHRINK deliberately as
# S1b authors batteries, and any growth means a mixin was declared without anyone classifying it.
PENDING_PROFILES = frozenset(
    {
        (2, "dataset"), (3, "dataset"),
        (2, "paper"), (3, "paper"),
        (2, "theme"), (3, "theme"),
        (2, "topic"), (3, "topic"),
    }
)


def _profiles() -> frozenset[tuple[int, str]]:
    return frozenset(
        (generation, kind)
        for generation, kinds in _MIXIN_VERSION_BY_GENERATION.items()
        for kind in kinds
    )


def test_the_declared_kinds_are_all_real_mixin_kinds() -> None:
    # A battery for a kind with no mixin reconciles nothing against nothing.
    unknown = VALUE_RECONCILED_KINDS - {kind for _, kind in _profiles()}
    assert not unknown, f"declared value-reconciled, but no mixin declares them: {sorted(unknown)}"


def test_pending_profiles_is_exactly_the_underived_remainder() -> None:
    # Both directions. A newly declared mixin or generation lands in `derived` and fails here
    # until someone either authors a battery or records the debt -- it cannot arrive silently.
    derived = frozenset(p for p in _profiles() if p[1] not in VALUE_RECONCILED_KINDS)
    assert PENDING_PROFILES == derived, (
        f"unclassified: {sorted(derived - PENDING_PROFILES)}; "
        f"stale: {sorted(PENDING_PROFILES - derived)}"
    )


def test_the_reconciled_profiles_are_the_complement() -> None:
    reconciled = _profiles() - PENDING_PROFILES
    assert reconciled == frozenset(
        {
            (2, "hypothesis"), (3, "hypothesis"),
            (2, "concept"), (3, "concept"),
            (2, "method"), (3, "method"),
        }
    ), (
        f"value-reconciled profiles are {sorted(reconciled)}; "
        f"expected both generations of hypothesis, concept and method, and nothing else"
    )
