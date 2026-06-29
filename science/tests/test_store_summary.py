from science_tool.graph.store.summary import is_empirical_evidence_type


def test_is_empirical_evidence_type_canonical():
    assert is_empirical_evidence_type("empirical_data")
    assert is_empirical_evidence_type("benchmark")


def test_is_empirical_evidence_type_suffixed():
    assert is_empirical_evidence_type("empirical_data_evidence")
    assert is_empirical_evidence_type("benchmark_evidence")


def test_is_empirical_evidence_type_negatives():
    assert not is_empirical_evidence_type("literature")
    assert not is_empirical_evidence_type("simulation_evidence")
    assert not is_empirical_evidence_type("expert_judgment")
    assert not is_empirical_evidence_type("")
