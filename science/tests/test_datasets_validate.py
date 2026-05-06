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
