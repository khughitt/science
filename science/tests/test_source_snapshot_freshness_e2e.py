"""E2E: content change without an `updated:` bump drives freshness via snapshots (Slice B)."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from rdflib import Dataset, URIRef
from rdflib.namespace import RDF

from science_tool.graph.materialize import materialize_graph
from science_tool.graph.source_snapshots import source_snapshot_uri
from science_tool.graph.store import PROJECT_NS, SCI_NS


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip("\n"))


def _build_min_project(tmp_path: Path) -> Path:
    root = tmp_path / "demo"
    _write(root / "science.yaml", "name: demo\nknowledge_profiles:\n  local: core\n")
    _write(root / "knowledge" / "graph.trig", "")
    _write(
        root / "entities" / "hypotheses" / "h1.md",
        """
        ---
        id: "hypothesis:h1"
        kind: "hypothesis"
        title: "Demo hypothesis"
        last_reviewed: "2026-05-01"
        created: "2026-04-01"
        updated: "2026-04-01"
        ---
        Original body.
        """,
    )
    return root


def _load(path: Path) -> Dataset:
    ds = Dataset()
    ds.parse(source=str(path), format="trig")
    return ds


def _state(ds: Dataset, target: URIRef) -> str | None:
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    for _, _, o in knowledge.triples((target, SCI_NS.freshnessState, None)):
        return str(o)
    return None


def _entity_uri(canonical_id: str) -> URIRef:
    from science_tool.graph.io import entity_uri_for_ref

    return entity_uri_for_ref(canonical_id)


def _snapshot_triples(ds: Dataset) -> set[tuple[str, str, str]]:
    """All SourceSnapshot/SourceChange-related provenance triples, as comparable strings."""
    prov = ds.graph(PROJECT_NS["graph/provenance"])
    out: set[tuple[str, str, str]] = set()
    for ss in prov.subjects(RDF.type, SCI_NS.SourceSnapshot):
        for p, o in prov.predicate_objects(ss):
            out.add((str(ss), str(p), str(o)))
    for c in prov.subjects(RDF.type, SCI_NS.SourceChange):
        for p, o in prov.predicate_objects(c):
            out.add((str(c), str(p), str(o)))
    return out


def test_first_build_establishes_baseline_no_change_node(tmp_path: Path):
    root = _build_min_project(tmp_path)
    trig = materialize_graph(root, strict=False)
    ds = _load(trig)
    prov = ds.graph(PROJECT_NS["graph/provenance"])

    ss = source_snapshot_uri("entities/hypotheses/h1.md")
    assert (ss, RDF.type, SCI_NS.SourceSnapshot) in prov
    # baseline: no SourceChange, entity not stale-by-source
    assert prov.value(ss, SCI_NS.latestSourceChange) is None
    h1 = _entity_uri("hypothesis:h1")
    # an entity with last_reviewed after created and no upstream change is fresh
    assert _state(ds, h1) == "fresh"


def test_content_edit_without_updated_bump_marks_needs_review(tmp_path: Path):
    root = _build_min_project(tmp_path)
    materialize_graph(root, strict=False)  # build 1: baseline

    # Edit the BODY only; leave the `updated:` frontmatter untouched.
    h1_path = root / "entities" / "hypotheses" / "h1.md"
    h1_path.write_text(h1_path.read_text().replace("Original body.", "Edited body — new evidence."))

    trig = materialize_graph(root, strict=False)  # build 2: detects content change
    ds = _load(trig)
    h1 = _entity_uri("hypothesis:h1")

    assert _state(ds, h1) == "needs-review"
    # triggeredBy points to the snapshot node (typed SourceSnapshot), not an entity
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    prov = ds.graph(PROJECT_NS["graph/provenance"])
    triggers = {str(o) for _, _, o in knowledge.triples((h1, SCI_NS.triggeredBy, None))}
    ss = source_snapshot_uri("entities/hypotheses/h1.md")
    assert str(ss) in triggers
    assert (ss, RDF.type, SCI_NS.SourceSnapshot) in prov
    # the change cause is reachable: snapshot -> latestSourceChange -> observedOn/sha256
    change_node = prov.value(ss, SCI_NS.latestSourceChange)
    assert change_node is not None
    assert prov.value(change_node, SCI_NS.observedOn) is not None


def test_unchanged_rebuild_is_snapshot_idempotent(tmp_path: Path):
    root = _build_min_project(tmp_path)
    trig = materialize_graph(root, strict=False)
    snap_triples_1 = _snapshot_triples(_load(trig))

    trig = materialize_graph(root, strict=False)  # rebuild, no edits
    snap_triples_2 = _snapshot_triples(_load(trig))

    assert snap_triples_1 == snap_triples_2  # no churn, no drift


def test_snapshot_layer_does_not_perturb_entity_freshness_when_unchanged(tmp_path: Path):
    """The additive snapshot nodes must not change entity freshnessState when no content changed."""
    from datetime import date as _d

    from science_tool.graph.materialize import _build_dataset_from_sources
    from science_tool.graph.source_snapshots import compute_source_snapshots
    from science_tool.graph.sources import load_project_sources

    root = _build_min_project(tmp_path)
    sources = load_project_sources(root, strict_identity=False)

    # Baseline build WITHOUT the snapshot layer (pre-Slice-B behavior).
    ds_without = _build_dataset_from_sources(sources)
    # Build WITH a freshly-computed (first-observation, no-change) snapshot layer.
    snaps = compute_source_snapshots(sources, prior_graph_path=root / "knowledge" / "graph.trig", today=_d(2026, 6, 15))
    ds_with = _build_dataset_from_sources(sources, source_snapshots=snaps)

    def _freshness(ds):
        k = ds.graph(PROJECT_NS["graph/knowledge"])
        return {(str(s), str(o)) for s, _, o in k.triples((None, SCI_NS.freshnessState, None))}

    assert _freshness(ds_without) == _freshness(ds_with)  # no change → identical entity freshness


def test_snapshot_provenance_persists_when_freshness_disabled(tmp_path: Path):
    """Snapshot OBSERVATION is not gated on freshness_enabled (High-2): baseline persists,
    but no freshness-state triples are emitted."""
    root = _build_min_project(tmp_path)
    # Disable freshness-state emission. Mirror the `freshness:` opt-out YAML shape used by
    # tests/test_freshness_opt_out.py (the canonical opt-out fixture).
    (root / "science.yaml").write_text(
        "name: demo\nknowledge_profiles:\n  local: core\nfreshness:\n  enabled: false\n"
    )
    trig = materialize_graph(root, strict=False)
    ds = _load(trig)
    prov = ds.graph(PROJECT_NS["graph/provenance"])
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    ss = source_snapshot_uri("entities/hypotheses/h1.md")

    assert (ss, RDF.type, SCI_NS.SourceSnapshot) in prov  # baseline persists regardless
    assert list(knowledge.triples((None, SCI_NS.freshnessState, None))) == []  # state gated off


def test_in_memory_sweep_sees_content_change(tmp_path: Path):
    from science_tool.graph.freshness import propagate_freshness_in_memory

    root = _build_min_project(tmp_path)
    materialize_graph(root, strict=False)  # baseline persisted to graph.trig

    h1_path = root / "entities" / "hypotheses" / "h1.md"
    h1_path.write_text(h1_path.read_text().replace("Original body.", "Edited body."))

    rows = propagate_freshness_in_memory(root)
    states = {row["id"]: row["state"] for row in rows}
    assert states.get("hypothesis:h1") == "needs-review"  # content-derived, no `updated:` bump
