"""workflow-run --sci:executes--> workflow (umbrella Spec 0, task:t087)."""

from pathlib import Path

import pytest
from rdflib import Dataset

from science_tool.graph.io import PROJECT_NS, SCI_NS, entity_uri_for_ref
from science_tool.graph.materialize import materialize_graph


def _project(root: Path, *, run_workflow: str | None) -> Path:
    (root / "science.yaml").write_text(
        "name: executes-test\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )
    workflows = root / "entities" / "workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    (workflows / "scrna-pipeline.md").write_text(
        "---\nid: workflow:scrna-pipeline\nkind: workflow\ntitle: scRNA pipeline\n---\n",
        encoding="utf-8",
    )
    runs = root / "entities" / "workflow-runs"
    runs.mkdir(parents=True, exist_ok=True)
    workflow_line = f"workflow: {run_workflow}\n" if run_workflow is not None else ""
    (runs / "r1.md").write_text(
        f"---\nid: workflow-run:r1\nkind: workflow-run\ntitle: R1\n{workflow_line}---\n",
        encoding="utf-8",
    )
    return root


def _knowledge(trig_path: Path):
    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    return dataset.graph(PROJECT_NS["graph/knowledge"])


def test_run_declaring_a_workflow_emits_executes(tmp_path: Path) -> None:
    trig_path = materialize_graph(_project(tmp_path, run_workflow="workflow:scrna-pipeline"))
    knowledge = _knowledge(trig_path)
    run_uri = entity_uri_for_ref("workflow-run:r1")
    assert list(knowledge.objects(run_uri, SCI_NS.executes)) == [entity_uri_for_ref("workflow:scrna-pipeline")]


def test_run_without_a_workflow_emits_no_edge(tmp_path: Path) -> None:
    trig_path = materialize_graph(_project(tmp_path, run_workflow=None))
    knowledge = _knowledge(trig_path)
    assert list(knowledge.objects(entity_uri_for_ref("workflow-run:r1"), SCI_NS.executes)) == []


def test_run_naming_a_nonexistent_workflow_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="workflow-run:r1"):
        materialize_graph(_project(tmp_path, run_workflow="workflow:does-not-exist"))


def test_run_naming_a_non_workflow_fails_loudly(tmp_path: Path) -> None:
    root = _project(tmp_path, run_workflow="workflow:scrna-pipeline")
    (root / "entities" / "workflow-runs" / "r1.md").write_text(
        "---\nid: workflow-run:r1\nkind: workflow-run\ntitle: R1\nworkflow: workflow-run:r1\n---\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="non-workflow"):
        materialize_graph(root)
