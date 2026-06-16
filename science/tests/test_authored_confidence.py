from science_tool.graph.belief import (
    EvidenceUnit,
    _authored_assertion_counts,
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
