from __future__ import annotations

import textwrap
from pathlib import Path

from science_model.entities import EntityType, WorkflowEntity
from science_model.frontmatter import parse_entity_file


def test_workflow_frontmatter_coerces_outputs_identity(tmp_path: Path) -> None:
    path = tmp_path / "entities" / "workflows" / "normalize-expression.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(
            """
            ---
            id: "workflow:normalize-expression"
            type: "workflow"
            title: "Normalize expression"
            status: "active"
            method: "method:normalization"
            outputs:
              - slug: "normalized-expression"
                title: "Normalized expression matrix"
                resource_names: ["expression"]
                ontology_terms: ["EFO:0002770"]
                schema_profile: "science-pkg-entity-1.0+bio.rnaseq/1.0"
                identity:
                  taxon: inherit
                  assembly: inherit
                  molecular_ids:
                    gene:
                      namespace: "hgnc_symbol"
                      transform:
                        type: "symbol_remap"
                        from: "input"
                        dataset: "dataset:gene-crosswalk-hgnc"
            created: "2026-07-02"
            updated: "2026-07-02"
            ---

            ## Purpose

            Normalize expression values.
            """
        ).lstrip(),
        encoding="utf-8",
    )

    entity = parse_entity_file(path, project_slug="demo")

    assert isinstance(entity, WorkflowEntity)
    assert entity.type == EntityType.WORKFLOW
    assert entity.outputs[0].slug == "normalized-expression"
    assert entity.outputs[0].identity is not None
    gene = entity.outputs[0].identity.molecular_ids["gene"]
    assert gene != "inherit"
    assert gene.transform is not None
    assert gene.transform.from_ == "input"
