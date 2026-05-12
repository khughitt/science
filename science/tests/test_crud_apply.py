"""crud.apply_status_change: orchestrator for ack/dismiss/fix."""

from __future__ import annotations

import subprocess
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from science_tool.annotation.crud import (
    CrudRefusedDirty,
    CrudResult,
    apply_status_change,
)
from science_tool.annotation.io import read_sidecar, write_sidecar
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)


def _ann(id_: str, status: Status = Status.OPEN) -> Annotation:
    base = Annotation(
        id=id_,
        target=SpecificResource(
            source="x.md",
            selector=TextQuoteSelector(exact="x", prefix="", suffix=""),
        ),
        bodies=(TextualBody(value="m"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="bare-author-year",
        source="lint:bare-author-year-v2026-05-11",
        status=Status.OPEN,
        creator="t",
        created=datetime(2026, 5, 11, tzinfo=timezone.utc),
        content_hash="sha256:d",
        match_text="m",
    )
    if status is Status.OPEN:
        return base
    return replace(
        base,
        status=status,
        modified=datetime(2026, 5, 11, 1, tzinfo=timezone.utc),
        modified_by="t",
    )


_NOW = datetime(2026, 5, 11, 12, tzinfo=timezone.utc)


def _git_init(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)


def _setup_clean(tmp_path: Path) -> Path:
    _git_init(tmp_path)
    sidecar_path = tmp_path / "foo.anno.trig"
    write_sidecar(sidecar_path, Sidecar(annotations=(_ann("a-aaa"),)))
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True,
    )
    return sidecar_path


# ---- happy paths ----------------------------------------------------

def test_open_to_ack(tmp_path: Path) -> None:
    _setup_clean(tmp_path)
    result = apply_status_change(
        tmp_path, "a-aaa", Status.ACK,
        actor="alice", now=_NOW,
    )
    assert isinstance(result, CrudResult)
    assert result.qualified_id == "foo:a-aaa"
    assert result.prior_status is Status.OPEN
    assert result.new_status is Status.ACK


def test_open_to_fixed(tmp_path: Path) -> None:
    _setup_clean(tmp_path)
    result = apply_status_change(
        tmp_path, "a-aaa", Status.FIXED,
        actor="alice", now=_NOW,
    )
    assert result.new_status is Status.FIXED


def test_open_to_dismissed_with_reason_persists(tmp_path: Path) -> None:
    sidecar_path = _setup_clean(tmp_path)
    apply_status_change(
        tmp_path, "a-aaa", Status.DISMISSED,
        actor="alice", now=_NOW, reason="not actionable",
    )
    sidecar = read_sidecar(sidecar_path)
    ann = sidecar.annotations[0]
    assert ann.status is Status.DISMISSED
    assert ann.description == "not actionable"


def test_prov_was_revision_of_records_prior_status(tmp_path: Path) -> None:
    sidecar_path = _setup_clean(tmp_path)
    apply_status_change(
        tmp_path, "a-aaa", Status.ACK, actor="alice", now=_NOW,
    )
    sidecar = read_sidecar(sidecar_path)
    ann = sidecar.annotations[0]
    assert len(ann.prior_states) == 1
    assert ann.prior_states[0].status is Status.OPEN


# ---- terminal-state refusals ---------------------------------------

@pytest.mark.parametrize(
    "source_status,target",
    [
        (Status.ACK, Status.FIXED),
        (Status.FIXED, Status.DISMISSED),
        (Status.DISMISSED, Status.ACK),
    ],
)
def test_terminal_state_refused(
    tmp_path: Path, source_status: Status, target: Status,
) -> None:
    _git_init(tmp_path)
    sidecar_path = tmp_path / "foo.anno.trig"
    write_sidecar(
        sidecar_path,
        Sidecar(annotations=(_ann("a-aaa", status=source_status),)),
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    with pytest.raises(ValueError, match="terminal status"):
        apply_status_change(
            tmp_path, "a-aaa", target, actor="alice", now=_NOW,
        )


# ---- non-OPEN-source (superseded) refusal --------------------------

@pytest.mark.parametrize("target", [Status.ACK, Status.FIXED, Status.DISMISSED])
def test_superseded_source_refused(tmp_path: Path, target: Status) -> None:
    _git_init(tmp_path)
    sidecar_path = tmp_path / "foo.anno.trig"
    write_sidecar(
        sidecar_path,
        Sidecar(annotations=(_ann("a-aaa", status=Status.SUPERSEDED),)),
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    with pytest.raises(ValueError, match="only 'open'"):
        apply_status_change(
            tmp_path, "a-aaa", target, actor="alice", now=_NOW,
        )


# ---- dirty-tree guard ----------------------------------------------

def test_dirty_sidecar_refused(tmp_path: Path) -> None:
    sidecar_path = _setup_clean(tmp_path)
    sidecar_path.write_text(
        sidecar_path.read_text(encoding="utf-8") + "\n# dirty\n",
        encoding="utf-8",
    )
    with pytest.raises(CrudRefusedDirty) as excinfo:
        apply_status_change(
            tmp_path, "a-aaa", Status.ACK, actor="alice", now=_NOW,
        )
    assert excinfo.value.sidecar_path == sidecar_path


def test_dirty_sidecar_force_dirty_bypass(tmp_path: Path) -> None:
    sidecar_path = _setup_clean(tmp_path)
    sidecar_path.write_text(
        sidecar_path.read_text(encoding="utf-8") + "\n# dirty\n",
        encoding="utf-8",
    )
    result = apply_status_change(
        tmp_path, "a-aaa", Status.ACK, actor="alice", now=_NOW,
        force_dirty=True,
    )
    assert result.new_status is Status.ACK


def test_dirty_other_sidecar_does_not_refuse(tmp_path: Path) -> None:
    sidecar_path = _setup_clean(tmp_path)
    other = tmp_path / "other.anno.trig"
    write_sidecar(other, Sidecar(annotations=(_ann("a-bbb"),)))
    result = apply_status_change(
        tmp_path, "a-aaa", Status.ACK, actor="alice", now=_NOW,
    )
    assert result.new_status is Status.ACK


# ---- round-trip -----------------------------------------------------

def test_round_trip_after_mutation(tmp_path: Path) -> None:
    sidecar_path = _setup_clean(tmp_path)
    apply_status_change(
        tmp_path, "a-aaa", Status.ACK, actor="alice", now=_NOW,
    )
    reloaded = read_sidecar(sidecar_path)
    ann = reloaded.annotations[0]
    assert ann.status is Status.ACK
    assert ann.modified is not None
    assert ann.modified_by == "alice"
