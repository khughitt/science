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
    ThemeEntity,
)
from science_model.identity import EntityScope, ExternalId
from science_model.profiles.schema import EntityKind, ProfileManifest
from science_model.source_contracts import BindingSource

from science_tool.graph.entity_registry import EntityKindShadowError
from science_tool.graph.errors import EntityIdentityCollisionError
from science_tool.graph.identity_table import build_identity_table
from science_tool.graph.sources import load_project_sources


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: unified\nprofile: research\nprofiles: {local: local}\n",
        encoding="utf-8",
    )


def test_load_produces_typed_entity_instances(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "entities" / "hypotheses").mkdir(parents=True)
    (tmp_path / "entities" / "hypotheses" / "h1.md").write_text(
        '---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\n---\n',
        encoding="utf-8",
    )
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t001] T001\n- type: research\n- priority: P1\n- status: active\n- created: 2026-04-20\n",
        encoding="utf-8",
    )
    sources = load_project_sources(tmp_path)
    by_id = {e.canonical_id: e for e in sources.entities}
    assert isinstance(by_id["hypothesis:h1"], ProjectEntity)
    assert isinstance(by_id["task:t001"], TaskEntity)


def test_legacy_typed_sources_are_parsed_once_per_load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import science_tool.graph.sources as sources_module

    _seed(tmp_path)
    local_sources = tmp_path / "knowledge" / "sources" / "local"
    local_sources.mkdir(parents=True)
    (local_sources / "models.yaml").write_text(
        "\n".join(
            [
                "models:",
                "  - canonical_id: model:m1",
                "    title: Model 1",
                "    profile: local",
                "    source_path: knowledge/sources/local/models.yaml",
                "    relations:",
                "      - predicate: sci:approximates",
                "        target: model:m2",
                "  - canonical_id: model:m2",
                "    title: Model 2",
                "    profile: local",
                "    source_path: knowledge/sources/local/models.yaml",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (local_sources / "parameters.yaml").write_text(
        "\n".join(
            [
                "parameters:",
                "  - canonical_id: parameter:p1",
                "    title: Parameter 1",
                "    symbol: p",
                "    profile: local",
                "    source_path: knowledge/sources/local/parameters.yaml",
                "    relations:",
                "      - predicate: sci:partOf",
                "        target: model:m1",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (local_sources / "bindings.yaml").write_text(
        "\n".join(
            [
                "bindings:",
                "  - model: model:m1",
                "    parameter: parameter:p1",
                "    source_path: knowledge/sources/local/bindings.yaml",
                "",
            ]
        ),
        encoding="utf-8",
    )

    parse_counts = {"models": 0, "parameters": 0, "bindings": 0}
    real_load = sources_module.yaml.load

    def counted_load(text: str, *args: object, Loader: object | None = None):
        if "models:" in text and "model:m1" in text:
            parse_counts["models"] += 1
        elif "parameters:" in text and "parameter:p1" in text:
            parse_counts["parameters"] += 1
        elif "bindings:" in text and "parameter:p1" in text:
            parse_counts["bindings"] += 1
        if Loader is not None:
            return real_load(text, Loader=Loader)
        return real_load(text, *args)

    monkeypatch.setattr(sources_module.yaml, "load", counted_load)

    sources = sources_module.load_project_sources(tmp_path)

    assert {"model:m1", "model:m2", "parameter:p1"} <= {entity.canonical_id for entity in sources.entities}
    assert parse_counts == {"models": 1, "parameters": 1, "bindings": 1}


def test_typed_records_use_c_safe_loader_when_available(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import science_tool.graph.sources as sources_module

    _seed(tmp_path)
    local_sources = tmp_path / "knowledge" / "sources" / "local"
    local_sources.mkdir(parents=True)
    (local_sources / "bindings.yaml").write_text("bindings: []\n", encoding="utf-8")
    loader_calls: list[object] = []

    def fake_load(_text: str, *args: object, Loader: object | None = None) -> dict[str, object]:
        loader_calls.append(Loader if Loader is not None else args[0])
        return {
            "bindings": [
                {
                    "model": "model:m1",
                    "parameter": "parameter:p1",
                    "source_path": "knowledge/sources/local/bindings.yaml",
                }
            ]
        }

    monkeypatch.setattr(sources_module.yaml, "load", fake_load)

    records = sources_module._load_typed_records(
        tmp_path,
        local_profile="local",
        file_name="bindings.yaml",
        root_key="bindings",
        model=BindingSource,
    )

    assert len(records) == 1
    assert loader_calls == [sources_module.yaml.CSafeLoader]


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


def test_orphan_datapackage_synthesizes_deprecated_owner(tmp_path: Path) -> None:
    # An orphan datapackage (no owner of the same id) keeps loading as a deprecated,
    # transitional owner (design §B4 rollout) so datapackage-only datasets are not
    # dropped before migration.
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
    owners = [d for d in sources.identity_declarations if d.canonical_id == "dataset:ds1"]
    assert len(owners) == 1
    assert owners[0].adapter == "datapackage"
    assert owners[0].deprecated is True


def test_datapackage_defers_to_markdown_owner(tmp_path: Path) -> None:
    # §B4: a datapackage is attached resource metadata, NOT a second owner. With a
    # real markdown owner of the same id, the datapackage DEFERS — markdown wins,
    # no competing owner row, no collision (this scenario used to raise).
    _seed(tmp_path)
    (tmp_path / "entities" / "datasets").mkdir(parents=True)
    (tmp_path / "entities" / "datasets" / "x.md").write_text(
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
    sources = load_project_sources(tmp_path)  # must NOT raise
    ds = next(e for e in sources.entities if e.canonical_id == "dataset:x")
    assert ds.title == "X md"  # the markdown owner won
    owners = [d for d in sources.identity_declarations if d.canonical_id == "dataset:x"]
    assert len(owners) == 1
    assert owners[0].adapter == "markdown" and owners[0].deprecated is False
    assert build_identity_table(sources).collisions() == []


def test_datapackage_defers_to_aggregate_stub_owner(tmp_path: Path) -> None:
    # §B4: a datapackage defers to ANY existing same-scope owner, including a
    # transitional entities.yaml aggregate stub. This previously strict-crashed
    # (EntityIdentityCollisionError); now the aggregate stub remains the (deprecated)
    # owner, the datapackage defers, nothing collides, and §B5 retires the stub later.
    _seed(tmp_path)
    (tmp_path / "knowledge" / "sources" / "local").mkdir(parents=True, exist_ok=True)
    (tmp_path / "knowledge" / "sources" / "local" / "entities.yaml").write_text(
        "entities:\n"
        '  - canonical_id: "dataset:x"\n'
        '    kind: "dataset"\n'
        '    title: "X agg"\n'
        '    origin: "external"\n'
        "    access:\n"
        '      level: "public"\n'
        "      verified: false\n",
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
    sources = load_project_sources(tmp_path)  # must NOT raise (was a strict crash)
    owners = [d for d in sources.identity_declarations if d.canonical_id == "dataset:x"]
    assert len(owners) == 1
    assert owners[0].adapter == "aggregate" and owners[0].deprecated is True  # stub owns; dp deferred
    assert build_identity_table(sources).collisions() == []


def test_global_identity_collision_two_markdown_owners(tmp_path: Path) -> None:
    # Two REAL markdown owners of one id are a genuine duplicate identity
    # declaration and still raise under strict (the §B4 datapackage deferral does
    # not apply — only DatapackageAdapter defers).
    _seed(tmp_path)
    (tmp_path / "entities" / "datasets").mkdir(parents=True)
    (tmp_path / "entities" / "datasets" / "x.md").write_text(
        '---\nid: "dataset:x"\ntype: "dataset"\ntitle: "X md"\n'
        'origin: "external"\n'
        'access:\n  level: "public"\n  verified: false\n---\n',
        encoding="utf-8",
    )
    (tmp_path / "entities" / "datasets" / "x2.md").write_text(
        '---\nid: "dataset:x"\ntype: "dataset"\ntitle: "X md 2"\n'
        'origin: "external"\n'
        'access:\n  level: "public"\n  verified: false\n---\n',
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


def test_load_project_sources_includes_research_question_with_rq_prefix(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "entities").mkdir()
    (tmp_path / "entities" / "research-question.md").write_text(
        "\n".join(
            [
                "---",
                'id: "rq:test"',
                'type: "research-question"',
                'title: "Master research question"',
                'related: ["hypothesis:h1"]',
                "source_refs: []",
                "---",
                "",
                "# Master research question",
                "",
            ]
        ),
        encoding="utf-8",
    )

    sources = load_project_sources(tmp_path)
    by_id = {entity.canonical_id: entity for entity in sources.entities}
    entity = by_id["rq:test"]

    assert isinstance(entity, ProjectEntity)
    assert entity.kind == "research-question"
    assert entity.type == EntityType.RESEARCH_QUESTION
    assert entity.related == ["hypothesis:h1"]


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


def test_load_project_sources_returns_typed_theme_entity(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "entities" / "themes").mkdir(parents=True)
    (tmp_path / "entities" / "themes" / "transportability.md").write_text(
        "\n".join(
            [
                "---",
                'id: "theme:transportability"',
                'type: "theme"',
                'title: "Transportability"',
                'status: "active"',
                'theme_kind: "methodological"',
                'theme_scope: "federation"',
                'related: ["question:q001-recurring"]',
                "source_refs: []",
                "evidence_refs: []",
                "---",
                "",
                "# Theme: Transportability",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "entities" / "questions").mkdir(parents=True)
    (tmp_path / "entities" / "questions" / "q001-recurring.md").write_text(
        "\n".join(
            [
                "---",
                'id: "question:q001-recurring"',
                'type: "question"',
                'title: "What recurs?"',
                "related: []",
                "source_refs: []",
                "---",
                "",
            ]
        ),
        encoding="utf-8",
    )

    sources = load_project_sources(tmp_path)
    by_id = {entity.canonical_id: entity for entity in sources.entities}
    theme = by_id["theme:transportability"]

    assert isinstance(theme, ThemeEntity)
    assert theme.kind == "theme"
    assert theme.type == EntityType.THEME
    assert theme.theme_kind == "methodological"
    assert theme.theme_scope == "federation"


def test_load_project_sources_rejects_invalid_reasoning_enum(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    (tmp_path / "entities" / "propositions" / "p1.md").write_text(
        "\n".join(
            [
                "---",
                'id: "proposition:p1"',
                'type: "proposition"',
                'title: "P1"',
                'claim_layer: "legacy-causal"',
                "related: []",
                "source_refs: []",
                "---",
                "",
                "Body.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid reasoning metadata"):
        load_project_sources(tmp_path)


def test_load_project_sources_preserves_markdown_identity_fields(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: unified\nprofile: research\nprofiles: {local: local}\nontologies: [biology]\n",
        encoding="utf-8",
    )
    (tmp_path / "entities" / "genes").mkdir(parents=True)
    (tmp_path / "entities" / "genes" / "EZH2.md").write_text(
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
    (tmp_path / "entities" / "parameters").mkdir(parents=True)
    (tmp_path / "entities" / "parameters" / "p1.md").write_text(
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
    (tmp_path / "entities" / "genes").mkdir(parents=True)
    (tmp_path / "entities" / "genes" / "phf19.md").write_text(
        '---\nid: "gene:phf19"\ntype: "gene"\ntitle: "PHF19"\nrelated: ["question:q01"]\n---\n',
        encoding="utf-8",
    )
    (tmp_path / "entities" / "questions").mkdir(parents=True)
    (tmp_path / "entities" / "questions" / "q01.md").write_text(
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
    (tmp_path / "entities").mkdir(exist_ok=True)
    (tmp_path / "entities" / "legacy.md").write_text(
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
    (tmp_path / "entities" / "meta").mkdir(parents=True)
    (tmp_path / "entities" / "meta" / "next-steps.md").write_text(
        '---\nid: "meta:next-steps"\ntype: "meta"\ntitle: "Next steps"\n---\n',
        encoding="utf-8",
    )

    sources = load_project_sources(tmp_path)
    by_id = {entity.canonical_id: entity for entity in sources.entities}

    assert isinstance(by_id["meta:next-steps"], ProjectEntity)
    assert by_id["meta:next-steps"].kind == "meta"
    assert by_id["meta:next-steps"].type is None
    assert by_id["meta:next-steps"].profile == "cbioportal"


def test_load_project_sources_skips_invalid_repo_local_profile_entity(tmp_path: Path) -> None:
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
                        "name": "labnote",
                        "canonical_prefix": "labnote",
                        "layer": "layer/local",
                        "description": "Project-local lab note kind.",
                    }
                ],
                "relation_kinds": [],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "entities" / "notes").mkdir(parents=True)
    (tmp_path / "entities" / "notes" / "labnote.md").write_text(
        '---\nid: "labnote:rollup"\ntype: "labnote"\n---\n',
        encoding="utf-8",
    )
    (tmp_path / "entities" / "hypotheses").mkdir(parents=True)
    (tmp_path / "entities" / "hypotheses" / "h1.md").write_text(
        '---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\n---\n',
        encoding="utf-8",
    )

    sources = load_project_sources(tmp_path)
    by_id = {entity.canonical_id: entity for entity in sources.entities}

    assert "hypothesis:h1" in by_id
    assert "labnote:rollup" not in by_id


def test_load_project_sources_local_kind_graduated_to_core_does_not_crash(tmp_path: Path) -> None:
    """A local manifest declaring a kind that has since become core must not crash.

    `synthesis` was promoted from a project-local extension kind to a core kind.
    Projects whose local manifest still declares it must keep loading: the core
    definition wins, the stale declaration is skipped, and the skip is surfaced
    as a SkippedEntity so the project can clean up its manifest.
    """
    (tmp_path / "science.yaml").write_text(
        "name: unified\nprofile: research\nknowledge_profiles:\n  local: meta-local\n",
        encoding="utf-8",
    )
    local_sources = tmp_path / "knowledge" / "sources" / "meta-local"
    local_sources.mkdir(parents=True)
    manifest_rel = "knowledge/sources/meta-local/manifest.yaml"
    (local_sources / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "meta-local",
                "imports": ["core"],
                "strictness": "typed-extension",
                "entity_kinds": [
                    {
                        "name": "synthesis",
                        "canonical_prefix": "synthesis",
                        "layer": "layer/local",
                        "entity_class": "epistemic",
                        "description": "Stale local declaration of a now-core kind.",
                    }
                ],
                "relation_kinds": [],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "entities" / "synthesis").mkdir(parents=True)
    (tmp_path / "entities" / "synthesis" / "rollup.md").write_text(
        '---\nid: "synthesis:rollup"\ntype: "synthesis"\ntitle: "Rollup"\n---\n',
        encoding="utf-8",
    )

    sources = load_project_sources(tmp_path)
    by_id = {entity.canonical_id: entity for entity in sources.entities}

    # The synthesis entity still loads, resolved against the core kind.
    assert isinstance(by_id["synthesis:rollup"], ProjectEntity)
    assert by_id["synthesis:rollup"].kind == "synthesis"
    # The stale local declaration is surfaced as a skip pointing at the manifest.
    graduated = [s for s in sources.skipped_entities if s.reason == "kind_graduated_to_core"]
    assert len(graduated) == 1
    assert graduated[0].kind == "synthesis"
    assert manifest_rel in graduated[0].path


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


def test_dataset_datapackages_records_deferred_datapackage_path(tmp_path: Path) -> None:
    # A real markdown dataset owner + a same-id datapackage.yaml. The datapackage
    # defers (§B4); its path must be recorded on ProjectSources.dataset_datapackages
    # so the geneset member gate can find it after the markdown owner wins.
    _seed(tmp_path)
    (tmp_path / "entities" / "datasets").mkdir(parents=True)
    (tmp_path / "entities" / "datasets" / "x.md").write_text(
        "---\n"
        'id: "dataset:x"\n'
        'type: "dataset"\n'
        'title: "X md"\n'
        'status: "active"\n'
        'origin: "external"\n'
        "access:\n"
        '  level: "public"\n'
        "  verified: false\n"
        'created: "2026-01-01"\n'
        'updated: "2026-01-01"\n'
        "---\n",
        encoding="utf-8",
    )
    (tmp_path / "data" / "x").mkdir(parents=True)
    (tmp_path / "data" / "x" / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "id": "dataset:x",
                "type": "dataset",
                "title": "X dp",
                "status": "active",
                "origin": "external",
                "access": {"level": "public", "verified": False},
            }
        ),
        encoding="utf-8",
    )
    # Non-strict mirrors the diagnostic load the orphan-check / promotion consumers
    # use; deferral happens in the adapter loop regardless of strictness.
    sources = load_project_sources(tmp_path, include_commons=False, strict_core_schema=False, strict_identity=False)
    assert sources.dataset_datapackages == {"dataset:x": "data/x/datapackage.yaml"}
    assert sources.entity_source_adapters["dataset:x"] == "markdown"


def test_dataset_datapackages_excludes_true_orphan(tmp_path: Path) -> None:
    # A datapackage with no entity-file owner IS the owner (a true orphan). It is
    # not "deferred", so it must NOT appear in dataset_datapackages.
    _seed(tmp_path)
    (tmp_path / "data" / "y").mkdir(parents=True)
    (tmp_path / "data" / "y" / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "id": "dataset:y",
                "type": "dataset",
                "title": "Y dp",
                "status": "active",
                "origin": "external",
                "access": {"level": "public", "verified": False},
            }
        ),
        encoding="utf-8",
    )
    # Non-strict mirrors the diagnostic load the orphan-check / promotion consumers use.
    sources = load_project_sources(tmp_path, include_commons=False, strict_core_schema=False, strict_identity=False)
    assert "dataset:y" not in sources.dataset_datapackages
    assert sources.entity_source_adapters["dataset:y"] == "datapackage"
