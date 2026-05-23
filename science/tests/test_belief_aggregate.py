from science_tool.graph.belief import EvidenceUnit, BeliefMagnitude, aggregate_belief

def _u(stance="supports", **kw):
    base = dict(line_uri="x", stance=stance, strength="strong", independence="independent",
                independence_group="g", evidence_role="direct_test", evidence_type="empirical_data_evidence",
                dispute_scope=None, proxy_directness=None, has_measurement_model=False,
                source=None, observability_keys=())
    base.update(kw); return EvidenceUnit(**base)

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
