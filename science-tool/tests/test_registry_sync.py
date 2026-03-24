from __future__ import annotations

from pathlib import Path

from science_tool.graph.sources import SourceEntity
from science_tool.registry.index import RegistryIndex
from science_tool.registry.sync import align_registry, collect_all_project_sources


def _write_project(root: Path, name: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "science.yaml").write_text(
        f"name: {name}\nknowledge_profiles:\n  curated: []\n  local: project_specific\n",
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
        f"---\nid: \"{entity_id}\"\ntype: {entity_type}\ntitle: \"{title}\"\n"
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


def test_align_deduplicates_across_projects() -> None:
    existing = RegistryIndex()
    project_sources = {
        "proj-a": [_source_entity("gene:tp53", "gene", "TP53", ["p53"], ["NCBIGene:7157"])],
        "proj-b": [_source_entity("gene:tp53", "gene", "TP53 tumor protein", ["TP53"], ["NCBIGene:7157"])],
    }
    result = align_registry(existing, project_sources)
    tp53_entries = [e for e in result.entities if e.canonical_id == "gene:tp53"]
    assert len(tp53_entries) == 1
    projects = {sp.project for sp in tp53_entries[0].source_projects}
    assert projects == {"proj-a", "proj-b"}
    # Aliases merged
    aliases = set(tp53_entries[0].aliases)
    assert "p53" in aliases
    assert "TP53" in aliases
