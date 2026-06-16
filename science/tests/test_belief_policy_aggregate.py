from dataclasses import replace

from science_tool.graph.belief import BeliefMagnitude, EvidenceUnit, aggregate_belief
from science_tool.graph.belief_policy import DEFAULT_BELIEF_POLICY


def _u(**kw) -> EvidenceUnit:
    base = dict(
        line_uri="a", stance="supports", strength="strong", independence="independent",
        independence_group="g1", evidence_role="direct_test", evidence_type="empirical_data",
        dispute_scope=None, proxy_directness=None, has_measurement_model=False,
        source=None, observability_keys=(), is_reference_dataset=False,
    )
    base.update(kw)
    return EvidenceUnit(**base)


def _two_clean_direct_tests() -> list[EvidenceUnit]:
    return [_u(line_uri="a", independence_group="g1"), _u(line_uri="b", independence_group="g2")]


def test_result_is_stamped_with_default_policy():
    r = aggregate_belief([_u()])
    assert r.policy_id == "core-default"
    assert r.policy_version == "1"


def test_explicit_default_equals_implicit_default():
    units = _two_clean_direct_tests()
    assert aggregate_belief(units) == aggregate_belief(units, policy=DEFAULT_BELIEF_POLICY)


def test_default_two_clean_direct_tests_is_well_supported():
    assert aggregate_belief(_two_clean_direct_tests()).magnitude == BeliefMagnitude.WELL_SUPPORTED


def test_seam_proof_raising_min_clean_support_demotes_to_supported():
    # A stricter policy that demands 3 clean supports must demote the SAME unit set
    # from well_supported to supported — proving the knob is actually read, not decorative.
    strict = replace(DEFAULT_BELIEF_POLICY, policy_id="strict", version="1",
                     well_supported_min_clean_support=3)
    units = _two_clean_direct_tests()
    assert aggregate_belief(units, policy=strict).magnitude == BeliefMagnitude.SUPPORTED
    assert aggregate_belief(units, policy=strict).policy_id == "strict"
