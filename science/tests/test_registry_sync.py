from __future__ import annotations

from datetime import date
from pathlib import Path

from science_model.identity import EntityScope, ExternalId
from science_model.entities import EntityType, ProjectEntity

from science_tool.registry.index import (
    RegistryEntity,
    RegistryEntitySource,
    RegistryIndex,
    load_registry_index,
    save_registry_index,
)
from science_tool.registry.sync import SyncReport, align_registry, collect_all_project_sources, run_sync


def _write_project(root: Path, name: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "science.yaml").write_text(
        f"name: {name}\nknowledge_profiles:\n  local: local\n",
        encoding="utf-8",
    )
    for subdir in ("doc", "specs", "tasks", "knowledge"):
        (root / subdir).mkdir(exist_ok=True)


def _write_entity_md(
    project_root: Path,
    filename: str,
    entity_id: str,
    entity_type: str,
    title: str,
    related: list[str] | None = None,
    ontology_terms: list[str] | None = None,
    aliases: list[str] | None = None,
    scope: str | None = None,
    primary_external_id: ExternalId | None = None,
    deprecated_ids: list[str] | None = None,
    taxon: str | None = None,
) -> None:
    doc_dir = project_root / "doc"
    doc_dir.mkdir(parents=True, exist_ok=True)
    rel = related or []
    ont = ontology_terms or []
    als = aliases or []
    dep = deprecated_ids or []
    lines = [
        "---",
        f'id: "{entity_id}"',
        f"type: {entity_type}",
        f'title: "{title}"',
    ]
    if scope is not None:
        lines.append(f"scope: {scope}")
    if primary_external_id is not None:
        lines.extend(
            [
                "primary_external_id:",
                f'  source: "{primary_external_id.source}"',
                f'  id: "{primary_external_id.id}"',
                f'  curie: "{primary_external_id.curie}"',
                f'  provenance: "{primary_external_id.provenance}"',
            ]
        )
    lines.append(f"related: {rel}")
    lines.append(f"ontology_terms: {ont}")
    lines.append(f"aliases: {als}")
    if dep:
        lines.append(f"deprecated_ids: {dep}")
    if taxon is not None:
        lines.append(f"taxon: {taxon}")
    lines.extend(["---", "Body."])
    (doc_dir / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _source_entity(
    canonical_id: str,
    kind: str,
    title: str,
    aliases: list[str] | None = None,
    ontology_terms: list[str] | None = None,
    scope: str = "project",
    primary_external_id: ExternalId | None = None,
    deprecated_ids: list[str] | None = None,
    taxon: str | None = None,
) -> ProjectEntity:
    try:
        etype = EntityType(kind)
    except ValueError:
        etype = None
    return ProjectEntity(
        id=canonical_id,
        canonical_id=canonical_id,
        kind=kind,
        type=etype,
        title=title,
        project="test",
        profile="core",
        file_path=f"doc/{canonical_id.replace(':', '-')}.md",
        aliases=aliases or [],
        ontology_terms=ontology_terms or [],
        related=[],
        source_refs=[],
        scope=EntityScope(scope),
        primary_external_id=primary_external_id,
        deprecated_ids=deprecated_ids or [],
        taxon=taxon,
        content_preview="",
    )


def test_align_registry_preserves_domain_kind_string() -> None:
    existing = RegistryIndex()
    result = align_registry(existing, {"proj-a": [_source_entity("gene:tp53", "gene", "TP53")]})
    entry = next(e for e in result.entities if "gene:tp53" in e.canonical_id)
    assert entry.kind == "gene"


def test_collect_skips_missing_paths(tmp_path: Path) -> None:
    results = collect_all_project_sources(
        project_paths=[tmp_path / "nonexistent"],
    )
    assert results == []


def test_collect_loads_project(tmp_path: Path) -> None:
    proj = tmp_path / "proj-a"
    _write_project(proj, "proj-a")
    _write_entity_md(proj, "q1.md", "question:q1", "question", "Question 1")
    results = collect_all_project_sources(project_paths=[proj])
    assert len(results) == 1
    assert results[0].project_name == "proj-a"
    assert any(e.canonical_id == "question:q1" for e in results[0].entities)


def test_collect_loads_declared_gene_kind_without_unknown_projection(tmp_path: Path) -> None:
    proj = tmp_path / "proj-a"
    _write_project(proj, "proj-a")
    (proj / "science.yaml").write_text(
        "name: proj-a\nknowledge_profiles:\n  local: local\nontologies: [biology]\n",
        encoding="utf-8",
    )
    _write_entity_md(proj, "tp53.md", "gene:tp53", "gene", "TP53")

    results = collect_all_project_sources(project_paths=[proj])

    assert len(results) == 1
    gene = next(entity for entity in results[0].entities if entity.canonical_id == "gene:tp53")
    assert gene.kind == "gene"
    assert gene.type is None


def test_align_deduplicates_within_project() -> None:
    """Same entity loaded twice from same project is deduplicated."""
    existing = RegistryIndex()
    project_sources = {
        "proj-a": [
            _source_entity("gene:tp53", "gene", "TP53", ["p53"], ["NCBIGene:7157"]),
            _source_entity("gene:tp53", "gene", "TP53", ["TP53"], ["NCBIGene:7157"]),
        ],
    }
    result = align_registry(existing, project_sources)
    tp53_entries = [e for e in result.entities if "gene:tp53" in e.canonical_id]
    assert len(tp53_entries) == 1
    aliases = set(tp53_entries[0].aliases)
    assert "p53" in aliases
    assert "TP53" in aliases


def test_align_does_not_merge_same_id_different_projects() -> None:
    """task:t001 in proj-a and task:t001 in proj-b are different entities."""
    existing = RegistryIndex()
    project_sources = {
        "proj-a": [_source_entity("task:t001", "task", "Run analysis on dataset X")],
        "proj-b": [_source_entity("task:t001", "task", "Set up CI pipeline")],
    }
    result = align_registry(existing, project_sources)
    t001_entries = [e for e in result.entities if "task:t001" in e.canonical_id]
    assert len(t001_entries) == 2
    for entry in t001_entries:
        assert len(entry.source_projects) == 1
    project_names = {entry.source_projects[0].project for entry in t001_entries}
    assert project_names == {"proj-a", "proj-b"}


def test_run_sync_warns_on_primary_external_id_collision(tmp_path: Path) -> None:
    proj_a = tmp_path / "proj-a"
    proj_b = tmp_path / "proj-b"
    _write_project(proj_a, "proj-a")
    _write_project(proj_b, "proj-b")
    shared_id = ExternalId(source="HGNC", id="7157", curie="HGNC:7157", provenance="manual")
    _write_entity_md(
        proj_a,
        "tp53.md",
        "question:tp53",
        "question",
        "TP53",
        primary_external_id=shared_id,
        scope="shared",
    )
    _write_entity_md(
        proj_b,
        "p53.md",
        "question:p53",
        "question",
        "P53",
        primary_external_id=shared_id,
        scope="shared",
    )

    report = run_sync(
        project_paths=[proj_a, proj_b],
        state_path=tmp_path / "sync_state.yaml",
        registry_dir=tmp_path / "registry",
        dry_run=True,
    )

    assert any("primary_external_id collision" in warning for warning in report.drift_warnings)


def test_run_sync_does_not_warn_on_compatible_shared_collision(tmp_path: Path) -> None:
    proj_a = tmp_path / "proj-a"
    proj_b = tmp_path / "proj-b"
    _write_project(proj_a, "proj-a")
    _write_project(proj_b, "proj-b")
    shared_id = ExternalId(source="HGNC", id="7157", curie="HGNC:7157", provenance="manual")
    _write_entity_md(
        proj_a,
        "tp53.md",
        "question:tp53",
        "question",
        "TP53",
        primary_external_id=shared_id,
        scope="shared",
        taxon="NCBITaxon:9606",
    )
    _write_entity_md(
        proj_b,
        "tp53.md",
        "question:tp53",
        "question",
        "TP53",
        primary_external_id=shared_id,
        scope="shared",
        taxon="NCBITaxon:9606",
    )

    report = run_sync(
        project_paths=[proj_a, proj_b],
        state_path=tmp_path / "sync_state.yaml",
        registry_dir=tmp_path / "registry",
        dry_run=True,
    )

    assert not any("canonical_id collision" in warning for warning in report.drift_warnings)


def test_run_sync_warns_on_canonical_id_collision(tmp_path: Path) -> None:
    proj_a = tmp_path / "proj-a"
    proj_b = tmp_path / "proj-b"
    _write_project(proj_a, "proj-a")
    _write_project(proj_b, "proj-b")
    _write_entity_md(proj_a, "tp53.md", "question:tp53", "question", "TP53", scope="project")
    _write_entity_md(proj_b, "tp53.md", "question:tp53", "question", "TP53", scope="project")

    report = run_sync(
        project_paths=[proj_a, proj_b],
        state_path=tmp_path / "sync_state.yaml",
        registry_dir=tmp_path / "registry",
        dry_run=True,
    )

    assert any("canonical_id collision" in warning for warning in report.drift_warnings)


def test_run_sync_updates_stale_registry_identity_metadata(tmp_path: Path) -> None:
    proj_a = tmp_path / "proj-a"
    registry_dir = tmp_path / "registry"
    _write_project(proj_a, "proj-a")
    corrected_id = ExternalId(source="HGNC", id="3527", curie="HGNC:3527", provenance="manual")
    _write_entity_md(
        proj_a,
        "ezh2.md",
        "question:ezh2",
        "question",
        "EZH2",
        primary_external_id=corrected_id,
        scope="shared",
        taxon="NCBITaxon:9606",
    )
    stale_index = RegistryIndex(
        entities=[
            RegistryEntity(
                canonical_id="proj-a::question:ezh2",
                kind="question",
                title="EZH2",
                profile="core",
                scope=EntityScope.PROJECT,
                primary_external_id=ExternalId(
                    source="HGNC",
                    id="9999",
                    curie="HGNC:9999",
                    provenance="manual",
                ),
                taxon=None,
                source_projects=[
                    RegistryEntitySource(project="proj-a", first_seen=date(2026, 4, 1)),
                ],
            ),
        ],
    )
    save_registry_index(stale_index, registry_dir)

    report = run_sync(
        project_paths=[proj_a],
        state_path=tmp_path / "sync_state.yaml",
        registry_dir=registry_dir,
        dry_run=False,
    )

    assert report.entities_total == 1
    loaded = load_registry_index(registry_dir)
    entry = next(entity for entity in loaded.entities if entity.canonical_id == "proj-a::question:ezh2")
    assert entry.scope == EntityScope.SHARED
    assert entry.primary_external_id is not None
    assert entry.primary_external_id.curie == "HGNC:3527"
    assert entry.taxon == "NCBITaxon:9606"


def test_full_sync_two_projects(tmp_path: Path) -> None:
    proj_a = tmp_path / "proj-a"
    proj_b = tmp_path / "proj-b"
    _write_project(proj_a, "proj-a")
    _write_project(proj_b, "proj-b")

    _write_entity_md(
        proj_a,
        "tp53.md",
        "gene:tp53",
        "concept",
        "TP53",
        ontology_terms=["NCBIGene:7157"],
        aliases=["p53"],
    )
    _write_entity_md(
        proj_a,
        "q1.md",
        "question:q1",
        "question",
        "TP53 question",
        related=["gene:tp53"],
    )
    _write_entity_md(
        proj_b,
        "tp53.md",
        "gene:tp53",
        "concept",
        "TP53",
        ontology_terms=["NCBIGene:7157"],
        aliases=["p53"],
    )

    report = run_sync(
        project_paths=[proj_a, proj_b],
        state_path=tmp_path / "sync_state.yaml",
        registry_dir=tmp_path / "registry",
    )
    assert isinstance(report, SyncReport)
    assert report.entities_total > 0
    # Propagation is disabled — registry-only sync does not write doc/sync/ files
    sync_dir = proj_b / "doc" / "sync"
    assert not sync_dir.exists() or len(list(sync_dir.glob("*.md"))) == 0


def test_sync_idempotent(tmp_path: Path) -> None:
    proj_a = tmp_path / "proj-a"
    proj_b = tmp_path / "proj-b"
    _write_project(proj_a, "proj-a")
    _write_project(proj_b, "proj-b")
    _write_entity_md(
        proj_a,
        "tp53.md",
        "gene:tp53",
        "concept",
        "TP53",
        ontology_terms=["NCBIGene:7157"],
        aliases=["p53"],
    )
    _write_entity_md(
        proj_b,
        "tp53.md",
        "gene:tp53",
        "concept",
        "TP53",
        ontology_terms=["NCBIGene:7157"],
        aliases=["p53"],
    )
    _write_entity_md(proj_a, "q1.md", "question:q1", "question", "Q1", related=["gene:tp53"])

    kwargs: dict[str, object] = dict(
        project_paths=[proj_a, proj_b],
        state_path=tmp_path / "sync_state.yaml",
        registry_dir=tmp_path / "registry",
    )
    run_sync(**kwargs)  # type: ignore[arg-type]
    run_sync(**kwargs)  # type: ignore[arg-type]
    # Second run should not duplicate propagations
    sync_files = list((proj_b / "doc" / "sync").glob("*.md"))
    assert len(sync_files) <= 1  # at most 1, not duplicated


def test_resync_with_existing_namespaced_registry(tmp_path: Path) -> None:
    proj_a = tmp_path / "proj-a"
    _write_project(proj_a, "proj-a")
    _write_entity_md(proj_a, "q1.md", "question:q1", "question", "Question 1")

    kwargs: dict[str, object] = dict(
        project_paths=[proj_a],
        state_path=tmp_path / "sync_state.yaml",
        registry_dir=tmp_path / "registry",
    )
    report1 = run_sync(**kwargs)  # type: ignore[arg-type]
    report2 = run_sync(**kwargs)  # type: ignore[arg-type]
    assert report1.entities_total == report2.entities_total
    assert report2.entities_new == 0
