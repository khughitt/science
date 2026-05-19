from pathlib import Path
import shutil
import subprocess

from click.testing import CliRunner


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@x"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "test"],
        check=True,
        capture_output=True,
    )


def _setup(tmp_path):
    src = Path(__file__).parent / "fixtures" / "promote" / "proj-dataset"
    proj = tmp_path / "proj-dataset"
    shutil.copytree(src, proj)
    _init_repo(proj)
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(proj), "commit", "-q", "-m", "init"],
        check=True,
    )
    commons = tmp_path / "commons"
    commons.mkdir()
    _init_repo(commons)
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


def test_cli_promote_dataset_rejects_positional_entity_id(tmp_path, monkeypatch):
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
            "dataset:other",
            "--from",
            "proj-dataset",
            "--slug",
            "fixture-ds",
        ],
    )
    output = f"{r.output}\n{r.stderr or ''}".lower()
    assert r.exit_code != 0
    assert "--slug" in output or "positional" in output or "entity_id" in output


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
