from types import MappingProxyType

import pytest

from science_tool.graph.belief_policy import BeliefPolicy, DEFAULT_BELIEF_POLICY
from science_tool.graph.belief_weights import (
    CURATION_STEP_PENALTY, DIAGNOSTIC_ROLES, EVIDENCE_ROLE_RANK,
    EVIDENCE_TYPE_RANK, GATED_PROXY, STRENGTH_RANK,
)


def test_default_policy_identity():
    assert DEFAULT_BELIEF_POLICY.policy_id == "core-default"
    assert DEFAULT_BELIEF_POLICY.version == "1"


def test_default_policy_values_match_belief_weights():
    p = DEFAULT_BELIEF_POLICY
    assert dict(p.evidence_type_rank) == EVIDENCE_TYPE_RANK
    assert dict(p.evidence_role_rank) == EVIDENCE_ROLE_RANK
    assert dict(p.strength_rank) == STRENGTH_RANK
    assert p.curation_step_penalty == CURATION_STEP_PENALTY
    assert p.gated_proxy == GATED_PROXY
    assert p.diagnostic_roles == DIAGNOSTIC_ROLES
    assert p.well_supported_min_clean_support == 2
    assert p.well_supported_requires_direct_test is True


def test_rank_tables_are_read_only_mappings():
    assert isinstance(DEFAULT_BELIEF_POLICY.evidence_type_rank, MappingProxyType)
    with pytest.raises(TypeError):
        DEFAULT_BELIEF_POLICY.evidence_type_rank["empirical_data"] = 99


def test_token_sets_are_frozen():
    assert isinstance(DEFAULT_BELIEF_POLICY.gated_proxy, frozenset)
    assert isinstance(DEFAULT_BELIEF_POLICY.diagnostic_roles, frozenset)


def test_constructor_normalizes_mutable_containers():
    p = BeliefPolicy(
        policy_id="x", version="1",
        evidence_type_rank={"a": 1}, evidence_role_rank={}, strength_rank={},
        curation_step_penalty=1, gated_proxy={"indirect"}, diagnostic_roles=set(),
        direct_test_role="direct_test", independent_token="independent",
        shared_source_token="shared-source", circular_token="circular",
        scope_whole_claim="whole_claim", decisive_strength="strong",
        well_supported_min_clean_support=2, well_supported_requires_direct_test=True,
    )
    assert isinstance(p.evidence_type_rank, MappingProxyType)
    assert isinstance(p.gated_proxy, frozenset)
    with pytest.raises(TypeError):
        p.evidence_type_rank["b"] = 2
