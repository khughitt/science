import pytest
from science_model.reasoning import CompositionRule

from science_tool.graph.belief import BeliefMagnitude, BeliefResult
from science_tool.graph.bundle_belief import (
    MemberBelief,
    MixedBeliefPolicyError,
    member_rank_key,
    roll_up_weakest_link,
)


def _result(mag, *, policy_id="core-default", policy_version="1") -> BeliefResult:
    return BeliefResult(
        magnitude=mag, contested=False, capped_by_refutation=False,
        support_units=[], dispute_units=[], diagnostics=[],
        contested_groups=set(), excluded=[], flagged_ungrouped=[],
        policy_id=policy_id, policy_version=policy_version,
    )


def _member(uri, result) -> MemberBelief:
    return MemberBelief(member_uri=uri, belief=result, scalar=None,
                        rank_key=member_rank_key(result, None, uri))


def test_rollup_stamps_shared_policy_identity():
    members = [_member("p:a", _result(BeliefMagnitude.SUPPORTED)),
               _member("p:b", _result(BeliefMagnitude.FRAGILE))]
    bundle = roll_up_weakest_link(members, rule=CompositionRule.CONJUNCTIVE)
    assert bundle.policy_id == "core-default"
    assert bundle.policy_version == "1"
    assert bundle.magnitude == BeliefMagnitude.FRAGILE  # weakest-link semantics unchanged


def test_rollup_rejects_mixed_policy_identities():
    members = [_member("p:a", _result(BeliefMagnitude.SUPPORTED, policy_id="core-default")),
               _member("p:b", _result(BeliefMagnitude.FRAGILE, policy_id="strict"))]
    with pytest.raises(MixedBeliefPolicyError):
        roll_up_weakest_link(members, rule=CompositionRule.CONJUNCTIVE)
