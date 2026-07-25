from __future__ import annotations

from pathlib import Path

import pytest
from rdflib.namespace import RDF

from science_tool.graph.autonomous_runs import run_node_uri
from science_tool.graph.dataset_usage import project_entity_uri
from science_tool.graph.materialize import build_dataset_from_sources
from science_tool.graph.sources import load_project_sources
from science_tool.graph.store import PROJECT_NS, SCI_NS

RUN_ID = "run:2026-07-24-curation-sweep-a3f1"

_RECORD = f"""---
id: {RUN_ID}
agent: curation-sweep
model: claude-opus-5
tier: belief-neutral
branch: auto/2026-07-24-curation-sweep-a3f1
base_commit: {"a" * 40}
head_commit: {"b" * 40}
toolkit_revision: {"c" * 40}
policy_identity:
  id: core-default
  version: "1"
basis_digest: {"d" * 64}
started: 2026-07-24T09:00:00+00:00
ended: 2026-07-24T09:30:00+00:00
budget:
  tokens: 12000
  wall_clock_seconds: 1800.5
disposition: clean
---

Swept stale status lines.
"""


def write_project(root: Path, *, with_run: bool = True, entity_extra: str = "") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "science.yaml").write_text(
        "name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )
    topics = root / "entities" / "topics"
    topics.mkdir(parents=True, exist_ok=True)
    (topics / "demo.md").write_text(
        "---\n"
        "id: topic:demo\n"
        "kind: topic\n"
        "title: Demo topic\n"
        "status: active\n"
        f"{entity_extra}"
        "---\n\nBody.\n",
        encoding="utf-8",
    )
    if with_run:
        runs = root / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        (runs / "2026-07-24-curation-sweep-a3f1.md").write_text(_RECORD, encoding="utf-8")


def graphs(root: Path):
    sources = load_project_sources(root)
    dataset = build_dataset_from_sources(sources)
    return (
        sources,
        dataset.graph(PROJECT_NS["graph/knowledge"]),
        dataset.graph(PROJECT_NS["graph/provenance"]),
    )


def test_run_records_reach_project_sources(tmp_path: Path) -> None:
    write_project(tmp_path)
    sources = load_project_sources(tmp_path)
    assert [record.id for record in sources.run_records] == [RUN_ID]


def test_project_without_runs_dir_loads_clean(tmp_path: Path) -> None:
    write_project(tmp_path, with_run=False)
    sources = load_project_sources(tmp_path)
    assert sources.run_records == []


def test_run_record_materializes_into_provenance(tmp_path: Path) -> None:
    write_project(tmp_path)
    _, _knowledge, provenance = graphs(tmp_path)
    node = run_node_uri(RUN_ID)
    assert (node, RDF.type, SCI_NS.AutonomousRun) in provenance
    assert (node, SCI_NS.runDisposition, None) in provenance


def test_no_run_triple_reaches_knowledge(tmp_path: Path) -> None:
    # Design testing item 9. Checked over the WHOLE knowledge graph in both subject and
    # object position: a run node that leaked into knowledge without a freshness state
    # would still pass a narrower "not an attention candidate" assertion.
    write_project(tmp_path)
    _, knowledge, _provenance = graphs(tmp_path)
    node = run_node_uri(RUN_ID)
    assert (node, None, None) not in knowledge
    assert (None, None, node) not in knowledge
    assert (None, RDF.type, SCI_NS.AutonomousRun) not in knowledge


def test_run_materialization_is_idempotent(tmp_path: Path) -> None:
    write_project(tmp_path)
    sources = load_project_sources(tmp_path)
    first = build_dataset_from_sources(sources).graph(PROJECT_NS["graph/provenance"])
    second = build_dataset_from_sources(sources).graph(PROJECT_NS["graph/provenance"])
    assert set(first) == set(second)


def test_entity_links_to_its_run(tmp_path: Path) -> None:
    write_project(tmp_path, entity_extra=f"autonomous_run: {RUN_ID}\n")
    _, _knowledge, provenance = graphs(tmp_path)
    topic = project_entity_uri("topic:demo")
    assert (topic, SCI_NS.autonomousRun, run_node_uri(RUN_ID)) in provenance


def test_the_entity_run_edge_stays_out_of_knowledge(tmp_path: Path) -> None:
    write_project(tmp_path, entity_extra=f"autonomous_run: {RUN_ID}\n")
    _, knowledge, _provenance = graphs(tmp_path)
    assert (None, SCI_NS.autonomousRun, None) not in knowledge


def test_unknown_run_id_raises(tmp_path: Path) -> None:
    write_project(
        tmp_path, entity_extra="autonomous_run: run:2026-07-24-curation-sweep-ffff\n"
    )
    with pytest.raises(ValueError, match="unknown run record"):
        graphs(tmp_path)


def test_entity_without_the_field_emits_no_edge(tmp_path: Path) -> None:
    write_project(tmp_path)
    _, _knowledge, provenance = graphs(tmp_path)
    assert (None, SCI_NS.autonomousRun, None) not in provenance


def test_added_by_still_materializes_alongside(tmp_path: Path) -> None:
    write_project(
        tmp_path, entity_extra=f"added_by: user\nautonomous_run: {RUN_ID}\n"
    )
    _, _knowledge, provenance = graphs(tmp_path)
    topic = project_entity_uri("topic:demo")
    assert (topic, SCI_NS.addedBy, None) in provenance
    assert (topic, SCI_NS.autonomousRun, None) in provenance
