"""Explicit, versioned belief policy (patchwork kernel Spec 5, Slice A).

A `BeliefPolicy` bundles the previously-implicit ordinal aggregation knobs — rank
tables, the curation step penalty, the reduction/vocabulary constants, the
magnitude thresholds, and the refutation-cap conditions — into one frozen,
deeply-immutable object with a recorded identity. `DEFAULT_BELIEF_POLICY` is the
single built-in policy and is constructed FROM the `belief_weights` constants, so
there is one source of truth for the values and the default reproduces today's
`aggregate_belief` output exactly.

This module imports only `belief_weights` (which imports nothing internal), so it
sits below `belief.py` in the import graph — there is no cycle.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .belief_weights import (
    CIRCULAR, CURATION_STEP_PENALTY, DIAGNOSTIC_ROLES, EVIDENCE_ROLE_RANK,
    EVIDENCE_TYPE_RANK, GATED_PROXY, INDEPENDENT, ROLE_DIRECT_TEST,
    SCOPE_WHOLE_CLAIM, SHARED_SOURCE, STRENGTH_RANK,
)


@dataclass(frozen=True)
class BeliefPolicy:
    """An explicit, versioned, deeply-immutable belief-aggregation policy."""

    policy_id: str
    version: str
    # Ordinal scoring knobs (consumed by quality_key).
    evidence_type_rank: Mapping[str, int]
    evidence_role_rank: Mapping[str, int]
    strength_rank: Mapping[str, int]
    curation_step_penalty: int
    # Reduction / vocabulary constants.
    gated_proxy: frozenset[str]
    diagnostic_roles: frozenset[str]
    direct_test_role: str
    independent_token: str
    shared_source_token: str
    circular_token: str
    scope_whole_claim: str
    # Refutation-cap + magnitude-threshold knobs.
    decisive_strength: str
    well_supported_min_clean_support: int
    well_supported_requires_direct_test: bool

    def __post_init__(self) -> None:
        # A frozen dataclass does not stop a caller mutating a dict/set it was handed.
        # Deep-freeze the container fields into read-only Mappings and frozensets.
        object.__setattr__(self, "evidence_type_rank", MappingProxyType(dict(self.evidence_type_rank)))
        object.__setattr__(self, "evidence_role_rank", MappingProxyType(dict(self.evidence_role_rank)))
        object.__setattr__(self, "strength_rank", MappingProxyType(dict(self.strength_rank)))
        object.__setattr__(self, "gated_proxy", frozenset(self.gated_proxy))
        object.__setattr__(self, "diagnostic_roles", frozenset(self.diagnostic_roles))


DEFAULT_BELIEF_POLICY = BeliefPolicy(
    policy_id="core-default",
    version="1",
    evidence_type_rank=EVIDENCE_TYPE_RANK,
    evidence_role_rank=EVIDENCE_ROLE_RANK,
    strength_rank=STRENGTH_RANK,
    curation_step_penalty=CURATION_STEP_PENALTY,
    gated_proxy=GATED_PROXY,
    diagnostic_roles=DIAGNOSTIC_ROLES,
    direct_test_role=ROLE_DIRECT_TEST,
    independent_token=INDEPENDENT,
    shared_source_token=SHARED_SOURCE,
    circular_token=CIRCULAR,
    scope_whole_claim=SCOPE_WHOLE_CLAIM,
    decisive_strength="strong",
    well_supported_min_clean_support=2,
    well_supported_requires_direct_test=True,
)
