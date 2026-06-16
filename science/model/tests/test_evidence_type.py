"""Tests for EvidenceType vocabulary + suffix normalization."""
from __future__ import annotations

import pytest

from science_model.reasoning import EvidenceType, canonical_evidence_type_token


def test_evidence_type_members():
    assert {m.value for m in EvidenceType} == {
        "empirical_data", "benchmark", "simulation",
        "literature", "expert_judgment", "negative_result",
    }


@pytest.mark.parametrize("raw,expected", [
    ("empirical_data_evidence", "empirical_data"),
    ("empirical_data", "empirical_data"),
    ("simulation_evidence", "simulation"),
    ("expert_judgment", "expert_judgment"),        # no suffix -> unchanged
    ("expert_judgment_evidence", "expert_judgment"),
    ("negative_result", "negative_result"),
    ("differential_expression", "differential_expression"),  # unknown token passes through unchanged
])
def test_canonical_token_strips_suffix(raw, expected):
    assert canonical_evidence_type_token(raw) == expected


def test_canonical_token_none_passthrough():
    assert canonical_evidence_type_token(None) is None
