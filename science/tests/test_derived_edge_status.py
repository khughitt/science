from science_tool.graph.derived_status import derived_edge_status


def test_eliminated_wins():
    s = derived_edge_status(belief_magnitude="well_supported", refuted=True, claim_layer="causal_effect",
                            has_grounding_evidence=True)
    assert s.status == "eliminated"


def test_ungrounded_structural_is_unknown_not_structural():
    s = derived_edge_status(belief_magnitude="speculative", refuted=False, claim_layer="structural_claim",
                            has_grounding_evidence=False)
    assert s.status == "unknown"            # unknown ordered BEFORE structural


def test_grounded_structural_is_structural():
    s = derived_edge_status(belief_magnitude="supported", refuted=False, claim_layer="structural_claim",
                            has_grounding_evidence=True)
    assert s.status == "structural"


def test_supported_and_tentative_bands():
    assert derived_edge_status(belief_magnitude="supported", refuted=False, claim_layer="causal_effect",
                               has_grounding_evidence=True).status == "supported"
    assert derived_edge_status(belief_magnitude="well_supported", refuted=False, claim_layer="causal_effect",
                               has_grounding_evidence=True).status == "supported"
    assert derived_edge_status(belief_magnitude="fragile", refuted=False, claim_layer="causal_effect",
                               has_grounding_evidence=True).status == "tentative"


def test_reason_records_which_rule_fired():
    assert derived_edge_status(belief_magnitude="well_supported", refuted=True, claim_layer="causal_effect",
                               has_grounding_evidence=True).reason  # non-empty, names the rule
