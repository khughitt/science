from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main


def _superseded(root: Path) -> None:
    (root / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = root / "entities" / "interpretations"
    d.mkdir(parents=True)
    (d / "0001-x.md").write_text(
        "---\nid: interpretation:0001-x\nkind: interpretation\ntitle: X\nstatus: superseded\n---\nbody\n",
        encoding="utf-8")


def test_archive_save_then_apply(tmp_path: Path) -> None:
    _superseded(tmp_path)
    plan_file = tmp_path / "plan.json"
    r1 = CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path),
                                   "--save-plan", str(plan_file)])
    assert r1.exit_code == 0, r1.output
    sha = json.loads(r1.output)["plan_sha256"]
    assert (tmp_path / "entities" / "interpretations" / "0001-x.md").exists()  # dry run so far
    r2 = CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path),
                                   "--apply-plan", str(plan_file), "--expected-plan-sha256", sha])
    assert r2.exit_code == 0, r2.output
    assert (tmp_path / "entities" / "_archive" / "interpretations" / "0001-x.md").exists()


def test_archive_apply_plan_requires_expected_sha(tmp_path: Path) -> None:
    _superseded(tmp_path)
    plan_file = tmp_path / "plan.json"
    CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path),
                              "--save-plan", str(plan_file)])
    r = CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path),
                                  "--apply-plan", str(plan_file)])
    assert r.exit_code != 0
    assert "--expected-plan-sha256" in r.output


def test_archive_apply_plan_rejects_wrong_sha(tmp_path: Path) -> None:
    _superseded(tmp_path)
    plan_file = tmp_path / "plan.json"
    CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path),
                              "--save-plan", str(plan_file)])
    r = CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path),
                                  "--apply-plan", str(plan_file), "--expected-plan-sha256", "0" * 64])
    assert r.exit_code != 0
    assert "approval envelope" in r.output
    # apply must not have happened
    assert not (tmp_path / "entities" / "_archive" / "interpretations" / "0001-x.md").exists()


def test_archive_apply_plan_rejects_status_flag(tmp_path: Path) -> None:
    _superseded(tmp_path)
    plan_file = tmp_path / "plan.json"
    CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path), "--save-plan", str(plan_file)])
    r = CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path),
                                  "--apply-plan", str(plan_file), "--expected-plan-sha256", "x", "--status", "superseded"])
    assert r.exit_code != 0
    assert "--status" in r.output


@pytest.mark.parametrize("extra_args,flag_name", [
    (["--status", "superseded"], "--status"),
    (["--id", "interpretation:0001-x"], "--id"),
    (["--ids-from", "__PLACEHOLDER_IDS_FROM__"], "--ids-from"),
    (["--save-plan", "__PLACEHOLDER_SAVE_PLAN__"], "--save-plan"),
    (["--overwrite-plan"], "--overwrite-plan"),
    (["--apply"], "--apply"),
])
def test_archive_apply_plan_mutual_exclusion(tmp_path: Path, extra_args: list[str], flag_name: str) -> None:
    _superseded(tmp_path)
    plan_file = tmp_path / "plan.json"
    CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path), "--save-plan", str(plan_file)])

    ids_from_file = tmp_path / "ids.txt"
    ids_from_file.write_text("interpretation:0001-x\n", encoding="utf-8")
    other_plan_file = tmp_path / "other-plan.json"
    resolved_args = [
        (str(ids_from_file) if a == "__PLACEHOLDER_IDS_FROM__"
         else str(other_plan_file) if a == "__PLACEHOLDER_SAVE_PLAN__"
         else a)
        for a in extra_args
    ]

    r = CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path),
                                  "--apply-plan", str(plan_file), "--expected-plan-sha256", "x",
                                  *resolved_args])
    assert r.exit_code != 0
    assert flag_name in r.output


def test_archive_save_plan_refuses_overwrite_without_flag(tmp_path: Path) -> None:
    _superseded(tmp_path)
    plan_file = tmp_path / "plan.json"
    r1 = CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path),
                                   "--save-plan", str(plan_file)])
    assert r1.exit_code == 0, r1.output
    r2 = CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path),
                                   "--save-plan", str(plan_file)])
    assert r2.exit_code != 0
    assert "--overwrite-plan" in r2.output


def test_archive_save_plan_overwrite_with_flag(tmp_path: Path) -> None:
    _superseded(tmp_path)
    plan_file = tmp_path / "plan.json"
    r1 = CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path),
                                   "--save-plan", str(plan_file)])
    assert r1.exit_code == 0, r1.output
    r2 = CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path),
                                   "--save-plan", str(plan_file), "--overwrite-plan"])
    assert r2.exit_code == 0, r2.output


def test_archive_legacy_report_mode_unchanged(tmp_path: Path) -> None:
    _superseded(tmp_path)
    r = CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path)])
    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    assert "candidates" in payload  # legacy report shape, not the plan/apply envelope
    assert "plan_sha256" not in payload
    assert (tmp_path / "entities" / "interpretations" / "0001-x.md").exists()  # dry-run, nothing moved
