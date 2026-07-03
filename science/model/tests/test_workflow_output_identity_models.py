from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_model.packages.schema import (
    MolecularTierIdentity,
    WorkflowOutput,
    WorkflowOutputAssemblyIdentity,
    WorkflowOutputIdentity,
    WorkflowOutputIdentityInheritFrom,
)


def test_workflow_output_identity_accepts_pass_through_inherit() -> None:
    identity = WorkflowOutputIdentity.model_validate(
        {
            "taxon": "inherit",
            "assembly": "inherit",
            "molecular_ids": {"gene": "inherit"},
        }
    )

    assert identity.taxon == "inherit"
    assert identity.assembly == "inherit"
    assert identity.molecular_ids["gene"] == "inherit"


def test_workflow_output_coerces_identity_contract() -> None:
    output = WorkflowOutput.model_validate(
        {
            "slug": "normalized-expression",
            "title": "Normalized expression matrix",
            "resource_names": ["expression"],
            "ontology_terms": ["EFO:0002770"],
            "schema_profile": "science-pkg-entity-1.0+bio.rnaseq/1.0",
            "identity": {
                "taxon": "inherit",
                "assembly": "inherit",
                "molecular_ids": {"gene": "inherit"},
            },
        }
    )

    assert output.slug == "normalized-expression"
    assert output.resource_names == ["expression"]
    assert output.ontology_terms == ["EFO:0002770"]
    assert output.schema_profile == "science-pkg-entity-1.0+bio.rnaseq/1.0"
    assert output.identity is not None
    assert output.identity.assembly == "inherit"


def test_workflow_output_identity_accepts_explicit_inherit_from() -> None:
    identity = WorkflowOutputIdentity.model_validate(
        {
            "taxon": {"inherit": {"from": "dataset:upstream"}},
            "assembly": {"inherit": {"from": "dataset:upstream"}},
            "molecular_ids": {"gene": {"inherit": {"from": "dataset:upstream"}}},
        }
    )

    assert isinstance(identity.taxon, WorkflowOutputIdentityInheritFrom)
    assert identity.taxon.inherit.from_ == "dataset:upstream"
    dumped = identity.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert dumped["taxon"]["inherit"]["from"] == "dataset:upstream"
    assert dumped["assembly"]["inherit"]["from"] == "dataset:upstream"
    assert dumped["molecular_ids"]["gene"]["inherit"]["from"] == "dataset:upstream"


def test_workflow_output_identity_accepts_symbol_remap_gene_transform() -> None:
    identity = WorkflowOutputIdentity.model_validate(
        {
            "taxon": "inherit",
            "molecular_ids": {
                "gene": {
                    "namespace": "hgnc_symbol",
                    "transform": {
                        "type": "symbol_remap",
                        "from": "input",
                        "dataset": "dataset:gene-crosswalk-hgnc",
                    },
                }
            },
        }
    )

    gene = identity.molecular_ids["gene"]
    assert isinstance(gene, MolecularTierIdentity)
    assert gene.transform is not None
    assert gene.transform.type == "symbol_remap"
    assert gene.transform.from_ == "input"


def test_workflow_output_identity_accepts_liftover_assembly_transform() -> None:
    identity = WorkflowOutputIdentity.model_validate(
        {
            "taxon": "inherit",
            "assembly": {
                "label": "GRCh38",
                "transform": {
                    "type": "liftover",
                    "from": "input",
                    "method": "ucsc_chain",
                    "dataset": "dataset:assembly-liftover-grch37-grch38",
                },
            },
            "molecular_ids": {"variant": "inherit"},
        }
    )

    assert isinstance(identity.assembly, WorkflowOutputAssemblyIdentity)
    assert identity.assembly.transform is not None
    assert identity.assembly.transform.type == "liftover"
    assert identity.assembly.transform.from_ == "input"
    assert identity.molecular_ids["variant"] == "inherit"


def test_workflow_output_identity_accepts_cytoband_proxy_with_sources() -> None:
    identity = WorkflowOutputIdentity.model_validate(
        {
            "taxon": 9606,
            "assembly": {
                "resolution_status": "declared_unresolved",
                "label": "mixed-build-cytoband-proxy",
                "seqcol_digest": "UNKNOWN",
                "registry": "dataset:assembly-registry",
                "proxy": {
                    "type": "cytoband_proxy",
                    "via": "dataset:cytoband-hg19",
                    "sources": [
                        {"dataset": "dataset:gse131651-shah2019-nsd2", "assembly": "inherit"},
                        {"dataset": "dataset:gse87585-wu2017", "assembly": "inherit"},
                    ],
                },
            },
        }
    )

    assert isinstance(identity.assembly, WorkflowOutputAssemblyIdentity)
    assert identity.assembly.proxy is not None
    assert len(identity.assembly.proxy.sources) == 2


def test_workflow_output_identity_rejects_proxy_with_empty_sources() -> None:
    with pytest.raises(ValidationError):
        WorkflowOutputIdentity.model_validate(
            {
                "taxon": 9606,
                "assembly": {
                    "resolution_status": "declared_unresolved",
                    "label": "mixed-build-cytoband-proxy",
                    "seqcol_digest": "UNKNOWN",
                    "registry": "dataset:assembly-registry",
                    "proxy": {
                        "type": "cytoband_proxy",
                        "via": "dataset:cytoband-hg19",
                        "sources": [],
                    },
                },
            }
        )
