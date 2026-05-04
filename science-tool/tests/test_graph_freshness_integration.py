"""End-to-end integration: materialize_graph emits bears_on + freshness triples."""

from __future__ import annotations

import pytest
from pathlib import Path
from textwrap import dedent

from rdflib import Dataset, URIRef

from science_tool.graph.materialize import materialize_graph
from science_tool.graph.store import PROJECT_NS, SCI_NS


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip("\n"))


def _build_min_project(tmp_path: Path) -> Path:
    """Minimal project with one hypothesis + one task that tests it.

    A task fixture is used (not workflow-run) because materialize.py converts
    `related: [hypothesis:foo]` to a `sci:tests` triple only when the source
    entity's kind is `task` (see `materialize.py:220`). Workflow-runs would
    need an explicit authored sci:tests relation, which is heavier to set up
    in a fixture; the bears_on derivation rule fires identically either way.
    """
    root = tmp_path / "demo"
    _write(root / "science.yaml", """
        name: demo
        knowledge_profiles:
          local: core
    """)
    _write(root / "knowledge" / "graph.trig", "")
    _write(root / "doc" / "hypotheses" / "h1.md", """
        ---
        id: "hypothesis:h1"
        kind: "hypothesis"
        title: "Demo hypothesis"
        created: "2026-04-01"
        updated: "2026-04-01"
        ---
        Body.
    """)
    _write(root / "doc" / "tasks" / "t1.md", """
        ---
        id: "task:t1"
        kind: "task"
        title: "Demo task"
        status: "active"
        created: "2026-05-01"
        updated: "2026-05-01"
        related: ["hypothesis:h1"]
        ---
        Body.
    """)
    return root


def _load_dataset(path: Path) -> Dataset:
    ds = Dataset()
    ds.parse(path, format="trig")
    return ds


def test_materialize_emits_bears_on_when_task_tests_hypothesis(tmp_path: Path):
    root = _build_min_project(tmp_path)
    trig = materialize_graph(root)
    ds = _load_dataset(trig)
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])

    pairs = {(str(s), str(o)) for s, _, o in knowledge.triples((None, SCI_NS.bearsOn, None))}
    task_uri = str(URIRef(PROJECT_NS["task/t1"]))
    h_uri = str(URIRef(PROJECT_NS["hypothesis/h1"]))
    assert (task_uri, h_uri) in pairs


def test_materialize_emits_freshness_state(tmp_path: Path):
    root = _build_min_project(tmp_path)
    trig = materialize_graph(root)
    ds = _load_dataset(trig)
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])

    h_uri = URIRef(PROJECT_NS["hypothesis/h1"])
    states = [str(o) for _, _, o in knowledge.triples((h_uri, SCI_NS.freshnessState, None))]
    # h1.created = 2026-04-01, last_reviewed unset, t1.updated = 2026-05-01 > created => needs-review.
    assert states == ["needs-review"]


def test_materialize_does_not_mutate_entity_files(tmp_path: Path):
    root = _build_min_project(tmp_path)
    h_path = root / "doc" / "hypotheses" / "h1.md"
    before = h_path.read_text()
    before_mtime = h_path.stat().st_mtime_ns

    materialize_graph(root)

    assert h_path.read_text() == before
    assert h_path.stat().st_mtime_ns == before_mtime


def test_materialize_rejects_hand_authored_bears_on_to_non_epistemic_target(tmp_path: Path):
    """A hand-authored sci:bearsOn pointing at a dataset (operational) is invalid."""
    root = _build_min_project(tmp_path)
    # Inject a structured relation that points bears_on at a dataset.
    (root / "doc" / "datasets").mkdir(parents=True, exist_ok=True)
    (root / "doc" / "datasets" / "d1.md").write_text(
        dedent(
            """
            ---
            id: "dataset:d1"
            kind: "dataset"
            title: "Demo"
            origin: "external"
            access:
              level: "public"
              verified: true
            created: "2026-04-01"
            updated: "2026-04-01"
            ---
            """
        ).lstrip()
    )
    # Relations go in knowledge/sources/{local_profile}/relations.yaml with a
    # top-level "relations:" key. The project uses local: core.
    relations_yaml = root / "knowledge" / "sources" / "core" / "relations.yaml"
    relations_yaml.parent.mkdir(parents=True, exist_ok=True)
    relations_yaml.write_text(
        "relations:\n"
        '  - subject: "task:t1"\n'
        '    predicate: "sci:bearsOn"\n'
        '    object: "dataset:d1"\n'
        '    graph_layer: "graph/knowledge"\n'
    )

    with pytest.raises(ValueError, match="bears_on"):
        materialize_graph(root)


def test_materialize_emits_closure_bears_on_through_observation(tmp_path: Path):
    """Closure end-to-end: workflow-run grounds observation supports proposition addresses hypothesis.

    Note: at materialize time, only the typed-edge bears_on rules fire directly
    (workflow-run grounds observation -> bears_on; observation supports proposition
    -> bears_on). Closure should then emit (workflow-run, bears_on, proposition)
    as a transitive triple.
    """
    root = tmp_path / "demo"
    _write(root / "science.yaml", """
        name: demo
        knowledge_profiles:
          local: core
    """)
    _write(root / "doc" / "propositions" / "p1.md", """
        ---
        id: "proposition:p1"
        kind: "proposition"
        title: "Demo prop"
        created: "2026-04-01"
        updated: "2026-04-01"
        ---
        Body.
    """)
    _write(root / "doc" / "observations" / "o1.md", """
        ---
        id: "observation:o1"
        kind: "observation"
        title: "Demo obs"
        created: "2026-04-01"
        updated: "2026-04-01"
        ---
        Body.
    """)
    # observation supports proposition (cito:supports edge via authored relations)
    _write(root / "knowledge" / "sources" / "core" / "relations.yaml", """
        relations:
          - subject: "observation:o1"
            predicate: "cito:supports"
            object: "proposition:p1"
            graph_layer: "graph/knowledge"
          - subject: "workflow-run:wfr1"
            predicate: "sci:grounds"
            object: "observation:o1"
            graph_layer: "graph/knowledge"
    """)
    _write(root / "doc" / "workflow-runs" / "wfr1.md", """
        ---
        id: "workflow-run:wfr1"
        kind: "workflow-run"
        title: "Demo run"
        status: "complete"
        created: "2026-04-01"
        updated: "2026-04-01"
        ---
        Body.
    """)

    trig = materialize_graph(root)
    ds = _load_dataset(trig)
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])

    pairs = {(str(s), str(o)) for s, _, o in knowledge.triples((None, SCI_NS.bearsOn, None))}
    wfr_uri = str(URIRef(PROJECT_NS["workflow-run/wfr1"]))
    o_uri = str(URIRef(PROJECT_NS["observation/o1"]))
    p_uri = str(URIRef(PROJECT_NS["proposition/p1"]))

    # Direct bears_on edges from typed-edge rules:
    assert (wfr_uri, o_uri) in pairs, "sci:grounds rule should produce bears_on"
    assert (o_uri, p_uri) in pairs, "cito:supports rule should produce bears_on"

    # Transitive closure should emit:
    assert (wfr_uri, p_uri) in pairs, "closure should produce wfr -> proposition"
