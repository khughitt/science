from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from science_model.autonomous_runs import PolicyIdentity, RunTier

from science_tool.autonomy.baseline import (
    BaselineError,
    RunBaseline,
    read_baseline,
    reject_baseline_inside_project,
    write_baseline,
)
from science_tool.graph.belief_basis import EntityBasis, build_snapshot


def _baseline() -> RunBaseline:
    rows = [
        EntityBasis(
            entity_id="hypothesis:h01", uri="urn:h01", target_uris=("urn:h01",),
            unit_keys=('{"line_uri": "urn:e1"}',), policy_id="core-default", policy_version="1",
        )
    ]
    return RunBaseline(
        run_id="run:2026-07-25-curation-sweep-a3f1",
        agent="curation-sweep",
        model="test-model",
        tier=RunTier.BELIEF_NEUTRAL,
        branch="auto/2026-07-25-curation-sweep-a3f1",
        base_commit="a" * 40,
        toolkit_revision="b" * 40,
        policy_identity=PolicyIdentity(id="core-default", version="1"),
        started=datetime(2026, 7, 25, 9, 0, tzinfo=UTC),
        snapshot=build_snapshot(rows),
    )


def test_a_baseline_round_trips(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    out = tmp_path / "state" / "run.json"

    write_baseline(out, _baseline(), project_root=project)
    assert read_baseline(out, project_root=project) == _baseline()


def test_a_baseline_inside_the_project_is_refused_on_write(tmp_path: Path):
    """The actor's whole job is writing the worktree; a baseline it can reach is a
    baseline it can rewrite."""
    project = tmp_path / "project"
    project.mkdir()
    with pytest.raises(BaselineError):
        write_baseline(project / "runs" / "b.json", _baseline(), project_root=project)


def test_a_baseline_inside_the_project_is_refused_on_read(tmp_path: Path):
    project = tmp_path / "project"
    (project / "sub").mkdir(parents=True)
    inside = project / "sub" / "b.json"
    inside.write_text("{}", encoding="utf-8")
    with pytest.raises(BaselineError):
        read_baseline(inside, project_root=project)


def test_the_project_root_itself_is_refused(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    with pytest.raises(BaselineError):
        reject_baseline_inside_project(project, project)


def test_a_path_spelled_inside_the_project_is_refused_even_through_an_outward_symlink(
    tmp_path: Path,
):
    """Resolving FIRST would pass this: the resolved target is outside. But the path the
    supervisor was handed is spelled inside the tree the actor writes, so the actor owns
    the symlink and therefore owns where the baseline goes. Both spellings must be
    refused -- lexical containment and resolved containment are different questions."""
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (project / "link").symlink_to(outside, target_is_directory=True)

    with pytest.raises(BaselineError):
        write_baseline(project / "link" / "b.json", _baseline(), project_root=project)


def test_a_path_spelled_outside_that_resolves_inside_is_refused(tmp_path: Path):
    """The other direction: an inward symlink cannot launder a path into the tree."""
    project = tmp_path / "project"
    (project / "state").mkdir(parents=True)
    (tmp_path / "outward").symlink_to(project / "state", target_is_directory=True)

    with pytest.raises(BaselineError):
        write_baseline(tmp_path / "outward" / "b.json", _baseline(), project_root=project)


def test_an_existing_baseline_is_never_silently_overwritten(tmp_path: Path):
    """Starting a second run onto an occupied baseline path would discard the first run's
    before-state, which is the only thing that can ever judge it."""
    project = tmp_path / "project"
    project.mkdir()
    out = tmp_path / "state" / "run.json"
    write_baseline(out, _baseline(), project_root=project)
    with pytest.raises(BaselineError):
        write_baseline(out, _baseline(), project_root=project)


def test_a_baseline_that_is_not_utf8_is_an_error_not_a_crash(tmp_path: Path):
    """`UnicodeDecodeError` is a ValueError, not an OSError. Catching only OSError and
    JSONDecodeError lets it escape past `read_baseline`, and an escaped exception in
    `finish` is not the `unwired` this design requires."""
    project = tmp_path / "project"
    project.mkdir()
    out = tmp_path / "state" / "run.json"
    out.parent.mkdir(parents=True)
    out.write_bytes(b"\xff\xfe not utf-8")

    with pytest.raises(BaselineError):
        read_baseline(out, project_root=project)


def test_a_tampered_snapshot_is_refused(tmp_path: Path):
    """The snapshot carries Plan A's digest seal; a rewritten baseline must not load."""
    project = tmp_path / "project"
    project.mkdir()
    out = tmp_path / "state" / "run.json"
    write_baseline(out, _baseline(), project_root=project)
    out.write_text(out.read_text(encoding="utf-8").replace("urn:e1", "urn:e2"), encoding="utf-8")

    with pytest.raises(BaselineError):
        read_baseline(out, project_root=project)


def test_an_unreadable_baseline_is_an_error_not_an_empty_one(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    with pytest.raises(BaselineError):
        read_baseline(tmp_path / "state" / "absent.json", project_root=project)


def test_the_baseline_is_frozen_and_closed(tmp_path: Path):
    from pydantic import ValidationError

    baseline = _baseline()
    with pytest.raises(ValidationError):
        baseline.run_id = "run:other"  # type: ignore[misc]
