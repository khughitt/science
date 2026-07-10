"""workflow-step --sci:applies--> method (umbrella Spec 1, task:t079)."""

from pathlib import Path

import pytest
from rdflib import Dataset

from science_tool.graph.io import PROJECT_NS, SCI_NS, entity_uri_for_ref
from science_tool.graph.materialize import materialize_graph


def _project(root: Path, *, step_method: str | None, extra_kind: str = "method") -> Path:
    (root / "science.yaml").write_text(
        "name: applies-test\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )
    methods = root / "entities" / "methods"
    methods.mkdir(parents=True, exist_ok=True)
    (methods / "leiden.md").write_text(
        f"---\nid: {extra_kind}:leiden\nkind: {extra_kind}\ntitle: Leiden\n---\n",
        encoding="utf-8",
    )
    steps = root / "entities" / "workflow-steps"
    steps.mkdir(parents=True, exist_ok=True)
    method_line = f"method: {step_method}\n" if step_method is not None else ""
    (steps / "cluster.md").write_text(
        f"---\nid: workflow-step:cluster\nkind: workflow-step\ntitle: Cluster\n{method_line}---\n",
        encoding="utf-8",
    )
    return root


def _knowledge(root: Path) -> Dataset:
    graph_path = materialize_graph(root)
    dataset = Dataset()
    dataset.parse(graph_path, format="trig")
    return dataset


def test_step_applies_edge_is_emitted(tmp_path: Path) -> None:
    root = _project(tmp_path, step_method="method:leiden")
    dataset = _knowledge(root)
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    triple = (
        entity_uri_for_ref("workflow-step:cluster"),
        SCI_NS.applies,
        entity_uri_for_ref("method:leiden"),
    )
    assert triple in knowledge


def test_step_without_a_method_emits_no_edge(tmp_path: Path) -> None:
    root = _project(tmp_path, step_method=None)
    dataset = _knowledge(root)
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    assert not list(knowledge.triples((None, SCI_NS.applies, None)))


def test_step_naming_a_non_method_is_a_hard_error(tmp_path: Path) -> None:
    # `topic:leiden` resolves, so the audit gate passes it; the kind check fires.
    root = _project(tmp_path, step_method="topic:leiden", extra_kind="topic")
    with pytest.raises(ValueError, match="non-method entity"):
        _knowledge(root)


def test_step_naming_an_unresolvable_method_is_a_hard_error(tmp_path: Path) -> None:
    root = _project(tmp_path, step_method="method:does-not-exist")
    with pytest.raises(ValueError):
        _knowledge(root)
