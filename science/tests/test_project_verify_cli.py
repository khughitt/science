import json
import subprocess
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main
from science_tool.project_package.serialize import serialize_project


def _make_project(root: Path) -> None:
    (root / "entities" / "questions").mkdir(parents=True)
    (root / "science.yaml").write_text("id: demo\nname: Demo\n", encoding="utf-8")
    (root / "entities" / "questions" / "q1.md").write_text("# q\n", encoding="utf-8")
    # data/ is gitignored so serialize records this as an untracked payload
    # without a TRACKED_PAYLOAD boundary violation.
    (root / ".gitignore").write_text("data/\n", encoding="utf-8")
    (root / "data" / "processed").mkdir(parents=True)
    (root / "data" / "processed" / "x.parquet").write_bytes(b"PAYLOAD")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=root, check=True)


def _bundle(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "proj"
    project.mkdir()
    _make_project(project)
    bundle = tmp_path / "bundle.tar.gz"
    serialize_project(project, bundle)
    return project, bundle


def test_cli_verify_self_check_exit_0(tmp_path: Path):
    _, bundle = _bundle(tmp_path)

    result = CliRunner().invoke(main, ["project", "verify", str(bundle)])

    assert result.exit_code == 0, result.output


def test_cli_verify_missing_bundle_exit_4(tmp_path: Path):
    result = CliRunner().invoke(main, ["project", "verify", str(tmp_path / "nope.tar.gz")])

    assert result.exit_code == 4


def test_cli_verify_corrupt_bundle_exit_2(tmp_path: Path):
    bad = tmp_path / "bad.tar.gz"
    bad.write_bytes(b"not a gzip")

    result = CliRunner().invoke(main, ["project", "verify", str(bad)])

    assert result.exit_code == 2


def test_cli_verify_against_missing_payload_exit_3(tmp_path: Path):
    project, bundle = _bundle(tmp_path)
    (project / "data" / "processed" / "x.parquet").unlink()

    result = CliRunner().invoke(main, ["project", "verify", str(bundle), "--against", str(project)])

    assert result.exit_code == 3, result.output


def test_cli_verify_against_differ_exit_1(tmp_path: Path):
    project, bundle = _bundle(tmp_path)
    (project / "data" / "processed" / "x.parquet").write_bytes(b"CHANGED")

    result = CliRunner().invoke(main, ["project", "verify", str(bundle), "--against", str(project)])

    assert result.exit_code == 1, result.output


def test_cli_verify_json_is_pure_json(tmp_path: Path):
    project, bundle = _bundle(tmp_path)
    (project / "data" / "processed" / "x.parquet").unlink()

    result = CliRunner().invoke(main, ["project", "verify", str(bundle), "--against", str(project), "--json"])

    assert result.exit_code == 3
    payload = json.loads(result.output)
    assert payload["status"] == "missing"
    assert payload["version"] == 1


def test_cli_verify_extract(tmp_path: Path):
    _, bundle = _bundle(tmp_path)
    dest = tmp_path / "out"

    result = CliRunner().invoke(main, ["project", "verify", str(bundle), "--extract", str(dest)])

    assert result.exit_code == 0, result.output
    assert (dest / "demo" / "science.yaml").is_file()
