from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_model.entity_schema.validator import EntityValidationError, EntityValidator
from science_model.packages.schema import AssemblyIdentity, IdentityContext, IdentityTransform


def assert_schema_error(error: EntityValidationError, path: list[str], validator: str) -> None:
    assert any(list(err.absolute_path) == path and err.validator == validator for err in error.errors)


@pytest.fixture
def base_idc_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.identity_context/1.0",
        "id": "dataset:example-idc",
        "type": "dataset",
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


def test_assembly_proxy_validates(base_idc_entity: dict) -> None:
    base_idc_entity["identity_context"]["assembly"]["proxy"] = {
        "type": "interval_overlap_proxy",
        "via": "dataset:grch38-intervals",
        "sources": [
            {
                "dataset": "dataset:source-assembly",
                "assembly": {"label": "GRCh37"},
            }
        ],
    }

    EntityValidator().validate(base_idc_entity)


def test_assembly_proxy_requires_sources(base_idc_entity: dict) -> None:
    base_idc_entity["identity_context"]["assembly"]["proxy"] = {
        "type": "interval_overlap_proxy",
        "via": "dataset:grch38-intervals",
        "sources": [],
    }

    with pytest.raises(EntityValidationError) as info:
        EntityValidator().validate(base_idc_entity)
    assert_schema_error(
        info.value,
        ["identity_context", "assembly", "proxy", "sources"],
        "minItems",
    )


def test_molecular_id_tier_transform_validates(base_idc_entity: dict) -> None:
    base_idc_entity["identity_context"]["molecular_ids"]["gene"] = {
        "namespace": "hgnc_id",
        "transform": {
            "type": "symbol_remap",
            "from": "hgnc_symbol",
            "method": "approved_symbol",
            "dataset": "dataset:hgnc-symbol-remap",
        },
    }

    EntityValidator().validate(base_idc_entity)


def test_molecular_id_tier_rejects_unknown_properties(base_idc_entity: dict) -> None:
    base_idc_entity["identity_context"]["molecular_ids"]["gene"] = {
        "namespace": "hgnc_id",
        "comment": "extra tier metadata",
    }

    with pytest.raises(EntityValidationError) as info:
        EntityValidator().validate(base_idc_entity)
    assert_schema_error(
        info.value,
        ["identity_context", "molecular_ids", "gene"],
        "additionalProperties",
    )


def test_declared_unresolved_assembly_allows_missing_seqcol_digest(base_idc_entity: dict) -> None:
    del base_idc_entity["identity_context"]["assembly"]["seqcol_digest"]
    base_idc_entity["identity_context"]["assembly"]["resolution_status"] = "declared_unresolved"

    EntityValidator().validate(base_idc_entity)


def test_assembly_proxy_rejects_unknown_type(base_idc_entity: dict) -> None:
    base_idc_entity["identity_context"]["assembly"]["proxy"] = {
        "type": "coordinate_guess",
        "via": "dataset:grch38-intervals",
        "sources": [
            {
                "dataset": "dataset:source-assembly",
                "assembly": "inherit",
            }
        ],
    }

    with pytest.raises(EntityValidationError) as info:
        EntityValidator().validate(base_idc_entity)
    assert_schema_error(
        info.value,
        ["identity_context", "assembly", "proxy", "type"],
        "enum",
    )


def test_identity_context_models_round_trip_proxy_and_transform() -> None:
    context = IdentityContext.model_validate(
        {
            "taxon": 9606,
            "assembly": {
                "label": "hg19 cytoband proxy",
                "registry": "dataset:assembly-registry",
                "resolution_status": "declared_unresolved",
                "proxy": {
                    "type": "cytoband_proxy",
                    "via": "dataset:ucsc-cytobands",
                    "sources": [
                        {
                            "dataset": "dataset:source-assembly",
                            "assembly": {"label": "GRCh37"},
                        }
                    ],
                },
            },
            "molecular_ids": {
                "gene": {
                    "namespace": "hgnc_id",
                    "registry": "dataset:hgnc",
                    "resolution_status": "resolved",
                    "transform": {
                        "type": "symbol_remap",
                        "from": "hgnc_symbol",
                        "method": "approved_symbol",
                        "dataset": "dataset:hgnc-symbol-remap",
                    },
                }
            },
        }
    )

    assert context.assembly is not None
    assert context.assembly.proxy is not None
    assert context.assembly.proxy.sources[0].dataset == "dataset:source-assembly"
    assert context.molecular_ids["gene"].transform == IdentityTransform(
        type="symbol_remap",
        from_="hgnc_symbol",
        method="approved_symbol",
        dataset="dataset:hgnc-symbol-remap",
    )
    assert context.model_dump(by_alias=True)["molecular_ids"]["gene"]["transform"]["from"] == "hgnc_symbol"


@pytest.mark.parametrize("seqcol_digest", [None, "UNKNOWN"])
def test_assembly_identity_resolved_requires_known_seqcol_digest(seqcol_digest: str | None) -> None:
    payload = {
        "registry": "dataset:assembly-registry",
        "resolution_status": "resolved",
    }
    if seqcol_digest is not None:
        payload["seqcol_digest"] = seqcol_digest

    with pytest.raises(ValidationError, match="resolved assembly requires seqcol_digest"):
        AssemblyIdentity.model_validate(payload)


def test_assembly_identity_proxy_requires_declared_unresolved() -> None:
    with pytest.raises(ValidationError, match="assembly proxy requires resolution_status"):
        AssemblyIdentity.model_validate(
            {
                "registry": "dataset:assembly-registry",
                "resolution_status": "resolved",
                "seqcol_digest": "g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp",
                "proxy": {
                    "type": "interval_overlap_proxy",
                    "via": "dataset:grch38-intervals",
                    "sources": [
                        {
                            "dataset": "dataset:source-assembly",
                            "assembly": {"label": "GRCh37"},
                        }
                    ],
                },
            }
        )
