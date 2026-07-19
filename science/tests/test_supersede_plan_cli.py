from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main


def _chain(root: Path) -> None:
    (root / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = root / "entities" / "interpretations"
    d.mkdir(parents=True)
    (d / "0001-a.md").write_text(
        "---\nid: interpretation:0001-a\nkind: interpretation\ntitle: A\nstatus: active\n"
        "relations:\n  - predicate: sci:supersedes\n    target: interpretation:0002-b\n---\nbody\n",
        encoding="utf-8")
    (d / "0002-b.md").write_text(
        "---\nid: interpretation:0002-b\nkind: interpretation\ntitle: B\nstatus: active\n---\nbody\n",
        encoding="utf-8")


def test_save_then_apply_plan(tmp_path: Path) -> None:
    _chain(tmp_path)
    plan_file = tmp_path / "plan.json"
    r1 = CliRunner().invoke(main, ["entities", "mark-superseded", "--project-root", str(tmp_path),
                                   "--save-plan", str(plan_file)])
    assert r1.exit_code == 0, r1.output
    sha = json.loads(r1.output)["plan_sha256"]
    assert plan_file.exists()
    r2 = CliRunner().invoke(main, ["entities", "mark-superseded", "--project-root", str(tmp_path),
                                   "--apply-plan", str(plan_file), "--expected-plan-sha256", sha])
    assert r2.exit_code == 0, r2.output
    assert "status: superseded" in (tmp_path / "entities" / "interpretations" / "0002-b.md").read_text()


def test_apply_plan_requires_envelope(tmp_path: Path) -> None:
    _chain(tmp_path)
    plan_file = tmp_path / "plan.json"
    CliRunner().invoke(main, ["entities", "mark-superseded", "--project-root", str(tmp_path),
                              "--save-plan", str(plan_file)])
    r = CliRunner().invoke(main, ["entities", "mark-superseded", "--project-root", str(tmp_path),
                                  "--apply-plan", str(plan_file)])
    assert r.exit_code != 0
    assert "expected-plan-sha256" in r.output


def test_apply_plan_rejects_edited_plan(tmp_path: Path) -> None:
    _chain(tmp_path)
    plan_file = tmp_path / "plan.json"
    r1 = CliRunner().invoke(main, ["entities", "mark-superseded", "--project-root", str(tmp_path),
                                   "--save-plan", str(plan_file)])
    sha = json.loads(r1.output)["plan_sha256"]
    plan_file.write_bytes(plan_file.read_bytes() + b" ")  # tamper one byte
    r = CliRunner().invoke(main, ["entities", "mark-superseded", "--project-root", str(tmp_path),
                                  "--apply-plan", str(plan_file), "--expected-plan-sha256", sha])
    assert r.exit_code != 0


def _two_chains(root: Path) -> None:
    # Two independent supersessions in one corpus — 0002-b and 0004-d are both markable.
    (root / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = root / "entities" / "interpretations"
    d.mkdir(parents=True)
    for sup, sub in (("0001-a", "0002-b"), ("0003-c", "0004-d")):
        (d / f"{sup}.md").write_text(
            f"---\nid: interpretation:{sup}\nkind: interpretation\ntitle: {sup}\nstatus: active\n"
            f"relations:\n  - predicate: sci:supersedes\n    target: interpretation:{sub}\n---\nbody\n",
            encoding="utf-8")
        (d / f"{sub}.md").write_text(
            f"---\nid: interpretation:{sub}\nkind: interpretation\ntitle: {sub}\nstatus: active\n---\nbody\n",
            encoding="utf-8")


def test_apply_plan_rejects_selection_swapped_to_broaden_the_cohort(tmp_path: Path) -> None:
    # I8 (selection authenticity, negative): editing the plan's `selection` to point at a different
    # eligible entity is a raw-byte change, so the approval envelope (digest over raw bytes, checked
    # before JSON parse) refuses it — a swapped selection cannot slip through. NOTE: the id-selection
    # flag is the repeatable `--id` (dest `ids`), not `--ids`.
    _two_chains(tmp_path)
    plan_file = tmp_path / "plan.json"
    r1 = CliRunner().invoke(main, ["entities", "mark-superseded", "--project-root", str(tmp_path),
                                   "--save-plan", str(plan_file), "--id", "interpretation:0002-b"])
    sha = json.loads(r1.output)["plan_sha256"]
    raw = plan_file.read_text(encoding="utf-8")
    plan_file.write_text(raw.replace("interpretation:0002-b", "interpretation:0004-d"), encoding="utf-8")
    r = CliRunner().invoke(main, ["entities", "mark-superseded", "--project-root", str(tmp_path),
                                  "--apply-plan", str(plan_file), "--expected-plan-sha256", sha])
    assert r.exit_code != 0  # digest mismatch (raw bytes changed)


def test_save_plan_rejects_apply_flag(tmp_path: Path) -> None:
    _chain(tmp_path)
    r = CliRunner().invoke(main, ["entities", "mark-superseded", "--project-root", str(tmp_path),
                                  "--save-plan", str(tmp_path / "p.json"), "--apply"])
    assert r.exit_code != 0
    assert "--apply" in r.output


def test_report_mode_rejects_staging_token(tmp_path: Path) -> None:
    _chain(tmp_path)
    r = CliRunner().invoke(main, ["entities", "mark-superseded", "--project-root", str(tmp_path),
                                  "--staging-token", "x"])
    assert r.exit_code != 0
    assert "--staging-token" in r.output


def test_apply_plan_reads_plan_file_exactly_once(tmp_path: Path, monkeypatch) -> None:
    # TOCTOU regression: the CLI must hash and parse the SAME single read, never reopen the path.
    import science_tool.plan_common as pc
    _chain(tmp_path)
    plan_file = tmp_path / "plan.json"
    r1 = CliRunner().invoke(main, ["entities", "mark-superseded", "--project-root", str(tmp_path),
                                   "--save-plan", str(plan_file)])
    sha = json.loads(r1.output)["plan_sha256"]

    calls = {"n": 0}
    real = pc.read_plan_bytes

    def counting(path):
        calls["n"] += 1
        return real(path)

    monkeypatch.setattr(pc, "read_plan_bytes", counting)
    r2 = CliRunner().invoke(main, ["entities", "mark-superseded", "--project-root", str(tmp_path),
                                   "--apply-plan", str(plan_file), "--expected-plan-sha256", sha])
    assert r2.exit_code == 0, r2.output
    assert calls["n"] == 1  # one read feeds BOTH the envelope hash and the parse


@pytest.mark.parametrize("flag", [
    "--id",
    "--ids-from",
    "--save-plan",
    "--overwrite-plan",
    "--apply",
])
def test_apply_plan_rejects_conflicting_flags(tmp_path: Path, flag: str) -> None:
    """Assert that --apply-plan rejects each of five mutually-exclusive flags before reading the plan."""
    _chain(tmp_path)

    # Create a valid plan file first (required by --apply-plan)
    plan_file = tmp_path / "plan.json"
    r_save = CliRunner().invoke(main, ["entities", "mark-superseded", "--project-root", str(tmp_path),
                                       "--save-plan", str(plan_file)])
    assert r_save.exit_code == 0, r_save.output
    sha = json.loads(r_save.output)["plan_sha256"]

    # Build the command with --apply-plan and the conflicting flag
    cmd = ["entities", "mark-superseded", "--project-root", str(tmp_path),
           "--apply-plan", str(plan_file), "--expected-plan-sha256", sha]

    if flag == "--id":
        cmd.extend(["--id", "interpretation:0001-a"])
    elif flag == "--ids-from":
        ids_file = tmp_path / "ids.txt"
        ids_file.write_text("interpretation:0001-a\n")
        cmd.extend(["--ids-from", str(ids_file)])
    elif flag == "--save-plan":
        save_file = tmp_path / "save.json"
        cmd.extend(["--save-plan", str(save_file)])
    else:  # --overwrite-plan or --apply
        cmd.append(flag)

    # Invoke and verify rejection
    r = CliRunner().invoke(main, cmd)
    assert r.exit_code != 0, f"Expected {flag} to be rejected with --apply-plan, but got: {r.output}"
    assert flag in r.output or "may not be combined" in r.output, \
        f"Error should mention {flag} or the mutual exclusion. Got: {r.output}"
