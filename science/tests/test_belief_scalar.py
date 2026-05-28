import math

from science_tool.graph.belief import EvidenceUnit, aggregate_belief
from science_tool.graph.belief_scalar import BeliefScalar, belief_scalar, unit_score


def _u(stance="supports", **kw):
    base = dict(line_uri="x", stance=stance, strength="strong", independence="independent",
                independence_group="g", evidence_role="direct_test",
                evidence_type="empirical_data_evidence", dispute_scope=None,
                proxy_directness=None, has_measurement_model=False, source=None,
                observability_keys=())
    base.update(kw)
    return EvidenceUnit(**base)


def _r6(x):
    return round(x, 6)


def test_unit_score_is_sum_of_steps():
    assert unit_score(_u()) == 7                      # 3 (empirical) + 2 (direct) + 2 (strong)
    assert unit_score(_u(evidence_role="background_constraint", strength="weak",
                         evidence_type="literature")) == 1   # 1 + 0 + 0


def test_proxy_gate_lowers_score_by_two():
    gated = _u(proxy_directness="indirect", has_measurement_model=False)  # is_proxy_gated -> True
    assert unit_score(gated) == 5                     # 7 - 2


def test_single_support_band_matches_tanh():
    r = aggregate_belief([_u(line_uri="a", independence_group="g1")])     # S=7, D=0
    s = belief_scalar(r)
    assert s.massed_support_score == 7 and s.massed_dispute_score == 0
    assert s.massed_support_band == (_r6(math.tanh(0.5 * 0.3 * 7)), _r6(math.tanh(0.5 * 1.0 * 7)))
    assert s.net_band == s.massed_support_band         # D=0 -> net == support
    assert s.net_robust is True


def test_balanced_evidence_is_not_net_robust():
    # Comparable support and dispute mass -> the adversarial corners straddle 0.
    r = aggregate_belief([
        _u(line_uri="a", independence_group="g1", evidence_role="proxy_support"),
        _u(line_uri="b", independence_group="g2", evidence_role="proxy_support"),
        _u(stance="disputes", line_uri="d", independence_group="g3",
           dispute_scope="mechanism", strength="moderate"),
    ])
    s = belief_scalar(r)
    assert s.net_band[0] < 0 < s.net_band[1]
    assert s.net_robust is False


def test_diagnostic_dispute_excluded_from_mass_but_counted():
    # model_criticism dispute is diagnostic: D=0, but contested + diagnostic_dispute_count=1
    r = aggregate_belief([
        _u(line_uri="yang", independence_group="g1"),
        _u(stance="disputes", line_uri="simeonov", independence_group="g2",
           evidence_role="model_criticism", dispute_scope="generalization"),
    ])
    s = belief_scalar(r)
    assert s.massed_dispute_score == 0
    assert s.diagnostic_dispute_count == 1
    assert s.contested is True
    assert isinstance(s, BeliefScalar)


def _decisions(root, body):
    (root / "core").mkdir(parents=True, exist_ok=True)
    (root / "core" / "decisions.md").write_text(body, encoding="utf-8")


def test_belief_scalar_enabled_true_when_active_flag(tmp_path):
    from science_tool.graph.belief_scalar import belief_scalar_enabled
    _decisions(tmp_path, "# Decisions\n\n## D-014: Enable scalar\n"
                         "- **Status:** active\n- **Feature flag:** belief-scalar\n")
    assert belief_scalar_enabled(tmp_path) is True


def test_belief_scalar_enabled_false_when_superseded(tmp_path):
    from science_tool.graph.belief_scalar import belief_scalar_enabled
    _decisions(tmp_path, "# Decisions\n\n## D-014: Enable scalar\n"
                         "- **Status:** superseded\n- **Feature flag:** belief-scalar\n")
    assert belief_scalar_enabled(tmp_path) is False


def test_belief_scalar_enabled_false_when_no_flag(tmp_path):
    from science_tool.graph.belief_scalar import belief_scalar_enabled
    _decisions(tmp_path, "# Decisions\n\n## D-001: Other\n- **Status:** active\n- **Decision:** x\n")
    assert belief_scalar_enabled(tmp_path) is False
    assert belief_scalar_enabled(tmp_path / "no-project") is False


def test_format_belief_weight_suppresses_net_for_fragile():
    from science_tool.graph.belief_scalar import belief_scalar, format_belief_weight
    r = aggregate_belief([_u(line_uri="a", independence_group="g1")])   # single -> fragile
    bw = format_belief_weight(r, belief_scalar(r))
    assert bw["net"] is None
    assert "single-unit ceiling applies" in bw["notes"]
    assert bw["massed_support"] == list(belief_scalar(r).massed_support_band)


def test_format_belief_weight_shows_net_when_robust_and_supported():
    from science_tool.graph.belief_scalar import belief_scalar, format_belief_weight
    r = aggregate_belief([_u(line_uri="a", independence_group="g1"),
                          _u(line_uri="b", independence_group="g2")])   # well_supported
    s = belief_scalar(r)
    bw = format_belief_weight(r, s)
    assert bw["net"] == list(s.net_band)
    assert bw["notes"] == []


def test_format_belief_weight_diagnostic_caveat():
    from science_tool.graph.belief_scalar import belief_scalar, format_belief_weight
    r = aggregate_belief([
        _u(line_uri="a", independence_group="g1"),
        _u(line_uri="b", independence_group="g2"),
        _u(stance="disputes", line_uri="c", independence_group="g3",
           evidence_role="model_criticism", dispute_scope="generalization"),
    ])
    bw = format_belief_weight(r, belief_scalar(r))
    assert "contested (diagnostic)" in bw["notes"]


def test_reference_dataset_lowers_score_by_one():
    assert unit_score(_u(is_reference_dataset=True)) == 6           # 7 - 1
    # floored at zero, and never negative even with a minimal unit:
    assert unit_score(_u(evidence_role="background_constraint", strength="weak",
                         evidence_type="literature", is_reference_dataset=True)) == 0   # 1 - 1


def test_proxy_and_curation_penalties_stack():
    gated_ref = _u(proxy_directness="indirect", has_measurement_model=False,
                   is_reference_dataset=True)
    assert unit_score(gated_ref) == 4                               # 7 - 2 - 1
