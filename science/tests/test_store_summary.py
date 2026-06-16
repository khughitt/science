from science_tool.graph.store.summary import _is_empirical_type


def test_is_empirical_type_canonical():
    assert _is_empirical_type("empirical_data")
    assert _is_empirical_type("benchmark")


def test_is_empirical_type_suffixed():
    assert _is_empirical_type("empirical_data_evidence")
    assert _is_empirical_type("benchmark_evidence")


def test_is_empirical_type_negatives():
    assert not _is_empirical_type("literature")
    assert not _is_empirical_type("simulation_evidence")
    assert not _is_empirical_type("expert_judgment")
    assert not _is_empirical_type("")
