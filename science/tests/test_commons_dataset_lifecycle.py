import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.dataset_lifecycle import (
    DatasetLifecycleError,
    dataset_status,
    dataset_paths,
    resolve_dataset_output_dir,
    scaffold_dataset_package,
    validate_dataset_package,
    validate_dataset_slug,
    validate_dataset_version,
)


def test_validate_dataset_slug_rejects_bad_values() -> None:
    for bad_slug in ("", "Bad_Name", "bad name", "dataset:bad", "../bad", "bad/slug"):
        with pytest.raises(DatasetLifecycleError):
            validate_dataset_slug(bad_slug)


def test_validate_dataset_version_rejects_non_semver_values() -> None:
    for bad_version in ("", "foo", "1", "1.0", "v1.0.0", "1.0.0-beta"):
        with pytest.raises(DatasetLifecycleError, match="semver"):
            validate_dataset_version(bad_version)


def test_dataset_paths_are_under_commons_dataset_dir(tmp_path: Path) -> None:
    root = tmp_path / "commons"
    paths = dataset_paths(root, "dbsnp-human")

    expected_dataset_dir = root / "datasets" / "dbsnp-human"
    assert paths.dataset_dir == expected_dataset_dir
    assert paths.entity_path == expected_dataset_dir / "entity.md"
    assert paths.datapackage_path == expected_dataset_dir / "datapackage.yaml"
    assert paths.snakefile_path == expected_dataset_dir / "recipe" / "Snakefile"
    assert paths.readme_path == expected_dataset_dir / "recipe" / "README.md"

    for path in (
        paths.dataset_dir,
        paths.entity_path,
        paths.datapackage_path,
        paths.snakefile_path,
        paths.readme_path,
    ):
        assert path.is_relative_to(expected_dataset_dir)


def test_scaffold_dataset_package_writes_required_files(tmp_path: Path) -> None:
    result = scaffold_dataset_package(
        tmp_path / "commons",
        "dbsnp-human",
        title="Human dbSNP labels",
        version="0.1.0",
        today="2026-06-29",
    )

    assert [path.relative_to(result.paths.dataset_dir) for path in result.created] == [
        Path("entity.md"),
        Path("datapackage.yaml"),
        Path("recipe/Snakefile"),
        Path("recipe/README.md"),
    ]

    entity_text = result.paths.entity_path.read_text(encoding="utf-8")
    assert "id: dataset:dbsnp-human" in entity_text
    assert 'version: "0.1.0"' in entity_text
    assert "origin: external" in entity_text
    assert "datapackage: datapackage.yaml" in entity_text

    datapackage = yaml.safe_load(
        result.paths.datapackage_path.read_text(encoding="utf-8")
    )
    assert datapackage == {
        "name": "dbsnp-human",
        "profile": "data-package",
        "resources": [],
    }

    snakefile_text = result.paths.snakefile_path.read_text(encoding="utf-8")
    assert "rule all:" in snakefile_text
    assert 'DATASET_SLUG = "dbsnp-human"' in snakefile_text
    assert "dataset_output_dir" in snakefile_text


def test_scaffold_dataset_package_loads_with_commons_entity_adapter(
    tmp_path: Path,
) -> None:
    root = tmp_path / "commons"
    scaffold_dataset_package(
        root,
        "dbsnp-human",
        title="Human dbSNP labels",
        version="0.1.0",
        today="2026-06-29",
    )

    record = CommonsEntityAdapter(root).load("dataset:dbsnp-human")

    assert record.canonical_id == "dataset:dbsnp-human"
    assert record.type == "dataset"
    assert record.slug == "dbsnp-human"


def test_scaffold_snakefile_parses_with_snakemake_dry_run(tmp_path: Path) -> None:
    if shutil.which("snakemake") is None:
        pytest.skip("snakemake is not installed")

    result = scaffold_dataset_package(
        tmp_path / "commons",
        "dbsnp-human",
        title="Human dbSNP labels",
        version="0.1.0",
        today="2026-06-29",
    )
    output_root = tmp_path / "science-commons-data"
    dataset_output_dir = output_root / "dbsnp-human"

    completed = subprocess.run(
        [
            "snakemake",
            "-n",
            "-s",
            str(result.paths.snakefile_path),
            "--cores",
            "1",
            "--config",
            "dataset_slug=dbsnp-human",
            f"dataset_output_dir={dataset_output_dir}",
            f"commons_data_root={output_root}",
            f"output_root={output_root}",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_scaffold_dataset_package_refuses_existing_dataset(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "commons" / "datasets" / "dbsnp-human"
    dataset_dir.mkdir(parents=True)

    with pytest.raises(DatasetLifecycleError, match="already exists"):
        scaffold_dataset_package(tmp_path / "commons", "dbsnp-human")


def test_resolve_dataset_output_dir_prefers_data_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    override = tmp_path / "override"
    (cfg_dir / "data.yaml").write_text(f"dbsnp-human: {override}\n", encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    monkeypatch.setenv("SCIENCE_COMMONS_DATA_ROOT", str(tmp_path / "fallback"))

    assert resolve_dataset_output_dir("dbsnp-human") == override


def test_resolve_dataset_output_dir_uses_commons_data_root_without_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "data.yaml").write_text("", encoding="utf-8")
    data_root = tmp_path / "data-root"
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    monkeypatch.setenv("SCIENCE_COMMONS_DATA_ROOT", str(data_root))

    assert resolve_dataset_output_dir("dbsnp-human") == data_root / "dbsnp-human"


def test_dataset_status_reports_unbuilt_scaffold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    monkeypatch.setenv("SCIENCE_COMMONS_DATA_ROOT", str(tmp_path / "data"))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")

    status = dataset_status(root, "dbsnp-human")

    assert status.exists is True
    assert status.workflow_exists is True
    assert status.lockfile_exists is False
    assert status.datapackage_exists is True
    assert status.datapackage_placeholder_hashes is False
    assert status.output_dir == tmp_path / "data" / "dbsnp-human"
    assert status.outputs_present == []
    assert status.outputs_missing == []


def test_dataset_status_reports_real_and_missing_resources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    override = tmp_path / "science-commons-data" / "dbsnp-human"
    (cfg / "data.yaml").write_text(f"dbsnp-human: {override}\n", encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    monkeypatch.setenv("SCIENCE_COMMONS_DATA_ROOT", str(tmp_path / "fallback"))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    override.mkdir(parents=True)
    (override / "built.txt").write_text("ok", encoding="utf-8")
    (root / "datasets" / "dbsnp-human" / "datapackage.yaml").write_text(
        "name: dbsnp-human\n"
        "profile: data-package\n"
        "resources:\n"
        "- name: built\n"
        "  path: built.txt\n"
        "  hash: sha256:0000000000000000000000000000000000000000000000000000000000000001\n"
        "- name: missing\n"
        "  path: missing.txt\n"
        "  hash: sha256:0000000000000000000000000000000000000000000000000000000000000002\n",
        encoding="utf-8",
    )

    status = dataset_status(root, "dbsnp-human")

    assert status.output_dir == override
    assert status.outputs_present == ["built.txt"]
    assert status.outputs_missing == ["missing.txt"]


def test_dataset_status_rejects_malformed_datapackage_yaml(tmp_path: Path) -> None:
    root = tmp_path / "commons"
    result = scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    result.paths.datapackage_path.write_text("resources: [\n", encoding="utf-8")

    with pytest.raises(DatasetLifecycleError, match="datapackage.yaml"):
        dataset_status(root, "dbsnp-human")


def test_dataset_status_rejects_unsafe_resource_path(tmp_path: Path) -> None:
    root = tmp_path / "commons"
    result = scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    result.paths.datapackage_path.write_text(
        "name: dbsnp-human\n"
        "profile: data-package\n"
        "resources:\n"
        "- name: unsafe\n"
        "  path: ../outside.txt\n",
        encoding="utf-8",
    )

    with pytest.raises(DatasetLifecycleError, match="path may not contain '..'"):
        dataset_status(root, "dbsnp-human")


def test_validate_dataset_package_accepts_unbuilt_scaffold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is True
    assert report.findings == []


def test_validate_dataset_package_reports_missing_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    (root / "datasets" / "dbsnp-human" / "recipe" / "Snakefile").unlink()

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is False
    assert any(f.code == "missing-workflow" for f in report.findings)


def test_validate_dataset_package_reports_missing_datapackage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    (root / "datasets" / "dbsnp-human" / "datapackage.yaml").unlink()

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is False
    assert any(f.code == "missing-datapackage" for f in report.findings)
    assert not any(f.code == "entity-invalid" for f in report.findings)


def test_validate_dataset_package_reports_malformed_datapackage_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    datapackage = root / "datasets" / "dbsnp-human" / "datapackage.yaml"
    datapackage.write_text("resources: [\n", encoding="utf-8")

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is False
    assert any(
        f.code == "datapackage-invalid" and f.path == datapackage
        for f in report.findings
    )


def test_validate_dataset_package_reports_non_utf8_datapackage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    datapackage = root / "datasets" / "dbsnp-human" / "datapackage.yaml"
    datapackage.write_bytes(b"\xff")

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is False
    assert any(
        f.code == "datapackage-invalid" and f.path == datapackage
        for f in report.findings
    )


def test_validate_dataset_package_reports_unsafe_datapackage_resource_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    datapackage = root / "datasets" / "dbsnp-human" / "datapackage.yaml"
    datapackage.write_text(
        "name: dbsnp-human\n"
        "profile: data-package\n"
        "resources:\n"
        "- name: unsafe\n"
        "  path: ../outside.txt\n",
        encoding="utf-8",
    )

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is False
    assert any(
        f.code == "datapackage-invalid" and f.path == datapackage
        for f in report.findings
    )


def test_validate_dataset_package_reports_resource_without_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    datapackage = root / "datasets" / "dbsnp-human" / "datapackage.yaml"
    datapackage.write_text(
        "name: dbsnp-human\n"
        "profile: data-package\n"
        "resources:\n"
        "- name: no-path\n",
        encoding="utf-8",
    )

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is False
    assert any(
        f.code == "datapackage-invalid" and f.path == datapackage
        for f in report.findings
    )


def test_validate_dataset_package_reports_resource_non_string_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    datapackage = root / "datasets" / "dbsnp-human" / "datapackage.yaml"
    datapackage.write_text(
        "name: dbsnp-human\n"
        "profile: data-package\n"
        "resources:\n"
        "- name: non-string-path\n"
        "  path: 123\n",
        encoding="utf-8",
    )

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is False
    assert any(
        f.code == "datapackage-invalid" and f.path == datapackage
        for f in report.findings
    )


def test_validate_dataset_package_reports_resource_malformed_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    datapackage = root / "datasets" / "dbsnp-human" / "datapackage.yaml"
    datapackage.write_text(
        "name: dbsnp-human\n"
        "profile: data-package\n"
        "resources:\n"
        "- name: bad-hash\n"
        "  path: ok.csv\n"
        "  hash: not-a-hash\n",
        encoding="utf-8",
    )

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is False
    assert any(
        f.code == "datapackage-invalid" and f.path == datapackage
        for f in report.findings
    )


def test_validate_dataset_package_reports_resource_malformed_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    datapackage = root / "datasets" / "dbsnp-human" / "datapackage.yaml"
    datapackage.write_text(
        "name: dbsnp-human\n"
        "profile: data-package\n"
        "resources:\n"
        "- name: bad-source\n"
        "  path: ok.csv\n"
        "  source:\n"
        "    type: bogus\n"
        "    ref: x\n",
        encoding="utf-8",
    )

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is False
    assert any(
        f.code == "datapackage-invalid" and f.path == datapackage
        for f in report.findings
    )


def test_validate_dataset_package_reports_non_mapping_datapackage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    datapackage = root / "datasets" / "dbsnp-human" / "datapackage.yaml"
    datapackage.write_text("[]\n", encoding="utf-8")

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is False
    assert any(
        f.code == "datapackage-invalid" and f.path == datapackage
        for f in report.findings
    )


def test_validate_dataset_package_reports_non_list_resources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    datapackage = root / "datasets" / "dbsnp-human" / "datapackage.yaml"
    datapackage.write_text(
        "name: dbsnp-human\n"
        "profile: data-package\n"
        "resources: nope\n",
        encoding="utf-8",
    )

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is False
    assert any(
        f.code == "datapackage-invalid" and f.path == datapackage
        for f in report.findings
    )


def test_validate_dataset_package_reports_non_mapping_resource_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    datapackage = root / "datasets" / "dbsnp-human" / "datapackage.yaml"
    datapackage.write_text(
        "name: dbsnp-human\n"
        "profile: data-package\n"
        "resources:\n"
        "- nope\n",
        encoding="utf-8",
    )

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is False
    assert any(
        f.code == "datapackage-invalid" and f.path == datapackage
        for f in report.findings
    )


def test_validate_dataset_package_reports_non_semver_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    entity = root / "datasets" / "dbsnp-human" / "entity.md"
    entity.write_text(
        entity.read_text(encoding="utf-8").replace('version: "0.1.0"', 'version: "foo"'),
        encoding="utf-8",
    )

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is False
    assert any(f.code == "version-invalid" for f in report.findings)


def test_validate_dataset_package_reports_tracked_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    payload = root / "datasets" / "dbsnp-human" / "bulk.feather"
    payload.write_bytes(b"x" * 10)

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is False
    assert any(f.code == "tracked-payload" and f.path == payload for f in report.findings)


def test_validate_dataset_package_respects_tracked_payload_allowlist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    entity = root / "datasets" / "dbsnp-human" / "entity.md"
    text = entity.read_text(encoding="utf-8")
    text = text.replace(
        "datapackage: datapackage.yaml\n",
        "datapackage: datapackage.yaml\ntracked_payload_allowlist:\n- path: bulk.feather\n  reason: tiny fixture\n",
    )
    entity.write_text(text, encoding="utf-8")
    (root / "datasets" / "dbsnp-human" / "bulk.feather").write_bytes(b"x" * 10)

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is True
    assert report.findings == []


def test_validate_dataset_package_reports_parent_project_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    (root / "datasets" / "dbsnp-human" / "recipe" / "Snakefile").write_text(
        "rule all:\n"
        "    input:\n"
        "        '/data/proj/example/data/raw/x.csv'\n",
        encoding="utf-8",
    )

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is False
    assert any(f.code == "parent-project-path" for f in report.findings)


def test_validate_dataset_package_reports_unreadable_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    snakefile = root / "datasets" / "dbsnp-human" / "recipe" / "Snakefile"
    snakefile.write_bytes(b"\xff")

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is False
    assert any(
        f.code == "workflow-unreadable" and f.path == snakefile
        for f in report.findings
    )


def test_validate_dataset_package_reports_payload_inside_recipe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    payload = root / "datasets" / "dbsnp-human" / "recipe" / "big.parquet"
    payload.write_bytes(b"x" * 10)

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is False
    assert any(f.code == "tracked-payload" and f.path == payload for f in report.findings)


def test_validate_dataset_package_reports_large_record_pattern_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    payload = root / "datasets" / "dbsnp-human" / "dbsnp-report.json"
    payload.write_bytes(b"x" * 200_000)

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is False
    assert any(f.code == "tracked-payload" and f.path == payload for f in report.findings)


def test_validate_dataset_package_reports_large_recipe_lookup_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg))
    root = tmp_path / "commons"
    scaffold_dataset_package(root, "dbsnp-human", today="2026-06-29")
    payload = root / "datasets" / "dbsnp-human" / "recipe" / "lookup.json"
    payload.write_bytes(b"x" * 200_000)

    report = validate_dataset_package(root, "dbsnp-human")

    assert report.valid is False
    assert any(f.code == "tracked-payload" and f.path == payload for f in report.findings)
