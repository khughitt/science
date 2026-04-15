from pydantic import BaseModel, ValidationError

from science_model import Entity, EntityType
from science_model.reasoning import (
    ClaimLayer,
    EvidenceLineMetadata,
    EvidenceRole,
    IdentificationStrength,
    MeasurementModel,
    ProxyDirectness,
    RivalModelPacket,
    SupportScope,
)


def test_claim_layer_accepts_valid_values() -> None:
    assert ClaimLayer("empirical_regularity") == ClaimLayer.EMPIRICAL_REGULARITY
    assert ClaimLayer("causal_effect") == ClaimLayer.CAUSAL_EFFECT
    assert ClaimLayer("mechanistic_narrative") == ClaimLayer.MECHANISTIC_NARRATIVE
    assert ClaimLayer("structural_claim") == ClaimLayer.STRUCTURAL_CLAIM


def test_claim_layer_rejects_invalid_values() -> None:
    class _Envelope(BaseModel):
        claim_layer: ClaimLayer

    try:
        _Envelope.model_validate({"claim_layer": "not-a-layer"})
    except ValidationError as exc:
        assert "claim_layer" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected validation error")


def test_reasoning_enums_reject_invalid_values() -> None:
    for model, field, value in [
        (EvidenceLineMetadata, "evidence_role", "not-a-role"),
        (MeasurementModel, "observed_entity", ""),
        (RivalModelPacket, "packet_id", ""),
    ]:
        try:
            model.model_validate({field: value})
        except ValidationError as exc:
            assert field in str(exc)
        else:  # pragma: no cover - defensive
            raise AssertionError("expected validation error")


def test_identification_strength_rejects_invalid_values() -> None:
    class _Envelope(BaseModel):
        identification_strength: IdentificationStrength

    try:
        _Envelope.model_validate({"identification_strength": "not-a-strength"})
    except ValidationError as exc:
        assert "identification_strength" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected validation error")


def test_proxy_directness_rejects_invalid_values() -> None:
    class _Envelope(BaseModel):
        proxy_directness: ProxyDirectness

    try:
        _Envelope.model_validate({"proxy_directness": "not-a-directness"})
    except ValidationError as exc:
        assert "proxy_directness" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected validation error")


def test_support_scope_rejects_invalid_values() -> None:
    class _Envelope(BaseModel):
        supports_scope: SupportScope

    try:
        _Envelope.model_validate({"supports_scope": "not-a-scope"})
    except ValidationError as exc:
        assert "supports_scope" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected validation error")


def test_measurement_model_and_rival_model_packet_validate() -> None:
    measurement = MeasurementModel(
        observed_entity="observation:obs-1",
        latent_construct="latent:cell-state",
        measurement_relation="proxy-for",
        rationale="Observation is a proxy for the latent construct.",
        known_failure_modes=["batch effects"],
        substitutable_with=["observation:obs-2"],
    )
    rival_packet = RivalModelPacket(
        packet_id="packet:dag-1",
        target_hypothesis="hypothesis:h01",
        current_working_model=None,
        alternative_models=["model:a", "model:b"],
        shared_observables=["observation:obs-1"],
        discriminating_predictions=["model:a predicts X"],
        adjudication_rule="Prefer the simplest model that explains all observables.",
    )
    metadata = EvidenceLineMetadata(
        claim_layer=ClaimLayer.MECHANISTIC_NARRATIVE,
        identification_strength=IdentificationStrength.INTERVENTIONAL,
        proxy_directness=ProxyDirectness.INDIRECT,
        supports_scope=SupportScope.HYPOTHESIS_BUNDLE,
        independence_group="batch-1",
        evidence_role=EvidenceRole.DIRECT_TEST,
        measurement_model=measurement,
        rival_model_packet_ref="packet:dag-1",
    )

    assert measurement.observed_entity == "observation:obs-1"
    assert rival_packet.current_working_model is None
    assert metadata.measurement_model == measurement
    assert metadata.claim_layer == ClaimLayer.MECHANISTIC_NARRATIVE
    assert metadata.evidence_role == EvidenceRole.DIRECT_TEST


def test_entity_round_trips_reasoning_metadata_fields() -> None:
    measurement = MeasurementModel(
        observed_entity="observation:obs-1",
        latent_construct="latent:cell-state",
        measurement_relation="proxy-for",
        rationale="Observation is a proxy for the latent construct.",
        known_failure_modes=["batch effects"],
        substitutable_with=["observation:obs-2"],
    )
    entity = Entity(
        id="proposition:p01",
        type=EntityType.PROPOSITION,
        title="Test proposition",
        project="p",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="doc/p01.md",
        claim_layer=ClaimLayer.MECHANISTIC_NARRATIVE,
        identification_strength=IdentificationStrength.OBSERVATIONAL,
        proxy_directness=ProxyDirectness.DIRECT,
        supports_scope=SupportScope.LOCAL_PROPOSITION,
        independence_group="group-a",
        measurement_model=measurement,
        rival_model_packet_ref="packet:dag-1",
    )

    dumped = entity.model_dump()
    assert dumped["claim_layer"] == "mechanistic_narrative"
    assert dumped["measurement_model"]["observed_entity"] == "observation:obs-1"
    assert dumped["rival_model_packet_ref"] == "packet:dag-1"
    restored = Entity.model_validate(dumped)
    assert restored == entity
