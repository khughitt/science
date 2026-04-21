from __future__ import annotations

from pathlib import Path

from science_tool.graph.sources import SourceEntity
from science_tool.registry.index import RegistryIndex
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
) -> None:
    doc_dir = project_root / "doc"
    doc_dir.mkdir(parents=True, exist_ok=True)
    rel = related or []
    ont = ontology_terms or []
    als = aliases or []
    (doc_dir / filename).write_text(
        f'---\nid: "{entity_id}"\ntype: {entity_type}\ntitle: "{title}"\n'
        f"related: {rel}\nontology_terms: {ont}\naliases: {als}\n---\nBody.\n",
        encoding="utf-8",
    )


def _source_entity(
    canonical_id: str,
    kind: str,
    title: str,
    aliases: list[str] | None = None,
    ontology_terms: list[str] | None = None,
) -> SourceEntity:
    return SourceEntity(
        canonical_id=canonical_id,
        kind=kind,
        title=title,
        profile="core",
        source_path=f"doc/{canonical_id.replace(':', '-')}.md",
        provider="markdown",
        aliases=aliases or [],
        ontology_terms=ontology_terms or [],
    )


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
