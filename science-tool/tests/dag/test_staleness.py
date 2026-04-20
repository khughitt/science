"""Tests for science_tool.dag.staleness — drift-based edge audit."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
import yaml

from science_tool.dag.paths import DagPaths
from science_tool.dag.staleness import (
    CandidateTask,
    DriftedEdge,
    StalenessReport,
    UnpropagatedTask,
    UnresolvedRef,
    check_staleness,
)

FIXTURE_ROOT = Path(__file__).parent / "fixtures/mm30"


def _paths_for(project_root: Path) -> DagPaths:
    return DagPaths(
        dag_dir=project_root / "doc/figures/dags",
        tasks_dir=project_root / "tasks",
        dags=None,
    )


def test_mm30_fixture_runs_without_error() -> None:
    """Smoke test on the real mm30 fixture. Must not raise even with 3 fixtures
    that fail EdgesYamlFile validation (staleness parses YAML dicts directly)."""
    report = check_staleness(_paths_for(FIXTURE_ROOT), today=date(2026, 4, 20))
    assert isinstance(report, StalenessReport)


def test_drift_flags_edge_with_newer_related_task(tmp_path: Path) -> None:
    """Edge cites t001 (completed 2026-01-01); t100 completed 2026-04-15 with
    related:[hypothesis:h1-epigenetic-commitment]. Edge belongs to h1-prognosis
    → should flag."""
    _build_minimal_project(
        tmp_path,
        slug="h1-prognosis",
        edges=[{"id": 1, "source": "a", "target": "b", "description": "x",
                "data_support": [{"task": "t001", "description": "old"}]}],
        tasks=[
            ("t001", date(2026, 1, 1), []),
            ("t100", date(2026, 4, 15), ["hypothesis:h1-epigenetic-commitment"]),
        ],
    )
    report = check_staleness(_paths_for(tmp_path), today=date(2026, 4, 20))
    assert len(report.drifted_edges) == 1
    assert report.drifted_edges[0].id == 1
    assert any(c.id == "t100" for c in report.drifted_edges[0].candidate_drift_tasks)


def test_drift_immune_to_calendar_age(tmp_path: Path) -> None:
    """Edge cites t001 (completed 2026-01-01); no new h1-related tasks; today=2026-07-01.
    Must NOT flag despite 6-month-old citation (age-based rule would fire; drift-based must not)."""
    _build_minimal_project(
        tmp_path,
        slug="h1-prognosis",
        edges=[{"id": 1, "source": "a", "target": "b", "description": "x",
                "data_support": [{"task": "t001", "description": "old"}]}],
        tasks=[
            ("t001", date(2026, 1, 1), []),
            ("t200", date(2026, 5, 1), ["topic:unrelated"]),   # not an h1-related task
        ],
    )
    report = check_staleness(_paths_for(tmp_path), today=date(2026, 7, 1))
    assert report.drifted_edges == ()


def test_drift_respects_last_reviewed_reset(tmp_path: Path) -> None:
    """Edge cites t001 (2026-01-01); t100 completed 2026-03-15 is candidate drift task;
    edge.last_reviewed=2026-04-01 → anchor becomes 2026-04-01; no drift."""
    _build_minimal_project(
        tmp_path,
        slug="h1-prognosis",
        edges=[{"id": 1, "source": "a", "target": "b", "description": "x",
                "last_reviewed": "2026-04-01",
                "data_support": [{"task": "t001", "description": "old"}]}],
        tasks=[
            ("t001", date(2026, 1, 1), []),
            ("t100", date(2026, 3, 15), ["hypothesis:h1-epigenetic-commitment"]),
        ],
    )
    report = check_staleness(_paths_for(tmp_path), today=date(2026, 4, 20))
    assert report.drifted_edges == ()


def test_drift_matches_via_source_or_target_node(tmp_path: Path) -> None:
    """Task's related:[] does not name the hypothesis but names the edge source 'prc2'.
    Still flagged."""
    _build_minimal_project(
        tmp_path,
        slug="custom-dag",
        edges=[{"id": 1, "source": "prc2", "target": "ifn", "description": "x",
                "data_support": [{"task": "t001", "description": "old"}]}],
        tasks=[
            ("t001", date(2026, 1, 1), []),
            ("t050", date(2026, 3, 15), ["node:prc2"]),
        ],
    )
    report = check_staleness(_paths_for(tmp_path), today=date(2026, 4, 20))
    assert len(report.drifted_edges) == 1


def test_eliminated_edges_are_frozen(tmp_path: Path) -> None:
    """Eliminated edges must not be flagged even if related tasks exist."""
    _build_minimal_project(
        tmp_path,
        slug="h1-h2-bridge",
        edges=[{"id": 1, "source": "a", "target": "b", "description": "x",
                "edge_status": "eliminated",
                "eliminated_by": [{"task": "t001", "description": "closed"}],
                "data_support": [{"task": "t001", "description": "old"}]}],
        tasks=[
            ("t001", date(2026, 4, 18), []),
            ("t100", date(2026, 4, 19), ["hypothesis:h1-epigenetic-commitment",
                                          "hypothesis:h2-cytogenetic-distinct-entities"]),
        ],
    )
    report = check_staleness(_paths_for(tmp_path), today=date(2026, 4, 20))
    assert report.drifted_edges == ()


def test_unpropagated_task_flagged(tmp_path: Path) -> None:
    """Recent DAG-related task that no edge cites — emit as UnpropagatedTask."""
    _build_minimal_project(
        tmp_path,
        slug="h1-prognosis",
        edges=[{"id": 1, "source": "a", "target": "b", "description": "x"}],
        tasks=[
            ("t100", date(2026, 4, 15), ["hypothesis:h1-epigenetic-commitment"]),
        ],
    )
    report = check_staleness(_paths_for(tmp_path), today=date(2026, 4, 20))
    assert any(u.id == "t100" for u in report.unpropagated_tasks)


def test_unresolved_ref_reported(tmp_path: Path) -> None:
    _build_minimal_project(
        tmp_path,
        slug="h1-prognosis",
        edges=[{"id": 1, "source": "a", "target": "b", "description": "x",
                "data_support": [{"task": "t99999", "description": "nonexistent"}]}],
        tasks=[],
    )
    report = check_staleness(_paths_for(tmp_path), today=date(2026, 4, 20))
    assert len(report.unresolved_refs) == 1
    assert report.unresolved_refs[0].value == "t99999"


def test_to_json_schema_stable(tmp_path: Path) -> None:
    _build_minimal_project(
        tmp_path, slug="h1-prognosis",
        edges=[{"id": 1, "source": "a", "target": "b", "description": "x"}],
        tasks=[],
    )
    report = check_staleness(_paths_for(tmp_path), today=date(2026, 4, 20))
    as_dict = report.to_json()
    keys = set(as_dict.keys())
    assert {"today", "recent_days", "drifted_edges", "under_reviewed_edges",
            "unresolved_refs", "unpropagated_tasks"} <= keys
    # Round-trip through json.dumps — must not raise.
    json.dumps(as_dict)


def test_has_findings_false_on_clean_project(tmp_path: Path) -> None:
    _build_minimal_project(
        tmp_path, slug="h1-prognosis",
        edges=[{"id": 1, "source": "a", "target": "b", "description": "x",
                "data_support": [{"task": "t001", "description": "ok"}]}],
        tasks=[("t001", date(2026, 4, 18), [])],
    )
    report = check_staleness(_paths_for(tmp_path), today=date(2026, 4, 20))
    assert not report.has_findings


# ---------------------------------------------------------------------------
# Helper — write out a minimal project layout for tests
# ---------------------------------------------------------------------------


def _build_minimal_project(
    root: Path,
    slug: str,
    edges: list[dict],
    tasks: list[tuple[str, date, list[str]]],
) -> None:
    dag_dir = root / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    # Minimal .dot file (only topology is used; not parsed by staleness)
    (dag_dir / f"{slug}.dot").write_text(f"digraph {slug.replace('-', '_')} " "{}\n")
    (dag_dir / f"{slug}.edges.yaml").write_text(
        yaml.safe_dump({"dag": slug, "edges": edges}, sort_keys=False)
    )
    tasks_dir = root / "tasks"
    tasks_dir.mkdir()
    # Everything goes to done/2026-04.md with completion dates
    done_dir = tasks_dir / "done"
    done_dir.mkdir()
    lines = []
    for tid, completed, related in tasks:
        lines.append(f"## [{tid}] Test task {tid}")
        lines.append(f"- priority: P2")
        lines.append(f"- status: done")
        lines.append(f"- completed: {completed.isoformat()}")
        if related:
            lines.append(f"- related: [{', '.join(related)}]")
        lines.append("")
    (done_dir / "2026-04.md").write_text("\n".join(lines))
    (tasks_dir / "active.md").write_text("")
