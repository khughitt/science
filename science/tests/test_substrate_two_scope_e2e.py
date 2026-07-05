from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from rdflib import Dataset
from rdflib.namespace import SKOS

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.registry import RegistryBuilder
from science_tool.graph.identity_table import build_identity_table
from science_tool.graph.materialize import materialize_graph
from science_tool.graph.migrate import audit_project_sources
from science_tool.graph.sources import load_project_sources
from science_tool.graph.store import PROJECT_NS

_COMMONS_FIXTURE = Path(__file__).parent / "fixtures" / "commons" / "valid"
_SHARED_ID = "topic:single-cell-foundation-models"


def _build_commons(tmp_path: Path) -> Path:
    commons_root = tmp_path / "commons"
    shutil.copytree(_COMMONS_FIXTURE, commons_root)
    RegistryBuilder(commons_root, CommonsEntityAdapter(commons_root)).rebuild()
    return commons_root


def _project_owning_and_referencing_shared_id(tmp_path: Path) -> Path:
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    manifest = project_root / "knowledge" / "sources" / "local" / "manifest.yaml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("", encoding="utf-8")
    # A LOCAL owner file for the same id commons owns.
    topic = project_root / "entities" / "topics" / "single-cell-foundation-models.md"
    topic.parent.mkdir(parents=True)
    topic.write_text(f'---\nid: "{_SHARED_ID}"\nkind: "topic"\ntitle: "SCFM (local)"\n---\n', encoding="utf-8")
    # A hypothesis that references the shared id with a BARE ref.
    hyp = project_root / "entities" / "hypotheses" / "h1.md"
    hyp.parent.mkdir(parents=True)
    hyp.write_text(
        f'---\nid: "hypothesis:h1"\nkind: "hypothesis"\ntitle: "H1"\nrelated: ["{_SHARED_ID}"]\n---\n',
        encoding="utf-8",
    )
    return project_root


def test_load_produces_two_scope_identity_table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = _project_owning_and_referencing_shared_id(tmp_path)

    sources = load_project_sources(project_root)
    scopes = build_identity_table(sources).owner_scopes_by_id()[_SHARED_ID]
    assert "commons" in scopes
    assert len(scopes) == 2  # this-project owner + commons owner


def test_audit_emits_ambiguous_reference_for_two_scope_bare_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = _project_owning_and_referencing_shared_id(tmp_path)

    sources = load_project_sources(project_root)
    rows, has_failures = audit_project_sources(sources)
    ambiguous = [r for r in rows if r["check"] == "ambiguous_reference"]
    assert has_failures is True
    assert len(ambiguous) == 1
    assert ambiguous[0]["target"] == _SHARED_ID
    assert ambiguous[0]["source"] == "hypothesis:h1"


def _project_with_scoped_ref(tmp_path: Path) -> Path:
    project_root = _project_owning_and_referencing_shared_id(tmp_path)
    # Re-author the hypothesis to use the scoped form -> unambiguous, must materialize.
    hyp = project_root / "entities" / "hypotheses" / "h1.md"
    hyp.write_text(
        f'---\nid: "hypothesis:h1"\nkind: "hypothesis"\ntitle: "H1"\nrelated: ["commons:{_SHARED_ID}"]\n---\n',
        encoding="utf-8",
    )
    return project_root


def _entity_uri(canonical_id: str):
    kind, slug = canonical_id.split(":", 1)
    return PROJECT_NS[f"{kind}/{slug.lower()}"]


def _has_hypothesis_topic_edge(trig_path: Path) -> bool:
    """True iff the materialized graph links hypothesis:h1 -> topic:single-cell-foundation-models.

    Loads the written TriG (rdflib Dataset / trig format) and checks the knowledge
    layer for a skos:related edge between the two entity URIs (same predicate +
    URI scheme the materializer emits for a `related:` ref). The local topic NODE
    is always present, so this edge check — not a node/substring check — is what
    discriminates a resolved scoped ref from a dropped one.
    """
    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    subject = _entity_uri("hypothesis:h1")
    target = _entity_uri(_SHARED_ID)
    return target in set(knowledge.objects(subject, SKOS.related))


def test_materialize_graph_refuses_two_scope_bare_ref(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = _project_owning_and_referencing_shared_id(tmp_path)

    with pytest.raises(ValueError) as excinfo:
        materialize_graph(project_root)
    assert _SHARED_ID in str(excinfo.value)


def test_scoped_ref_resolves_and_materializes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = _project_with_scoped_ref(tmp_path)

    # Audit clean (scoped form disambiguates) ...
    sources = load_project_sources(project_root)
    rows, _ = audit_project_sources(sources)
    assert [r for r in rows if r["check"] == "ambiguous_reference"] == []
    # ... and the build resolves the scoped ref into a real edge between
    # hypothesis:h1 and topic:single-cell-foundation-models.
    trig_path = materialize_graph(project_root)
    assert trig_path.exists()
    assert _has_hypothesis_topic_edge(trig_path)


def _project_scoped_ref_no_local_owner(tmp_path: Path) -> Path:
    """A project that references commons:topic:x via the scoped form WITHOUT locally owning it.

    This is the natural real-world scoped-ref usage and a distinct loader path from the
    collision channel: the commons topic is pulled through the normal commons-load path
    (not recorded as a cross-scope owner), so `commons` lands in `scope_names` via the
    loaded commons entity rather than via a recorded second owner row.
    """
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    manifest = project_root / "knowledge" / "sources" / "local" / "manifest.yaml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("", encoding="utf-8")
    # No local topic owner — only a scoped reference into commons.
    hyp = project_root / "entities" / "hypotheses" / "h1.md"
    hyp.parent.mkdir(parents=True)
    hyp.write_text(
        f'---\nid: "hypothesis:h1"\nkind: "hypothesis"\ntitle: "H1"\nrelated: ["commons:{_SHARED_ID}"]\n---\n',
        encoding="utf-8",
    )
    return project_root


def test_wholly_scoped_no_local_owner_materializes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = _project_scoped_ref_no_local_owner(tmp_path)

    sources = load_project_sources(project_root)
    # Single-scope ownership (commons only); audit clean; scoped ref still resolves to a real edge.
    assert build_identity_table(sources).owner_scopes_by_id()[_SHARED_ID] == frozenset({"commons"})
    rows, _ = audit_project_sources(sources)
    assert [r for r in rows if r["check"] == "ambiguous_reference"] == []
    trig_path = materialize_graph(project_root)
    assert trig_path.exists()
    assert _has_hypothesis_topic_edge(trig_path)
