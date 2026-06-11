# science/tests/test_bundle_belief_rollup.py
from __future__ import annotations

from science_tool.graph.belief import BeliefMagnitude, BeliefResult
from science_tool.graph.bundle_belief import (
    MemberBelief,
    member_rank_key,
    roll_up_weakest_link,
)
from science_model.reasoning import CompositionRule


def _belief(magnitude, *, contested=False, capped=False) -> BeliefResult:
    return BeliefResult(
        magnitude=magnitude, contested=contested, capped_by_refutation=capped,
        support_units=[], dispute_units=[], diagnostics=[],
        contested_groups=set(), excluded=[], flagged_ungrouped=[],
    )


def _member(uri, magnitude, *, contested=False, capped=False) -> MemberBelief:
    b = _belief(magnitude, contested=contested, capped=capped)
    return MemberBelief(
        member_uri=uri, belief=b, scalar=None,
        rank_key=member_rank_key(b, None, uri),
        reason=("speculative: no evidence" if magnitude == BeliefMagnitude.SPECULATIVE else None),
    )


def test_magnitude_is_weakest_member():
    members = [
        _member("p:a", BeliefMagnitude.WELL_SUPPORTED),
        _member("p:b", BeliefMagnitude.FRAGILE),
        _member("p:c", BeliefMagnitude.SUPPORTED),
    ]
    r = roll_up_weakest_link(members, rule=CompositionRule.ALL_STEPS)
    assert r.magnitude == BeliefMagnitude.FRAGILE
    assert r.bottleneck_members == ["p:b"]
    assert r.composition_rule == "all_steps"


def test_refutation_is_separate_axis_not_an_ordinal():
    # A refuted member is FRAGILE (capped); an unestablished member is SPECULATIVE.
    # Magnitude bottoms out at the speculative member; refutation is still flagged.
    members = [
        _member("p:refuted", BeliefMagnitude.FRAGILE, capped=True),
        _member("p:unestablished", BeliefMagnitude.SPECULATIVE),
    ]
    r = roll_up_weakest_link(members, rule=CompositionRule.ALL_STEPS)
    assert r.magnitude == BeliefMagnitude.SPECULATIVE       # unestablished < refuted
    assert r.bottleneck_members == ["p:unestablished"]
    assert r.capped_by_refutation is True                   # refutation still surfaced
    assert r.unresolved_members == ["p:unestablished"]


def test_contested_propagates_if_any_member_contested():
    members = [
        _member("p:a", BeliefMagnitude.SUPPORTED, contested=True),
        _member("p:b", BeliefMagnitude.SUPPORTED),
    ]
    r = roll_up_weakest_link(members, rule=CompositionRule.CONJUNCTIVE)
    assert r.contested is True
    assert r.contested_members == ["p:a"]


def test_rank_key_deterministic_without_scalar():
    # Same ordinal magnitude → tiebreak by member_uri (scalar None → 0.0 component).
    members = [
        _member("p:z", BeliefMagnitude.SUPPORTED),
        _member("p:a", BeliefMagnitude.SUPPORTED),
    ]
    r = roll_up_weakest_link(members, rule=CompositionRule.ALL_STEPS)
    assert [m.member_uri for m in r.member_results] == ["p:a", "p:z"]
    assert set(r.bottleneck_members) == {"p:a", "p:z"}  # both share the min ordinal
