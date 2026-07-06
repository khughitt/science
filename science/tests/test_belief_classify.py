from science_tool.graph.belief import EvidenceUnit, is_diagnostic, is_proxy_gated, is_qualifying_direct_test


def _u(**kw):
    base = dict(line_uri="x", stance="supports", strength="strong", independence="independent",
                independence_group="g", evidence_role="direct_test", evidence_type="empirical_data_evidence",
                dispute_scope=None, proxy_directness=None, has_measurement_model=False,
                source=None, observability_keys=())
    base.update(kw)
    return EvidenceUnit(**base)

def test_direct_test_qualifies():
    assert is_qualifying_direct_test(_u()) is True

def test_proxy_gate_blocks_ungated_proxy():
    assert is_proxy_gated(_u(proxy_directness="indirect")) is True
    assert is_qualifying_direct_test(_u(proxy_directness="indirect")) is False
    assert is_qualifying_direct_test(_u(proxy_directness="indirect", has_measurement_model=True)) is True

def test_model_criticism_is_diagnostic():
    assert is_diagnostic(_u(evidence_role="model_criticism")) is True
    assert is_diagnostic(_u(evidence_role="direct_test")) is False
