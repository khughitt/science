from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.commons.cli import commons_group


def test_dataset_init_creates_package(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "commons"
    (root / "datasets").mkdir(parents=True)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))

    result = CliRunner().invoke(
        commons_group,
        [
            "dataset",
            "init",
            "dbsnp-human",
            "--title",
            "Human dbSNP labels",
            "--date",
            "2026-06-29",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["slug"] == "dbsnp-human"
    assert payload["dataset_dir"] == "datasets/dbsnp-human"
    assert payload["created"] == [
        "datasets/dbsnp-human/entity.md",
        "datasets/dbsnp-human/datapackage.yaml",
        "datasets/dbsnp-human/recipe/Snakefile",
        "datasets/dbsnp-human/recipe/README.md",
    ]
    assert (root / "datasets" / "dbsnp-human" / "recipe" / "Snakefile").is_file()


def test_dataset_init_human_output_names_next_steps(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "commons"
    (root / "datasets").mkdir(parents=True)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))

    result = CliRunner().invoke(commons_group, ["dataset", "init", "dbsnp-human", "--date", "2026-06-29"])

    assert result.exit_code == 0, result.output
    assert "created commons dataset dataset:dbsnp-human" in result.output
    assert "science commons dataset build dbsnp-human" in result.output
    assert "science commons dataset validate dbsnp-human" in result.output


def test_dataset_init_refuses_existing_package(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "commons"
    (root / "datasets" / "dbsnp-human").mkdir(parents=True)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))

    result = CliRunner().invoke(commons_group, ["dataset", "init", "dbsnp-human"])

    assert result.exit_code == 1
    assert "already exists" in result.output


def test_dataset_init_refuses_non_semver_version(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "commons"
    (root / "datasets").mkdir(parents=True)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))

    result = CliRunner().invoke(commons_group, ["dataset", "init", "dbsnp-human", "--version", "foo"])

    assert result.exit_code == 1
    assert "invalid dataset version" in result.output


def test_dataset_init_reports_scaffold_write_errors(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "commons"
    (root / "datasets").mkdir(parents=True)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))

    def fail_scaffold(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("science_tool.commons.cli.scaffold_dataset_package", fail_scaffold)

    result = CliRunner().invoke(commons_group, ["dataset", "init", "dbsnp-human"])

    assert result.exit_code == 1
    assert "disk full" in result.output
    assert "Traceback" not in result.output


def test_dataset_status_json_reports_unbuilt_scaffold(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "commons"
    (root / "datasets").mkdir(parents=True)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    runner = CliRunner()
    init = runner.invoke(commons_group, ["dataset", "init", "dbsnp-human", "--date", "2026-06-29"])
    assert init.exit_code == 0, init.output

    result = runner.invoke(commons_group, ["dataset", "status", "dbsnp-human", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["slug"] == "dbsnp-human"
    assert payload["exists"] is True
    assert payload["workflow_exists"] is True
    assert payload["lockfile_exists"] is False
    assert payload["output_dir"] == str(tmp_path / "data" / "dbsnp-human")


def test_dataset_status_human_does_not_fail_for_missing_payloads(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "commons"
    (root / "datasets").mkdir(parents=True)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    runner = CliRunner()
    runner.invoke(commons_group, ["dataset", "init", "dbsnp-human", "--date", "2026-06-29"])

    result = runner.invoke(commons_group, ["dataset", "status", "dbsnp-human"])

    assert result.exit_code == 0, result.output
    assert "dataset:dbsnp-human" in result.output
    assert "workflow: present" in result.output


def test_dataset_status_reports_malformed_data_yaml_as_click_error(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "commons"
    (root / "datasets").mkdir(parents=True)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    runner = CliRunner()
    init = runner.invoke(commons_group, ["dataset", "init", "dbsnp-human", "--date", "2026-06-29"])
    assert init.exit_code == 0, init.output
    (cfg / "data.yaml").write_text('": bad: yaml', encoding="utf-8")

    result = runner.invoke(commons_group, ["dataset", "status", "dbsnp-human"])

    assert result.exit_code == 1
    assert str(cfg / "data.yaml") in result.output
    assert "Traceback" not in result.output
