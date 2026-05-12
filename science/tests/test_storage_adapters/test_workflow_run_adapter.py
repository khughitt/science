from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from science_model.entities import WorkflowRunEntity

from science_tool.graph.sources import load_project_sources
from science_tool.graph.storage_adapters.workflow_run import WorkflowRunAdapter


def test_workflow_run_adapter_loads_results_datapackage_json(tmp_path, monkeypatch) -> None:
    project = tmp_path / "project"
    manifest = project / "results" / "run-a" / "datapackage.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        """
{
  "name": "run-a",
  "title": "Run A",
  "resources": [{"path": "table.csv"}],
  "created": "2026-05-12T10:00:00Z"
}
""".strip(),
        encoding="utf-8",
    )

    adapter = WorkflowRunAdapter()
    refs = adapter.discover(project)
    monkeypatch.chdir(project)
    raw = adapter.load_raw(refs[0])

    assert len(refs) == 1
    assert raw["kind"] == "workflow-run"
    assert raw["id"] == "workflow-run:run-a"
    assert raw["title"] == "Run A"
    assert raw["created"] == "2026-05-12"
    assert raw["manifest_path"] == "results/run-a/datapackage.json"


def test_load_project_sources_loads_workflow_run_manifest(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: project\nprofiles: {local: local}\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "results" / "run-a" / "datapackage.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        """
{
  "name": "run-a",
  "title": "Run A",
  "resources": [{"path": "table.csv"}],
  "created": "2026-05-12T10:00:00Z"
}
""".strip(),
        encoding="utf-8",
    )

    sources = load_project_sources(tmp_path)
    entity = next(e for e in sources.entities if e.canonical_id == "workflow-run:run-a")

    assert isinstance(entity, WorkflowRunEntity)
    assert entity.title == "Run A"
    assert entity.created == date(2026, 5, 12)
    assert entity.file_path == "results/run-a/datapackage.json"


def test_workflow_run_adapter_preserves_date_only_created(tmp_path, monkeypatch) -> None:
    project = tmp_path / "project"
    manifest = project / "results" / "run-a" / "datapackage.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        """
{
  "name": "run-a",
  "title": "Run A",
  "created": "2026-05-12"
}
""".strip(),
        encoding="utf-8",
    )

    adapter = WorkflowRunAdapter()
    refs = adapter.discover(project)
    monkeypatch.chdir(project)

    assert adapter.load_raw(refs[0])["created"] == "2026-05-12"


def test_workflow_run_adapter_rejects_invalid_created_with_manifest_path(tmp_path, monkeypatch) -> None:
    project = tmp_path / "project"
    manifest = project / "results" / "run-a" / "datapackage.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        """
{
  "name": "run-a",
  "title": "Run A",
  "created": "2026-05-12Tnot-a-time"
}
""".strip(),
        encoding="utf-8",
    )

    adapter = WorkflowRunAdapter()
    refs = adapter.discover(project)
    monkeypatch.chdir(project)

    with pytest.raises(ValueError, match="results/run-a/datapackage.json"):
        adapter.load_raw(refs[0])


def test_workflow_run_adapter_rejects_invalid_json_with_manifest_path(tmp_path, monkeypatch) -> None:
    project = tmp_path / "project"
    manifest = project / "results" / "run-a" / "datapackage.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{not-json", encoding="utf-8")

    adapter = WorkflowRunAdapter()
    refs = adapter.discover(project)
    monkeypatch.chdir(project)

    with pytest.raises(ValueError, match="results/run-a/datapackage.json"):
        adapter.load_raw(refs[0])
