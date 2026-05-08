from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from science_tool.evidence_payload import EvidencePayload, PayloadValidationError
from science_tool.synthesis_payload import (
    SYNTHESIS_FAMILIES,
    SYNTHESIS_OPERATION_EXTENSION,
    SYNTHESIS_PRIMARY_EXTENSION_NAMES,
    SynthesisOperation,
    build_synthesis_registry,
    derivation_edges,
    route_synthesis_family,
    validate_synthesis_payload,
)


def _synthesis_payload(payload_id: str, **overrides: Any) -> EvidencePayload:
    core: dict[str, Any] = {
        "payload_id": payload_id,
        "artifact_type": "bayesian-model-comparison",
        "extensions": ["bayesian-model-comparison", "synthesis-operation"],
        "created_at": "2026-05-08T10:00:00Z",
        "input_artifact_refs": ["study:gronau-input"],
        "method_ref": "paper:Gronau2021",
        "agent_ref": "agent:synthesis-runner",
        "pipeline_provenance_ref": "pipeline:bma-synthesis-v1",
        "proposition_refs": ["prop:model-a-over-null"],
        "comparison_target": "model-set",
        "support_direction": "supports",
        "validation_role": "prioritize-attention",
        "validation_status": "pending",
        "uncertainty_summary": "PMP(model-a)=0.72",
        "reason_codes": [],
    }
    core.update(overrides.pop("core", {}))
    extension_sections: dict[str, dict[str, Any]] = {
        "bayesian-model-comparison": {},
        "synthesis-operation": {
            "output_artifact_refs": ["payload:bma-model-summary"],
            "operator_assumption_refs": ["assumption:prior-model-probabilities-explicit"],
        },
    }
    extension_sections.update(overrides.pop("extension_sections", {}))
    return EvidencePayload.model_validate({"core": core, "extension_sections": extension_sections, **overrides})


def test_synthesis_operation_section_parses_required_refs() -> None:
    payload = _synthesis_payload("syn-2026-bma")

    validate_synthesis_payload(payload)

    operation = SynthesisOperation.model_validate(payload.extension_sections["synthesis-operation"])
    assert operation.output_artifact_refs == ["payload:bma-model-summary"]
    assert operation.operator_assumption_refs == ["assumption:prior-model-probabilities-explicit"]


def test_all_non_reserved_synthesis_families_register_primary_extensions() -> None:
    registry = build_synthesis_registry()

    for name in SYNTHESIS_PRIMARY_EXTENSION_NAMES:
        spec = registry.extension(name)
        assert spec.name == name
        assert spec.artifact_type == name
        assert SYNTHESIS_OPERATION_EXTENSION in spec.co_required_extensions


def test_reserved_decision_analytic_score_is_rejected_for_production_payloads() -> None:
    payload = _synthesis_payload(
        "syn-2026-mcda",
        core={
            "artifact_type": "decision-analytic-score",
            "extensions": ["decision-analytic-score", "synthesis-operation"],
            "validation_role": "record-only",
            "proposition_refs": [],
            "comparison_target": "n-a",
            "support_direction": "operation-record",
        },
        extension_sections={"decision-analytic-score": {}},
    )

    with pytest.raises(PayloadValidationError, match="reserved synthesis family"):
        validate_synthesis_payload(payload)


def test_synthesis_payload_requires_synthesis_operation_extension() -> None:
    payload = _synthesis_payload(
        "syn-2026-missing-operation",
        core={"extensions": ["bayesian-model-comparison"]},
        extension_sections={"synthesis-operation": {}},
    )

    with pytest.raises(PayloadValidationError, match="co-required extension 'synthesis-operation'"):
        validate_synthesis_payload(payload)


def test_family_permission_ceiling_blocks_strengthen_belief_for_feature_selection() -> None:
    payload = _synthesis_payload(
        "syn-2026-feature-selection",
        core={
            "artifact_type": "feature-selection-synthesis",
            "extensions": ["feature-selection-synthesis", "synthesis-operation"],
            "validation_role": "strengthen-belief",
            "proposition_refs": ["prop:selected-feature-supports-biology"],
        },
        extension_sections={"feature-selection-synthesis": {}},
    )

    with pytest.raises(PayloadValidationError, match="exceeds max permission"):
        validate_synthesis_payload(payload)


def test_route_synthesis_family_sends_bma_to_model_comparison() -> None:
    assert route_synthesis_family("bayesian-model-averaging") == "bayesian-model-comparison"
    assert route_synthesis_family("bayes-factor-model-set") == "bayesian-model-comparison"


def test_route_synthesis_family_prefers_effect_pooling_for_pooled_effects() -> None:
    assert route_synthesis_family("pooled-effect-estimate") == "effect-size-pooling"
    assert route_synthesis_family("meta-analysis-effect-size") == "effect-size-pooling"


def test_route_synthesis_family_distinguishes_graph_posterior_from_graph_estimate() -> None:
    assert route_synthesis_family("graph-posterior") == "graph-posterior-synthesis"
    assert route_synthesis_family("conditional-dependence-graph") == "graph-estimate-synthesis"


def test_route_synthesis_family_rejects_unknown_operator() -> None:
    with pytest.raises(PayloadValidationError, match="no synthesis-family route"):
        route_synthesis_family("ambiguous-literature-summary")


def test_derivation_edges_emit_inputs_outputs_propositions_method_and_agent() -> None:
    payload = _synthesis_payload("syn-2026-bma")

    edges = derivation_edges(payload)

    assert edges == [
        ("syn-2026-bma", "consumes", "study:gronau-input"),
        ("syn-2026-bma", "uses-method", "paper:Gronau2021"),
        ("syn-2026-bma", "performed-by", "agent:synthesis-runner"),
        ("syn-2026-bma", "targets-proposition", "prop:model-a-over-null"),
        ("syn-2026-bma", "produced", "payload:bma-model-summary"),
        ("payload:bma-model-summary", "derived-from-synthesis", "syn-2026-bma"),
    ]


def test_derivation_edges_skip_empty_proposition_refs() -> None:
    payload = _synthesis_payload(
        "syn-2026-graph",
        core={
            "artifact_type": "graph-posterior-synthesis",
            "extensions": ["graph-posterior-synthesis", "synthesis-operation"],
            "proposition_refs": [],
            "comparison_target": "n-a",
            "support_direction": "methodological-input",
            "validation_role": "prioritize-attention",
            "uncertainty_summary": "edge inclusion table: 102 rows",
        },
        extension_sections={"graph-posterior-synthesis": {}},
    )

    edges = derivation_edges(payload)

    assert not any(edge[1] == "targets-proposition" for edge in edges)
    assert ("syn-2026-graph", "produced", "payload:bma-model-summary") in edges


def test_typed_synthesis_docs_list_every_family() -> None:
    docs = Path(__file__).resolve().parents[1] / "docs" / "typed-synthesis-nodes.md"
    text = docs.read_text()

    for family in SYNTHESIS_FAMILIES:
        assert f"`{family}`" in text
