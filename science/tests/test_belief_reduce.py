from science_tool.graph.belief import EvidenceUnit, reduce_units

def _u(**kw):
    base = dict(line_uri="x", stance="supports", strength="moderate", independence="independent",
                independence_group=None, evidence_role="proxy_support", evidence_type="literature_evidence",
                dispute_scope=None, proxy_directness=None, has_measurement_model=False,
                source=None, observability_keys=())
    base.update(kw); return EvidenceUnit(**base)

def test_same_stance_shared_source_collapses_to_strongest():
    weak = _u(line_uri="a", independence="shared-source", independence_group="g1", strength="weak")
    strong = _u(line_uri="b", independence="shared-source", independence_group="g1",
                strength="strong", evidence_type="empirical_data_evidence", evidence_role="direct_test")
    r = reduce_units([weak, strong])
    assert [u.line_uri for u in r.kept] == ["b"]
    assert len(r.collapsed) == 1
    assert r.contested_groups == set()

def test_circular_excluded_and_ungrouped_flagged():
    circ = _u(line_uri="c", independence="circular", independence_group="g1")
    ungrouped = _u(line_uri="d", independence="shared-source", independence_group=None)
    r = reduce_units([circ, ungrouped])
    assert r.kept == []
    assert [u.line_uri for u in r.excluded_circular] == ["c"]
    assert [u.line_uri for u in r.flagged_ungrouped] == ["d"]

def test_two_independents_survive():
    r = reduce_units([_u(line_uri="a", independence_group="g1"), _u(line_uri="b", independence_group="g2")])
    assert len(r.kept) == 2

def test_opposite_stance_same_group_both_kept_and_contested():
    sup = _u(line_uri="s", independence_group="g1", stance="supports")
    dis = _u(line_uri="d", independence_group="g1", stance="disputes")
    r = reduce_units([sup, dis])
    assert {u.line_uri for u in r.kept} == {"s", "d"}
    assert r.contested_groups == {"g1"}
