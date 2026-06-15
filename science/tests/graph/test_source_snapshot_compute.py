"""compute_source_snapshots: baseline / change / carry-forward (Slice B)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from rdflib import Dataset, Literal
from rdflib.namespace import RDF

from science_tool.graph.source_snapshots import (
    compute_source_snapshots,
    read_prior_snapshots,
    source_snapshot_uri,
)
from science_tool.graph.store import PROJECT_NS, SCHEMA_NS, SCI_NS


class _Sources:
    """Minimal ProjectSources stand-in for compute (only the read fields)."""

    def __init__(self, project_root: str, entities: list, adapters: dict[str, str]):
        self.project_root = project_root
        self.entities = entities
        self.entity_source_adapters = adapters


class _Entity:
    def __init__(self, canonical_id: str, file_path: str):
        self.canonical_id = canonical_id
        self.file_path = file_path


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _prior_graph_with(tmp: Path, *, source_path: str, sha256: str) -> Path:
    """Hand-build a prior graph.trig carrying one baseline snapshot (no change)."""
    ds = Dataset()
    prov = ds.graph(PROJECT_NS["graph/provenance"])
    ss = source_snapshot_uri(source_path)
    prov.add((ss, RDF.type, SCI_NS.SourceSnapshot))
    prov.add((ss, SCI_NS.sourcePath, Literal(source_path)))
    prov.add((ss, SCHEMA_NS.sha256, Literal(sha256)))
    out = tmp / "knowledge" / "graph.trig"
    out.parent.mkdir(parents=True, exist_ok=True)
    ds.serialize(destination=str(out), format="trig")
    return out


def test_first_build_establishes_baseline_no_change(tmp_path: Path):
    root = tmp_path / "demo"
    _write(root / "entities" / "h1.md", "alpha")
    sources = _Sources(str(root), [_Entity("hypothesis:h1", "entities/h1.md")], {"hypothesis:h1": "markdown"})

    result = compute_source_snapshots(sources, prior_graph_path=root / "knowledge" / "graph.trig", today=date(2026, 6, 15))

    assert len(result.emissions) == 1
    snap = result.emissions[0].snapshot
    assert snap.source_path == "entities/h1.md"
    assert snap.latest_change is None
    assert result.source_changes == {}  # no origin on first observation


def test_unchanged_rebuild_carries_forward_verbatim(tmp_path: Path):
    root = tmp_path / "demo"
    _write(root / "entities" / "h1.md", "alpha")
    import hashlib

    sha = hashlib.sha256(b"alpha").hexdigest()
    prior = _prior_graph_with(root, source_path="entities/h1.md", sha256=sha)
    sources = _Sources(str(root), [_Entity("hypothesis:h1", "entities/h1.md")], {"hypothesis:h1": "markdown"})

    result = compute_source_snapshots(sources, prior_graph_path=prior, today=date(2026, 6, 15))

    snap = result.emissions[0].snapshot
    assert snap.sha256 == sha
    assert snap.latest_change is None  # unchanged → no event, no churn
    assert result.source_changes == {}


def test_changed_content_mints_one_source_change(tmp_path: Path):
    root = tmp_path / "demo"
    _write(root / "entities" / "h1.md", "BETA")  # differs from baseline below
    prior = _prior_graph_with(root, source_path="entities/h1.md", sha256="oldhash")
    sources = _Sources(str(root), [_Entity("hypothesis:h1", "entities/h1.md")], {"hypothesis:h1": "markdown"})

    result = compute_source_snapshots(sources, prior_graph_path=prior, today=date(2026, 6, 15))

    snap = result.emissions[0].snapshot
    assert snap.latest_change is not None
    assert snap.latest_change.observed_on == date(2026, 6, 15)
    assert snap.sha256 == snap.latest_change.sha256
    assert result.source_changes == {str(source_snapshot_uri("entities/h1.md")): date(2026, 6, 15)}


def test_only_markdown_backed_entities_are_snapshotted(tmp_path: Path):
    root = tmp_path / "demo"
    _write(root / "entities" / "h1.md", "alpha")
    sources = _Sources(
        str(root),
        [_Entity("hypothesis:h1", "entities/h1.md"), _Entity("dataset:d1", "data/d1.csv")],
        {"hypothesis:h1": "markdown", "dataset:d1": "datapackage"},
    )

    result = compute_source_snapshots(sources, prior_graph_path=root / "knowledge" / "graph.trig", today=date(2026, 6, 15))

    assert [e.entity_canonical_id for e in result.emissions] == ["hypothesis:h1"]


def test_missing_prior_graph_is_empty_baseline(tmp_path: Path):
    assert read_prior_snapshots(tmp_path / "nope" / "graph.trig") == {}


def test_empty_prior_graph_is_empty_baseline(tmp_path: Path):
    p = tmp_path / "graph.trig"
    p.write_text("")  # first build writes an empty graph.trig
    assert read_prior_snapshots(p) == {}


def test_corrupt_prior_graph_fails_loud(tmp_path: Path):
    import pytest

    bad = tmp_path / "graph.trig"
    bad.write_text("@@ this is not valid trig @@ <<<>>>")
    with pytest.raises(Exception):  # corrupt non-empty must NOT be silently empty-baselined
        read_prior_snapshots(bad)
