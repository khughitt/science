"""Tests for ReadinessResolver."""

from __future__ import annotations

from science_model.entities import (
    DatasetEntity,
    EntityType,
    ProjectEntity,
    Readiness,
    WorkflowRunEntity,
)
from science_model.packages.schema import DerivationBlock

from science_tool.tasks_readiness import ReadinessResolver


def _minimal(kind: EntityType, id_: str, status: str | None = None) -> dict:
    return {
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


def _wfr(run_id: str, status: str) -> WorkflowRunEntity:
    return WorkflowRunEntity(**_minimal(EntityType.WORKFLOW_RUN, run_id, status=status))


def _derived(ds_id: str, run_id: str) -> DatasetEntity:
    return DatasetEntity(
        **_minimal(EntityType.DATASET, ds_id),
        origin="derived",
        derivation=DerivationBlock(
            workflow="workflow:w",
            workflow_run=run_id,
            git_commit="x",
            config_snapshot="y",
            produced_at="2026-05-03",
        ),
    )


def test_resolver_returns_unresolved_for_unknown_ref():
    resolver = ReadinessResolver(lookup=lambda _: None)
    r = resolver.resolve_ref("dataset:nope")
    assert r.ready is False
    assert r.state == "unresolved"
    assert "dataset:nope" in r.detail


def test_resolver_delegates_to_entity_readiness():
    wfr = _wfr("workflow-run:r1", status="complete")
    resolver = ReadinessResolver(lookup={"workflow-run:r1": wfr}.get)
    r = resolver.resolve_ref("workflow-run:r1")
    assert r == Readiness(ready=True, state="complete")


def test_resolver_caches_repeated_lookups():
    wfr = _wfr("workflow-run:r1", status="complete")
    calls: list[str] = []

    def lookup(ref: str) -> ProjectEntity | None:
        calls.append(ref)
        return wfr if ref == "workflow-run:r1" else None

    resolver = ReadinessResolver(lookup=lookup)
    resolver.resolve_ref("workflow-run:r1")
    resolver.resolve_ref("workflow-run:r1")
    resolver.resolve_ref("workflow-run:r1")
    assert calls == ["workflow-run:r1"]


def test_resolver_detects_cycle():
    # dataset:A is derived from workflow-run:R, which (in this synthetic case)
    # has been authored to reference dataset:A. The resolver must not infinite-loop.
    ds_a = _derived("dataset:A", "workflow-run:R")

    class CyclingRun(WorkflowRunEntity):
        def readiness(self, resolver=None):
            # Simulate a cycle: this run's readiness re-asks about dataset:A.
            assert resolver is not None
            return resolver.resolve_ref("dataset:A")

    run = CyclingRun(**_minimal(EntityType.WORKFLOW_RUN, "workflow-run:R", status="complete"))
    store = {"dataset:A": ds_a, "workflow-run:R": run}
    resolver = ReadinessResolver(lookup=store.get)
    r = resolver.resolve_ref("dataset:A")
    assert r.ready is False
    assert r.state == "cycle"


def test_resolver_drives_derived_dataset_to_workflow_run():
    wfr = _wfr("workflow-run:r1", status="complete")
    ds = _derived("dataset:derived", "workflow-run:r1")
    store = {"dataset:derived": ds, "workflow-run:r1": wfr}
    resolver = ReadinessResolver(lookup=store.get)
    r = resolver.resolve_ref("dataset:derived")
    assert r.ready is True
    assert r.state == "complete"


def test_resolver_drives_derived_dataset_workflow_run_not_yet_complete():
    wfr = _wfr("workflow-run:r1", status="running")
    ds = _derived("dataset:derived", "workflow-run:r1")
    store = {"dataset:derived": ds, "workflow-run:r1": wfr}
    resolver = ReadinessResolver(lookup=store.get)
    r = resolver.resolve_ref("dataset:derived")
    assert r.ready is False
    assert r.state == "running"
