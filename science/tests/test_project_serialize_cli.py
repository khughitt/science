import subprocess
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)


def _project(root: Path) -> None:
    (root / "entities" / "questions").mkdir(parents=True)
    (root / "science.yaml").write_text("id: demo\nname: Demo\n", encoding="utf-8")
    (root / "entities" / "questions" / "q1.md").write_text("# q\n", encoding="utf-8")
    _init_repo(root)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=root, check=True)


def test_cli_serialize_success(tmp_path: Path):
    proj = tmp_path / "proj"
    proj.mkdir()
    _project(proj)
    out = tmp_path / "bundle.tar.gz"
    result = CliRunner().invoke(
        main, ["project", "serialize", "--project-root", str(proj), "--out", str(out)]
    )
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert "Serialized" in result.output


def test_cli_serialize_refuses_violation_exit_1(tmp_path: Path):
    proj = tmp_path / "proj"
    (proj / "data" / "processed" / "exp").mkdir(parents=True)
    (proj / "science.yaml").write_text("id: demo\nname: Demo\n", encoding="utf-8")
    (proj / "data" / "processed" / "exp" / "RESULTS.md").write_text("# r\n", encoding="utf-8")
    _init_repo(proj)
    subprocess.run(["git", "add", "-A"], cwd=proj, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=proj, check=True)
    out = tmp_path / "b.tar.gz"
    result = CliRunner().invoke(
        main, ["project", "serialize", "--project-root", str(proj), "--out", str(out)]
    )
    assert result.exit_code == 1
    assert not out.exists()
