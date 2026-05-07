"""Tests for chain-audit entity models (StructuralChain, ChainAudit, BayesFactorEvidence)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_model.entities import BayesFactorEvidence, ChainAuditInterpretation


class TestBayesFactorEvidence:
    def test_public_api_exports(self):
        from science_model import BayesFactorEvidence as ExportedBayesFactorEvidence
        from science_model import ChainAuditInterpretation as ExportedChainAuditInterpretation

        assert ExportedBayesFactorEvidence is BayesFactorEvidence
        assert ExportedChainAuditInterpretation is ChainAuditInterpretation

    def test_interpretation_values_are_exact(self):
        assert {interpretation.value for interpretation in ChainAuditInterpretation} == {
            "evidence-for",
            "evidence-against",
            "mixed",
            "inconclusive",
        }

    def test_minimal_evidence_for(self):
        bf = BayesFactorEvidence(
            hypothesis_ref="hypothesis:foo",
            null_baseline="uniform random link substitution",
            interpretation=ChainAuditInterpretation.EVIDENCE_FOR,
        )
        assert bf.bf10 is None
        assert bf.interpretation is ChainAuditInterpretation.EVIDENCE_FOR

    def test_accepts_all_four_interpretations(self):
        for interp in ChainAuditInterpretation:
            bf = BayesFactorEvidence(
                hypothesis_ref="hypothesis:foo",
                null_baseline="uniform",
                interpretation=interp,
            )
            assert bf.interpretation is interp

    def test_coerces_raw_string_interpretation(self):
        bf = BayesFactorEvidence.model_validate(
            {
                "hypothesis_ref": "hypothesis:foo",
                "null_baseline": "uniform",
                "interpretation": "evidence-for",
            }
        )
        assert bf.interpretation is ChainAuditInterpretation.EVIDENCE_FOR

    def test_rejects_evidence_for_risk(self):
        # evidence-for-risk is intentionally dropped from chain-audit's enum
        # (t037-specific risk framing has no clean predicted-direction-agnostic mapping).
        with pytest.raises(ValidationError):
            BayesFactorEvidence.model_validate(
                {
                    "hypothesis_ref": "hypothesis:foo",
                    "null_baseline": "uniform",
                    "interpretation": "evidence-for-risk",
                }
            )

    def test_rejects_unknown_interpretation(self):
        with pytest.raises(ValidationError):
            BayesFactorEvidence.model_validate(
                {
                    "hypothesis_ref": "hypothesis:foo",
                    "null_baseline": "uniform",
                    "interpretation": "bogus",
                }
            )

    def test_bf10_optional(self):
        bf = BayesFactorEvidence(
            hypothesis_ref="hypothesis:foo",
            null_baseline="uniform",
            interpretation=ChainAuditInterpretation.EVIDENCE_FOR,
            bf10=3.5,
        )
        assert bf.bf10 == 3.5

    def test_rejects_non_positive_bf10(self):
        with pytest.raises(ValidationError):
            BayesFactorEvidence(
                hypothesis_ref="hypothesis:foo",
                null_baseline="uniform",
                interpretation=ChainAuditInterpretation.EVIDENCE_FOR,
                bf10=0.0,
            )
        with pytest.raises(ValidationError):
            BayesFactorEvidence(
                hypothesis_ref="hypothesis:foo",
                null_baseline="uniform",
                interpretation=ChainAuditInterpretation.EVIDENCE_FOR,
                bf10=-1.0,
            )

    @pytest.mark.parametrize("null_baseline", ["", "   "])
    def test_rejects_empty_null_baseline(self, null_baseline):
        with pytest.raises(ValidationError):
            BayesFactorEvidence(
                hypothesis_ref="hypothesis:foo",
                null_baseline=null_baseline,
                interpretation=ChainAuditInterpretation.EVIDENCE_FOR,
            )
