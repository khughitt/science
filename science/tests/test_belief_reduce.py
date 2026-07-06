from science_tool.graph.belief import EvidenceUnit, reduce_units


def _u(**kw):
    base = dict(line_uri="x", stance="supports", strength="moderate", independence="independent",
                independence_group=None, evidence_role="proxy_support", evidence_type="literature_evidence",
                dispute_scope=None, proxy_directness=None, has_measurement_model=False,
                source=None, observability_keys=())
    base.update(kw)
    return EvidenceUnit(**base)

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


def test_reference_unit_loses_winner_selection_tiebreak():
    # Two support units, same independence group, IDENTICAL type/role/strength; one rests on a
    # reference dataset. The curation discount is the least-significant quality_key component, so
    # the non-reference unit wins the tie and the reference unit is collapsed.
    ref = _u(line_uri="r", independence_group="g", stance="supports", is_reference_dataset=True)
    nonref = _u(line_uri="n", independence_group="g", stance="supports", is_reference_dataset=False)
    reduced = reduce_units([ref, nonref])
    kept_uris = {u.line_uri for u in reduced.kept}
    assert kept_uris == {"n"}                       # non-reference kept on the exact tie
    assert any(u.line_uri == "r" for u in reduced.collapsed)


def test_reference_penalty_is_tiebreaker_only_not_cross_tier():
    # The curation demotion is the LEAST-significant quality_key component, so a reference unit
    # that is strictly stronger on a higher tier (here strength) STILL wins — the penalty never
    # crosses type/role/strength.
    strong_ref = _u(line_uri="r", independence_group="g", stance="supports",
                    strength="strong", is_reference_dataset=True)
    weak_nonref = _u(line_uri="n", independence_group="g", stance="supports",
                     strength="moderate", is_reference_dataset=False)
    reduced = reduce_units([strong_ref, weak_nonref])
    assert {u.line_uri for u in reduced.kept} == {"r"}   # stronger reference unit still wins
