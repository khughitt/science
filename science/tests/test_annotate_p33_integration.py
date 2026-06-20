"""End-to-end pipeline: audit → list → ack → dismiss → fix → stats."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from click.testing import CliRunner

from science_tool.annotation.cli import annotate_group
from science_tool.annotation.io import read_sidecar
from science_tool.annotation.model import Status

_FIXTURE = """\
---
title: Integration fixture
---

Brunton 2022 wrote about modes. h04 is also referenced bare.

A claim is uncited [UNVERIFIED] and stands alone.
"""


def _git_init(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)


def test_full_pipeline(tmp_path: Path) -> None:
    _git_init(tmp_path)
    # prose_lint._collect_markdown_files only scans doc/ and specs/ subdirs,
    # so the fixture must live inside one of those directories.
    doc_dir = tmp_path / "doc"
    doc_dir.mkdir()
    md = doc_dir / "fixture.md"
    md.write_text(_FIXTURE, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

    runner = CliRunner()

    # 1. Audit populates the sidecar.
    result = runner.invoke(annotate_group, [
        "audit", "--root", str(tmp_path), "--actor", "t",
    ])
    assert result.exit_code == 0, result.output
    sidecar_path = doc_dir / "fixture.anno.trig"
    assert sidecar_path.exists()

    # Commit the sidecar so dirty-tree guard doesn't trip later.
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "audit"], cwd=tmp_path, check=True,
    )

    # 2. list shows multiple open rows.
    result = runner.invoke(annotate_group, ["list", "--root", str(tmp_path)])
    assert result.exit_code == 0
    open_count_before = result.output.count(":a-")  # rough row counter

    sidecar = read_sidecar(sidecar_path)
    assert open_count_before > 0
    first_id = sidecar.annotations[0].id

    # 3. ack the first one.
    result = runner.invoke(annotate_group, [
        "ack", first_id, "--root", str(tmp_path), "--actor", "alice",
    ])
    assert result.exit_code == 0, result.output
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "ack"], cwd=tmp_path, check=True,
    )

    sidecar = read_sidecar(sidecar_path)
    acked = next(a for a in sidecar.annotations if a.id == first_id)
    assert acked.status is Status.ACK

    # 4. dismiss another with a reason.
    second_id = next(
        a.id for a in sidecar.annotations
        if a.id != first_id and a.status is Status.OPEN
    )
    result = runner.invoke(annotate_group, [
        "dismiss", second_id, "--root", str(tmp_path),
        "--actor", "alice", "--reason", "covered elsewhere",
    ])
    assert result.exit_code == 0, result.output
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "dismiss"], cwd=tmp_path, check=True,
    )

    sidecar = read_sidecar(sidecar_path)
    dismissed = next(a for a in sidecar.annotations if a.id == second_id)
    assert dismissed.status is Status.DISMISSED
    assert dismissed.description == "covered elsewhere"

    # 5. fix a third (if available).
    third = next(
        (a for a in sidecar.annotations if a.status is Status.OPEN),
        None,
    )
    if third is not None:
        result = runner.invoke(annotate_group, [
            "fix", third.id, "--root", str(tmp_path), "--actor", "alice",
        ])
        assert result.exit_code == 0
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "fix"], cwd=tmp_path, check=True,
        )
        sidecar = read_sidecar(sidecar_path)
        fixed = next(a for a in sidecar.annotations if a.id == third.id)
        assert fixed.status is Status.FIXED

    # 6. stats reflects the mutations.
    result = runner.invoke(annotate_group, [
        "stats", "--root", str(tmp_path), "--format", "json",
    ])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    by_status = payload["by_status"]
    assert by_status.get("ack", 0) >= 1
    assert by_status.get("dismissed", 0) >= 1

    # 7. list with --status all shows the dismissed/ack rows.
    result = runner.invoke(annotate_group, [
        "list", "--root", str(tmp_path), "--status", "all",
    ])
    assert result.exit_code == 0
    assert "ack" in result.output
    assert "dismissed" in result.output
