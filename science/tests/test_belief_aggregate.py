from science_tool.graph.belief import EvidenceUnit, BeliefMagnitude, aggregate_belief, reduce_units
from science_tool.graph.io import PROJECT_NS

def _u(stance="supports", **kw):
    base = dict(line_uri="x", stance=stance, strength="strong", independence="independent",
                independence_group="g", evidence_role="direct_test", evidence_type="empirical_data_evidence",
                dispute_scope=None, proxy_directness=None, has_measurement_model=False,
                source=None, observability_keys=())
    base.update(kw)
    return EvidenceUnit(**base)

def test_no_support_is_speculative():
    assert aggregate_belief([]).magnitude == BeliefMagnitude.SPECULATIVE

def test_single_unit_is_fragile():
    r = aggregate_belief([_u(line_uri="a", independence_group="g1")])
    assert r.magnitude == BeliefMagnitude.FRAGILE and r.contested is False

def test_two_independents_with_direct_test_is_well_supported():
    r = aggregate_belief([_u(line_uri="a", independence_group="g1"),
                          _u(line_uri="b", independence_group="g2")])
    assert r.magnitude == BeliefMagnitude.WELL_SUPPORTED

def test_two_independents_no_direct_test_is_supported():
    r = aggregate_belief([_u(line_uri="a", independence_group="g1", evidence_role="proxy_support"),
                          _u(line_uri="b", independence_group="g2", evidence_role="proxy_support")])
    assert r.magnitude == BeliefMagnitude.SUPPORTED

def test_contested_group_support_is_not_clean_corroboration():
    clean = _u(line_uri="a", independence_group="g1")
    sup_c = _u(line_uri="b", independence_group="g2")
    dis_c = _u(stance="disputes", line_uri="c", independence_group="g2", dispute_scope="mechanism")
    r = aggregate_belief([clean, sup_c, dis_c])
    assert r.contested is True
    assert r.magnitude in (BeliefMagnitude.FRAGILE, BeliefMagnitude.SUPPORTED)

def test_decisive_refutation_caps_below_supported_and_contests():
    r = aggregate_belief([
        _u(line_uri="a", independence_group="g1"),
        _u(line_uri="b", independence_group="g2"),
        _u(stance="disputes", line_uri="d", independence_group="g3", dispute_scope="whole_claim"),
    ])
    assert r.contested is True and r.capped_by_refutation is True
    assert r.magnitude == BeliefMagnitude.FRAGILE

def test_pilot_shape_fragile_contested_not_eliminated():
    support = _u(line_uri="yang", independence_group="kp-tracer")
    criticism = _u(stance="disputes", line_uri="simeonov", independence_group="macsgestalt",
                   evidence_role="model_criticism", dispute_scope="generalization")
    r = aggregate_belief([support, criticism])
    assert r.magnitude == BeliefMagnitude.FRAGILE
    assert r.contested is True and r.capped_by_refutation is False
    assert r.display() == "fragile (contested)"


def test_aggregate_belief_candidates_do_not_collapse_but_committed_records_do() -> None:
    ungrouped = [
        EvidenceUnit(str(PROJECT_NS["evidence-line/a"]), "supports", "medium", None, None, None, None, None, None, False, None, ()),
        EvidenceUnit(str(PROJECT_NS["evidence-line/b"]), "supports", "medium", None, None, None, None, None, None, False, None, ()),
    ]
    committed = [
        EvidenceUnit(str(PROJECT_NS["evidence-line/a"]), "supports", "medium", "shared-source", "dataset-derived:gtex-v8", None, None, None, None, False, None, ()),
        EvidenceUnit(str(PROJECT_NS["evidence-line/b"]), "supports", "medium", "shared-source", "dataset-derived:gtex-v8", None, None, None, None, False, None, ()),
    ]

    assert len(reduce_units(ungrouped).kept) == 2
    reduced = reduce_units(committed)
    assert len(reduced.kept) == 1
    assert len(reduced.collapsed) == 1


def test_base_magnitude_matches_inline_and_qa_failed_not_qualifying():
    from science_tool.graph.belief import (
        BeliefMagnitude, _base_magnitude, is_qualifying_direct_test,
    )
    from science_tool.graph.belief_policy import DEFAULT_BELIEF_POLICY as P

    def unit(group=None, role="direct_test", strength="strong", qa=()):
        from science_tool.graph.belief import EvidenceUnit
        return EvidenceUnit(line_uri=f"u{id(group)}{role}{strength}{qa}", stance="supports",
            strength=strength, independence="independent", independence_group=group,
            evidence_role=role, evidence_type="empirical_data", dispute_scope=None,
            proxy_directness=None, has_measurement_model=False, source=None,
            observability_keys=(), qa_failed_datasets=qa)

    two_clean = [unit(role="direct_test"), unit(role="proxy_support")]
    assert _base_magnitude(two_clean, set(), policy=P) == BeliefMagnitude.WELL_SUPPORTED

    # A QA-failed direct test is NOT a qualifying direct test.
    assert is_qualifying_direct_test(unit(qa=("dataset:bad",)), policy=P) is False
    assert is_qualifying_direct_test(unit(), policy=P) is True


def test_contested_groups_for_intersects_support_and_dispute_groups():
    from science_tool.graph.belief import EvidenceUnit, _contested_groups_for

    def u(stance, group):
        return EvidenceUnit(line_uri=f"{stance}-{group}", stance=stance, strength="strong",
            independence="independent", independence_group=group, evidence_role="direct_test",
            evidence_type="empirical_data", dispute_scope=None, proxy_directness=None,
            has_measurement_model=False, source=None, observability_keys=())

    support = [u("supports", "g1"), u("supports", "g2"), u("supports", None)]
    dispute = [u("disputes", "g1"), u("disputes", "g3")]
    assert _contested_groups_for(support, dispute) == {"g1"}   # only the shared group; None ignored
