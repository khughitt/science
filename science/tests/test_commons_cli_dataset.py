from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.commons.cli import commons_group

BIO_CNA_PROFILE = "science-entity-base/1.0+dataset/1.0+bio.cna/1.0+bio.identity_context/1.0"


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


def test_dataset_init_refuses_identity_bearing_profile_without_identity(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "commons"
    (root / "datasets").mkdir(parents=True)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))

    result = CliRunner().invoke(
        commons_group,
        [
            "dataset",
            "init",
            "copy-number",
            "--schema-profile",
            BIO_CNA_PROFILE,
        ],
    )

    assert result.exit_code == 1
    assert "identity-bearing" in result.output
    assert "--taxon" in result.output
    assert "--assembly" in result.output
    assert not (root / "datasets" / "copy-number").exists()


def test_dataset_init_refuses_blank_assembly_for_identity_bearing_profile(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "commons"
    (root / "datasets").mkdir(parents=True)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))

    result = CliRunner().invoke(
        commons_group,
        [
            "dataset",
            "init",
            "copy-number",
            "--schema-profile",
            BIO_CNA_PROFILE,
            "--taxon",
            "9606",
            "--assembly",
            "",
        ],
    )

    assert result.exit_code == 1
    assert "--assembly" in result.output
    assert "Traceback" not in result.output
    assert not (root / "datasets" / "copy-number").exists()


def test_dataset_init_refuses_malformed_schema_profile(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "commons"
    (root / "datasets").mkdir(parents=True)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))

    result = CliRunner().invoke(
        commons_group,
        [
            "dataset",
            "init",
            "bad-profile",
            "--schema-profile",
            "not-a-profile",
        ],
    )

    assert result.exit_code == 1
    assert "invalid schema_profile" in result.output
    assert not (root / "datasets" / "bad-profile").exists()


def test_dataset_init_writes_declared_unresolved_identity_for_unknown_assembly(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "commons"
    (root / "datasets").mkdir(parents=True)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))

    result = CliRunner().invoke(
        commons_group,
        [
            "dataset",
            "init",
            "copy-number",
            "--schema-profile",
            BIO_CNA_PROFILE,
            "--taxon",
            "9606",
            "--assembly",
            "UNKNOWN",
            "--gene-namespace",
            "hgnc_symbol",
            "--protein-namespace",
            "uniprot",
        ],
    )

    assert result.exit_code == 0, result.output
    entity_text = (root / "datasets" / "copy-number" / "entity.md").read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(entity_text.split("---", 2)[1])
    assert frontmatter["schema_profile"] == BIO_CNA_PROFILE
    assert frontmatter["identity_context"] == {
        "taxon": 9606,
        "assembly": {
            "label": "UNKNOWN",
            "registry": "dataset:assembly-registry",
            "resolution_status": "declared_unresolved",
        },
        "molecular_ids": {
            "gene": {
                "namespace": "hgnc_symbol",
                "registry": "dataset:gene-crosswalk-hgnc",
                "resolution_status": "declared_unresolved",
            },
            "protein": {
                "namespace": "uniprot",
                "registry": "dataset:protein-crosswalk-uniprot",
                "resolution_status": "declared_unresolved",
            },
        },
    }


def test_dataset_init_accepts_format_json(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "commons"
    (root / "datasets").mkdir(parents=True)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))

    result = CliRunner().invoke(
        commons_group,
        [
            "dataset",
            "init",
            "dbsnp-human",
            "--date",
            "2026-06-29",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["slug"] == "dbsnp-human"
    assert payload["dataset_dir"] == "datasets/dbsnp-human"


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


def test_dataset_status_accepts_format_json(tmp_path: Path, monkeypatch) -> None:
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

    result = runner.invoke(commons_group, ["dataset", "status", "dbsnp-human", "--format", "json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["slug"] == "dbsnp-human"
    assert payload["exists"] is True


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


def test_dataset_validate_json_accepts_unbuilt_scaffold(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "commons"
    (root / "datasets").mkdir(parents=True)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    runner = CliRunner()
    runner.invoke(commons_group, ["dataset", "init", "dbsnp-human", "--date", "2026-06-29"])

    result = runner.invoke(commons_group, ["dataset", "validate", "dbsnp-human", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["valid"] is True
    assert payload["findings"] == []


def test_dataset_validate_accepts_format_json(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "commons"
    (root / "datasets").mkdir(parents=True)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    runner = CliRunner()
    runner.invoke(commons_group, ["dataset", "init", "dbsnp-human", "--date", "2026-06-29"])

    result = runner.invoke(commons_group, ["dataset", "validate", "dbsnp-human", "--format", "json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["valid"] is True
    assert payload["findings"] == []


def test_dataset_validate_exits_1_for_missing_workflow(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "commons"
    (root / "datasets").mkdir(parents=True)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    runner = CliRunner()
    runner.invoke(commons_group, ["dataset", "init", "dbsnp-human", "--date", "2026-06-29"])
    (root / "datasets" / "dbsnp-human" / "recipe" / "Snakefile").unlink()

    result = runner.invoke(commons_group, ["dataset", "validate", "dbsnp-human"])

    assert result.exit_code == 1
    assert "missing-workflow" in result.output


def test_dataset_build_invokes_snakemake(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "commons"
    (root / "datasets").mkdir(parents=True)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    runner = CliRunner()
    runner.invoke(commons_group, ["dataset", "init", "dbsnp-human", "--date", "2026-06-29"])
    calls: list[list[str]] = []

    def fake_run(command, check=False):
        calls.append(list(command))

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr("science_tool.commons.dataset_lifecycle.subprocess.run", fake_run)

    result = runner.invoke(commons_group, ["dataset", "build", "dbsnp-human", "--cores", "2"])

    assert result.exit_code == 0, result.output
    assert "snakemake exited 0" in result.output
    assert calls
    assert calls[0][0] == "snakemake"
    assert "--cores" in calls[0]
    assert "2" in calls[0]


def test_dataset_build_reports_missing_snakefile_as_click_error(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "commons"
    (root / "datasets").mkdir(parents=True)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    runner = CliRunner()
    runner.invoke(commons_group, ["dataset", "init", "dbsnp-human", "--date", "2026-06-29"])
    (root / "datasets" / "dbsnp-human" / "recipe" / "Snakefile").unlink()

    result = runner.invoke(commons_group, ["dataset", "build", "dbsnp-human"])

    assert result.exit_code == 1
    assert "missing recipe/Snakefile" in result.output


def test_dataset_build_reports_malformed_data_yaml_as_click_error(tmp_path: Path, monkeypatch) -> None:
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
    (cfg / "data.yaml").write_text('": bad: yaml', encoding="utf-8")

    result = runner.invoke(commons_group, ["dataset", "build", "dbsnp-human"])

    assert result.exit_code == 1
    assert str(cfg / "data.yaml") in result.output
    assert "Traceback" not in result.output


def test_dataset_build_reports_missing_snakemake_as_click_error(tmp_path: Path, monkeypatch) -> None:
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

    def missing_snakemake(command, check=False):
        raise FileNotFoundError("snakemake")

    monkeypatch.setattr("science_tool.commons.dataset_lifecycle.subprocess.run", missing_snakemake)

    result = runner.invoke(commons_group, ["dataset", "build", "dbsnp-human"])

    assert result.exit_code == 1
    assert "snakemake" in result.output
    assert "Traceback" not in result.output
