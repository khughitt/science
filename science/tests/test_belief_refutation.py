from science_tool.graph.belief import EvidenceUnit, is_decisive_refutation


def _d(**kw):
    base = dict(line_uri="x", stance="disputes", strength="strong", independence="independent",
                independence_group="g", evidence_role="direct_test", evidence_type="empirical_data_evidence",
                dispute_scope="whole_claim", proxy_directness=None, has_measurement_model=False,
                source=None, observability_keys=())
    base.update(kw); return EvidenceUnit(**base)


def test_whole_claim_direct_test_strong_is_decisive():
    assert is_decisive_refutation(_d()) is True


def test_scoped_or_criticism_or_weak_is_not_decisive():
    assert is_decisive_refutation(_d(dispute_scope="generalization")) is False
    assert is_decisive_refutation(_d(evidence_role="model_criticism")) is False
    assert is_decisive_refutation(_d(strength="moderate")) is False
    assert is_decisive_refutation(_d(independence="shared-source")) is False
    assert is_decisive_refutation(_d(proxy_directness="indirect")) is False  # ungated proxy (rule 5)


def test_unset_scope_defaults_to_whole_claim_decisive():
    assert is_decisive_refutation(_d(dispute_scope=None)) is True
