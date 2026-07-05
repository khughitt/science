from __future__ import annotations

import pytest

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import ProfileComponent
from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_idc_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.identity_context/1.0",
        "id": "dataset:example-idc",
        "kind": "dataset",
        "title": "Example dataset with identity context",
        "version": "1.0.0",
        "created": "2026-05-26",
        "updated": "2026-05-26",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
        "identity_context": {
            "taxon": 9606,
            "molecular_ids": {"gene": {"namespace": "hgnc", "canonical": True}},
            "assembly": {
                "seqcol_digest": "g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp",
                "label": "GRCh38",
                "registry": "dataset:assembly-registry",
                "resolution_status": "resolved",
            },
        },
    }


def test_loader_resolves_identity_context_schema() -> None:
    schema = SchemaLoader().load(ProfileComponent(name="bio.identity_context", version="1.0"))
    assert schema["$id"].endswith("extension-bio-identity_context-1.0.json")


def test_minimal_valid_identity_context_passes(base_idc_entity: dict) -> None:
    EntityValidator().validate(base_idc_entity)


def test_identity_context_required_when_extension_declared(base_idc_entity: dict) -> None:
    del base_idc_entity["identity_context"]
    with pytest.raises(EntityValidationError, match="identity_context"):
        EntityValidator().validate(base_idc_entity)


def test_taxon_required(base_idc_entity: dict) -> None:
    del base_idc_entity["identity_context"]["taxon"]
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_idc_entity)


def test_assembly_requires_seqcol_digest(base_idc_entity: dict) -> None:
    del base_idc_entity["identity_context"]["assembly"]["seqcol_digest"]
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_idc_entity)


def test_assembly_requires_resolution_status(base_idc_entity: dict) -> None:
    del base_idc_entity["identity_context"]["assembly"]["resolution_status"]
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_idc_entity)


def test_assembly_requires_registry(base_idc_entity: dict) -> None:
    # The declared reference collection is part of the contract, not advisory
    # (finding 1): a keyed reference must name the registry it resolves against.
    del base_idc_entity["identity_context"]["assembly"]["registry"]
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_idc_entity)


def test_assembly_rejects_unknown_resolution_status(base_idc_entity: dict) -> None:
    base_idc_entity["identity_context"]["assembly"]["resolution_status"] = "maybe"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_idc_entity)


def test_assembly_declared_unresolved_passes(base_idc_entity: dict) -> None:
    # A keyed reference may be declared_unresolved (RCM-D2, guardrail 1).
    base_idc_entity["identity_context"]["assembly"]["resolution_status"] = "declared_unresolved"
    EntityValidator().validate(base_idc_entity)


def test_registry_must_be_dataset_ref(base_idc_entity: dict) -> None:
    base_idc_entity["identity_context"]["assembly"]["registry"] = "assembly-registry"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_idc_entity)


def test_identity_context_allows_future_sibling_keys(base_idc_entity: dict) -> None:
    # additionalProperties: true on identity_context leaves room for later
    # non-molecular siblings (cell_line, disease, ontology) — C-D6.
    base_idc_entity["identity_context"]["cell_line"] = {"namespace": "cellosaurus"}
    EntityValidator().validate(base_idc_entity)


def test_molecular_ids_gene_accepts_registry_and_resolution_status(base_idc_entity: dict) -> None:
    base_idc_entity["identity_context"]["molecular_ids"]["gene"] = {
        "namespace": "hgnc_id",
        "canonical": True,
        "registry": "dataset:gene-crosswalk-hgnc",
        "resolution_status": "resolved",
    }
    EntityValidator().validate(base_idc_entity)


def test_molecular_ids_gene_registry_must_be_dataset_ref(base_idc_entity: dict) -> None:
    base_idc_entity["identity_context"]["molecular_ids"]["gene"] = {
        "namespace": "hgnc_id",
        "registry": "gene-crosswalk-hgnc",
    }
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_idc_entity)


def test_molecular_ids_gene_rejects_unknown_resolution_status(base_idc_entity: dict) -> None:
    base_idc_entity["identity_context"]["molecular_ids"]["gene"] = {
        "namespace": "hgnc_id",
        "resolution_status": "maybe",
    }
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_idc_entity)


def test_molecular_ids_gene_declared_unresolved_passes(base_idc_entity: dict) -> None:
    base_idc_entity["identity_context"]["molecular_ids"]["gene"] = {
        "namespace": "hgnc_id",
        "resolution_status": "declared_unresolved",
    }
    EntityValidator().validate(base_idc_entity)
