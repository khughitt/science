from dataclasses import replace

import pytest

from science_tool.graph.belief_policy import DEFAULT_BELIEF_POLICY


def test_default_policy_authored_knobs():
    assert DEFAULT_BELIEF_POLICY.authored_assertion_type == "expert_judgment"
    assert DEFAULT_BELIEF_POLICY.authored_min_confidence == 0.5
    assert DEFAULT_BELIEF_POLICY.authored_only_ceiling == "fragile"


def test_min_confidence_out_of_range_rejected():
    with pytest.raises(ValueError):
        replace(DEFAULT_BELIEF_POLICY, policy_id="bad", version="1", authored_min_confidence=1.5)
    with pytest.raises(ValueError):
        replace(DEFAULT_BELIEF_POLICY, policy_id="bad", version="1", authored_min_confidence=-0.1)


def test_unknown_ceiling_rejected():
    with pytest.raises(ValueError):
        replace(DEFAULT_BELIEF_POLICY, policy_id="bad", version="1", authored_only_ceiling="bogus")


def test_valid_ceiling_accepted():
    p = replace(DEFAULT_BELIEF_POLICY, policy_id="ok", version="1", authored_only_ceiling="supported")
    assert p.authored_only_ceiling == "supported"


def test_authored_knobs_immutable():
    with pytest.raises(Exception):
        DEFAULT_BELIEF_POLICY.authored_min_confidence = 0.9  # frozen dataclass
