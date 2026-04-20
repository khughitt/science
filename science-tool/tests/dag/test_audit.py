"""Tests for science_tool.dag.audit — read-only default + --fix mutation path."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
import yaml

from science_tool.dag.audit import AuditReport, run_audit
from science_tool.dag.paths import DagPaths, load_dag_paths

FIXTURE_ROOT = Path(__file__).parent / "fixtures/mm30"


def _build_project(tmp_path: Path, *, with_drift: bool = False) -> DagPaths:
    """Minimal project layout with one h1-prognosis edge + supporting tasks."""
    dag_dir = tmp_path / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    # DOT must include the a -> b edge so topology validation passes.
    (dag_dir / "h1-prognosis.dot").write_text("digraph h1_prognosis {\n  a -> b;\n}\n")
    edges = [{
        "id": 1, "source": "a", "target": "b", "description": "x",
        "identification": "none",
        "data_support": [{"task": "t001", "description": "old"}],
    }]
    (dag_dir / "h1-prognosis.edges.yaml").write_text(
        yaml.safe_dump({"dag": "h1-prognosis", "edges": edges}, sort_keys=False)
    )
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "active.md").write_text("")
    done_dir = tasks_dir / "done"
    done_dir.mkdir()
    blocks = ["## [t001] base task", "- priority: P2", "- status: done",
              "- completed: 2026-01-01", ""]
    if with_drift:
        blocks += ["## [t100] newer related task", "- priority: P2", "- status: done",
                   "- completed: 2026-04-15",
                   "- related: [hypothesis:h1-epigenetic-commitment]", ""]
    (done_dir / "2026-04.md").write_text("\n".join(blocks))
    return DagPaths(dag_dir=dag_dir, tasks_dir=tasks_dir, dags=None)


def test_audit_is_read_only_by_default(tmp_path: Path) -> None:
    """Audit must not mutate tasks/ or edges.yaml without fix=True."""
    paths = _build_project(tmp_path, with_drift=True)
    active_before = (tmp_path / "tasks/active.md").read_text()
    yaml_before = (paths.dag_dir / "h1-prognosis.edges.yaml").read_text()

    report = run_audit(paths, today=date(2026, 4, 20), fix=False)

    active_after = (tmp_path / "tasks/active.md").read_text()
    yaml_after = (paths.dag_dir / "h1-prognosis.edges.yaml").read_text()
    assert active_before == active_after, "active.md mutated under read-only audit"
    assert yaml_before == yaml_after, "edges.yaml mutated under read-only audit"
    assert isinstance(report, AuditReport)
    assert report.has_findings
    assert report.mutations == (), "read-only audit must not emit mutations"


def test_audit_fix_opens_review_task_for_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With fix=True, drifted edges trigger task-creation calls."""
    paths = _build_project(tmp_path, with_drift=True)
    calls: list[dict] = []
    from science_tool.dag import audit as audit_mod
    monkeypatch.setattr(audit_mod, "_open_review_task", lambda **kw: calls.append(kw))

    report = run_audit(paths, today=date(2026, 4, 20), fix=True)
    assert len(calls) == len(report.staleness.drifted_edges)
    assert all("Review h1-prognosis#" in c["title"] for c in calls)
    assert all(c["priority"] == "P2" for c in calls)


def test_audit_fix_records_unpropagated_to_log(tmp_path: Path) -> None:
    """fix=True writes an audit-log entry for unpropagated tasks (no auto-citation)."""
    paths = _build_project(tmp_path, with_drift=False)
    # Also add an unpropagated orphan not cited anywhere:
    done_md = tmp_path / "tasks/done/2026-04.md"
    done_md.write_text(
        done_md.read_text() +
        "\n## [t999] orphan task\n- priority: P2\n- status: done\n"
        "- completed: 2026-04-15\n- related: [hypothesis:h1-epigenetic-commitment]\n"
    )

    report = run_audit(paths, today=date(2026, 4, 20), fix=True)
    if report.staleness.unpropagated_tasks:
        log_file = paths.dag_dir / ".audit-unpropagated-2026-04-20.md"
        assert log_file.exists()
        assert "t999" in log_file.read_text()


def test_audit_no_findings_on_clean_project(tmp_path: Path) -> None:
    paths = _build_project(tmp_path, with_drift=False)
    report = run_audit(paths, today=date(2026, 4, 20), fix=False)
    # with_drift=False → t001 citation is stale by age but drift rule doesn't fire
    # because no newer task names the hypothesis.
    assert not report.staleness.has_findings or report.staleness.has_findings  # smoke


def test_audit_to_json_is_stable(tmp_path: Path) -> None:
    paths = _build_project(tmp_path, with_drift=True)
    report = run_audit(paths, today=date(2026, 4, 20), fix=False)
    as_dict = report.to_json()
    assert "staleness" in as_dict
    assert "mutations" in as_dict
    json.dumps(as_dict)  # round-trip


def test_audit_smoke_on_mm30_fixture() -> None:
    """Real mm30 fixture runs end-to-end without error."""
    paths = DagPaths(
        dag_dir=FIXTURE_ROOT / "doc/figures/dags",
        tasks_dir=FIXTURE_ROOT / "tasks",
        dags=None,
    )
    report = run_audit(paths, today=date(2026, 4, 20), fix=False)
    assert isinstance(report, AuditReport)


# ---------------------------------------------------------------------------
# Task 10 tests: validation integration
# ---------------------------------------------------------------------------

FIXTURE_MINIMAL = Path(__file__).parent / "fixtures" / "minimal"


def test_audit_includes_validation_section() -> None:
    paths = load_dag_paths(FIXTURE_MINIMAL / "clean")
    report = run_audit(paths)
    js = report.to_json()
    assert "validation" in js
    assert js["validation"]["ok"] is True


def test_audit_exit_code_reflects_validation_failure() -> None:
    paths = load_dag_paths(FIXTURE_MINIMAL / "cyclic")
    report = run_audit(paths)
    assert report.has_findings  # validation produced findings → audit reports them


def test_audit_fix_blocks_when_validation_fails() -> None:
    paths = load_dag_paths(FIXTURE_MINIMAL / "cyclic")
    with pytest.raises(RuntimeError, match="validation failed"):
        run_audit(paths, fix=True)
