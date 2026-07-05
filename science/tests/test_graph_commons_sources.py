from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from science_model.entities import DatasetEntity, Entity, PaperEntity, ThemeEntity
from science_model.identity import EntityScope
from science_model.source_contracts import BindingSource
from science_model.source_ref import SourceRef

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.errors import CommonsEntityError, CommonsRootNotFoundError, OverlayValidationError
from science_tool.commons.overlay import MergedEntity
from science_tool.commons.registry import RegistryBuilder
from science_tool.graph.commons_sources import (
    _OVERLAY_ONLY_FIELDS,
    _load_commons_referenced_entities,
    _materialize_commons_entity,
    collect_referenced_commons_ids,
)
from science_tool.graph.entity_registry import EntityRegistry
from science_tool.graph.sources import SourceRelation, load_project_sources

_COMMONS_FIXTURE = Path(__file__).parent / "fixtures" / "commons" / "valid"


def _build_commons(tmp_path: Path) -> Path:
    commons_root = tmp_path / "commons"
    shutil.copytree(_COMMONS_FIXTURE, commons_root)
    RegistryBuilder(commons_root, CommonsEntityAdapter(commons_root)).rebuild()
    return commons_root


def _entity(
    canonical_id: str,
    *,
    related: list[str] | None = None,
    source_refs: list[str] | None = None,
) -> Entity:
    kind = canonical_id.split(":", 1)[0]
    return Entity.model_validate(
        {
            "id": canonical_id,
            "kind": kind,
            "type": kind,
            "title": canonical_id,
            "project": "demo",
            "ontology_terms": [],
            "related": related or [],
            "source_refs": source_refs or [],
            "content_preview": "",
            "file_path": "",
        }
    )


def _collect(
    *,
    entities: list[object] | None = None,
    relations: list[SourceRelation] | None = None,
    bindings: list[BindingSource] | None = None,
) -> set[str]:
    return collect_referenced_commons_ids(
        project_entities=cast(list[Entity], entities or []),
        project_relations=relations or [],
        project_bindings=bindings or [],
    )


def _load_commons(
    project_root: Path,
    *,
    project_entities: list[Entity] | None = None,
    identity_table: dict[str, SourceRef] | None = None,
) -> tuple[list[tuple[Entity, SourceRef]], dict[str, str]]:
    loaded, overlay_paths, _collisions = _load_commons_referenced_entities(
        project_root=project_root,
        project_slug="demo",
        project_entities=project_entities or [],
        project_relations=[],
        project_bindings=[],
        identity_table=identity_table or {},
        registry=EntityRegistry.with_core_types(),
        active_kinds=frozenset({"dataset", "paper", "theme", "topic"}),
        ontology_catalogs=[],
    )
    return loaded, overlay_paths


def test_collect_referenced_commons_ids_returns_empty_set_for_no_references() -> None:
    assert _collect(entities=[_entity("concept:local")]) == set()


def test_collect_referenced_commons_ids_collects_entity_related() -> None:
    assert _collect(entities=[_entity("concept:local", related=["paper:smith2024"])]) == {"paper:smith2024"}


def test_collect_referenced_commons_ids_collects_entity_source_refs() -> None:
    assert _collect(entities=[_entity("concept:local", source_refs=["dataset:rnaseq"])]) == {"dataset:rnaseq"}


def test_collect_referenced_commons_ids_collects_b1_entity_usage_refs() -> None:
    paper = SimpleNamespace(
        kind="paper",
        dataset_usage=[SimpleNamespace(ref="dataset:authored")],
        datasets=["dataset:legacy"],
    )
    derived = SimpleNamespace(kind="dataset", derivation=SimpleNamespace(inputs=["dataset:upstream"]))

    assert _collect(entities=[paper, derived]) == {"dataset:authored", "dataset:legacy", "dataset:upstream"}


@pytest.mark.parametrize(
    ("field_name", "reference"),
    [
        ("evidence_refs", "paper:evidence"),
        ("commits_to", "theme:program"),
        ("blocked_by", "topic:blocker"),
        ("chain", "paper:chain"),
        ("proposition_refs", "dataset:derived"),
        ("same_as", "topic:equivalent"),
        ("participants", "theme:participant"),
        ("propositions", "paper:proposition"),
    ],
)
def test_collect_referenced_commons_ids_collects_list_fields(field_name: str, reference: str) -> None:
    entity = SimpleNamespace(**{field_name: [reference]})

    assert _collect(entities=[entity]) == {reference}


def test_collect_referenced_commons_ids_collects_singular_audits_field() -> None:
    assert _collect(entities=[SimpleNamespace(audits="paper:audit")]) == {"paper:audit"}


def test_collect_referenced_commons_ids_collects_relation_endpoints() -> None:
    relation = SourceRelation(
        subject="paper:subject",
        predicate="supports",
        object="topic:object",
        source_path="knowledge/sources/local/relations.yaml",
    )

    assert _collect(relations=[relation]) == {"paper:subject", "topic:object"}


def test_collect_referenced_commons_ids_collects_binding_model_parameter_and_source_refs() -> None:
    binding = BindingSource(
        model="paper:model",
        parameter="topic:parameter",
        source_path="knowledge/sources/local/bindings.yaml",
        source_refs=["dataset:inputs", "theme:context"],
    )

    assert _collect(bindings=[binding]) == {
        "paper:model",
        "topic:parameter",
        "dataset:inputs",
        "theme:context",
    }


def test_collect_referenced_commons_ids_filters_to_commons_types() -> None:
    entity = SimpleNamespace(
        related=[
            "dataset:rnaseq",
            "paper:smith2024",
            "topic:phf19",
            "theme:reproducibility",
            "concept:local",
            "hypothesis:h1",
            "model:m1",
        ]
    )

    assert _collect(entities=[entity]) == {
        "dataset:rnaseq",
        "paper:smith2024",
        "topic:phf19",
        "theme:reproducibility",
    }


def test_collect_referenced_commons_ids_ignores_empty_commons_local_parts() -> None:
    entity = SimpleNamespace(related=["paper:", "dataset:", "topic:", "topic:phf19"])

    assert _collect(entities=[entity]) == {"topic:phf19"}


def test_collect_referenced_commons_ids_ignores_external_ontology_and_metadata_refs() -> None:
    entity = SimpleNamespace(
        related=[
            "https://example.org/source",
            "/tmp/results.csv",
            "./local.csv",
            "../parent.csv",
            "results/table.csv",
            "doi:10.1000/example",
            "go:0008150",
            "meta:reviewed",
            "paper",
            "",
            None,
            "topic:phf19",
        ]
    )

    assert _collect(entities=[entity]) == {"topic:phf19"}


@dataclass(frozen=True)
class _StubCanonical:
    canonical_id: str
    type: str
    slug: str
    schema_profile: str
    frontmatter: dict[str, object]
    body_path: Path
    datapackage_path: Path | None = None
    mtime_ns: int = 0


def _merged(frontmatter: dict[str, object]) -> MergedEntity:
    canonical_id = str(frontmatter["id"])
    kind = str(frontmatter.get("kind") or frontmatter.get("type"))
    canonical = _StubCanonical(
        canonical_id=canonical_id,
        type=kind,
        slug=canonical_id.split(":", 1)[-1],
        schema_profile="shared",
        frontmatter=frontmatter,
        body_path=Path("commons") / kind / f"{canonical_id.split(':', 1)[-1]}.md",
    )
    return MergedEntity(
        canonical=canonical,  # type: ignore[arg-type]
        overlay=None,
        merged_frontmatter=frontmatter,
        merged_body="",
        field_sources={},
    )


def _translate(frontmatter: dict[str, object]) -> Entity:
    return _materialize_commons_entity(
        _merged(frontmatter),
        registry=EntityRegistry.with_core_types(),
        project_slug="demo",
        active_kinds=frozenset({"dataset", "paper", "theme", "topic"}),
        ontology_catalogs=[],
    )


def test_translate_topic_sets_scope_shared() -> None:
    entity = _translate({"id": "topic:phf19", "kind": "topic", "title": "PHF19"})

    assert entity.scope == EntityScope.SHARED
    assert entity.canonical_id == "topic:phf19"
    assert entity.kind == "topic"
    assert entity.title == "PHF19"
    assert entity.file_path == "commons/topic/phf19.md"


def test_translate_commons_record_accepts_kind_without_type() -> None:
    entity = _translate({"id": "paper:Persi2025", "kind": "paper", "title": "Persi 2025"})

    assert isinstance(entity, PaperEntity)
    assert entity.kind == "paper"
    assert entity.canonical_id == "paper:Persi2025"


def test_translate_commons_record_rejects_type_without_kind() -> None:
    with pytest.raises(CommonsEntityError, match="missing kind"):
        _translate({"id": "paper:Persi2025", "type": "paper", "title": "Persi 2025"})


def test_translate_topic_description_flows_to_content_preview() -> None:
    description = "Shared topic description."

    entity = _translate({"id": "topic:phf19", "kind": "topic", "title": "PHF19", "description": description})

    assert not hasattr(entity, "summary")
    assert entity.content_preview == description


def test_translate_theme_description_flows_to_summary() -> None:
    description = "Shared theme description."

    entity = _translate({"id": "theme:program", "kind": "theme", "title": "Program", "description": description})

    assert isinstance(entity, ThemeEntity)
    assert entity.summary == description


def test_translate_dataset_carries_mixin_fields() -> None:
    entity = _translate(
        {
            "id": "dataset:rnaseq",
            "kind": "dataset",
            "title": "RNA-seq",
            "origin": "external",
            "access": {"level": "public", "verified": False},
            "accessions": ["GSE123"],
            "datapackage": "datapackage.json",
            "tier": "use-now",
            "update_cadence": "static",
        }
    )

    assert isinstance(entity, DatasetEntity)
    assert entity.origin == "external"
    assert entity.access is not None
    assert entity.access.level == "public"
    assert entity.accessions == ["GSE123"]
    assert entity.datapackage == "datapackage.json"
    assert entity.tier == "use-now"
    assert entity.update_cadence == "static"


def test_translate_derived_dataset_accepts_commons_workflow_recipe_derivation() -> None:
    entity = _translate(
        {
            "id": "dataset:clean-base",
            "kind": "dataset",
            "title": "Clean base",
            "origin": "derived",
            "datapackage": "datapackage.yaml",
            "tier": "use-now",
            "source_class": "observational",
            "derivation": {
                "kind": "workflow",
                "workflow_recipe": "workflow:h07-fidelity",
                "inputs": ["dataset:raw-source"],
                "recipe_lockfile": "workflows/h07-fidelity/config.yaml",
            },
        }
    )

    assert isinstance(entity, DatasetEntity)
    assert entity.origin == "derived"
    assert entity.derivation is not None
    assert getattr(entity.derivation, "kind") == "workflow"
    assert getattr(entity.derivation, "workflow_recipe") == "workflow:h07-fidelity"
    assert getattr(entity.derivation, "inputs") == ["dataset:raw-source"]


def test_translate_paper_carries_mixin_fields() -> None:
    entity = _translate(
        {
            "id": "paper:Adams2025",
            "kind": "paper",
            "title": "Adams paper",
            "bibkey": "Adams2025",
            "authors": ["Adams, A.", "Baker, B."],
            "year": 2025,
            "venue": "Science",
            "doi": "10.1000/adams.2025",
            "key_findings": ["Finding one", "Finding two"],
            "methods_summary": "Measured representative samples.",
            "limitations": ["Small cohort"],
        }
    )

    assert isinstance(entity, PaperEntity)
    assert entity.bibkey == "Adams2025"
    assert entity.authors == ["Adams, A.", "Baker, B."]
    assert entity.year == 2025
    assert entity.venue == "Science"
    assert entity.doi == "10.1000/adams.2025"
    assert entity.key_findings == ["Finding one", "Finding two"]
    assert entity.methods_summary == "Measured representative samples."
    assert entity.limitations == ["Small cohort"]


def test_translate_paper_legacy_journal_flows_to_venue() -> None:
    entity = _translate(
        {
            "id": "paper:Adams2025",
            "kind": "paper",
            "title": "Adams paper",
            "schema_profile": "science-entity-base/1.0+paper/1.0",
            "bibkey": "Adams2025",
            "journal": "Nature Methods",
        }
    )

    assert isinstance(entity, PaperEntity)
    assert entity.venue == "Nature Methods"


def test_translate_theme_with_cross_project_scope() -> None:
    entity = _translate(
        {
            "id": "theme:program",
            "kind": "theme",
            "title": "Program",
            "theme_kind": "conceptual",
            "theme_scope": "cross-project",
        }
    )

    assert isinstance(entity, ThemeEntity)
    assert entity.theme_kind == "conceptual"
    assert entity.theme_scope == "cross-project"


def test_translate_drops_overlay_only_fields() -> None:
    assert set(_OVERLAY_ONLY_FIELDS) == {
        "relevance",
        "hypothesis_links",
        "task_links",
        "question_links",
        "project_tags",
        "project_notes",
        "source",
    }
    entity = _translate(
        {
            "id": "topic:phf19",
            "kind": "topic",
            "title": "PHF19",
            "relevance": "high",
            "hypothesis_links": ["hypothesis:h1"],
            "task_links": ["task:t1"],
            "question_links": ["question:q1"],
            "project_tags": ["tag"],
            "project_notes": "note",
            "source": "overlay",
        }
    )

    for field_name in _OVERLAY_ONLY_FIELDS:
        assert not hasattr(entity, field_name)


def test_orchestrator_loads_referenced_topic_from_commons_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = tmp_path / "project"
    project_root.mkdir()

    loaded, overlay_paths = _load_commons(
        project_root,
        project_entities=[_entity("topic:local", related=["topic:single-cell-foundation-models"])],
    )

    assert overlay_paths == {}
    assert len(loaded) == 1
    entity, ref = loaded[0]
    assert entity.canonical_id == "topic:single-cell-foundation-models"
    assert entity.scope == EntityScope.SHARED
    assert ref.adapter_name == "commons-merged"
    assert ref.path == "commons://topics/single-cell-foundation-models.md"


def test_orchestrator_skips_referenced_missing_canonical(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = tmp_path / "project"
    project_root.mkdir()

    loaded, overlay_paths = _load_commons(
        project_root,
        project_entities=[_entity("topic:local", related=["topic:does-not-exist"])],
    )

    assert loaded == []
    assert overlay_paths == {}


def test_orchestrator_raises_overlay_validation_error_on_orphan_overlay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = tmp_path / "project"
    overlay_path = project_root / "overlays" / "topics" / "orphan.md"
    overlay_path.parent.mkdir(parents=True)
    overlay_path.write_text(
        """---
id: "topic:orphan"
overlay_of: "topic:orphan"
relevance: "no canonical counterpart"
---

## Project Notes
""",
        encoding="utf-8",
    )

    with pytest.raises(OverlayValidationError) as excinfo:
        _load_commons(project_root)

    assert excinfo.value.overlay_path == overlay_path
    assert excinfo.value.canonical_id == "topic:orphan"


def test_orchestrator_loads_overlay_without_explicit_reference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = tmp_path / "project"
    overlay_path = project_root / "overlays" / "topics" / "single-cell-foundation-models.md"
    overlay_path.parent.mkdir(parents=True)
    overlay_path.write_text(
        """---
id: "topic:single-cell-foundation-models"
overlay_of: "topic:single-cell-foundation-models"
relevance: "central to this project"
project_tags: ["project-anchor"]
---

## Project Notes
""",
        encoding="utf-8",
    )

    loaded, overlay_paths = _load_commons(project_root)

    assert [entity.canonical_id for entity, _ref in loaded] == ["topic:single-cell-foundation-models"]
    assert overlay_paths == {
        "topic:single-cell-foundation-models": str(overlay_path),
    }


def test_orchestrator_skips_overlay_when_project_identity_already_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = tmp_path / "project"
    overlay_path = project_root / "overlays" / "topics" / "single-cell-foundation-models.md"
    overlay_path.parent.mkdir(parents=True)
    overlay_path.write_text(
        """---
id: "topic:single-cell-foundation-models"
overlay_of: "topic:single-cell-foundation-models"
relevance: "central to this project"
---
""",
        encoding="utf-8",
    )

    loaded, overlay_paths = _load_commons(
        project_root,
        identity_table={
            "topic:single-cell-foundation-models": SourceRef(
                adapter_name="markdown",
                path="entities/topics/single-cell-foundation-models.md",
            )
        },
    )

    assert loaded == []
    assert overlay_paths == {}


def test_orchestrator_no_overlays_and_no_refs_is_noop_with_missing_commons_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "missing-commons"))
    project_root = tmp_path / "project"
    project_root.mkdir()

    loaded, overlay_paths = _load_commons(project_root)

    assert loaded == []
    assert overlay_paths == {}


def test_orchestrator_raises_missing_commons_root_when_overlays_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing_root = tmp_path / "missing-commons"
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(missing_root))
    project_root = tmp_path / "project"
    overlay_path = project_root / "overlays" / "topics" / "single-cell-foundation-models.md"
    overlay_path.parent.mkdir(parents=True)
    overlay_path.write_text(
        """---
id: "topic:single-cell-foundation-models"
overlay_of: "topic:single-cell-foundation-models"
relevance: "central to this project"
---
""",
        encoding="utf-8",
    )

    with pytest.raises(CommonsRootNotFoundError) as excinfo:
        _load_commons(project_root)

    assert excinfo.value.root == missing_root


def test_load_project_sources_pulls_commons_referenced_topic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    manifest_path = project_root / "knowledge" / "sources" / "local" / "manifest.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text("", encoding="utf-8")
    hypothesis_path = project_root / "entities" / "hypotheses" / "h1.md"
    hypothesis_path.parent.mkdir(parents=True)
    hypothesis_path.write_text(
        """---
id: "hypothesis:h1"
kind: "hypothesis"
title: "H1"
related: ["topic:single-cell-foundation-models"]
---
""",
        encoding="utf-8",
    )

    sources = load_project_sources(project_root)

    entity_ids = [entity.canonical_id for entity in sources.entities]
    assert "hypothesis:h1" in entity_ids
    assert "topic:single-cell-foundation-models" in entity_ids
    assert entity_ids == sorted(entity_ids)
    assert sources.commons_overlay_paths == {}


def test_load_project_sources_pulls_commons_dataset_usage_ref(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    manifest_path = project_root / "knowledge" / "sources" / "local" / "manifest.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text("", encoding="utf-8")
    paper_path = project_root / "entities" / "papers" / "Adams2025.md"
    paper_path.parent.mkdir(parents=True)
    paper_path.write_text(
        """---
id: "paper:Adams2025"
kind: "paper"
title: "Adams"
dataset_usage:
  - ref: "dataset:rnaseq-example"
    role: analyzed
---
""",
        encoding="utf-8",
    )

    sources = load_project_sources(project_root)

    assert "dataset:rnaseq-example" in {entity.canonical_id for entity in sources.entities}


def test_load_project_sources_pulls_transitive_commons_dataset_usage_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commons_root = _build_commons(tmp_path)
    paper_path = commons_root / "papers" / "Adams2025.md"
    paper_text = paper_path.read_text(encoding="utf-8")
    paper_path.write_text(
        paper_text.replace(
            "\n---\n\n#",
            '\ndataset_usage:\n  - ref: "dataset:rnaseq-example"\n    role: analyzed\n---\n\n#',
        ),
        encoding="utf-8",
    )
    RegistryBuilder(commons_root, CommonsEntityAdapter(commons_root)).rebuild()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    manifest_path = project_root / "knowledge" / "sources" / "local" / "manifest.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text("", encoding="utf-8")
    hypothesis_path = project_root / "entities" / "hypotheses" / "h1.md"
    hypothesis_path.parent.mkdir(parents=True)
    hypothesis_path.write_text(
        """---
id: "hypothesis:h1"
kind: "hypothesis"
title: "H1"
related: ["paper:Adams2025"]
---
""",
        encoding="utf-8",
    )

    sources = load_project_sources(project_root)

    assert {"paper:Adams2025", "dataset:rnaseq-example"} <= {entity.canonical_id for entity in sources.entities}


def test_load_project_sources_pulls_commons_geneset_row_usage_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    manifest_path = project_root / "knowledge" / "sources" / "local" / "manifest.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text("", encoding="utf-8")
    dp_dir = project_root / "data" / "reactome"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text(
        """profiles: [science-pkg-entity-1.0]
id: dataset:reactome-v89
kind: dataset
title: Reactome
status: active
origin: external
tier: use-now
datapackage: datapackage.yaml
schema_profile: science-entity-base/1.0+dataset/1.0+bio.geneset/1.0
source_class: reference
access: {level: public, verified: true}
member_key_column: set_key
members_resource: sets
n_sets: 1
set_size_summary: {min: 2, median: 2, max: 2}
identifier_space: {tier: gene, namespace: hgnc_id, resolution_status: declared_unresolved}
resources:
  - name: sets
    path: sets.csv
""",
        encoding="utf-8",
    )
    (dp_dir / "sets.csv").write_text(
        "set_key,name,member_ids,dataset_usage\n"
        'R-HSA-1,Cell cycle,HGNC:1;HGNC:2,"[{""ref"":""dataset:rnaseq-example"",""role"":""set_definition_source""}]"\n',
        encoding="utf-8",
    )

    sources = load_project_sources(project_root)

    assert "dataset:rnaseq-example" in {entity.canonical_id for entity in sources.entities}


def test_load_project_sources_populates_overlay_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    manifest_path = project_root / "knowledge" / "sources" / "local" / "manifest.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text("", encoding="utf-8")
    overlay_path = project_root / "overlays" / "topics" / "single-cell-foundation-models.md"
    overlay_path.parent.mkdir(parents=True)
    overlay_path.write_text(
        """---
id: "topic:single-cell-foundation-models"
overlay_of: "topic:single-cell-foundation-models"
relevance: "central to this project"
---
""",
        encoding="utf-8",
    )

    sources = load_project_sources(project_root)

    assert sources.commons_overlay_paths == {
        "topic:single-cell-foundation-models": str(overlay_path),
    }


def test_pinned_overlay_matching_commons_version_does_not_warn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import logging

    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = tmp_path / "project"
    for canonical_id, subdir, slug in (
        ("paper:Adams2025", "papers", "Adams2025"),
        ("topic:single-cell-foundation-models", "topics", "single-cell-foundation-models"),
    ):
        overlay_path = project_root / "overlays" / subdir / f"{slug}.md"
        overlay_path.parent.mkdir(parents=True, exist_ok=True)
        overlay_path.write_text(
            f'---\nid: "{canonical_id}"\noverlay_of: "{canonical_id}"\npin_version: "1.0.0"\n---\n\n## Notes\n',
            encoding="utf-8",
        )

    with caplog.at_level(logging.WARNING, logger="science_tool.graph.commons_sources"):
        _load_commons(project_root)

    pin_records = [r for r in caplog.records if "pinning is not enforced" in r.getMessage()]
    assert pin_records == []


def test_pinned_overlay_rejects_commons_version_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = tmp_path / "project"
    overlay_path = project_root / "overlays" / "papers" / "Adams2025.md"
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    overlay_path.write_text(
        '---\nid: "paper:Adams2025"\noverlay_of: "paper:Adams2025"\npin_version: "9.9.9"\n---\n\n## Notes\n',
        encoding="utf-8",
    )

    with pytest.raises(OverlayValidationError) as excinfo:
        _load_commons(project_root)

    assert excinfo.value.canonical_id == "paper:Adams2025"
    assert "pins 9.9.9 but commons canonical is 1.0.0" in str(excinfo.value)


def test_commons_owner_of_locally_owned_referenced_id_is_reported_as_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = tmp_path / "project"
    project_root.mkdir()

    # The project locally owns topic:single-cell-foundation-models (seeded in
    # identity_table) AND references it; commons also owns it.
    cid = "topic:single-cell-foundation-models"
    loaded, overlay_paths, commons_owner_collisions = _load_commons_referenced_entities(
        project_root=project_root,
        project_slug="demo",
        project_entities=[_entity("topic:local", related=[cid])],
        project_relations=[],
        project_bindings=[],
        identity_table={cid: SourceRef(adapter_name="markdown", path="entities/topics/x.md")},
        registry=EntityRegistry.with_core_types(),
        active_kinds=frozenset({"dataset", "paper", "theme", "topic"}),
        ontology_catalogs=[],
    )

    # NOT materialized as a project entity (no duplicate Entity), but reported as a
    # cross-scope commons owner so the caller can record the second owner row.
    assert loaded == []
    assert overlay_paths == {}
    assert [ref.adapter_name for _cid, ref in commons_owner_collisions] == ["commons-merged"]
    assert [c for c, _ref in commons_owner_collisions] == [cid]


def test_collect_referenced_commons_ids_collects_inner_id_from_scoped_ref() -> None:
    # The Phase-1.3 scoped form commons:<kind>:<slug> must collect the underlying
    # commons id, else a scoped ref could never pull/record its commons owner.
    assert _collect(entities=[_entity("topic:local", related=["commons:topic:phf19"])]) == {"topic:phf19"}
    # A non-commons inner kind is still ignored.
    assert _collect(entities=[_entity("topic:local", related=["commons:hypothesis:h1"])]) == set()
