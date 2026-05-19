from pathlib import Path
import shutil
import subprocess

from click.testing import CliRunner


def _setup(tmp_path):
    src = Path(__file__).parent / "fixtures" / "promote" / "proj-dataset"
    proj = tmp_path / "proj-dataset"
    shutil.copytree(src, proj)
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(proj),
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-q",
            "-m",
            "init",
        ],
        check=True,
    )
    commons = tmp_path / "commons"
    commons.mkdir()
    subprocess.run(["git", "init", "-q", str(commons)], check=True)
    return proj, commons


def test_cli_promote_dataset_requires_slug(tmp_path, monkeypatch):
    proj, commons = _setup(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setattr(
        "science_tool.commons.config.resolve_project_by_id",
        lambda s: proj,
    )
    from science_tool.commons.cli import commons_group

    r = CliRunner().invoke(commons_group, ["promote", "dataset", "--from", "proj-dataset"])
    assert r.exit_code != 0
    assert "slug" in r.output.lower() or "slug" in (r.stderr or "").lower()


def test_cli_promote_dataset_dry_run_completes(tmp_path, monkeypatch):
    proj, commons = _setup(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setattr(
        "science_tool.commons.config.resolve_project_by_id",
        lambda s: proj,
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda s: proj,
    )
    from science_tool.commons.cli import commons_group

    r = CliRunner().invoke(
        commons_group,
        [
            "promote",
            "dataset",
            "--from",
            "proj-dataset",
            "--slug",
            "fixture-ds",
        ],
    )
    assert r.exit_code == 0, r.output
    assert "fixture-ds" in r.output
    assert not (commons / "datasets/fixture-ds").exists()


def test_cli_promote_dataset_apply_writes_artifacts(tmp_path, monkeypatch):
    proj, commons = _setup(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setattr(
        "science_tool.commons.config.resolve_project_by_id",
        lambda s: proj,
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda s: proj,
    )
    from science_tool.commons.cli import commons_group

    r = CliRunner().invoke(
        commons_group,
        [
            "promote",
            "dataset",
            "--from",
            "proj-dataset",
            "--slug",
            "fixture-ds",
            "--apply",
        ],
    )
    assert r.exit_code == 0, r.output
    assert (commons / "datasets/fixture-ds/entity.md").is_file()
