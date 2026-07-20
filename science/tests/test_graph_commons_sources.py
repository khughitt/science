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
from science_tool.commons.registry import RegistryBuilder
from science_tool.graph.commons_sources import (
    _OVERLAY_ONLY_FIELDS,
    CommonsClosure,
    _materialize_commons_candidate,
    collect_commons_contributions,
    collect_referenced_commons_ids,
)
from science_tool.graph.entity_registry import EntityRegistry
from science_tool.graph.errors import ContributionConflictError
from science_tool.graph.identity_arbitration import (
    ArbitrationCode,
    AttachmentContribution,
    EntityContribution,
)
from science_tool.graph.identity_table import ParticipationMode
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


def _closure(project_root: Path, *, project_entities: list[Entity] | None = None) -> CommonsClosure:
    return collect_commons_contributions(
        project_root=project_root,
        project_slug="demo",
        seed_entities=project_entities or [],
        project_relations=[],
        project_bindings=[],
        registry=EntityRegistry.with_core_types(),
        active_kinds=frozenset({"dataset", "paper", "theme", "topic"}),
        ontology_catalogs=[],
    )


def _load_commons(
    project_root: Path,
    *,
    project_entities: list[Entity] | None = None,
) -> tuple[list[tuple[Entity, SourceRef | None]], dict[str, str]]:
    """The closure's owner candidates and the overlays it attached.

    Overlay paths are DERIVED from the attachment contributions rather than read from a field
    of their own: an attachment already carries where it came from, and a second copy of that
    fact is one more thing that can disagree with the first.
    """
    closure = _closure(project_root, project_entities=project_entities)
    owners = [
        (c.candidate, c.declaration.source_ref)
        for c in closure.contributions
        if isinstance(c, EntityContribution)
    ]
    return owners, _attached_overlay_paths(closure)


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

    assert _collect(entities=[paper, derived]) == {"dataset:authored", "dataset:upstream"}


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


def _record(frontmatter: dict[str, object]) -> _StubCanonical:
    canonical_id = str(frontmatter["id"])
    kind = str(frontmatter.get("kind") or frontmatter.get("type"))
    return _StubCanonical(
        canonical_id=canonical_id,
        type=kind,
        slug=canonical_id.split(":", 1)[-1],
        schema_profile="shared",
        frontmatter=frontmatter,
        body_path=Path("commons") / kind / f"{canonical_id.split(':', 1)[-1]}.md",
    )


def _translate(frontmatter: dict[str, object]) -> Entity:
    """The canonical alone. No overlay is applied -- arbitration composes that later."""
    return _materialize_commons_candidate(
        _record(frontmatter),  # type: ignore[arg-type]
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


def test_orchestrator_warns_when_commons_registry_is_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A project graph built against a stale commons registry composes an
    out-of-date snapshot yet reports itself fresh. The graph-load path must
    surface the staleness (fb-2026-07-16-005), not silence it."""
    commons_root = _build_commons(tmp_path)
    # Add a file post-rebuild so the registry is genuinely stale.
    (commons_root / "topics" / "post-rebuild.md").write_text(
        "---\n"
        'schema_profile: "science-entity-base/1.0+topic/1.0"\n'
        'id: "topic:post-rebuild"\n'
        'kind: "topic"\n'
        'title: "Post"\n'
        'version: "1.0.0"\n'
        'status: "active"\n'
        'created: "2026-05-13"\n'
        'updated: "2026-05-13"\n'
        "ontology_terms: []\n"
        "tags: []\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    # Note: SCIENCE_COMMONS_QUIET_STALE is deliberately NOT set here.
    project_root = tmp_path / "project"
    project_root.mkdir()

    _load_commons(
        project_root,
        project_entities=[_entity("topic:local", related=["topic:single-cell-foundation-models"])],
    )

    err = capsys.readouterr().err
    assert "stale" in err
    assert "science commons index rebuild" in err


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


def _attached_overlay_paths(closure: CommonsClosure) -> dict[str, str]:
    return {
        c.declaration.canonical_id: str(c.record.overlay_path)
        for c in closure.contributions
        if isinstance(c, AttachmentContribution)
    }


def test_closure_contributes_even_when_the_project_owns_the_same_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Close does not know, or ask, what the project owns.

    It used to take the owned-id set and skip those ids, which is an ARBITRATION decision made
    inside collection -- and the reason a bib entry could suppress a commons canonical: the
    "already owned" test could not tell an owner from a citation. Close now contributes what
    commons says; whether commons wins is decided once, later, over everything.
    """
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

    closure = _closure(project_root)

    # Both rows exist. The project owning this id is not Close's business; `_select_scope` gives
    # the project the representative, and the commons owner row remains visible so a bare
    # cross-scope reference can be reported as ambiguous (design §B3a).
    assert {
        (c.declaration.canonical_id, c.declaration.participation_mode, c.declaration.adapter)
        for c in closure.contributions
    } == {
        ("topic:single-cell-foundation-models", ParticipationMode.OWNER, "commons-merged"),
        ("topic:single-cell-foundation-models", ParticipationMode.BORROWER, "overlay"),
    }
    assert _attached_overlay_paths(closure) == {
        "topic:single-cell-foundation-models": str(overlay_path)
    }


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


def _project_referencing_commons_topic(tmp_path: Path) -> Path:
    """A project whose only commons contact is a hypothesis referencing a commons topic id.

    Deliberately reaches a commons id WITHOUT an overlay, so the reference alone drives the
    closure. That is what makes `include_commons` observable: in federation mode the topic is
    materialized as a commons owner; self-contained, the same id stays an unresolved reference.
    """
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
    return project_root


def test_federation_mode_with_a_reachable_reference_fails_when_the_root_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fail-closed default: a reached commons id + no store is a named error, never a partial graph.

    The project references a commons topic, so the closure has a non-empty pending set and must
    open the store. With the store absent, silently returning a graph missing that topic would be
    the silent-instrument failure this whole arc removes. The load must raise instead.
    """
    missing_root = tmp_path / "missing-commons"
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(missing_root))
    project_root = _project_referencing_commons_topic(tmp_path)

    with pytest.raises(CommonsRootNotFoundError) as excinfo:
        load_project_sources(project_root)

    assert excinfo.value.root == missing_root


def test_self_contained_mode_loads_the_same_reference_without_a_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`include_commons=False` is the explicit opt-out: the store is never opened, so no root is needed.

    This is the deliberate self-contained build. The commons topic is NOT materialized -- it
    stays a bare reference the hypothesis points at -- and that is the point: a project that
    genuinely stands alone can build, without weakening the federated default above.
    """
    missing_root = tmp_path / "missing-commons"
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(missing_root))
    project_root = _project_referencing_commons_topic(tmp_path)

    sources = load_project_sources(project_root, include_commons=False)

    entity_ids = [entity.canonical_id for entity in sources.entities]
    assert "hypothesis:h1" in entity_ids
    assert "topic:single-cell-foundation-models" not in entity_ids


def test_self_contained_mode_cannot_be_mistaken_for_commons_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even with a fully reachable store, the two modes produce materially different graphs.

    If self-contained mode could ever return commons content, it would be a fallback rather than
    an opt-out, and a partial build could pass for a full one. With the SAME real store present,
    the federated load materializes the commons topic and the self-contained load does not. The
    modes are not interchangeable, and the missing owner is the observable proof.
    """
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = _project_referencing_commons_topic(tmp_path)

    federated = [e.canonical_id for e in load_project_sources(project_root).entities]
    self_contained = [
        e.canonical_id for e in load_project_sources(project_root, include_commons=False).entities
    ]

    assert "topic:single-cell-foundation-models" in federated
    assert "topic:single-cell-foundation-models" not in self_contained
    assert "hypothesis:h1" in self_contained


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


def test_commons_owner_of_a_referenced_id_is_contributed_not_special_cased(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A commons owner is an ordinary OWNER contribution, in the commons scope.

    It used to travel a separate `commons_owner_collisions` channel whose whole reason for
    existing was that Close had already decided not to materialize the id. With the decision
    moved out, the second channel has nothing left to carry: one owner row in a different scope
    is exactly what an EntityContribution already expresses, and arbitration's `_select_scope`
    is what declines to materialize a duplicate.
    """
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = tmp_path / "project"
    project_root.mkdir()

    cid = "topic:single-cell-foundation-models"
    closure = _closure(project_root, project_entities=[_entity("topic:local", related=[cid])])

    owners = [c for c in closure.contributions if isinstance(c, EntityContribution)]
    assert [c.declaration.canonical_id for c in owners] == [cid]
    assert owners[0].declaration.owner_scope == "commons"
    assert owners[0].declaration.adapter == "commons-merged"
    # The policy travels WITH the contribution: a commons owner arbitration cannot ask for a
    # policy is a commons owner whose overlay could never be composed.
    assert ("commons", cid) in closure.field_policies


def test_collect_referenced_commons_ids_collects_inner_id_from_scoped_ref() -> None:
    # The Phase-1.3 scoped form commons:<kind>:<slug> must collect the underlying
    # commons id, else a scoped ref could never pull/record its commons owner.
    assert _collect(entities=[_entity("topic:local", related=["commons:topic:phf19"])]) == {"topic:phf19"}
    # A non-commons inner kind is still ignored.
    assert _collect(entities=[_entity("topic:local", related=["commons:hypothesis:h1"])]) == set()


def _bib_overlay_project(tmp_path: Path) -> Path:
    """A project that both cites Adams2025 in references.bib and overlays it.

    This is the shape every real project has: papers are cited (bib) AND carry
    project-side commentary (overlay). fb-2026-07-16-005.
    """
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    manifest_path = project_root / "knowledge" / "sources" / "local" / "manifest.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text("", encoding="utf-8")
    bib_path = project_root / "papers" / "references.bib"
    bib_path.parent.mkdir(parents=True)
    bib_path.write_text(
        "@article{Adams2025,\n"
        "  title = {A representative paper about homology-aware evaluation},\n"
        "  author = {Adams, A. and Baker, B.},\n"
        "  journal = {Nature Methods},\n"
        "  year = {2025},\n"
        "  doi = {10.1038/example}\n"
        "}\n",
        encoding="utf-8",
    )
    overlay_path = project_root / "overlays" / "papers" / "Adams2025.md"
    overlay_path.parent.mkdir(parents=True)
    overlay_path.write_text(
        """---
id: "paper:Adams2025"
overlay_of: "paper:Adams2025"
pin_version: "1.0.0"
relevance: "central to this project"
related: ["question:0042-driver-specificity"]
---

## Relevance

Project-side commentary that must reach the graph.
""",
        encoding="utf-8",
    )
    return project_root


def test_bib_entry_does_not_shadow_paper_overlay(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A bib entry must not suppress the commons+overlay branch (fb-2026-07-16-005).

    bib is an EXTERNAL_REFERENCE adapter and `identity_table.classify_owner_scope`
    states "bib rows are never owners". But the load loop seeds the identity dict
    from bib before commons loads, so the overlay is skipped: never merged, never
    pin-checked.
    """
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = _bib_overlay_project(tmp_path)

    sources = load_project_sources(project_root)

    assert sources.commons_overlay_paths.get("paper:Adams2025") == str(
        project_root / "overlays" / "papers" / "Adams2025.md"
    ), "overlay was skipped because the bib entry claimed the id first"

    # All three sources speak for this id, in their three different standings. The bug was that
    # the bib row's mere presence deleted the other two; recording all three is what makes the
    # arbitration auditable rather than a coincidence of load order.
    rows = [row for row in sources.identity_declarations if row.canonical_id == "paper:Adams2025"]
    assert {(row.participation_mode, row.adapter) for row in rows} == {
        (ParticipationMode.OWNER, "commons-merged"),
        (ParticipationMode.BORROWER, "overlay"),
        (ParticipationMode.EXTERNAL_REFERENCE, "bib"),
    }
    # Three declarations, ONE node. Exhaustive collection must not become duplicate entities.
    assert len([entity for entity in sources.entities if entity.canonical_id == "paper:Adams2025"]) == 1


def test_closure_collects_a_commons_id_reachable_only_through_an_overlay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A commons id that ONLY the overlay names must still be collected.

    The canonical Adams2025 says nothing about this topic and no project file references it;
    the borrower is the sole source of the reference. Closure that reads references off owners
    alone is blind to exactly the ids a project pulls in through its own commentary.
    """
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = _bib_overlay_project(tmp_path)
    overlay_path = project_root / "overlays" / "papers" / "Adams2025.md"
    overlay_path.write_text(
        overlay_path.read_text(encoding="utf-8").replace(
            'related: ["question:0042-driver-specificity"]',
            'related: ["topic:single-cell-foundation-models"]',
        ),
        encoding="utf-8",
    )

    sources = load_project_sources(project_root)

    owners = {
        (row.canonical_id, row.adapter)
        for row in sources.identity_declarations
        if row.participation_mode is ParticipationMode.OWNER
    }
    assert ("paper:Adams2025", "commons-merged") in owners
    assert ("topic:single-cell-foundation-models", "commons-merged") in owners
    assert any(e.canonical_id == "topic:single-cell-foundation-models" for e in sources.entities)


def test_bib_entry_does_not_suppress_overlay_pin_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An overlay pin must be enforced even when the id is also a bib entry.

    The pin check lives behind the same skip, so a project pinning a stale version
    validates green against a drifted commons canonical.
    """
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = _bib_overlay_project(tmp_path)
    overlay_path = project_root / "overlays" / "papers" / "Adams2025.md"
    overlay_path.write_text(
        overlay_path.read_text(encoding="utf-8").replace('pin_version: "1.0.0"', 'pin_version: "0.9.0"'),
        encoding="utf-8",
    )

    with pytest.raises(OverlayValidationError):
        load_project_sources(project_root)


def _status_demo_project(
    tmp_path: Path,
    commons_root: Path,
    *,
    dataset_mixin: str,
    canonical_status: str,
    overlay_fields: dict[str, str],
) -> Path:
    """A commons dataset owner plus a project overlay proposing project_only fields.

    Parameterized on the dataset mixin version because that is the whole question: the same
    two files must merge under dataset/2.0 and refuse to merge under dataset/1.0. Parameterized
    on the overlay's fields because 2.0 declares three of them -- `status`, `created`, `updated`
    -- and one field passing proves nothing about the other two.

    The canonical owner authors `created`/`updated` as well as `status`, so every one of the
    three is a field the owner HAS spoken on. That is what makes the 1.0 control a contest.
    """
    entity_path = commons_root / "datasets" / "status-demo" / "entity.md"
    entity_path.parent.mkdir(parents=True)
    entity_path.write_text(
        f"""---
schema_profile: "science-entity-base/1.0+{dataset_mixin}"
id: "dataset:status-demo"
kind: "dataset"
title: "Status demo dataset"
version: "1.0.0"
status: "{canonical_status}"
created: "2026-07-16"
updated: "2026-07-16"
origin: "external"
tier: "use-now"
dataset_class: "pointer"
access:
  level: "public"
  verified: true
---

# Status demo dataset

A pointer dataset used to certify overlay status merging.
""",
        encoding="utf-8",
    )
    RegistryBuilder(commons_root, CommonsEntityAdapter(commons_root)).rebuild()

    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    manifest_path = project_root / "knowledge" / "sources" / "local" / "manifest.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text("", encoding="utf-8")

    overlay_path = project_root / "overlays" / "datasets" / "status-demo.md"
    overlay_path.parent.mkdir(parents=True)
    proposed = "\n".join(f'{field}: "{value}"' for field, value in overlay_fields.items())
    overlay_path.write_text(
        f"""---
id: "dataset:status-demo"
overlay_of: "dataset:status-demo"
{proposed}
---

## Project-Specific Notes

This project uses the pointer.
""",
        encoding="utf-8",
    )
    return project_root


def test_dataset_2_0_overlay_status_reaches_the_materialized_entity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """dataset/2.0 declares status project_only, so the overlay's status is the graph's status.

    End-to-end over the real loader: the model-level policy test proves what the schema says,
    which is a different claim from whether a project overlay's status survives closure,
    arbitration, and materialization to reach the entity a reader sees.
    """
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = _status_demo_project(
        tmp_path,
        commons_root,
        dataset_mixin="dataset/2.0",
        canonical_status="canonical",
        overlay_fields={"status": "active"},
    )

    sources = load_project_sources(project_root)

    entity = next(e for e in sources.entities if e.canonical_id == "dataset:status-demo")
    assert entity.status == "active"
    assert sources.arbitration_errors == []


def test_dataset_2_0_overlay_dates_reach_the_materialized_entity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`created` and `updated` are project_only on dataset/2.0, exactly as on paper/theme/topic.

    Dates are the fields most likely to differ between the store and a project: the commons
    records when the canonical record was written, the project when IT adopted the dataset.
    Without these annotations an overlay's dates are a contest against the owner, and a dataset
    is the one kind where that fails -- which is precisely the asymmetry this pins shut.
    """
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = _status_demo_project(
        tmp_path,
        commons_root,
        dataset_mixin="dataset/2.0",
        canonical_status="canonical",
        overlay_fields={"created": "2026-01-02", "updated": "2026-03-04"},
    )

    sources = load_project_sources(project_root)

    entity = next(e for e in sources.entities if e.canonical_id == "dataset:status-demo")
    assert str(entity.created) == "2026-01-02"
    assert str(entity.updated) == "2026-03-04"
    assert sources.arbitration_errors == []


def test_dataset_1_0_refuses_an_overlay_replacing_defended_dates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The date half of the versioning-atomicity control.

    dataset/1.0 mentions neither date, so both resolve to default `replace` through the base
    schema and the owner's dates are defended. This is what a project pinned to 1.0 must keep
    seeing after 2.0 ships.
    """
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = _status_demo_project(
        tmp_path,
        commons_root,
        dataset_mixin="dataset/1.0",
        canonical_status="canonical",
        overlay_fields={"created": "2026-01-02", "updated": "2026-03-04"},
    )

    sources = load_project_sources(project_root, strict_identity=False)

    conflicted = {
        error.field
        for error in sources.arbitration_errors
        if error.code is ArbitrationCode.CONTRIBUTION_CONFLICT
    }
    assert conflicted == {"created", "updated"}

    entity = next(e for e in sources.entities if e.canonical_id == "dataset:status-demo")
    assert str(entity.created) == "2026-07-16"
    assert str(entity.updated) == "2026-07-16"


def test_dataset_1_0_refuses_an_overlay_replacing_a_defended_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The versioning atomicity control: pinning 1.0 keeps 1.0's answer.

    dataset/1.0 does not mention `status` at all -- the profile RESOLVES to the default
    `replace` through the base schema's bare declaration. That is the semantics 2.0 opts out of
    explicitly, so this control pins default-replace rather than a mixin's own statement. The
    canonical owner has spoken, so the overlay is a contest rather than a contribution. If this
    ever passes by merging, the 2.0 profile is not a version -- it is a global behavior change
    that pinned entities cannot opt out of.
    """
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = _status_demo_project(
        tmp_path,
        commons_root,
        dataset_mixin="dataset/1.0",
        canonical_status="canonical",
        overlay_fields={"status": "active"},
    )
    overlay_path = project_root / "overlays" / "datasets" / "status-demo.md"

    sources = load_project_sources(project_root, strict_identity=False)

    conflicts = [
        error
        for error in sources.arbitration_errors
        if error.code is ArbitrationCode.CONTRIBUTION_CONFLICT and error.field == "status"
    ]
    assert len(conflicts) == 1
    assert conflicts[0].canonical_id == "dataset:status-demo"
    assert [ref.path for ref in conflicts[0].contributors] == [str(overlay_path)]

    entity = next(e for e in sources.entities if e.canonical_id == "dataset:status-demo")
    assert entity.status == "canonical"

    with pytest.raises(ContributionConflictError):
        load_project_sources(project_root)
