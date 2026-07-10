import shutil
import subprocess
from pathlib import Path

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
        "science_tool.commons.config.registry_root_for_id",
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
        "science_tool.commons.config.registry_root_for_id",
        lambda s: proj,
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.registry_root_for_id",
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
        "science_tool.commons.config.registry_root_for_id",
        lambda s: proj,
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.registry_root_for_id",
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
    assert "datasets/fixture-ds/entity.md" in r.output
    assert "datasets/fixture-ds/datapackage.yaml" in r.output
    assert "datasets/fixture-ds/recipe/README.md" in r.output
    assert "sha256:" in r.output
    assert "bytes: 12" in r.output
    assert "data.yaml" in r.output
    assert str(proj / "data" / "fixture-ds") in r.output
    assert "overlays/datasets/fixture-ds.md" in r.output
    assert "source: data/fixture-ds/datapackage.json" in r.output
    assert "1 overlay rewrites" in r.output
    assert "dropped fields" in r.output.lower()
    assert "ontologies" in r.output
    assert not (commons / "datasets/fixture-ds").exists()


def test_cli_promote_dataset_single_slug_omits_unrelated_failed_candidates(
    tmp_path, monkeypatch
):
    proj, commons = _setup(tmp_path)
    broken = proj / "entities" / "datasets" / "unrelated-broken.md"
    broken.write_text(
        "---\n"
        "id: dataset:unrelated-broken\n"
        "kind: dataset\n"
        "title: Unrelated broken dataset\n"
        "origin: external\n"
        "tier: evaluate-next\n"
        "access:\n"
        "  level: public\n"
        "  verified: true\n"
        "---\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setattr(
        "science_tool.commons.config.registry_root_for_id",
        lambda s: proj,
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.registry_root_for_id",
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
    assert "unrelated-broken" not in r.output
    assert "failed candidates" not in r.output


def test_cli_promote_dataset_dry_run_override_conflict_is_click_error(tmp_path, monkeypatch):
    proj, commons = _setup(tmp_path)
    config_dir = tmp_path / "science-config"
    config_dir.mkdir(parents=True)
    (config_dir / "data.yaml").write_text("fixture-ds: /wrong/path\n", encoding="utf-8")
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(config_dir))
    monkeypatch.setattr(
        "science_tool.commons.config.registry_root_for_id",
        lambda s: proj,
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.registry_root_for_id",
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
    output = f"{r.output}\n{r.stderr or ''}"
    assert r.exit_code != 0
    assert "traceback" not in output.lower()
    assert "override conflicts" in output
    assert "fixture-ds" in output
    assert r.exception is None or isinstance(r.exception, SystemExit)


def test_cli_promote_dataset_dry_run_resource_read_failure_is_click_error(
    tmp_path, monkeypatch
):
    proj, commons = _setup(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setattr(
        "science_tool.commons.config.registry_root_for_id",
        lambda s: proj,
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.registry_root_for_id",
        lambda s: proj,
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.stream_sha256_and_bytes",
        lambda path: (_ for _ in ()).throw(OSError("simulated read failure")),
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
    output = f"{r.output}\n{r.stderr or ''}"
    assert r.exit_code != 0
    assert "traceback" not in output.lower()
    assert "cannot read" in output
    assert "simulated read failure" in output
    assert r.exception is None or isinstance(r.exception, SystemExit)


def test_cli_promote_dataset_apply_writes_artifacts(tmp_path, monkeypatch):
    proj, commons = _setup(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setattr(
        "science_tool.commons.config.registry_root_for_id",
        lambda s: proj,
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.registry_root_for_id",
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


def test_promote_dataset_verify_digests_prints_skip(tmp_path, monkeypatch):
    from promote_source_fixtures import init_commons, sourced_project

    from science_tool.commons.cli import commons_group

    proj = sourced_project(tmp_path, "${OUTPUT_ROOT}/scrna/x.h5ad")
    commons = init_commons(tmp_path)

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.delenv("SCIENCE_CONFIG_DIR", raising=False)
    monkeypatch.delenv("OUTPUT_ROOT", raising=False)
    monkeypatch.setattr(
        "science_tool.commons.config.registry_root_for_id",
        lambda s: {"proj-dataset": proj}[s],
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.registry_root_for_id",
        lambda s: {"proj-dataset": proj}[s],
    )

    result = CliRunner().invoke(
        commons_group,
        ["promote", "dataset", "--from", "proj-dataset", "--slug", "fixture-ds", "--verify-digests"],
    )
    assert result.exit_code == 0, result.output
    assert "verify:" in result.output
    assert "skipped_off_host" in result.output
