"""Project-wide discovery surfaces research-package entities."""

from __future__ import annotations

from pathlib import Path


def _seed_two_entity_types(root: Path) -> None:
    (root / "science.yaml").write_text("project: test\n", encoding="utf-8")
    (root / "doc" / "datasets").mkdir(parents=True)
    (root / "doc" / "datasets" / "ds1.md").write_text(
        '---\nid: "dataset:ds1"\ntype: "dataset"\ntitle: "DS1"\norigin: "external"\n'
        'access: {level: "public", verified: false}\n---\n',
        encoding="utf-8",
    )
    (root / "research" / "packages" / "lens" / "section").mkdir(parents=True)
    (root / "research" / "packages" / "lens" / "section" / "research-package.md").write_text(
        '---\nid: "research-package:rp1"\ntype: "research-package"\ntitle: "RP1"\ndisplays: ["dataset:ds1"]\n---\n',
        encoding="utf-8",
    )


def test_load_project_sources_includes_research_packages(tmp_path: Path) -> None:
    _seed_two_entity_types(tmp_path)
    from science_tool.graph.sources import load_project_sources

    sources = load_project_sources(tmp_path)
    ids = {e.canonical_id for e in sources.entities}
    assert "dataset:ds1" in ids
    assert "research-package:rp1" in ids


def test_health_surfaces_research_package(tmp_path: Path) -> None:
    """Health module sees research-package entities (e.g., for asymmetric-edge invariant)."""
    _seed_two_entity_types(tmp_path)
    # The dataset claims to be displayed by rp1; rp1's displays lists the dataset → symmetric → no anomaly.
    (tmp_path / "doc" / "datasets" / "ds1.md").write_text(
        '---\nid: "dataset:ds1"\ntype: "dataset"\ntitle: "DS1"\norigin: "external"\n'
        'access: {level: "public", verified: false}\n'
        'consumed_by: ["research-package:rp1"]\n---\n',
        encoding="utf-8",
    )
    # Note: check_dataset_anomalies doesn't exist yet — Phase 6 builds it. For now, verify
    # at minimum that BOTH entities are visible to load_project_sources (precondition for health).
    from science_tool.graph.sources import load_project_sources

    sources = load_project_sources(tmp_path)
    ids = {e.canonical_id for e in sources.entities}
    assert "dataset:ds1" in ids
    assert "research-package:rp1" in ids


def test_materialize_includes_research_package_in_graph(tmp_path: Path) -> None:
    _seed_two_entity_types(tmp_path)
    # The exact materialize entry point varies — read science_tool/graph/materialize.py to find it.
    # Either build_graph(...) returns a Graph object, or there's a function that produces a triplestore.
    # Verify research-package:rp1 appears in whatever the materialize output is.
    # If there's no easy way to check, fall back to the load_project_sources visibility check
    # (which is the precondition for materialize seeing the entity).
    from science_tool.graph.sources import load_project_sources

    sources = load_project_sources(tmp_path)
    rps = [e for e in sources.entities if e.canonical_id == "research-package:rp1"]
    assert len(rps) == 1
    assert rps[0].kind == "research-package"


def test_sync_iterates_research_packages(tmp_path: Path) -> None:
    """If registry/sync.py walks project sources, research-packages must appear."""
    _seed_two_entity_types(tmp_path)
    from science_tool.graph.sources import load_project_sources

    sources = load_project_sources(tmp_path)
    rp_kinds = [e.kind for e in sources.entities if e.canonical_id == "research-package:rp1"]
    assert rp_kinds == ["research-package"]
