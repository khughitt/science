"""Canary coverage for mm30-shaped commons/project references.

The fixture exercises four patterns: a hypothesis reference to a commons
topic, an interpretation reference to a commons topic, a task DSL reference to
a commons topic, and a project overlay for the same commons topic that is also
referenced by a project entity.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from rdflib import Dataset, Literal
from rdflib.namespace import SKOS

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.registry import RegistryBuilder
from science_tool.graph.io import SCI_NS
from science_tool.graph.materialize import _entity_uri, materialize_graph
from science_tool.graph.migrate import audit_project_sources
from science_tool.graph.sources import ProjectSources, load_project_sources

_FIXTURE = Path(__file__).parent / "fixtures" / "commons_mm30_canary"


def _stage_fixture(tmp_path: Path) -> tuple[Path, Path]:
    commons = tmp_path / "commons"
    project = tmp_path / "project"
    shutil.copytree(_FIXTURE / "commons", commons)
    shutil.copytree(_FIXTURE / "project", project)
    RegistryBuilder(commons, CommonsEntityAdapter(commons)).rebuild()
    return project, commons


def _load_sources(project: Path) -> ProjectSources:
    sources = load_project_sources(project)
    rows, has_failures = audit_project_sources(sources)
    assert not has_failures, rows
    return sources


def _entity_ids(sources: ProjectSources) -> set[str]:
    return {entity.canonical_id for entity in sources.entities}


def test_canary_hypothesis_ref_resolves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, commons = _stage_fixture(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")

    sources = _load_sources(project)

    assert "hypothesis:h4-attractor-convergence" in _entity_ids(sources)
    assert "topic:cancer-as-singular-evolutionary-disease" in _entity_ids(sources)


def test_canary_interpretation_ref_resolves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, commons = _stage_fixture(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")

    sources = _load_sources(project)

    assert "interpretation:2026-04-23-t650-demo" in _entity_ids(sources)
    assert "topic:formal-causal-mediation" in _entity_ids(sources)


def test_canary_task_ref_resolves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, commons = _stage_fixture(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")

    sources = _load_sources(project)

    assert "task:t286" in _entity_ids(sources)
    assert "topic:causal-inference-biology-foundations" in _entity_ids(sources)


def test_canary_overlay_and_inbound_ref_share_single_entity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, commons = _stage_fixture(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")

    sources = _load_sources(project)

    matches = [
        entity for entity in sources.entities if entity.canonical_id == "topic:epigenetic-chromatin-mm-progression"
    ]
    assert len(matches) == 1
    assert sources.entity_source_adapters[matches[0].canonical_id] == "commons-merged"
    assert sources.commons_overlay_paths == {
        "topic:epigenetic-chromatin-mm-progression": str(
            project / "overlays" / "topics" / "epigenetic-chromatin-mm-progression.md"
        )
    }


def test_canary_materialize_succeeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, commons = _stage_fixture(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")

    trig_path = materialize_graph(project)

    ds = Dataset()
    ds.parse(source=str(trig_path), format="trig")
    hypothesis_uri = _entity_uri("hypothesis:h4-attractor-convergence")
    cancer_uri = _entity_uri("topic:cancer-as-singular-evolutionary-disease")
    scopes = [obj for _, _, obj, _ in ds.quads((cancer_uri, SCI_NS.scope, None, None))]
    related_targets = [obj for _, _, obj, _ in ds.quads((hypothesis_uri, SKOS.related, None, None))]

    assert cancer_uri in related_targets
    assert Literal("cross-project") in scopes
