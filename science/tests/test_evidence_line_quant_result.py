"""Tests for EvidenceLineEntity quantitative_result and belief_eligible fields."""

from __future__ import annotations

from science_model.entities import EvidenceLineEntity, EntityType, QuantitativeResult


def _base_evidence_line(**kwargs) -> EvidenceLineEntity:
    """Construct a minimal EvidenceLineEntity with all base-required fields."""
    defaults = dict(
        id="evidence-line:e1",
        kind="evidence-line",
        type=EntityType.EVIDENCE_LINE,
        title="",
        project="",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="",
    )
    defaults.update(kwargs)
    return EvidenceLineEntity(**defaults)


def test_quantitative_result_and_staging_fields() -> None:
    e = _base_evidence_line(
        stance="supports",
        target="proposition:p1",
        evidence_type="empirical_data_evidence",
        quantitative_result={"beta": 0.41, "hdi": [0.2, 0.6], "prob_sign": 0.98},
        belief_eligible=False,
    )
    assert isinstance(e.quantitative_result, QuantitativeResult)
    assert e.quantitative_result.prob_sign == 0.98
    assert e.quantitative_result.beta == 0.41
    assert e.quantitative_result.hdi == [0.2, 0.6]
    assert e.belief_eligible is False


def test_belief_eligible_defaults_true() -> None:
    e = _base_evidence_line(
        stance="supports",
        target="proposition:p1",
        evidence_type="literature_evidence",
    )
    assert e.belief_eligible is True
    assert e.quantitative_result is None


def test_quantitative_result_partial_fields() -> None:
    """QuantitativeResult fields are all optional; partial dicts are accepted."""
    e = _base_evidence_line(
        stance="supports",
        target="proposition:p1",
        quantitative_result={"fit_task": "t123", "model": "logistic_regression"},
    )
    assert e.quantitative_result is not None
    assert e.quantitative_result.fit_task == "t123"
    assert e.quantitative_result.model == "logistic_regression"
    assert e.quantitative_result.beta is None
    assert e.quantitative_result.prob_sign is None
