# science/tests/test_data_audit_cli.py
"""CLI surface for `science data audit`."""
import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)


def _write(root: Path, rel: str, content: bytes = b"x") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)


def _run(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli, ["data", "audit", "--project", str(tmp_path), *args],
        catch_exceptions=False,
    )


def test_audit_reports_violation_nonzero_exit(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# r\n")
    res = _run(tmp_path)
    assert res.exit_code == 1
    assert "stranded_record" in res.output or "RESULTS.md" in res.output


def test_audit_clean_zero_exit(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "results/exp1/RESULTS.md", b"# r\n")
    res = _run(tmp_path)
    assert res.exit_code == 0


def test_audit_json_contract(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# r\n")
    res = _run(tmp_path, "--json")
    payload = json.loads(res.output)
    assert payload["version"] == 1
    assert payload["violations"][0]["target"] == "results/exp1/RESULTS.md"
    assert payload["violations"][0]["performed"] is False


def test_audit_format_json_contract(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# r\n")
    res = _run(tmp_path, "--format", "json")
    payload = json.loads(res.output)
    assert payload["version"] == 1
    assert payload["violations"][0]["target"] == "results/exp1/RESULTS.md"
    assert payload["violations"][0]["performed"] is False


def test_fix_moves_and_reports_performed(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# r\n")
    out = tmp_path / "audit.json"
    res = _run(tmp_path, "--fix", "--json", "--output", str(out))
    assert res.exit_code == 0
    payload = json.loads(out.read_text())
    assert payload["violations"][0]["performed"] is True
    assert (tmp_path / "results/exp1/RESULTS.md").exists()


def test_fix_without_output_refuses(tmp_path: Path):
    """The report size cannot be bounded before the moves, so --fix demands --output."""
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# r\n")
    res = _run(tmp_path, "--fix", "--json")
    assert res.exit_code != 0
    assert "--output" in res.output
    assert not (tmp_path / "results/exp1/RESULTS.md").exists()


def test_fix_recollects_before_preflight_guards(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from science_tool import data_cli
    from science_tool.data_audit import DataAuditSnapshot, Quadrant, Violation
    from science_tool.data_policy import FileClass

    _init_repo(tmp_path)
    snapshots = iter(
        (
            DataAuditSnapshot(violations=(), notes=()),
            DataAuditSnapshot(
                violations=(
                    Violation(
                        quadrant=Quadrant.STRANDED_RECORD,
                        path="data/processed/exp1/RESULTS.md",
                        file_class=FileClass.RECORD,
                        proposed_target="results/exp1/RESULTS.md",
                    ),
                ),
                notes=(),
            ),
        )
    )
    monkeypatch.setattr(data_cli, "collect_data_audit", lambda *_args: next(snapshots))

    result = _run(tmp_path, "--fix", "--json")

    assert result.exit_code != 0
    assert "--output" in result.output


def test_fix_rejects_output_that_is_a_violation_source(tmp_path: Path):
    _init_repo(tmp_path)
    source = tmp_path / "data/processed/exp1/RESULTS.md"
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# sentinel source\n")

    res = _run(tmp_path, "--fix", "--json", "--output", str(source))

    assert res.exit_code != 0
    assert "collides with" in res.output
    assert "source" in res.output
    assert source.read_bytes() == b"# sentinel source\n"
    assert not (tmp_path / "results/exp1/RESULTS.md").exists()


def test_fix_rejects_relative_output_that_is_a_proposed_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# source\n")
    destination = tmp_path / "results/exp1/RESULTS.md"
    _write(tmp_path, "results/exp1/RESULTS.md", b"# prior destination\n")
    monkeypatch.chdir(tmp_path)

    res = _run(
        tmp_path,
        "--fix",
        "--json",
        "--output",
        "results/exp1/RESULTS.md",
    )

    assert res.exit_code != 0
    assert "collides with" in res.output
    assert "proposed destination" in res.output
    assert (tmp_path / "data/processed/exp1/RESULTS.md").read_bytes() == b"# source\n"
    assert destination.read_bytes() == b"# prior destination\n"


def test_fix_rejects_output_directory_that_would_contain_a_proposed_destination(
    tmp_path: Path,
):
    _init_repo(tmp_path)
    source = tmp_path / "data/processed/exp1/RESULTS.md"
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# source\n")
    (tmp_path / "results").mkdir()
    output = tmp_path / "results/exp1"

    res = _run(tmp_path, "--fix", "--json", "--output", str(output))

    assert res.exit_code != 0
    assert "overlaps" in res.output
    assert "proposed destination" in res.output
    assert source.read_bytes() == b"# source\n"
    assert not output.exists()
    assert list((tmp_path / "results").glob(".exp1.*.tmp")) == []


def test_fix_rejects_symlink_normalized_output_collision(tmp_path: Path):
    _init_repo(tmp_path)
    source = tmp_path / "data/processed/exp1/RESULTS.md"
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# source\n")
    alias = tmp_path / "audit-link"
    alias.symlink_to(source)

    res = _run(tmp_path, "--fix", "--json", "--output", str(alias))

    assert res.exit_code != 0
    assert "collides with" in res.output
    assert source.read_bytes() == b"# source\n"
    assert alias.is_symlink()
    assert not (tmp_path / "results/exp1/RESULTS.md").exists()


@pytest.mark.parametrize("destination_kind", ["missing-parent", "directory"])
def test_fix_rejects_unreservable_output_before_mutation(
    tmp_path: Path,
    destination_kind: str,
):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# source\n")
    if destination_kind == "missing-parent":
        output = tmp_path / "missing" / "audit.json"
    else:
        output = tmp_path / "report-dir"
        output.mkdir()

    res = _run(tmp_path, "--fix", "--json", "--output", str(output))

    assert res.exit_code != 0
    if destination_kind == "missing-parent":
        assert "Refusing before any file is moved" in res.output
    else:
        assert "is a directory" in res.output
    assert (tmp_path / "data/processed/exp1/RESULTS.md").exists()
    assert not (tmp_path / "results/exp1/RESULTS.md").exists()


def test_fix_preserves_prior_output_when_render_fails_after_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from science_tool import data_cli

    project = tmp_path / "project"
    project.mkdir()
    _init_repo(project)
    _write(project, "data/processed/exp1/RESULTS.md", b"# source\n")
    output = tmp_path / "audit.json"
    output.write_bytes(b'{"prior": true}\n')

    def fail_render(*_args, **_kwargs):
        raise RuntimeError("injected render failure")

    monkeypatch.setattr(data_cli, "render_json", fail_render)
    result = CliRunner().invoke(
        science_cli,
        [
            "data",
            "audit",
            "--project",
            str(project),
            "--fix",
            "--json",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code != 0
    assert isinstance(result.exception, RuntimeError)
    assert output.read_bytes() == b'{"prior": true}\n'
    assert (project / "results/exp1/RESULTS.md").exists()
    assert list(tmp_path.glob(".audit.json.*.tmp")) == []


def test_honors_science_project_root_env(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# r\n")
    # No --project flag; resolution comes from the env var.
    res = CliRunner().invoke(
        science_cli, ["data", "audit", "--json"],
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)}, catch_exceptions=False,
    )
    payload = json.loads(res.output)
    assert payload["violations"][0]["target"] == "results/exp1/RESULTS.md"


def test_audit_json_reports_external_data_root_note(monkeypatch, tmp_path: Path):
    _init_repo(tmp_path)
    external = tmp_path.parent / f"{tmp_path.name}-external-data"
    _write(
        tmp_path,
        "science.yaml",
        (
            "name: Demo\n"
            "id: demo\n"
            "data:\n"
            f"  root: {external}\n"
            "data_policy:\n"
            "  record_patterns:\n"
            "    - science.yaml\n"
        ).encode(),
    )
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    res = _run(tmp_path, "--json")
    payload = json.loads(res.output)
    assert res.exit_code == 0
    assert payload["violations"] == []
    assert payload["notes"][0]["code"] == "external-data-root"


def test_audit_json_omits_notes_for_in_repo_nondefault_data_root(monkeypatch, tmp_path: Path):
    _init_repo(tmp_path)
    _write(
        tmp_path,
        "science.yaml",
        b"name: Demo\n"
        b"id: demo\n"
        b"data:\n"
        b"  root: bulk\n"
        b"data_policy:\n"
        b"  record_patterns:\n"
        b"    - science.yaml\n",
    )
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    res = _run(tmp_path, "--json")
    payload = json.loads(res.output)
    assert res.exit_code == 0
    assert payload["violations"] == []
    assert "notes" not in payload


def test_audit_reports_invalid_configured_data_root(monkeypatch, tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "science.yaml", b"name: Demo\nid: demo\n")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("SCIENCE_DATA_ROOT", "relative-data")

    res = CliRunner().invoke(
        science_cli,
        ["data", "audit", "--project", str(tmp_path)],
    )

    assert res.exit_code != 0
    assert "SCIENCE_DATA_ROOT must be absolute" in res.output
