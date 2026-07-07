# science/tests/test_data_audit_cli.py
"""CLI surface for `science data audit`."""
import json
import subprocess
from pathlib import Path

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
    res = _run(tmp_path, "--fix", "--json")
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload["violations"][0]["performed"] is True
    assert (tmp_path / "results/exp1/RESULTS.md").exists()


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
    external = tmp_path / "external-data"
    _write(
        tmp_path,
        "science.yaml",
        f"name: Demo\nid: demo\ndata:\n  root: {external}\n".encode(),
    )
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    res = _run(tmp_path, "--json")
    payload = json.loads(res.output)
    assert res.exit_code == 0
    assert payload["violations"] == []
    assert payload["notes"][0]["code"] == "external-data-root"
