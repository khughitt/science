"""Tests for the Readiness protocol on project entities."""
from __future__ import annotations

import pytest

from science_model.entities import (
    DatasetEntity,
    EntityType,
    Readiness,
    TaskEntity,
    WorkflowRunEntity,
)
from science_model.packages.schema import AccessBlock, AccessException, DerivationBlock


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


# ---------------------------------------------------------------------------
# DatasetEntity readiness tests
# ---------------------------------------------------------------------------


def _external_dataset(access: AccessBlock) -> DatasetEntity:
    return DatasetEntity(**_minimal(EntityType.DATASET, "dataset:foo"), origin="external", access=access)


def _derived_dataset(workflow_run: str = "workflow-run:wfr-001") -> DatasetEntity:
    return DatasetEntity(
        **_minimal(EntityType.DATASET, "dataset:foo-derived"),
        origin="derived",
        derivation=DerivationBlock(
            workflow="workflow:foo",
            workflow_run=workflow_run,
            git_commit="deadbeef",
            config_snapshot="cfg",
            produced_at="2026-05-03",
        ),
    )


def test_dataset_external_available_verified_is_ready():
    ds = _external_dataset(AccessBlock(level="public", verified=True))
    r = ds.readiness()
    assert r.ready is True
    assert r.state == "available"


def test_dataset_external_available_unverified_is_not_ready():
    ds = _external_dataset(AccessBlock(level="controlled", verified=False))
    r = ds.readiness()
    assert r.ready is False
    assert r.state == "controlled, unverified"


def test_dataset_external_embargoed_is_not_ready():
    ds = _external_dataset(
        AccessBlock(level="controlled", verified=False, availability="embargoed")
    )
    r = ds.readiness()
    assert r.ready is False
    assert r.state == "embargoed"


def test_dataset_external_embargoed_with_window_includes_detail():
    ds = _external_dataset(
        AccessBlock(
            level="controlled",
            verified=False,
            availability="embargoed",
            available_after="2026-Q3",
        )
    )
    r = ds.readiness()
    assert r.ready is False
    assert r.state == "embargoed"
    assert "2026-Q3" in r.detail


def test_dataset_external_withdrawn_is_not_ready():
    ds = _external_dataset(
        AccessBlock(level="controlled", verified=True, availability="withdrawn")
    )
    r = ds.readiness()
    assert r.ready is False
    assert r.state == "withdrawn"


def test_dataset_external_exception_scope_reduced_is_ready():
    ds = _external_dataset(
        AccessBlock(
            level="controlled",
            verified=False,
            exception=AccessException(mode="scope-reduced", rationale="subset only"),
        )
    )
    r = ds.readiness()
    assert r.ready is True
    assert r.state == "consumable-via-scope-reduced"
    assert "subset only" in r.detail


def test_dataset_external_exception_substituted_is_ready():
    ds = _external_dataset(
        AccessBlock(
            level="controlled",
            verified=False,
            exception=AccessException(mode="substituted", rationale="using mirror"),
        )
    )
    r = ds.readiness()
    assert r.ready is True
    assert r.state == "consumable-via-substituted"
    assert "using mirror" in r.detail


def test_dataset_external_exception_acquiring_is_not_ready():
    ds = _external_dataset(
        AccessBlock(
            level="controlled",
            verified=False,
            exception=AccessException(mode="expanded-to-acquire", rationale="dbGaP request open"),
        )
    )
    r = ds.readiness()
    assert r.ready is False
    assert r.state == "acquiring"
    assert "dbGaP" in r.detail


def test_dataset_derived_without_resolver_degrades_gracefully():
    ds = _derived_dataset()
    r = ds.readiness()
    assert r.ready is False
    assert r.state == "unknown"
    assert "resolver" in r.detail
