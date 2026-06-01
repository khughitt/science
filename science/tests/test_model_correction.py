"""Tests for the latent-construct measurement-model correction (science_tool.model.correction)."""
from __future__ import annotations

import math

import pytest

from science_tool.model.correction import (
    CorrectedAssociation,
    attention,
    is_specific,
    pmi,
    ppmi,
)


def test_pmi_subtracts_both_attention_axes():
    """PMI == log(C_ab/N) − α_a − β_b (both attention axes subtracted)."""
    cooc, ma, mb, n = 181.0, 13446.0, 53140.0, 392448605.0
    direct = pmi(cooc, ma, mb, n)
    decomposed = math.log(cooc / n) - attention(ma, n) - attention(mb, n)
    assert direct == pytest.approx(decomposed)
    assert direct > 0  # specific association: co-occurs more than attention predicts


def test_universal_pair_goes_negative():
    """A high-attention pair whose raw count is modest goes negative under correction."""
    # huge marginals, small observed count -> over-predicted by attention -> PMI < 0
    assert pmi(192.0, 4_975_675.0, 53_140.0, 392_448_605.0) < 0


def test_no_cooccurrence_has_no_pmi():
    assert pmi(0, 1000, 1000, 10_000) is None
    assert ppmi(0, 1000, 1000, 10_000) == 0.0


def test_ppmi_clips_negative_tail():
    assert ppmi(192.0, 4_975_675.0, 53_140.0, 392_448_605.0) == 0.0
    assert ppmi(181.0, 13446.0, 53140.0, 392448605.0) > 0.0


def test_is_specific():
    assert is_specific(0.5) and not is_specific(-0.1)
    assert not is_specific(0.0) and not is_specific(None)


def test_corrected_association_props():
    ca = CorrectedAssociation(key="g", raw_count=10, pmi=2.0)
    assert ca.ppmi == 2.0 and ca.specific
    neg = CorrectedAssociation(key="h", raw_count=10, pmi=-1.0)
    assert neg.ppmi == 0.0 and not neg.specific
    absent = CorrectedAssociation(key="z", raw_count=0, pmi=None)
    assert absent.ppmi == 0.0 and not absent.specific
