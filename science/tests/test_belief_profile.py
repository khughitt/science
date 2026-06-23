from science_tool.graph.store.summary import is_empirical_evidence_type


def test_profile_reuses_summary_empirical_type_semantics() -> None:
    assert is_empirical_evidence_type("empirical_data")
    assert is_empirical_evidence_type("empirical_data_evidence")
    assert is_empirical_evidence_type("benchmark")
    assert not is_empirical_evidence_type("literature")
