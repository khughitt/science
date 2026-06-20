"""Tests for dag/workbench.py — WorkbenchRow + WorkbenchFile schema (Task 5a).

Verifies:
- Allowed fields validate without error.
- Forbidden fields (edge_status, belief, posterior-as-row-status, support arrays)
  raise ValidationError via extra="forbid".
- quantitative_result is allowed only inside an EvidenceStub, not at row level.
- WorkbenchFile wraps a list of WorkbenchRows.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_tool.dag.workbench import EvidenceStub, WorkbenchFile, WorkbenchRow

# ---------------------------------------------------------------------------
# Minimal valid row
# ---------------------------------------------------------------------------


def test_minimal_row_validates() -> None:
    row = WorkbenchRow.model_validate(
        {
            "subject": "gene:CCND1",
            "predicate": "affects",
            "object": "outcome:proliferation",
            "patch": "p001",
        }
    )
    assert row.subject == "gene:CCND1"
    assert row.predicate == "affects"
    assert row.id is None


def test_full_allowed_row_validates() -> None:
    row = WorkbenchRow.model_validate(
        {
            "id": "prop:p001-001",
            "subject": "gene:CCND1",
            "predicate": "affects",
            "object": "outcome:proliferation",
            "patch": "p001",
            "claim_layer": "causal_effect",
            "identification_strength": "observational",
            "epistemic_role": "data_discovered_adjacency",
            "polarity": "positive",
            "legacy_relation_label": "old-label",
            "evidence": [],
        }
    )
    assert row.id == "prop:p001-001"
    assert row.claim_layer == "causal_effect"
    assert row.epistemic_role == "data_discovered_adjacency"
    assert row.polarity == "positive"


def test_row_id_optional() -> None:
    row = WorkbenchRow.model_validate(
        {"subject": "gene:A", "predicate": "regulates", "object": "gene:B", "patch": "p002"}
    )
    assert row.id is None


# ---------------------------------------------------------------------------
# Evidence stubs
# ---------------------------------------------------------------------------


def test_evidence_stub_with_quantitative_result() -> None:
    stub = EvidenceStub.model_validate(
        {
            "stance": "supports",
            "quantitative_result": {
                "beta": 1.5,
                "hdi": [0.8, 2.2],
                "prob_sign": 0.97,
                "fit_task": "t491",
                "model": "DESeq2",
            },
        }
    )
    assert stub.quantitative_result is not None
    assert stub.quantitative_result.beta == pytest.approx(1.5)


def test_evidence_stub_minimal() -> None:
    stub = EvidenceStub.model_validate({"stance": "supports"})
    assert stub.quantitative_result is None


def test_row_with_evidence_stubs() -> None:
    row = WorkbenchRow.model_validate(
        {
            "subject": "gene:CCND1",
            "predicate": "affects",
            "object": "outcome:proliferation",
            "patch": "p001",
            "evidence": [
                {
                    "stance": "supports",
                    "source": "dataset:GSE12345",
                    "evidence_type": "empirical_data_evidence",
                    "dataset_usage": "primary",
                    "quantitative_result": {"beta": 0.9, "prob_sign": 0.95},
                },
                {
                    "stance": "disputes",
                    "source": "dataset:GSE99999",
                },
            ],
        }
    )
    assert len(row.evidence) == 2
    assert row.evidence[0].quantitative_result is not None
    assert row.evidence[0].quantitative_result.beta == pytest.approx(0.9)
    assert row.evidence[1].quantitative_result is None


# ---------------------------------------------------------------------------
# Forbidden fields raise ValidationError (extra="forbid" allowlist)
# ---------------------------------------------------------------------------


def test_edge_status_forbidden() -> None:
    with pytest.raises(ValidationError, match="edge_status"):
        WorkbenchRow.model_validate(
            {
                "subject": "gene:A",
                "predicate": "affects",
                "object": "outcome:X",
                "patch": "p001",
                "edge_status": "supported",
            }
        )


def test_belief_forbidden() -> None:
    with pytest.raises(ValidationError, match="belief"):
        WorkbenchRow.model_validate(
            {
                "subject": "gene:A",
                "predicate": "affects",
                "object": "outcome:X",
                "patch": "p001",
                "belief": 0.9,
            }
        )


def test_posterior_as_row_field_forbidden() -> None:
    """posterior at row level is forbidden (it lives on edges.yaml, not workbench rows)."""
    with pytest.raises(ValidationError, match="posterior"):
        WorkbenchRow.model_validate(
            {
                "subject": "gene:A",
                "predicate": "affects",
                "object": "outcome:X",
                "patch": "p001",
                "posterior": {"beta": 1.0},
            }
        )


def test_support_array_forbidden() -> None:
    with pytest.raises(ValidationError, match="support"):
        WorkbenchRow.model_validate(
            {
                "subject": "gene:A",
                "predicate": "affects",
                "object": "outcome:X",
                "patch": "p001",
                "support": ["evidence:e001"],
            }
        )


def test_dispute_array_forbidden() -> None:
    with pytest.raises(ValidationError, match="dispute"):
        WorkbenchRow.model_validate(
            {
                "subject": "gene:A",
                "predicate": "affects",
                "object": "outcome:X",
                "patch": "p001",
                "dispute": ["evidence:e002"],
            }
        )


def test_massed_support_forbidden() -> None:
    with pytest.raises(ValidationError, match="massed_support"):
        WorkbenchRow.model_validate(
            {
                "subject": "gene:A",
                "predicate": "affects",
                "object": "outcome:X",
                "patch": "p001",
                "massed_support": 3,
            }
        )


# ---------------------------------------------------------------------------
# quantitative_result is NOT allowed at row level
# ---------------------------------------------------------------------------


def test_quantitative_result_at_row_level_forbidden() -> None:
    """quantitative_result must be inside an evidence stub, not a row-level field."""
    with pytest.raises(ValidationError, match="quantitative_result"):
        WorkbenchRow.model_validate(
            {
                "subject": "gene:A",
                "predicate": "affects",
                "object": "outcome:X",
                "patch": "p001",
                "quantitative_result": {"beta": 1.0},
            }
        )


# ---------------------------------------------------------------------------
# EvidenceStub also forbids unknown keys
# ---------------------------------------------------------------------------


def test_evidence_stub_unknown_key_forbidden() -> None:
    with pytest.raises(ValidationError):
        EvidenceStub.model_validate(
            {
                "stance": "supports",
                "unknown_extra_field": "oops",
            }
        )


# ---------------------------------------------------------------------------
# WorkbenchFile wraps rows
# ---------------------------------------------------------------------------


def test_workbench_file_empty_rows() -> None:
    wf = WorkbenchFile.model_validate({"patch": "p001", "rows": []})
    assert wf.rows == []


def test_workbench_file_parses_rows() -> None:
    wf = WorkbenchFile.model_validate(
        {
            "patch": "p001",
            "rows": [
                {
                    "subject": "gene:CCND1",
                    "predicate": "affects",
                    "object": "outcome:proliferation",
                    "patch": "p001",
                    "polarity": "positive",
                },
                {
                    "id": "prop:p001-002",
                    "subject": "gene:MYC",
                    "predicate": "regulates",
                    "object": "gene:CDKN1A",
                    "patch": "p001",
                    "claim_layer": "empirical_regularity",
                },
            ],
        }
    )
    assert len(wf.rows) == 2
    assert wf.rows[0].subject == "gene:CCND1"
    assert wf.rows[1].id == "prop:p001-002"


def test_workbench_file_patch_header_optional() -> None:
    wf = WorkbenchFile.model_validate(
        {
            "rows": [
                {
                    "subject": "gene:A",
                    "predicate": "affects",
                    "object": "outcome:X",
                    "patch": "p001",
                }
            ]
        }
    )
    assert wf.patch is None
    assert len(wf.rows) == 1


def test_evidence_stub_canonicalizes_evidence_type() -> None:
    from science_model.reasoning import EvidenceType
    stub = EvidenceStub.model_validate({"stance": "supports", "evidence_type": "empirical_data_evidence"})
    assert stub.evidence_type is EvidenceType.EMPIRICAL_DATA


def test_evidence_stub_rejects_unknown_evidence_type() -> None:
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        EvidenceStub.model_validate({"stance": "supports", "evidence_type": "differential_expression"})
