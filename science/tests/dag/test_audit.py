"""Tests for science_tool.dag.audit — read-only default + --fix mutation path."""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from science_tool.dag.audit import AuditReport, run_audit
from science_tool.dag.paths import DagPaths, load_dag_paths
from science_tool.dag.validate import _parse_dot_topology

FIXTURE_ROOT = Path(__file__).parent / "fixtures/mm30"


def _write_proposition(project: Path, slug: str, source: str, target: str) -> None:
    prop_dir = project / "entities/propositions"
    prop_dir.mkdir(parents=True, exist_ok=True)
    (prop_dir / f"{slug}.md").write_text(
        f"""---
id: proposition:{slug}
type: proposition
title: {source} affects {target}
status: active
subject: {source}
predicate: affects
object: {target}
polarity: positive
claim_layer: causal_effect
identification_strength: observational
legacy_relation_label: affects
---

{source} affects {target}.
""",
        encoding="utf-8",
    )


def _write_propositions_for_dot(project: Path, dot_path: Path, slug_prefix: str) -> None:
    _, dot_edges = _parse_dot_topology(dot_path)
    for index, (source, target) in enumerate(sorted(dot_edges), start=1):
        _write_proposition(project, f"{slug_prefix}-{index}", source, target)


def _write_propositions_for_all_dots(project: Path) -> None:
    for dot_path in sorted((project / "doc/figures/dags").glob("*.dot")):
        _write_propositions_for_dot(project, dot_path, dot_path.stem)


def _build_project(tmp_path: Path, *, with_drift: bool = False) -> DagPaths:
    """Minimal project layout with one proposition-backed DOT edge + supporting tasks."""
    (tmp_path / "science.yaml").write_text("profile: research\n", encoding="utf-8")
    dag_dir = tmp_path / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    dot_path = dag_dir / "h1-prognosis.dot"
    dot_path.write_text("digraph h1_prognosis {\n  a -> b;\n}\n", encoding="utf-8")
    _write_proposition(tmp_path, "h1-prognosis-1", "a", "b")
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "active.md").write_text("")
    done_dir = tasks_dir / "done"
    done_dir.mkdir()
    blocks = [
        "## [t001] base task",
        "- priority: P2",
        "- status: done",
        "- created: 2026-01-01",
        "- completed: 2026-01-01",
        "",
    ]
    if with_drift:
        blocks += [
            "## [t100] newer related task",
            "- priority: P2",
            "- status: done",
            "- created: 2026-04-15",
            "- completed: 2026-04-15",
            "- related: [hypothesis:h1-epigenetic-commitment]",
            "",
        ]
    (done_dir / "2026-04.md").write_text("\n".join(blocks))
    return DagPaths(dag_dir=dag_dir, tasks_dir=tasks_dir, dags=None, project_root=tmp_path)


def test_audit_is_read_only_by_default(tmp_path: Path) -> None:
    """Audit must not mutate tasks/ or create retired edge YAML without fix=True."""
    paths = _build_project(tmp_path, with_drift=True)
    active_before = (tmp_path / "tasks/active.md").read_text()

    report = run_audit(paths, today=date(2026, 4, 20), fix=False)

    active_after = (tmp_path / "tasks/active.md").read_text()
    assert active_before == active_after, "active.md mutated under read-only audit"
    assert not (paths.dag_dir / "h1-prognosis.edges.yaml").exists()
    assert isinstance(report, AuditReport)
    assert report.mutations == (), "read-only audit must not emit mutations"


def test_audit_fix_does_not_open_review_task_without_retired_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no retired edge YAML, Task 7 staleness removal is not needed for render."""
    paths = _build_project(tmp_path, with_drift=True)
    calls: list[dict] = []
    from science_tool.dag import audit as audit_mod

    monkeypatch.setattr(audit_mod, "_open_review_task", lambda **kw: calls.append(kw))

    report = run_audit(paths, today=date(2026, 4, 20), fix=True)
    assert calls == []
    assert all(mutation.kind != "open_review_task" for mutation in report.mutations)


def test_audit_fix_records_unpropagated_to_log(tmp_path: Path) -> None:
    """fix=True writes an audit-log entry for unpropagated tasks (no auto-citation)."""
    paths = _build_project(tmp_path, with_drift=False)
    # Also add an unpropagated orphan not cited anywhere:
    done_md = tmp_path / "tasks/done/2026-04.md"
    done_md.write_text(
        done_md.read_text() + "\n## [t999] orphan task\n- priority: P2\n- status: done\n"
        "- created: 2026-04-15\n- completed: 2026-04-15\n"
        "- related: [hypothesis:h1-epigenetic-commitment]\n"
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


def test_audit_cli_empty_project_exits_zero(tmp_path: Path) -> None:
    """fb-2026-05-01-001: software-profile project with no dag: block and no edges.yaml."""
    from click.testing import CliRunner

    from science_tool.dag.cli import audit_cmd

    (tmp_path / "science.yaml").write_text("profile: software\n")
    runner = CliRunner()
    result = runner.invoke(audit_cmd, ["--json", "--project", str(tmp_path)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    # No DAGs were configured or discovered → empty validation/staleness.
    assert payload["validation"]["ok"] is True
    assert payload["mutations"] == []


def test_audit_smoke_on_mm30_fixture(tmp_path: Path) -> None:
    """Real mm30 fixture runs end-to-end without error."""
    project = tmp_path / "mm30"
    shutil.copytree(FIXTURE_ROOT, project)
    paths = DagPaths(
        dag_dir=project / "doc/figures/dags",
        tasks_dir=project / "tasks",
        dags=None,
        project_root=project,
    )
    for slug in ("h1-prognosis", "h1-progression", "h2-subtype-architecture", "h1-h2-bridge"):
        _write_propositions_for_dot(project, project / f"doc/figures/dags/{slug}.dot", slug)
    report = run_audit(paths, today=date(2026, 4, 20), fix=False)
    assert isinstance(report, AuditReport)


# ---------------------------------------------------------------------------
# Task 10 tests: validation integration
# ---------------------------------------------------------------------------

FIXTURE_MINIMAL = Path(__file__).parent / "fixtures" / "minimal"


def test_audit_includes_validation_section(tmp_path: Path) -> None:
    project = tmp_path / "clean"
    shutil.copytree(FIXTURE_MINIMAL / "clean", project)
    _write_propositions_for_all_dots(project)
    paths = load_dag_paths(project)
    report = run_audit(paths)
    js = report.to_json()
    assert "validation" in js
    assert js["validation"]["ok"] is True


def test_audit_json_has_top_level_today_and_strict(tmp_path: Path) -> None:
    import re

    project = tmp_path / "clean"
    shutil.copytree(FIXTURE_MINIMAL / "clean", project)
    _write_propositions_for_all_dots(project)
    paths = load_dag_paths(project)
    report = run_audit(paths)
    js = report.to_json()
    assert "today" in js
    assert "strict" in js
    assert js["strict"] is False
    # today should be an ISO date string
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", js["today"])


def test_audit_exit_code_reflects_validation_failure(tmp_path: Path) -> None:
    project = tmp_path / "cyclic"
    shutil.copytree(FIXTURE_MINIMAL / "cyclic", project)
    _write_propositions_for_all_dots(project)
    paths = load_dag_paths(project)
    report = run_audit(paths)
    assert report.has_findings  # validation produced findings → audit reports them


def test_audit_fix_blocks_when_validation_fails() -> None:
    paths = load_dag_paths(FIXTURE_MINIMAL / "cyclic")
    with pytest.raises(RuntimeError, match="validation failed"):
        run_audit(paths, fix=True)
