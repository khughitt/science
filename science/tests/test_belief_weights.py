from science_tool.graph import belief_weights as bw


def test_normalization_handles_evidence_suffix():
    assert bw.normalize_evidence_type("empirical_data_evidence") == "empirical_data"
    assert bw.normalize_evidence_type("empirical_data") == "empirical_data"
    assert bw.normalize_evidence_type(None) == ""


def test_type_ordering_via_rank():
    def rank(value):
        return bw.EVIDENCE_TYPE_RANK.get(bw.normalize_evidence_type(value), 0)

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


def test_steps_are_rank_minus_one_floored_at_zero():
    from science_tool.graph.belief_weights import role_steps, strength_steps, type_steps
    assert type_steps("empirical_data_evidence") == 3   # rank 4 normalized - 1
    assert type_steps("literature") == 1                # rank 2 - 1
    assert role_steps("direct_test") == 2               # rank 3 - 1
    assert role_steps("background_constraint") == 0     # rank 1 - 1
    assert strength_steps("strong") == 2
    assert strength_steps("weak") == 0
    # Unknown / missing -> 0 (graceful), never negative
    assert type_steps("nonsense") == 0
    assert role_steps(None) == 0
    assert strength_steps("") == 0


def test_magnitude_names_reconcile_with_enum():
    from science_tool.graph.belief import BeliefMagnitude
    from science_tool.graph.belief_weights import MAGNITUDE_NAMES

    # MAGNITUDE_NAMES is the cycle-free home for the magnitude strings (belief_weights
    # imports nothing internal); it must stay in lock-step with the BeliefMagnitude enum.
    assert set(MAGNITUDE_NAMES) == {m.value for m in BeliefMagnitude}
    # Ordering matches the ordinal ladder used by aggregate_belief.
    assert MAGNITUDE_NAMES == ("speculative", "fragile", "supported", "well_supported")


def test_phase2_constants_present():
    from science_tool.graph import belief_weights as bw
    assert bw.PROXY_STEP_PENALTY == 2
    assert bw.CURATION_STEP_PENALTY == 1
    assert bw.DELTA_ENVELOPE == (0.3, 1.0)
    assert bw.CONFIG_VERSION == "belief-logodds-v3"
