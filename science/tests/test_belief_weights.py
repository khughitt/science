from science_tool.graph import belief_weights as bw


def test_normalization_handles_evidence_suffix():
    assert bw.normalize_evidence_type("empirical_data_evidence") == "empirical_data"
    assert bw.normalize_evidence_type("empirical_data") == "empirical_data"
    assert bw.normalize_evidence_type(None) == ""


def test_type_ordering_via_rank():
    rank = lambda v: bw.EVIDENCE_TYPE_RANK.get(bw.normalize_evidence_type(v), 0)
    assert rank("empirical_data_evidence") > rank("simulation_evidence")
    assert rank("simulation_evidence") == rank("benchmark_evidence")
    assert rank("simulation_evidence") > rank("literature_evidence")
    assert rank("literature_evidence") > rank("expert_judgment_evidence")


def test_role_and_strength_ordering():
    assert bw.EVIDENCE_ROLE_RANK["direct_test"] > bw.EVIDENCE_ROLE_RANK["proxy_support"]
    assert bw.EVIDENCE_ROLE_RANK["proxy_support"] > bw.EVIDENCE_ROLE_RANK["background_constraint"]
    assert bw.STRENGTH_RANK["strong"] > bw.STRENGTH_RANK["moderate"] > bw.STRENGTH_RANK["weak"]


def test_diagnostic_roles():
    assert {"model_criticism", "negative_control"} <= bw.DIAGNOSTIC_ROLES
    assert "direct_test" not in bw.DIAGNOSTIC_ROLES
