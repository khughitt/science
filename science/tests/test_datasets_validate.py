"""Tests for dataset validation commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

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
