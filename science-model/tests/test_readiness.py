"""Tests for the Readiness protocol on project entities."""
from __future__ import annotations

import pytest

from science_model.entities import (
    EntityType,
    Readiness,
    TaskEntity,
    WorkflowRunEntity,
)


def _minimal(kind: EntityType, id_: str, status: str | None = None) -> dict:
    base = {
        "id": id_,
        "canonical_id": id_,
        "kind": kind.value,
        "type": kind,
        "title": id_,
        "status": status,
        "project": "demo",
        "ontology_terms": [],
        "related": [],
        "source_refs": [],
        "content_preview": "",
        "file_path": f"{id_}.md",
    }
    return base


def _task(status: str = "active") -> TaskEntity:
    return TaskEntity(**_minimal(EntityType.TASK, "task:t001", status=status))


def _workflow_run(status: str = "complete") -> WorkflowRunEntity:
    return WorkflowRunEntity(**_minimal(EntityType.WORKFLOW_RUN, "workflow-run:wfr-001", status=status))


def test_readiness_model_shape():
    r = Readiness(ready=True, state="done")
    assert r.ready is True
    assert r.state == "done"
    assert r.detail == ""


def test_default_readiness_done_is_ready():
    assert _task(status="done").readiness() == Readiness(ready=True, state="done")


@pytest.mark.parametrize("status", ["proposed", "active", "blocked", "deferred", "retired"])
def test_default_readiness_non_done_is_not_ready(status: str):
    r = _task(status=status).readiness()
    assert r.ready is False
    assert r.state == status


def test_default_readiness_empty_status_is_unknown():
    r = _task(status="").readiness()
    assert r.ready is False
    assert r.state == "unknown"


def test_workflow_run_readiness_complete():
    r = _workflow_run(status="complete").readiness()
    assert r.ready is True
    assert r.state == "complete"


@pytest.mark.parametrize("status", ["", "pending", "running", "failed"])
def test_workflow_run_readiness_not_complete(status: str):
    r = _workflow_run(status=status).readiness()
    assert r.ready is False
    assert r.state == (status or "unknown")
