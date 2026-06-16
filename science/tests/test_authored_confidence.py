from science_tool.graph.belief import (
    BeliefMagnitude,
    EvidenceUnit,
    _authored_assertion_counts,
    aggregate_belief,
    is_authored_assertion,
)
from science_tool.graph.belief_policy import DEFAULT_BELIEF_POLICY


def _u(**kw) -> EvidenceUnit:
    base = dict(
        line_uri="a", stance="supports", strength=None, independence="independent",
        independence_group=None, evidence_role=None, evidence_type="expert_judgment",
        dispute_scope=None, proxy_directness=None, has_measurement_model=False,
        source=None, observability_keys=(), is_reference_dataset=False,
    )
    base.update(kw)
    return EvidenceUnit(**base)


def test_confidence_defaults_none():
    assert _u().confidence is None


def test_positional_constructor_still_builds():
    # 12 positional args (through observability_keys) — the historical call shape. Adding
    # confidence as the LAST field must not break it.
    u = EvidenceUnit("a", "supports", "medium", None, None, None, None, None, None, False, None, ())
    assert u.confidence is None


def test_is_authored_assertion_by_type():
    assert is_authored_assertion(_u(evidence_type="expert_judgment"))
    assert is_authored_assertion(_u(evidence_type="expert_judgment_evidence"))  # suffix normalized
    assert not is_authored_assertion(_u(evidence_type="empirical_data"))
    assert not is_authored_assertion(_u(evidence_type=None))


def test_gate_admits_at_or_above_threshold():
    assert _authored_assertion_counts(_u(confidence=0.5), policy=DEFAULT_BELIEF_POLICY)
    assert _authored_assertion_counts(_u(confidence=0.9), policy=DEFAULT_BELIEF_POLICY)


def test_gate_rejects_below_threshold_none_and_out_of_range():
    p = DEFAULT_BELIEF_POLICY
    assert not _authored_assertion_counts(_u(confidence=0.3), policy=p)
    assert not _authored_assertion_counts(_u(confidence=None), policy=p)
    assert not _authored_assertion_counts(_u(confidence=1.2), policy=p)   # range-rejected
    assert not _authored_assertion_counts(_u(confidence=-0.1), policy=p)  # range-rejected


def _empirical(**kw) -> EvidenceUnit:
    base = dict(
        line_uri="e", stance="supports", strength="strong", independence="independent",
        independence_group=None, evidence_role="direct_test", evidence_type="empirical_data",
        dispute_scope=None, proxy_directness=None, has_measurement_model=False,
        source=None, observability_keys=(), is_reference_dataset=False, confidence=None,
    )
    base.update(kw)
    return EvidenceUnit(**base)


def test_single_authored_assertion_is_fragile():
    r = aggregate_belief([_u(line_uri="a", confidence=0.9)])
    assert r.magnitude == BeliefMagnitude.FRAGILE
    assert r.authored_capped is False  # n_support==1 -> FRAGILE already; ceiling is a no-op


def test_two_authored_assertions_capped_to_fragile():
    r = aggregate_belief([_u(line_uri="a", confidence=0.9), _u(line_uri="b", confidence=0.9)])
    # Two clean supports would compute SUPPORTED; authored-only ceiling caps to FRAGILE.
    assert r.magnitude == BeliefMagnitude.FRAGILE
    assert r.authored_capped is True


def test_sub_threshold_authored_excluded_and_speculative():
    r = aggregate_belief([_u(line_uri="a", confidence=0.3)])
    assert r.magnitude == BeliefMagnitude.SPECULATIVE
    assert [u.line_uri for u in r.excluded_authored_confidence] == ["a"]
    assert r.support_units == []


def test_out_of_range_authored_excluded():
    r = aggregate_belief([_u(line_uri="a", confidence=1.2)])
    assert r.magnitude == BeliefMagnitude.SPECULATIVE
    assert [u.line_uri for u in r.excluded_authored_confidence] == ["a"]


def test_authored_corroborates_but_empirical_path_untouched():
    # Two clean empirical direct tests -> WELL_SUPPORTED; an authored assertion alongside
    # must NOT cap it (mixed support is not authored-only).
    units = [
        _empirical(line_uri="e1", independence_group="g1"),
        _empirical(line_uri="e2", independence_group="g2"),
        _u(line_uri="a", confidence=0.9),
    ]
    r = aggregate_belief(units)
    assert r.magnitude == BeliefMagnitude.WELL_SUPPORTED
    assert r.authored_capped is False


def test_authored_dispute_is_not_decisive_refutation():
    # An authored dispute with role=direct_test, strong, independent, whole_claim would be a
    # decisive refutation IF it were a qualifying direct test — refutation symmetry bars it.
    support = [
        _empirical(line_uri="e1", independence_group="g1"),
        _empirical(line_uri="e2", independence_group="g2"),
    ]
    authored_dispute = _u(
        line_uri="d", stance="disputes", strength="strong", evidence_role="direct_test",
        evidence_type="expert_judgment", confidence=0.9, dispute_scope="whole_claim",
    )
    r = aggregate_belief([*support, authored_dispute])
    assert r.capped_by_refutation is False        # authored dispute cannot decisively cap
    assert r.magnitude == BeliefMagnitude.WELL_SUPPORTED
    assert r.contested is True                     # but it IS recorded as a dispute


def test_gate_failing_authored_dispute_has_zero_downstream_effect():
    # A gate-failing authored dispute sharing a group must NOT reach reduce_units: contested,
    # contested_groups, winners and clean_support must equal the same scenario without it.
    base = [
        _empirical(line_uri="e1", independence_group="g1"),
        _empirical(line_uri="e2", independence_group="g2"),
    ]
    rejected = _u(
        line_uri="d", stance="disputes", evidence_type="expert_judgment",
        independence_group="g1", confidence=0.3,  # below threshold -> rejected
    )
    r_without = aggregate_belief(base)
    r_with = aggregate_belief([*base, rejected])
    assert r_with.magnitude == r_without.magnitude
    assert r_with.contested == r_without.contested
    assert r_with.contested_groups == r_without.contested_groups
    assert {u.line_uri for u in r_with.support_units} == {u.line_uri for u in r_without.support_units}
    assert [u.line_uri for u in r_with.excluded_authored_confidence] == ["d"]
