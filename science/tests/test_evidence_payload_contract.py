from __future__ import annotations

from typing import Any

import pytest

from science_tool.evidence_payload import (
    EvidencePayload,
    EvidencePayloadRegistry,
    ExtensionSpec,
    PayloadValidationError,
    ReasonCodeSpec,
    ValidationRule,
    effective_reason_codes,
)


def _registry() -> EvidencePayloadRegistry:
    registry = EvidencePayloadRegistry()
    registry.register_reason_code(ReasonCodeSpec(code="identification-missing", blocking=True))
    registry.register_reason_code(ReasonCodeSpec(code="source-dependent", blocking=False))
    registry.register_reason_code(ReasonCodeSpec(code="code-or-data-unavailable", blocking=True))
    registry.register_extension(
        ExtensionSpec(
            name="causal-discovery-run",
            artifact_type="causal-discovery-run",
            required_fields=["discovery_algorithm"],
            co_required_extensions=["causal-graph"],
        )
    )
    registry.register_extension(
        ExtensionSpec(
            name="causal-graph",
            artifact_type="causal-graph",
            required_fields=["identification_status"],
            validation_rules=[
                ValidationRule(
                    role="strengthen-belief",
                    required_fields={"identification_status": "identified"},
                    blocked_by_reason_codes=["identification-missing"],
                )
            ],
        )
    )
    registry.register_extension(
        ExtensionSpec(
            name="reproducibility-checklist-audit",
            artifact_type="reproducibility-checklist-audit",
            required_fields=["checklist_ref"],
            propagation_policy="propagate-blocking",
        )
    )
    registry.register_extension(
        ExtensionSpec(
            name="truth-discovery",
            artifact_type="truth-discovery-result",
            required_fields=["source_reliability_estimates"],
            static_reason_codes=["source-dependent"],
            propagation_policy="propagate-blocking",
        )
    )
    return registry


def _payload(payload_id: str, **overrides: Any) -> EvidencePayload:
    core: dict[str, Any] = {
        "payload_id": payload_id,
        "artifact_type": "causal-discovery-run",
        "extensions": ["causal-discovery-run", "causal-graph"],
        "created_at": "2026-05-06T13:00:00Z",
        "input_artifact_refs": ["dataset:covid-vaccine-obs-cohort"],
        "method_ref": "paper:Petersen2014",
        "agent_ref": "agent:pc-runner",
        "pipeline_provenance_ref": "pipeline:causal-discovery-pc-v3",
        "proposition_refs": ["prop:vaccination-reduces-severe-illness"],
        "comparison_target": "hypothesis-set",
        "support_direction": "methodological-input",
        "validation_role": "prioritize-attention",
        "validation_status": "pending",
        "uncertainty_summary": "CPDAG, 12 edges",
        "reason_codes": ["identification-missing"],
    }
    core.update(overrides.pop("core", {}))
    sections: dict[str, dict[str, Any]] = {
        "causal-discovery-run": {"discovery_algorithm": "PC"},
        "causal-graph": {"identification_status": "not-attempted"},
    }
    sections.update(overrides.pop("extension_sections", {}))
    return EvidencePayload.model_validate({"core": core, "extension_sections": sections, **overrides})


def test_payload_validates_core_source_method_split_and_multi_extension_contract() -> None:
    payload = _payload("ev-2026-vaccine-cpdag-pc-run")

    _registry().validate_payload(payload)

    assert payload.core.input_artifact_refs == ["dataset:covid-vaccine-obs-cohort"]
    assert payload.core.method_ref == "paper:Petersen2014"
    assert payload.core.extensions == ["causal-discovery-run", "causal-graph"]


def test_payload_rejects_missing_co_required_extension_before_silent_fallback() -> None:
    payload = _payload(
        "ev-2026-bad-cpdag",
        core={"extensions": ["causal-discovery-run"]},
        extension_sections={"causal-graph": {}},
    )

    with pytest.raises(PayloadValidationError, match="co-required extension 'causal-graph'"):
        _registry().validate_payload(payload)


def test_payload_rejects_strengthen_belief_when_effective_blocking_reason_inherited() -> None:
    audit = EvidencePayload.model_validate(
        {
            "core": {
                "payload_id": "ev-2026-dishonesty-osiris-audit",
                "artifact_type": "reproducibility-checklist-audit",
                "extensions": ["reproducibility-checklist-audit"],
                "created_at": "2026-05-06T14:30:00Z",
                "input_artifact_refs": ["study:dishonesty-19lab"],
                "method_ref": "paper:Banzi2026",
                "agent_ref": "agent:reproducibility-auditor",
                "proposition_refs": [],
                "target_artifact_ref": "study:dishonesty-19lab",
                "comparison_target": "artifact-target",
                "support_direction": "quality-record",
                "validation_role": "quality-record-only",
                "validation_status": "validated",
                "uncertainty_summary": "OSIRIS 24/32 items present",
                "reason_codes": ["code-or-data-unavailable"],
            },
            "extension_sections": {"reproducibility-checklist-audit": {"checklist_ref": "checklist:OSIRIS-32"}},
        }
    )
    downstream = _payload(
        "ev-2026-downstream-causal-update",
        core={
            "input_artifact_refs": ["ev-2026-dishonesty-osiris-audit"],
            "support_direction": "supports",
            "validation_role": "strengthen-belief",
            "reason_codes": [],
        },
        extension_sections={"causal-graph": {"identification_status": "identified"}},
    )
    registry = _registry()

    with pytest.raises(PayloadValidationError, match="code-or-data-unavailable"):
        registry.validate_payload(downstream, payloads_by_id={audit.core.payload_id: audit})

    codes = effective_reason_codes(downstream, registry, payloads_by_id={audit.core.payload_id: audit})
    inherited = [item for item in codes if item.origin == "inherited"]
    assert [(item.code, item.chain) for item in inherited] == [
        ("code-or-data-unavailable", ("ev-2026-downstream-causal-update", "ev-2026-dishonesty-osiris-audit"))
    ]


def test_nonblocking_codes_do_not_propagate_under_default_blocking_policy() -> None:
    upstream = EvidencePayload.model_validate(
        {
            "core": {
                "payload_id": "ev-2026-effect-truth-discovery",
                "artifact_type": "truth-discovery-result",
                "extensions": ["truth-discovery"],
                "created_at": "2026-05-06T12:30:00Z",
                "input_artifact_refs": ["claim:s1-effect-x"],
                "method_ref": "paper:Zhao2012",
                "proposition_refs": ["prop:effect-x-magnitude"],
                "comparison_target": "hypothesis-set",
                "support_direction": "supports",
                "validation_role": "prioritize-attention",
                "validation_status": "pending",
                "uncertainty_summary": "TD posterior: x~=0.31",
                "reason_codes": [],
            },
            "extension_sections": {"truth-discovery": {"source_reliability_estimates": {"s1": {"sensitivity": 0.83}}}},
        }
    )
    downstream = _payload(
        "ev-2026-downstream-from-truth-discovery",
        core={"input_artifact_refs": ["ev-2026-effect-truth-discovery"], "reason_codes": []},
    )

    codes = effective_reason_codes(downstream, _registry(), payloads_by_id={upstream.core.payload_id: upstream})

    assert "source-dependent" not in [item.code for item in codes if item.origin == "inherited"]


def test_extension_section_reason_codes_join_effective_codes_with_extension_origin() -> None:
    payload = _payload(
        "ev-2026-causal-extension-coded",
        core={"reason_codes": []},
        extension_sections={
            "causal-graph": {"identification_status": "not-attempted", "reason_codes": ["identification-missing"]}
        },
    )

    codes = effective_reason_codes(payload, _registry())

    assert ("identification-missing", "causal-graph") in [(item.code, item.origin) for item in codes]


def test_payload_accepts_create_hypothesis_validation_role() -> None:
    payload = _payload(
        "ev-2026-candidate-hypothesis",
        core={
            "validation_role": "create-hypothesis",
            "proposition_refs": [],
            "support_direction": "methodological-input",
        },
    )

    _registry().validate_payload(payload)

    assert payload.core.validation_role == "create-hypothesis"
