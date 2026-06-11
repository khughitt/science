"""Task 3a: oriented posterior quantitative_result → scalar belief input.

A fitted posterior (beta + prob_sign) carried by an evidence-line shifts the
continuous massed_support/massed_dispute bands, ORIENTED by the target
proposition's authored polarity and the line stance, scaled by prob_sign. A
stance that contradicts the observed beta-sign fails loudly. The ordinal integer
scores and the magnitude path are untouched.
"""
from __future__ import annotations

import math

import pytest
from rdflib import Graph, Literal, RDF, URIRef

from science_tool.graph.belief import aggregate_belief, collect_evidence_units, EVIDENCE_LINE_CLASS
from science_tool.graph.belief_scalar import belief_scalar
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS

CLAIM = URIRef("http://example.org/science/entity/proposition/p")
LINE = URIRef("http://example.org/science/entity/evidence-line/e")


def _build(*, stance: str, polarity: str | None, quant: dict | None = None) -> tuple[Graph, Graph]:
    knowledge, provenance = Graph(), Graph()
    knowledge.add((LINE, RDF.type, EVIDENCE_LINE_CLASS))
    predicate = CITO_NS.supports if stance == "supports" else CITO_NS.disputes
    knowledge.add((LINE, predicate, CLAIM))
    # Minimal scoring metadata so the line contributes ordinal mass too.
    provenance.add((LINE, SCI_NS.evidenceStrength, Literal("strong")))
    provenance.add((LINE, SCI_NS.evidenceRole, Literal("direct_test")))
    provenance.add((LINE, SCI_NS.evidenceType, Literal("empirical_data_evidence")))
    provenance.add((LINE, SCI_NS.independenceGroup, Literal("g1")))
    provenance.add((LINE, SCI_NS.evidenceIndependence, Literal("independent")))
    if polarity is not None:
        provenance.add((CLAIM, SCI_NS.polarity, Literal(polarity)))
    if quant is not None:
        if "beta" in quant:
            provenance.add((LINE, SCI_NS.quantBeta, Literal(quant["beta"])))
        if "prob_sign" in quant:
            provenance.add((LINE, SCI_NS.quantProbSign, Literal(quant["prob_sign"])))
        if "hdi" in quant:
            provenance.add((LINE, SCI_NS.quantHdiLow, Literal(quant["hdi"][0])))
            provenance.add((LINE, SCI_NS.quantHdiHigh, Literal(quant["hdi"][1])))
    return knowledge, provenance


def _scalar(knowledge: Graph, provenance: Graph):
    units = collect_evidence_units(knowledge, provenance, [CLAIM])
    return belief_scalar(aggregate_belief(units))


# --- (a) presence of a quantitative_result shifts the bands ---------------------


def test_quant_result_shifts_support_band_vs_absent():
    """A supporting line whose beta agrees with positive polarity pushes the
    support band HIGHER than the same line with no quantitative_result."""
    without = _scalar(*_build(stance="supports", polarity="positive"))
    with_q = _scalar(
        *_build(stance="supports", polarity="positive", quant={"beta": 1.2, "prob_sign": 0.95})
    )
    # Ordinal integer scores are unchanged (ordinal path untouched).
    assert with_q.massed_support_score == without.massed_support_score
    assert with_q.massed_dispute_score == without.massed_dispute_score
    # Continuous support band shifts UP when the oriented posterior is present.
    assert with_q.massed_support_band[0] > without.massed_support_band[0]
    assert with_q.massed_support_band[1] >= without.massed_support_band[1]


def test_quant_magnitude_scales_with_prob_sign():
    """Higher prob_sign (more sign confidence) => larger support-band shift."""
    low = _scalar(
        *_build(stance="supports", polarity="positive", quant={"beta": 1.0, "prob_sign": 0.55})
    )
    high = _scalar(
        *_build(stance="supports", polarity="positive", quant={"beta": 1.0, "prob_sign": 0.99})
    )
    assert high.massed_support_band[0] > low.massed_support_band[0]


# --- (b) truth table for sign-meaningful polarity -------------------------------


def test_positive_polarity_positive_beta_supports_is_support_mass():
    s = _scalar(*_build(stance="supports", polarity="positive", quant={"beta": 0.8, "prob_sign": 0.9}))
    baseline = _scalar(*_build(stance="supports", polarity="positive"))
    assert s.massed_support_band[0] > baseline.massed_support_band[0]
    # No dispute mass introduced.
    assert s.massed_dispute_band == baseline.massed_dispute_band


def test_negative_polarity_negative_beta_supports_is_support_mass():
    s = _scalar(*_build(stance="supports", polarity="negative", quant={"beta": -0.7, "prob_sign": 0.9}))
    baseline = _scalar(*_build(stance="supports", polarity="negative"))
    assert s.massed_support_band[0] > baseline.massed_support_band[0]
    assert s.massed_dispute_band == baseline.massed_dispute_band


def test_positive_polarity_negative_beta_disputes_is_dispute_mass():
    s = _scalar(*_build(stance="disputes", polarity="positive", quant={"beta": -0.6, "prob_sign": 0.9}))
    baseline = _scalar(*_build(stance="disputes", polarity="positive"))
    assert s.massed_dispute_band[0] > baseline.massed_dispute_band[0]
    assert s.massed_support_band == baseline.massed_support_band


# --- (c) contradiction cases fail loudly ----------------------------------------


def test_supports_with_beta_opposing_polarity_raises():
    """stance=supports but beta runs AGAINST the claimed polarity is a contradiction."""
    knowledge, provenance = _build(
        stance="supports", polarity="positive", quant={"beta": -0.9, "prob_sign": 0.95}
    )
    units = collect_evidence_units(knowledge, provenance, [CLAIM])
    with pytest.raises(ValueError, match="contradict"):
        belief_scalar(aggregate_belief(units))


def test_disputes_with_beta_agreeing_polarity_raises():
    """stance=disputes but beta AGREES with the claimed polarity is a contradiction."""
    knowledge, provenance = _build(
        stance="disputes", polarity="positive", quant={"beta": 0.9, "prob_sign": 0.95}
    )
    units = collect_evidence_units(knowledge, provenance, [CLAIM])
    with pytest.raises(ValueError, match="contradict"):
        belief_scalar(aggregate_belief(units))


# --- (d) unsigned falls back to stance; not_applicable contributes no oriented mass --


def test_unsigned_polarity_falls_back_to_stance():
    """unsigned => no claimed sign; orientation follows stance, magnitude scales by prob_sign."""
    s = _scalar(*_build(stance="supports", polarity="unsigned", quant={"beta": -2.0, "prob_sign": 0.9}))
    baseline = _scalar(*_build(stance="supports", polarity="unsigned"))
    # supports stance => support mass regardless of beta sign.
    assert s.massed_support_band[0] > baseline.massed_support_band[0]
    assert s.massed_dispute_band == baseline.massed_dispute_band


def test_not_applicable_polarity_contributes_no_oriented_mass():
    """not_applicable => sign-less proposition; a signed beta has no oriented meaning."""
    s = _scalar(
        *_build(stance="supports", polarity="not_applicable", quant={"beta": 1.5, "prob_sign": 0.95})
    )
    baseline = _scalar(*_build(stance="supports", polarity="not_applicable"))
    assert s.massed_support_band == baseline.massed_support_band
    assert s.massed_dispute_band == baseline.massed_dispute_band


# --- (e) undetermined-sign: no raise, falls back to stance ---------------------


def test_beta_zero_sign_meaningful_polarity_no_raise():
    """beta==0 means no determined sign: must NOT raise even with high prob_sign.
    Falls back to stance orientation → support mass contributed."""
    s = _scalar(
        *_build(stance="supports", polarity="positive", quant={"beta": 0, "prob_sign": 0.9})
    )
    baseline = _scalar(*_build(stance="supports", polarity="positive"))
    # Stance-oriented support mass is added (magnitude = QUANT_MASS_STEPS * 0.9).
    assert s.massed_support_band[0] > baseline.massed_support_band[0]
    assert s.massed_dispute_band == baseline.massed_dispute_band


def test_low_prob_sign_opposing_beta_no_raise():
    """prob_sign ≤ 0.5 means sign undetermined: beta opposing polarity must NOT raise.
    Falls back to stance orientation → small support mass contributed."""
    s = _scalar(
        *_build(stance="supports", polarity="positive", quant={"beta": -1.5, "prob_sign": 0.4})
    )
    baseline = _scalar(*_build(stance="supports", polarity="positive"))
    # Small stance-oriented support shift (magnitude = QUANT_MASS_STEPS * 0.4).
    assert s.massed_support_band[0] > baseline.massed_support_band[0]
    assert s.massed_dispute_band == baseline.massed_dispute_band


def test_prob_sign_none_with_beta_returns_zero_mass():
    """prob_sign is None with beta set → (0.0, 0.0), no raise (early-exit guard)."""
    knowledge, provenance = _build(
        stance="supports", polarity="positive", quant={"beta": 2.0}
    )
    # quant dict has only beta, no prob_sign key, so quant_prob_sign will be None.
    units = collect_evidence_units(knowledge, provenance, [CLAIM])
    from science_tool.graph.belief_scalar import _oriented_quant_mass

    (unit,) = units
    assert _oriented_quant_mass(unit) == (0.0, 0.0)


def test_genuine_contradiction_still_raises():
    """High prob_sign (0.98) + beta confidently opposing polarity + stance=supports → ValueError."""
    knowledge, provenance = _build(
        stance="supports", polarity="positive", quant={"beta": -1.2, "prob_sign": 0.98}
    )
    units = collect_evidence_units(knowledge, provenance, [CLAIM])
    with pytest.raises(ValueError, match="contradict"):
        belief_scalar(aggregate_belief(units))


# --- materialize round-trip -----------------------------------------------------


def test_materialize_emits_quant_predicates():
    from science_model.entities import EntityType, EvidenceLineEntity, QuantitativeResult
    from science_model.reasoning import EvidenceStance
    from science_tool.graph.materialize import _add_evidence_line_metadata

    provenance = Graph()
    uri = PROJECT_NS["evidence-line/q"]
    entity = EvidenceLineEntity(
        id="evidence-line:q",
        title="q",
        kind="evidence-line",
        type=EntityType.EVIDENCE_LINE,
        project="x",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="x.md",
        stance=EvidenceStance.SUPPORTS,
        target="proposition:p",
        quantitative_result=QuantitativeResult(
            beta=1.25, hdi=[0.1, 2.4], prob_sign=0.97, fit_task="t1", model="logistic"
        ),
    )
    _add_evidence_line_metadata(uri=uri, provenance=provenance, entity=entity)
    assert (uri, SCI_NS.quantBeta, Literal(1.25)) in provenance
    assert (uri, SCI_NS.quantProbSign, Literal(0.97)) in provenance
    assert (uri, SCI_NS.quantHdiLow, Literal(0.1)) in provenance
    assert (uri, SCI_NS.quantHdiHigh, Literal(2.4)) in provenance


# Sanity: a pure-ordinal claim (no quant) reproduces the legacy band formula
# (proves the ordinal path is untouched when no posterior is present).
def test_no_quant_band_matches_legacy_tanh_formula():
    s = _scalar(*_build(stance="supports", polarity="positive"))
    score = s.massed_support_score
    expected = (round(math.tanh(0.5 * 0.3 * score), 6), round(math.tanh(0.5 * 1.0 * score), 6))
    assert s.massed_support_band == expected
