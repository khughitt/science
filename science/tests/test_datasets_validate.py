"""Tests for dataset validation commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from science_tool.datasets.validate import validate_data_packages


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create a minimal data directory with a valid data package."""
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)

    csv_path = raw / "observations.csv"
    csv_path.write_text("sample_id,gene,expression\nS1,TP53,12.5\nS2,BRCA1,8.3\n")

    pkg = {
        "name": "test-data",
        "resources": [
            {
                "name": "observations",
                "path": "observations.csv",
                "format": "csv",
                "schema": {
                    "fields": [
                        {"name": "sample_id", "type": "string"},
                        {"name": "gene", "type": "string"},
                        {"name": "expression", "type": "number"},
                    ]
                },
            }
        ],
    }
    (raw / "datapackage.json").write_text(json.dumps(pkg))
    return tmp_path / "data"


@pytest.fixture
def bad_data_dir(tmp_path: Path) -> Path:
    """Create a data directory with validation issues."""
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)

    csv_path = raw / "bad.csv"
    csv_path.write_text("id,count\nA,not_a_number\n")

    pkg = {
        "name": "bad-data",
        "resources": [
            {
                "name": "bad",
                "path": "bad.csv",
                "format": "csv",
                "schema": {
                    "fields": [
                        {"name": "id", "type": "string"},
                        {"name": "count", "type": "integer"},
                    ]
                },
            }
        ],
    }
    (raw / "datapackage.json").write_text(json.dumps(pkg))
    return tmp_path / "data"


class TestValidateDataPackages:
    def test_valid_package_passes(self, data_dir: Path) -> None:
        results = validate_data_packages(data_dir)
        failures = [r for r in results if r["status"] == "fail"]
        assert len(failures) == 0

    def test_missing_datapackage_warns(self, tmp_path: Path) -> None:
        raw = tmp_path / "data" / "raw"
        raw.mkdir(parents=True)
        results = validate_data_packages(tmp_path / "data")
        statuses = [r["status"] for r in results]
        assert "warn" in statuses or "fail" in statuses

    def test_schema_presence_check(self, data_dir: Path) -> None:
        results = validate_data_packages(data_dir)
        check_names = [r["check"] for r in results]
        assert any("datapackage" in c.lower() for c in check_names)

    def test_bad_data_reports_errors(self, bad_data_dir: Path) -> None:
        results = validate_data_packages(bad_data_dir)
        failures = [r for r in results if r["status"] == "fail"]
        assert len(failures) > 0


def _write_pkg(tmp_path: Path, pkg: dict, csv: str = "a\n1\n") -> Path:
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "x.csv").write_text(csv)  # data file so the file-exists check passes
    (raw / "datapackage.json").write_text(json.dumps(pkg))
    return tmp_path / "data"


class TestDescriptorValidation:
    def test_rich_valid_descriptor_has_no_descriptor_failures(self, tmp_path: Path) -> None:
        pkg = {
            "name": "p",
            "resources": [{
                "name": "x", "path": "x.csv",
                "schema": {
                    "fields": [
                        {"name": "a", "type": "integer", "constraints": {"required": True, "unique": True}},
                        {"name": "v", "type": "number", "constraints": {"minimum": 0}, "qa": {"low_variance": True}},
                    ],
                    "primaryKey": "a",
                },
            }],
        }
        # CSV columns match the declared fields so the case is valid end-to-end.
        results = validate_data_packages(_write_pkg(tmp_path, pkg, csv="a,v\n1,0.5\n"))
        descriptor_fails = [r for r in results if "descriptor" in r["check"] and r["status"] == "fail"]
        assert descriptor_fails == []

    def test_qa_on_string_field_fails_descriptor(self, tmp_path: Path) -> None:
        pkg = {
            "name": "p",
            "resources": [{
                "name": "x", "path": "x.csv",
                "schema": {"fields": [{"name": "a", "type": "string", "qa": {"low_variance": True}}]},
            }],
        }
        results = validate_data_packages(_write_pkg(tmp_path, pkg))
        assert any("descriptor" in r["check"] and r["status"] == "fail" for r in results)

    def test_dangling_exclusive_flags_fails(self, tmp_path: Path) -> None:
        pkg = {
            "name": "p",
            "resources": [{
                "name": "x", "path": "x.csv",
                "schema": {"fields": [{"name": "is_a", "type": "boolean"}],
                           "qa": {"exclusive_flags": [["is_a", "is_b"]]}},
            }],
        }
        results = validate_data_packages(_write_pkg(tmp_path, pkg))
        assert any("descriptor" in r["check"] and r["status"] == "fail" for r in results)

    def test_unresolved_cross_resource_fk_fails(self, tmp_path: Path) -> None:
        pkg = {
            "name": "p",
            "resources": [{
                "name": "edges", "path": "x.csv",
                "schema": {"fields": [{"name": "src"}],
                           "foreignKeys": [{"fields": "src", "reference": {"resource": "ghost", "fields": "id"}}]},
            }],
        }
        results = validate_data_packages(_write_pkg(tmp_path, pkg))
        assert any("consistency" in r["check"] and r["status"] == "fail" for r in results)

    def test_legacy_name_type_only_still_passes(self, data_dir: Path) -> None:
        # data_dir fixture: name/type-only schema, no constraints/qa — must remain clean.
        results = validate_data_packages(data_dir)
        descriptor_fails = [r for r in results if "descriptor" in r["check"] and r["status"] == "fail"]
        assert descriptor_fails == []


from science_tool.datasets.validate import validate_package_descriptor


def _pkg_dir(tmp_path: Path, pkg: dict, fmt: str = "json", csv: str = "a\n1\n") -> Path:
    """Write a self-contained package dir (descriptor + one data file) and return it."""
    d = tmp_path / "pkg"
    d.mkdir(parents=True, exist_ok=True)
    (d / "x.csv").write_text(csv)
    if fmt == "json":
        (d / "datapackage.json").write_text(json.dumps(pkg))
    else:
        (d / "datapackage.yaml").write_text(yaml.safe_dump(pkg))
    return d


class TestDescriptorTargetValidation:
    def test_valid_json_package_dir_passes(self, tmp_path: Path) -> None:
        pkg = {"name": "p", "resources": [
            {"name": "x", "path": "x.csv",
             "schema": {"fields": [{"name": "a", "type": "integer"}]}}]}
        results = validate_package_descriptor(_pkg_dir(tmp_path, pkg))
        assert results and all(r["status"] == "pass" for r in results)

    def test_valid_yaml_package_dir_passes(self, tmp_path: Path) -> None:
        pkg = {"name": "p", "resources": [
            {"name": "x", "path": "x.csv",
             "schema": {"fields": [{"name": "a", "type": "integer"}]}}]}
        results = validate_package_descriptor(_pkg_dir(tmp_path, pkg, fmt="yaml"))
        assert results and all(r["status"] == "pass" for r in results)

    def test_descriptor_file_path_accepted(self, tmp_path: Path) -> None:
        pkg = {"name": "p", "resources": [
            {"name": "x", "path": "x.csv",
             "schema": {"fields": [{"name": "a", "type": "integer"}]}}]}
        d = _pkg_dir(tmp_path, pkg)
        results = validate_package_descriptor(d / "datapackage.json")
        assert results and all(r["status"] == "pass" for r in results)

    def test_invalid_descriptor_fails(self, tmp_path: Path) -> None:
        # qa.low_variance on a string field violates Spec 1.
        pkg = {"name": "p", "resources": [
            {"name": "x", "path": "x.csv",
             "schema": {"fields": [{"name": "a", "type": "string", "qa": {"low_variance": True}}]}}]}
        results = validate_package_descriptor(_pkg_dir(tmp_path, pkg))
        assert any(r["status"] == "fail" for r in results)

    def test_consistency_failure_reported(self, tmp_path: Path) -> None:
        pkg = {"name": "p", "resources": [
            {"name": "edges", "path": "x.csv",
             "schema": {"fields": [{"name": "src"}],
                        "foreignKeys": [{"fields": "src",
                                         "reference": {"resource": "ghost", "fields": "id"}}]}}]}
        results = validate_package_descriptor(_pkg_dir(tmp_path, pkg))
        assert any("consistency" in r["check"] and r["status"] == "fail" for r in results)

    def test_no_descriptor_is_fail_not_silent(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        results = validate_package_descriptor(empty)
        assert results and all(r["status"] == "fail" for r in results)

    def test_no_resources_is_fail(self, tmp_path: Path) -> None:
        results = validate_package_descriptor(_pkg_dir(tmp_path, {"name": "p", "resources": []}))
        assert any(r["status"] == "fail" for r in results)

    # --- resource-level table checks (file presence + schema<->table agreement) ---

    def test_missing_data_file_fails(self, tmp_path: Path) -> None:
        d = tmp_path / "pkg"
        d.mkdir()
        pkg = {"name": "p", "resources": [
            {"name": "x", "path": "absent.csv",
             "schema": {"fields": [{"name": "a", "type": "integer"}]}}]}
        (d / "datapackage.json").write_text(json.dumps(pkg))
        results = validate_package_descriptor(d)
        assert any(r["status"] == "fail" and "file" in r["check"].lower() for r in results)

    def test_stale_schema_field_fails(self, tmp_path: Path) -> None:
        # schema declares 'ghost'; the table's only column is 'a' -> add/remove mismatch.
        pkg = {"name": "p", "resources": [
            {"name": "x", "path": "x.csv",
             "schema": {"fields": [{"name": "ghost", "type": "integer"}]}}]}
        results = validate_package_descriptor(_pkg_dir(tmp_path, pkg, csv="a\n1\n"))
        assert any("matches table" in r["check"] and r["status"] == "fail" for r in results)

    def test_type_conflict_with_table_fails(self, tmp_path: Path) -> None:
        # declared string, but the column is integer-valued -> coarse-type conflict.
        pkg = {"name": "p", "resources": [
            {"name": "x", "path": "x.csv",
             "schema": {"fields": [{"name": "a", "type": "string"}]}}]}
        results = validate_package_descriptor(_pkg_dir(tmp_path, pkg, csv="a\n1\n2\n"))
        assert any("matches table" in r["check"] and r["status"] == "fail" for r in results)
