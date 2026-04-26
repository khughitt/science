"""End-to-end tests for the unified load flow (registry + adapters)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_model.entities import (
    DatasetEntity,
    DomainEntity,
    Entity,
    EntityType,
    MechanismEntity,
    ProjectEntity,
    TaskEntity,
)
from science_model.identity import EntityScope, ExternalId
from science_model.profiles.schema import EntityKind, ProfileManifest

from science_tool.graph.entity_registry import EntityKindShadowError
from science_tool.graph.errors import EntityIdentityCollisionError
from science_tool.graph.sources import load_project_sources


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: unified\nprofile: research\nprofiles: {local: local}\n",
        encoding="utf-8",
    )


def test_load_produces_typed_entity_instances(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "doc" / "hypotheses").mkdir(parents=True)
    (tmp_path / "doc" / "hypotheses" / "h1.md").write_text(
        '---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\n---\n',
        encoding="utf-8",
    )
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t01] T01\n- type: research\n- priority: P1\n- status: active\n- created: 2026-04-20\n",
        encoding="utf-8",
    )
    sources = load_project_sources(tmp_path)
    by_id = {e.canonical_id: e for e in sources.entities}
    assert isinstance(by_id["hypothesis:h1"], ProjectEntity)
    assert isinstance(by_id["task:t01"], TaskEntity)


def test_load_produces_dataset_entity_for_datapackage(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "data" / "ds1").mkdir(parents=True)
    (tmp_path / "data" / "ds1" / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "name": "ds1",
                "id": "dataset:ds1",
                "type": "dataset",
                "title": "DS1",
                "origin": "external",
                "access": {"level": "public", "verified": False},
            }
        ),
        encoding="utf-8",
    )
    sources = load_project_sources(tmp_path)
    ds = next(e for e in sources.entities if e.canonical_id == "dataset:ds1")
    assert isinstance(ds, DatasetEntity)
    assert ds.origin == "external"


def test_global_identity_collision_across_adapters(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "doc" / "datasets").mkdir(parents=True)
    (tmp_path / "doc" / "datasets" / "x.md").write_text(
        '---\nid: "dataset:x"\ntype: "dataset"\ntitle: "X md"\n'
        'origin: "external"\n'
        'access:\n  level: "public"\n  verified: false\n---\n',
        encoding="utf-8",
    )
    (tmp_path / "data" / "x").mkdir(parents=True)
    (tmp_path / "data" / "x" / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "name": "x",
                "id": "dataset:x",
                "type": "dataset",
                "title": "X dp",
                "origin": "external",
                "access": {"level": "public", "verified": False},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(EntityIdentityCollisionError, match="dataset:x"):
        load_project_sources(tmp_path)


def test_all_entities_inherit_from_entity(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "doc" / "hypotheses").mkdir(parents=True)
    (tmp_path / "doc" / "hypotheses" / "h1.md").write_text(
        '---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\n---\n',
        encoding="utf-8",
    )
    sources = load_project_sources(tmp_path)
    assert all(isinstance(e, Entity) for e in sources.entities)


def test_load_project_sources_reads_lightweight_terms_yaml(tmp_path: Path) -> None:
    _seed(tmp_path)
    local_sources = tmp_path / "knowledge" / "sources" / "local"
    local_sources.mkdir(parents=True)
    (local_sources / "terms.yaml").write_text(
        yaml.safe_dump(
            {
                "terms": [
                    {
                        "id": "concept:treatment-response",
                        "title": "Treatment response",
                        "description": "Lightweight local concept",
                        "content": "ignored body payload",
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    sources = load_project_sources(tmp_path)
    by_id = {entity.canonical_id: entity for entity in sources.entities}
    entity = by_id["concept:treatment-response"]

    assert isinstance(entity, ProjectEntity)
    assert entity.kind == "concept"
    assert entity.type == EntityType.CONCEPT
    assert entity.title == "Treatment response"
    assert entity.content_preview == "Lightweight local concept"
    assert entity.content == ""
    assert entity.file_path == "knowledge/sources/local/terms.yaml"


def test_load_project_sources_returns_typed_mechanism_entity(tmp_path: Path) -> None:
    _seed(tmp_path)
    local_sources = tmp_path / "knowledge" / "sources" / "local"
    local_sources.mkdir(parents=True)
    (local_sources / "entities.yaml").write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {
                        "id": "concept:translation",
                        "kind": "concept",
                        "title": "Translation",
                    },
                    {
                        "id": "concept:cell-state",
                        "kind": "concept",
                        "title": "Cell state",
                    },
                    {
                        "id": "proposition:anti-coupling",
                        "kind": "proposition",
                        "title": "Translation and cell-state programs move in opposite directions",
                    },
                    {
                        "id": "mechanism:anti-coupling-axis",
                        "kind": "mechanism",
                        "title": "Anti-coupling axis",
                        "participants": ["concept:translation", "concept:cell-state"],
                        "propositions": ["proposition:anti-coupling"],
                        "summary": "Translation and cell-state programs move in opposite directions.",
                    },
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    sources = load_project_sources(tmp_path)
    by_id = {entity.canonical_id: entity for entity in sources.entities}
    mechanism = by_id["mechanism:anti-coupling-axis"]

    assert isinstance(mechanism, MechanismEntity)
    assert mechanism.participants == ["concept:translation", "concept:cell-state"]
    assert mechanism.propositions == ["proposition:anti-coupling"]


def test_load_project_sources_preserves_markdown_identity_fields(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: unified\nprofile: research\nprofiles: {local: local}\nontologies: [biology]\n",
        encoding="utf-8",
    )
    (tmp_path / "doc" / "genes").mkdir(parents=True)
    (tmp_path / "doc" / "genes" / "EZH2.md").write_text(
        "\n".join(
            [
                "---",
                'id: "gene:EZH2"',
                'kind: "gene"',
                'title: "EZH2"',
                "primary_external_id:",
                '  source: "HGNC"',
                '  id: "3527"',
                '  curie: "HGNC:3527"',
                '  provenance: "manual"',
                "xrefs:",
                '  - source: "NCBIGene"',
                '    id: "2146"',
                '    curie: "NCBIGene:2146"',
                '    provenance: "manual"',
                'scope: "shared"',
                'deprecated_ids: ["gene:ENX1"]',
                'replaced_by: "gene:EZH2-v2"',
                'taxon: "NCBITaxon:9606"',
                "---",
                "",
                "EZH2 body.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    sources = load_project_sources(tmp_path)
    entity = next(e for e in sources.entities if e.canonical_id == "gene:EZH2")

    assert isinstance(entity, DomainEntity)
    assert entity.primary_external_id == ExternalId(
        source="HGNC",
        id="3527",
        curie="HGNC:3527",
        provenance="manual",
    )
    assert entity.xrefs == [
        ExternalId(
            source="NCBIGene",
            id="2146",
            curie="NCBIGene:2146",
            provenance="manual",
        )
    ]
    assert entity.scope == EntityScope.SHARED
    assert entity.deprecated_ids == ["gene:ENX1"]
    assert entity.replaced_by == "gene:EZH2-v2"
    assert entity.taxon == "NCBITaxon:9606"


def test_load_project_sources_preserves_aggregate_identity_fields(tmp_path: Path) -> None:
    _seed(tmp_path)
    local_sources = tmp_path / "knowledge" / "sources" / "local"
    local_sources.mkdir(parents=True)
    (local_sources / "entities.yaml").write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {
                        "canonical_id": "concept:chromatin",
                        "kind": "concept",
                        "title": "Chromatin",
                        "primary_external_id": {
                            "source": "GO",
                            "id": "0000785",
                            "curie": "GO:0000785",
                            "provenance": "manual",
                        },
                        "xrefs": [
                            {
                                "source": "MeSH",
                                "id": "D002478",
                                "curie": "MeSH:D002478",
                                "provenance": "manual",
                            }
                        ],
                        "scope": "shared",
                        "deprecated_ids": ["concept:chromatin-state"],
                        "replaced_by": "concept:chromatin-remodeling-context",
                        "taxon": "NCBITaxon:9606",
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    sources = load_project_sources(tmp_path)
    entity = next(e for e in sources.entities if e.canonical_id == "concept:chromatin")

    assert isinstance(entity, ProjectEntity)
    assert entity.primary_external_id == ExternalId(
        source="GO",
        id="0000785",
        curie="GO:0000785",
        provenance="manual",
    )
    assert entity.xrefs == [
        ExternalId(
            source="MeSH",
            id="D002478",
            curie="MeSH:D002478",
            provenance="manual",
        )
    ]
    assert entity.scope == EntityScope.SHARED
    assert entity.deprecated_ids == ["concept:chromatin-state"]
    assert entity.replaced_by == "concept:chromatin-remodeling-context"
    assert entity.taxon == "NCBITaxon:9606"


def test_load_normalizes_legacy_parameter_kind(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "doc" / "parameters").mkdir(parents=True)
    (tmp_path / "doc" / "parameters" / "p1.md").write_text(
        '---\nid: "parameter:kcat"\ntype: "parameter"\ntitle: "kcat"\n---\n',
        encoding="utf-8",
    )
    sources = load_project_sources(tmp_path)
    by_id = {e.canonical_id: e for e in sources.entities}
    assert "parameter:kcat" in by_id
    assert by_id["parameter:kcat"].kind == "canonical_parameter"
    assert isinstance(by_id["parameter:kcat"], ProjectEntity)


def test_load_project_sources_accepts_local_gene_entity_when_biology_declared(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: unified\nprofile: research\nprofiles: {local: local}\nontologies: [biology]\n",
        encoding="utf-8",
    )
    (tmp_path / "doc" / "genes").mkdir(parents=True)
    (tmp_path / "doc" / "genes" / "phf19.md").write_text(
        '---\nid: "gene:phf19"\ntype: "gene"\ntitle: "PHF19"\nrelated: ["question:q01"]\n---\n',
        encoding="utf-8",
    )
    (tmp_path / "doc" / "questions").mkdir(parents=True)
    (tmp_path / "doc" / "questions" / "q01.md").write_text(
        '---\nid: "question:q01"\ntype: "question"\ntitle: "Question"\n---\n',
        encoding="utf-8",
    )

    sources = load_project_sources(tmp_path)
    by_id = {e.canonical_id: e for e in sources.entities}

    assert isinstance(by_id["gene:phf19"], DomainEntity)
    assert by_id["gene:phf19"].kind == "gene"
    assert by_id["gene:phf19"].type is None


def test_load_project_sources_skips_local_gene_entity_without_declared_ontology(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "doc" / "genes").mkdir(parents=True)
    (tmp_path / "doc" / "genes" / "phf19.md").write_text(
        '---\nid: "gene:phf19"\ntype: "gene"\ntitle: "PHF19"\n---\n',
        encoding="utf-8",
    )

    sources = load_project_sources(tmp_path)

    assert all(entity.canonical_id != "gene:phf19" for entity in sources.entities)


def test_load_project_sources_preserves_legacy_unknown_type(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "doc").mkdir(exist_ok=True)
    (tmp_path / "doc" / "legacy.md").write_text(
        '---\nid: "unknown:legacy-record"\ntype: "unknown"\ntitle: "Legacy unknown"\n---\n',
        encoding="utf-8",
    )

    sources = load_project_sources(tmp_path)
    by_id = {e.canonical_id: e for e in sources.entities}

    assert by_id["unknown:legacy-record"].kind == "unknown"
    assert by_id["unknown:legacy-record"].type == EntityType.UNKNOWN


def test_load_project_sources_raises_when_catalog_collides_with_profile_kind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(tmp_path)
    (tmp_path / "science.yaml").write_text(
        "name: unified\nprofile: research\nprofiles: {local: local}\nontologies: [biology]\n",
        encoding="utf-8",
    )
    shared_profile = ProfileManifest(
        name="shared",
        imports=["core"],
        strictness="curated",
        entity_kinds=[
            EntityKind(
                name="gene",
                canonical_prefix="gene",
                layer="layer/shared",
                description="Shared gene profile kind.",
            )
        ],
        relation_kinds=[],
    )
    monkeypatch.setattr("science_tool.graph.sources.load_shared_profile", lambda: shared_profile)

    with pytest.raises(EntityKindShadowError, match="gene"):
        load_project_sources(tmp_path)


def test_load_project_sources_allows_duplicate_kind_names_across_catalogs(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: unified\nprofile: research\nprofiles: {local: local}\nontologies: [physics, units]\n",
        encoding="utf-8",
    )
    local_sources = tmp_path / "knowledge" / "sources" / "local"
    local_sources.mkdir(parents=True)
    (local_sources / "entities.yaml").write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {
                        "canonical_id": "electric_field:test-field",
                        "kind": "electric_field",
                        "title": "Test field",
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    sources = load_project_sources(tmp_path)
    entity = next(e for e in sources.entities if e.canonical_id == "electric_field:test-field")

    assert isinstance(entity, DomainEntity)
    assert entity.kind == "electric_field"


def test_load_project_sources_reads_repo_local_profile_manifest(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: unified\nprofile: research\nknowledge_profiles:\n  local: cbioportal\n",
        encoding="utf-8",
    )
    local_sources = tmp_path / "knowledge" / "sources" / "cbioportal"
    local_sources.mkdir(parents=True)
    (local_sources / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "cbioportal-local",
                "imports": ["core"],
                "strictness": "typed-extension",
                "entity_kinds": [
                    {
                        "name": "meta",
                        "canonical_prefix": "meta",
                        "layer": "layer/local",
                        "description": "Project-local meta document kind.",
                    }
                ],
                "relation_kinds": [],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "doc" / "meta").mkdir(parents=True)
    (tmp_path / "doc" / "meta" / "next-steps.md").write_text(
        '---\nid: "meta:next-steps"\ntype: "meta"\ntitle: "Next steps"\n---\n',
        encoding="utf-8",
    )

    sources = load_project_sources(tmp_path)
    by_id = {entity.canonical_id: entity for entity in sources.entities}

    assert isinstance(by_id["meta:next-steps"], ProjectEntity)
    assert by_id["meta:next-steps"].kind == "meta"
    assert by_id["meta:next-steps"].type is None
    assert by_id["meta:next-steps"].profile == "cbioportal"


def test_load_project_sources_raises_when_repo_local_manifest_shadows_catalog_kind(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: unified\nprofile: research\nknowledge_profiles:\n  local: cbioportal\nontologies: [biology]\n",
        encoding="utf-8",
    )
    local_sources = tmp_path / "knowledge" / "sources" / "cbioportal"
    local_sources.mkdir(parents=True)
    (local_sources / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "cbioportal-local",
                "imports": ["core"],
                "strictness": "typed-extension",
                "entity_kinds": [
                    {
                        "name": "gene",
                        "canonical_prefix": "gene",
                        "layer": "layer/local",
                        "description": "Incorrect project-local shadow of a catalog kind.",
                    }
                ],
                "relation_kinds": [],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(EntityKindShadowError, match="gene"):
        load_project_sources(tmp_path)
