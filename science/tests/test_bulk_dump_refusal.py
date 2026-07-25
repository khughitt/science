from __future__ import annotations

import json
import subprocess
from pathlib import Path

from click.testing import CliRunner

from science_tool.budget.registry import BUDGETS
from science_tool.cli import main

# Enough stranded records that both the text and JSON reports exceed the data-audit
# budget (20_000 chars); kept modest so the positive test's per-move `git add` stays fast.
STRANDED_RECORDS = 400


def _invoke(args: list[str]):
    return CliRunner().invoke(main, args, prog_name="science")


def _project(root: Path, entities: int) -> None:
    (root / "science.yaml").write_text("id: demo\nname: demo\n")
    questions = root / "entities" / "questions"
    questions.mkdir(parents=True)
    for i in range(entities):
        (questions / f"{i:04d}-q.md").write_text(
            f"---\nid: question:q{i:04d}\nkind: question\ntitle: Question {i}\n---\n\n"
            + ("body text " * 200)
        )


def _stranded_project(root: Path) -> None:
    """A git repo whose data/ holds many *movable* stranded records.

    Uses the exact shape the existing CLI suite proves movable
    (data/processed/exp/RESULTS.md -> results/exp/RESULTS.md; see
    test_data_audit_cli.py::test_audit_json_contract), scaled until the report exceeds
    the data-audit budget.

    A real repository is required: for each untracked move `apply_fixes` runs
    `git add <target>` (data_audit_fix.py:171), which errors outside a repo. Without
    `git init` the positive --fix test would exit nonzero after partially mutating.
    """
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    (root / "science.yaml").write_text(
        "id: demo\n"
        "name: demo\n"
        "data_policy:\n"
        "  record_patterns:\n"
        "    - science.yaml\n"
        "    - RESULTS*.md\n"
    )
    for i in range(STRANDED_RECORDS):
        record = root / "data" / "processed" / f"exp{i:05d}" / "RESULTS.md"
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text("# r\n")


# Do not rely on chdir for this command. Its Click option currently uses
# `default=Path.cwd()`, which is evaluated when entities_inventory_cli is imported,
# before these tests change directory. Pass the fixture root explicitly in every
# inventory invocation so the test cannot inspect the developer's checkout by accident.
def test_small_inventory_prints_to_stdout(tmp_path: Path, monkeypatch) -> None:
    _project(tmp_path, entities=1)
    monkeypatch.chdir(tmp_path)
    result = _invoke(["entities", "inventory", "--project-root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    json.loads(result.output)


def test_oversized_inventory_is_refused_not_truncated(tmp_path: Path, monkeypatch) -> None:
    _project(tmp_path, entities=400)
    monkeypatch.chdir(tmp_path)
    result = _invoke(["entities", "inventory", "--project-root", str(tmp_path)])
    assert result.exit_code != 0
    assert "--output" in result.output
    assert "schema_version" not in result.output  # no partial document leaked


def test_inventory_output_file_is_complete(tmp_path: Path, monkeypatch) -> None:
    _project(tmp_path, entities=400)
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "inv.json"
    result = _invoke(
        ["entities", "inventory", "--project-root", str(tmp_path), "--output", str(target)]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(target.read_text())
    assert payload["schema_version"] == "2"
    assert len(target.read_text()) > BUDGETS["entities inventory"].max_chars


def test_data_audit_text_branch_is_budgeted(tmp_path: Path, monkeypatch) -> None:
    """The default format is text; the previous plan guarded only JSON."""
    _stranded_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = _invoke(["data", "audit"])
    assert result.exit_code != 0
    assert "--output" in result.output
    assert "stranded_record" not in result.output
    assert "data/processed/exp00000/RESULTS.md" not in result.output
    assert "data/processed/exp00399/RESULTS.md" not in result.output


def test_data_audit_output_file_is_complete_in_text_format(
    tmp_path: Path, monkeypatch
) -> None:
    _stranded_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "audit.txt"
    result = _invoke(["data", "audit", "--output", str(target)])
    assert result.exit_code == 1
    report = target.read_text()
    assert report.count("[stranded_record]") == STRANDED_RECORDS
    assert (
        "  [stranded_record] data/processed/exp00000/RESULTS.md "
        "→ results/exp00000/RESULTS.md\n"
    ) in report
    assert report.endswith(
        "  [stranded_record] data/processed/exp00399/RESULTS.md "
        "→ results/exp00399/RESULTS.md\n"
    )
    assert len(report) > BUDGETS["data audit"].max_chars
    assert result.output == f"wrote the data audit report to {target}\n"


def test_data_audit_json_branch_is_budgeted(tmp_path: Path, monkeypatch) -> None:
    _stranded_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = _invoke(["data", "audit", "--format", "json"])
    assert result.exit_code != 0
    assert "--output" in result.output
    assert '"violations"' not in result.output
    assert "data/processed/exp00000/RESULTS.md" not in result.output
    assert "data/processed/exp00399/RESULTS.md" not in result.output


def test_data_audit_output_file_is_complete_in_json_format(
    tmp_path: Path, monkeypatch
) -> None:
    _stranded_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "audit.json"
    result = _invoke(["data", "audit", "--format", "json", "--output", str(target)])
    assert result.exit_code == 1
    report = target.read_text()
    payload = json.loads(report)
    assert len(payload["violations"]) == STRANDED_RECORDS
    assert payload["violations"][0]["path"] == "data/processed/exp00000/RESULTS.md"
    assert payload["violations"][-1]["path"] == "data/processed/exp00399/RESULTS.md"
    assert all(not row["performed"] for row in payload["violations"])
    assert len(report) > BUDGETS["data audit"].max_chars
    assert result.output == f"wrote the data audit report to {target}\n"


def test_fix_without_output_refuses_before_moving_any_file(
    tmp_path: Path, monkeypatch
) -> None:
    """apply_fixes mutates the tree, so --fix must not depend on a later budget check."""
    _stranded_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = _invoke(["data", "audit", "--fix"])

    assert result.exit_code != 0
    assert "--output" in result.output
    assert not (tmp_path / "results").exists(), "files were moved despite the command failing"


def test_fix_refuses_a_missing_parent_output_before_moving(
    tmp_path: Path, monkeypatch
) -> None:
    """A missing output parent must fail while the tree is intact."""
    _stranded_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = _invoke(
        ["data", "audit", "--fix", "--output", "does/not/exist/audit.json"]
    )

    assert result.exit_code != 0
    assert not (tmp_path / "results").exists(), "files were moved despite an unwritable --output"


def test_fix_refuses_a_directory_output_before_moving(
    tmp_path: Path, monkeypatch
) -> None:
    """Path.touch() accepts a directory; the command must reject it before moving."""
    _stranded_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "report-dir"
    target.mkdir()

    result = _invoke(["data", "audit", "--fix", "--output", str(target)])

    assert result.exit_code != 0
    assert not (tmp_path / "results").exists(), "files were moved despite a directory --output"


def test_fix_refuses_an_unreservable_output_before_moving(
    tmp_path: Path, monkeypatch
) -> None:
    """Creating the sibling temp, not touching the target, proves output is reservable."""
    from science_tool.budget import sink as sink_module

    _stranded_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "audit.json"

    def deny_reservation(*args: object, **kwargs: object):
        raise PermissionError("read-only destination")

    monkeypatch.setattr(sink_module.tempfile, "mkstemp", deny_reservation)
    result = _invoke(["data", "audit", "--fix", "--output", str(target)])

    assert result.exit_code != 0
    assert not (tmp_path / "results").exists(), "files were moved despite a read-only --output"


def test_fix_with_output_mutates_and_writes_the_complete_report(
    tmp_path: Path, monkeypatch
) -> None:
    """A pre-opened file sink removes the known size and destination failures."""
    _stranded_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "audit.json"

    result = _invoke(
        ["data", "audit", "--fix", "--format", "json", "--output", str(target)]
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(target.read_text())
    assert len(payload["violations"]) == STRANDED_RECORDS
    assert all(row["performed"] for row in payload["violations"])
    assert (tmp_path / "results" / "exp00000" / "RESULTS.md").exists()
    assert len(target.read_text()) > BUDGETS["data audit"].max_chars


def test_fix_on_a_clean_project_still_works_without_output(
    tmp_path: Path, monkeypatch
) -> None:
    """The gate keys on there being violations, not on --fix alone."""
    (tmp_path / "science.yaml").write_text(
        "id: demo\n"
        "name: demo\n"
        "data_policy:\n"
        "  record_patterns:\n"
        "    - science.yaml\n"
    )
    (tmp_path / "data").mkdir()
    monkeypatch.chdir(tmp_path)

    result = _invoke(["data", "audit", "--fix"])

    assert result.exit_code == 0, result.output
