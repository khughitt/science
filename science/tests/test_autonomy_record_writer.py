from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from science_model.autonomous_runs import (
    AutonomousRunRecord,
    PolicyIdentity,
    RunBudget,
    RunDisposition,
    RunRecordError,
    RunTier,
)

from science_tool.autonomy.record_writer import (
    RecordWriteError,
    generate_run_id,
    record_path,
    write_run_record,
)
from science_tool.graph.autonomous_runs import load_run_records


def _record(**overrides) -> AutonomousRunRecord:
    fields = dict(
        id="run:2026-07-25-curation-sweep-a3f1",
        agent="curation-sweep",
        model="test-model",
        tier=RunTier.BELIEF_NEUTRAL,
        branch="auto/2026-07-25-curation-sweep-a3f1",
        base_commit="a" * 40,
        head_commit="b" * 40,
        toolkit_revision="c" * 40,
        policy_identity=PolicyIdentity(id="core-default", version="1"),
        basis_digest="d" * 64,
        started=datetime(2026, 7, 25, 9, 0, tzinfo=UTC),
        ended=datetime(2026, 7, 25, 9, 30, tzinfo=UTC),
        budget=RunBudget(tokens=1000, wall_clock_seconds=1800.0),
        disposition=RunDisposition.CLEAN,
    )
    fields.update(overrides)
    return AutonomousRunRecord(**fields)


def test_a_written_record_reloads_identically(tmp_path: Path):
    """The reader is the writer's specification."""
    record = _record()
    write_run_record(tmp_path, record)

    loaded = load_run_records(tmp_path)
    assert loaded == [record]


def test_an_unwired_record_omits_the_digest_and_reloads(tmp_path: Path):
    record = _record(disposition=RunDisposition.UNWIRED, basis_digest=None)
    path = write_run_record(tmp_path, record)

    assert "basis_digest" not in path.read_text(encoding="utf-8")
    assert load_run_records(tmp_path) == [record]


def test_a_quarantined_record_reloads(tmp_path: Path):
    record = _record(disposition=RunDisposition.QUARANTINED)
    write_run_record(tmp_path, record)
    assert load_run_records(tmp_path) == [record]


def test_the_filename_stem_is_the_slug(tmp_path: Path):
    record = _record()
    path = write_run_record(tmp_path, record)
    assert path.stem == record.slug
    assert path.parent == tmp_path / "runs"


def test_an_existing_record_is_never_overwritten(tmp_path: Path):
    """An attestation is written once. Silently replacing one would let a second finish
    rewrite the verdict on a run that already has it."""
    write_run_record(tmp_path, _record())
    with pytest.raises(RecordWriteError):
        write_run_record(tmp_path, _record(disposition=RunDisposition.QUARANTINED))


def test_a_symlinked_runs_directory_is_refused(tmp_path: Path):
    """The actor owns the worktree, so it can point `runs/` anywhere. An existence check
    on the record path would follow the link and file the attestation outside the
    project -- where `load_run_records` then refuses to read it."""
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (project / "runs").symlink_to(outside, target_is_directory=True)

    with pytest.raises(RecordWriteError):
        write_run_record(project, _record())
    assert not (outside / f"{_record().slug}.md").exists()


def test_a_symlinked_record_path_is_refused(tmp_path: Path):
    """`Path.exists()` reports False for a symlink to a MISSING target, so an
    exists()-then-write would follow the dangling link and create the external file."""
    project = tmp_path / "project"
    (project / "runs").mkdir(parents=True)
    target = tmp_path / "planted.md"
    (project / "runs" / f"{_record().slug}.md").symlink_to(target)

    with pytest.raises(RecordWriteError):
        write_run_record(project, _record())
    assert not target.exists()


def test_generate_run_id_refuses_an_unusable_agent_or_short_id():
    """Fail at `start`, not four hours later when `finish` builds the record. The model's
    identity rules are the same rules; this is the earliest place to apply them."""
    with pytest.raises(RunRecordError):
        generate_run_id(date(2026, 7, 25), "Curation_Sweep", "a3f1")
    with pytest.raises(RunRecordError):
        generate_run_id(date(2026, 7, 25), "curation-sweep", "a3")


def test_an_omitted_triggered_by_is_absent_not_blank(tmp_path: Path):
    """Design §2: omitted, not blank, when absent."""
    path = write_run_record(tmp_path, _record())
    assert "triggered_by" not in path.read_text(encoding="utf-8")


def test_generated_ids_carry_the_run_prefix_and_parse():
    run_id = generate_run_id(date(2026, 7, 25), "curation-sweep", "a3f1")
    assert run_id == "run:2026-07-25-curation-sweep-a3f1"
    assert _record(id=run_id).slug == "2026-07-25-curation-sweep-a3f1"


def test_record_path_does_not_write(tmp_path: Path):
    assert not record_path(tmp_path, _record()).exists()
