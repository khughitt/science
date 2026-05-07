"""Tests for chain-audit entity models (StructuralChain, ChainAudit, BayesFactorEvidence)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from science_model.entities import (
    BayesFactorEvidence,
    ChainAuditEntity,
    ChainAuditInterpretation,
    StructuralChainEntity,
)


class TestBayesFactorEvidence:
    def test_public_api_exports(self):
        from science_model import BayesFactorEvidence as ExportedBayesFactorEvidence
        from science_model import ChainAuditEntity as ExportedChainAuditEntity
        from science_model import ChainAuditInterpretation as ExportedChainAuditInterpretation
        from science_model import StructuralChainEntity as ExportedStructuralChainEntity

        assert ExportedBayesFactorEvidence is BayesFactorEvidence
        assert ExportedChainAuditEntity is ChainAuditEntity
        assert ExportedChainAuditInterpretation is ChainAuditInterpretation
        assert ExportedStructuralChainEntity is StructuralChainEntity

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


def _chain_kwargs(**overrides: Any) -> dict[str, Any]:
    """Common required fields for a structural-chain instance."""
    base: dict[str, Any] = dict(
        id="chain:fp",
        canonical_id="natural-systems/chain:fp",
        kind="structural-chain",
        title="FP chain",
        project="natural-systems",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="core/chains/fp.md",
        chain=["mechanism:a", "mechanism:b", "mechanism:c"],
    )
    base.update(overrides)
    return base


class TestStructuralChainEntity:
    def test_minimal_three_link(self):
        entity = StructuralChainEntity(**_chain_kwargs())
        assert entity.kind == "structural-chain"
        assert len(entity.chain) == 3

    def test_two_links_minimum_accepted(self):
        entity = StructuralChainEntity(**_chain_kwargs(chain=["mechanism:a", "mechanism:b"]))
        assert len(entity.chain) == 2

    def test_rejects_single_link(self):
        with pytest.raises(ValidationError):
            StructuralChainEntity(**_chain_kwargs(chain=["mechanism:a"]))

    def test_rejects_empty_chain(self):
        with pytest.raises(ValidationError):
            StructuralChainEntity(**_chain_kwargs(chain=[]))

    def test_rejects_duplicate_links(self):
        with pytest.raises(ValidationError):
            StructuralChainEntity(**_chain_kwargs(chain=["mechanism:a", "mechanism:b", "mechanism:a"]))

    def test_title_required(self):
        # Entity.title is required at the base class; missing it should ValidationError.
        kwargs = _chain_kwargs()
        del kwargs["title"]
        with pytest.raises(ValidationError):
            StructuralChainEntity(**kwargs)


def _audit_kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = dict(
        id="chain-audit:fp-2026-05",
        canonical_id="natural-systems/chain-audit:fp-2026-05",
        kind="chain-audit",
        title="FP coupling audit (2026-05)",
        project="natural-systems",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="doc/audits/fp-2026-05.md",
        audits="chain:fp",
        proposition_refs=[],
        bayes_factor_evidence=BayesFactorEvidence(
            hypothesis_ref="hypothesis:fp-coupling",
            null_baseline="uniform random link substitution",
            interpretation=ChainAuditInterpretation.EVIDENCE_AGAINST,
        ),
        verdict={
            "composite": "[-]",
            "rule": "single-claim",
            "claims": [
                {
                    "id": "claim:fp-coupling-load-bearing",
                    "polarity": "[-]",
                    "strength": "load-bearing",
                    "evidence_summary": "Removing FP eliminates the coupling.",
                }
            ],
        },
    )
    base.update(overrides)
    return base


class TestChainAuditEntity:
    def test_minimal_audit(self):
        entity = ChainAuditEntity(**_audit_kwargs())
        assert entity.audits == "chain:fp"
        assert entity.bayes_factor_evidence.interpretation == "evidence-against"

    def test_audits_required(self):
        kwargs = _audit_kwargs()
        del kwargs["audits"]
        with pytest.raises(ValidationError):
            ChainAuditEntity(**kwargs)

    def test_bayes_factor_evidence_required(self):
        kwargs = _audit_kwargs()
        del kwargs["bayes_factor_evidence"]
        with pytest.raises(ValidationError):
            ChainAuditEntity(**kwargs)

    def test_verdict_required(self):
        kwargs = _audit_kwargs()
        del kwargs["verdict"]
        with pytest.raises(ValidationError):
            ChainAuditEntity(**kwargs)

    def test_verdict_bf_consistency_evidence_for_maps_to_positive(self):
        bf = BayesFactorEvidence(
            hypothesis_ref="hypothesis:fp-coupling",
            null_baseline="uniform",
            interpretation=ChainAuditInterpretation.EVIDENCE_FOR,
        )
        verdict = {
            "composite": "[+]",
            "rule": "single-claim",
            "claims": [{"id": "claim:x", "polarity": "[+]"}],
        }
        entity = ChainAuditEntity(**_audit_kwargs(bayes_factor_evidence=bf, verdict=verdict))
        assert entity.verdict["composite"] == "[+]"

    def test_verdict_bf_consistency_mismatch_rejected(self):
        # interpretation: evidence-against -> expected composite [-]; but verdict says [+].
        verdict = {
            "composite": "[+]",
            "rule": "single-claim",
            "claims": [{"id": "claim:x", "polarity": "[+]"}],
        }
        with pytest.raises(ValidationError) as excinfo:
            ChainAuditEntity(**_audit_kwargs(verdict=verdict))
        assert "interpretation" in str(excinfo.value).lower() or "composite" in str(excinfo.value).lower()

    def test_verdict_bf_consistency_full_mapping(self):
        cases = [
            (ChainAuditInterpretation.EVIDENCE_FOR, "[+]"),
            (ChainAuditInterpretation.EVIDENCE_AGAINST, "[-]"),
            (ChainAuditInterpretation.MIXED, "[~]"),
            (ChainAuditInterpretation.INCONCLUSIVE, "[?]"),
        ]
        for interp, token in cases:
            bf = BayesFactorEvidence(
                hypothesis_ref="hypothesis:fp-coupling",
                null_baseline="uniform",
                interpretation=interp,
            )
            verdict = {
                "composite": token,
                "rule": "single-claim",
                "claims": [{"id": "claim:x", "polarity": token}],
            }
            entity = ChainAuditEntity(**_audit_kwargs(bayes_factor_evidence=bf, verdict=verdict))
            assert entity.verdict["composite"] == token
