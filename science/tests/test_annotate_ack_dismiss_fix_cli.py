"""ack/dismiss/fix CLI happy + error paths."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from click.testing import CliRunner

from science_tool.annotation.cli import annotate_group
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
    from dataclasses import replace
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
        base, status=status,
        modified=datetime(2026, 5, 11, 1, tzinfo=timezone.utc),
        modified_by="t",
    )


def _git_setup(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    sidecar_path = tmp_path / "foo.anno.trig"
    write_sidecar(sidecar_path, Sidecar(annotations=(_ann("a-aaa"),)))
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    return sidecar_path


def test_ack_happy(tmp_path: Path) -> None:
    sidecar_path = _git_setup(tmp_path)
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "ack", "a-aaa", "--root", str(tmp_path), "--actor", "alice",
    ])
    assert result.exit_code == 0, result.output
    assert "ack:" in result.output
    assert "open → ack" in result.output
    assert read_sidecar(sidecar_path).annotations[0].status is Status.ACK


def test_dismiss_requires_reason(tmp_path: Path) -> None:
    _git_setup(tmp_path)
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "dismiss", "a-aaa", "--root", str(tmp_path), "--actor", "alice",
    ])
    assert result.exit_code != 0


def test_dismiss_empty_reason_rejected(tmp_path: Path) -> None:
    _git_setup(tmp_path)
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "dismiss", "a-aaa", "--root", str(tmp_path),
        "--actor", "alice", "--reason", "   ",
    ])
    assert result.exit_code == 1
    assert "reason cannot be empty" in result.output


def test_dismiss_happy(tmp_path: Path) -> None:
    sidecar_path = _git_setup(tmp_path)
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "dismiss", "a-aaa", "--root", str(tmp_path),
        "--actor", "alice", "--reason", "not actionable",
    ])
    assert result.exit_code == 0, result.output
    assert "dismiss:" in result.output
    assert "dismissed:" not in result.output
    assert "open → dismissed" in result.output
    assert "(reason: not actionable)" in result.output
    sidecar = read_sidecar(sidecar_path)
    assert sidecar.annotations[0].description == "not actionable"


def test_fix_happy(tmp_path: Path) -> None:
    sidecar_path = _git_setup(tmp_path)
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "fix", "a-aaa", "--root", str(tmp_path), "--actor", "alice",
    ])
    assert result.exit_code == 0
    assert "fix:" in result.output
    assert "open → fixed" in result.output
    assert read_sidecar(sidecar_path).annotations[0].status is Status.FIXED


def test_ack_not_found_exits_1(tmp_path: Path) -> None:
    _git_setup(tmp_path)
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "ack", "a-zzz", "--root", str(tmp_path), "--actor", "alice",
    ])
    assert result.exit_code == 1
    assert "no annotation" in result.output.lower()


def test_ack_ambiguous_exits_2_with_candidates(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    notes = tmp_path / "notes"
    notes.mkdir()
    appendix = tmp_path / "appendix"
    appendix.mkdir()
    write_sidecar(notes / "foo.anno.trig", Sidecar(annotations=(_ann("a-aaa"),)))
    write_sidecar(appendix / "foo.anno.trig", Sidecar(annotations=(_ann("a-aaa"),)))
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "ack", "a-aaa", "--root", str(tmp_path), "--actor", "alice",
    ])
    assert result.exit_code == 2
    assert "notes/foo:a-aaa" in result.output
    assert "appendix/foo:a-aaa" in result.output


def test_ack_refuses_dirty_sidecar(tmp_path: Path) -> None:
    sidecar_path = _git_setup(tmp_path)
    sidecar_path.write_text(
        sidecar_path.read_text(encoding="utf-8") + "\n# dirty\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "ack", "a-aaa", "--root", str(tmp_path), "--actor", "alice",
    ])
    assert result.exit_code == 1
    assert "uncommitted" in result.output


def test_ack_force_dirty_bypass(tmp_path: Path) -> None:
    sidecar_path = _git_setup(tmp_path)
    sidecar_path.write_text(
        sidecar_path.read_text(encoding="utf-8") + "\n# dirty\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "ack", "a-aaa", "--root", str(tmp_path),
        "--actor", "alice", "--force-dirty",
    ])
    assert result.exit_code == 0


def test_fix_refused_when_already_acked(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    sidecar_path = tmp_path / "foo.anno.trig"
    write_sidecar(
        sidecar_path,
        Sidecar(annotations=(_ann("a-aaa", status=Status.ACK),)),
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "fix", "a-aaa", "--root", str(tmp_path), "--actor", "alice",
    ])
    assert result.exit_code == 1
    assert "terminal" in result.output


def test_actor_falls_back_to_git_user_email(tmp_path: Path) -> None:
    sidecar_path = _git_setup(tmp_path)
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "ack", "a-aaa", "--root", str(tmp_path),
    ])
    assert result.exit_code == 0
    sidecar = read_sidecar(sidecar_path)
    assert sidecar.annotations[0].modified_by == "t@example.com"
