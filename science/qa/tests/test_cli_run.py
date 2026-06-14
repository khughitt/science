import json
import subprocess
import sys

import pandas as pd


def _setup(tmp_path):
    pd.DataFrame({"SUBJECT_ID": [1, 1]}).to_parquet(tmp_path / "t.parquet")
    (tmp_path / "qa.yaml").write_text("qa:\n  program: scrna-qc-table\n  unique_key: SUBJECT_ID\n")


def test_cli_run_exits_nonzero_on_structural(tmp_path):
    _setup(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "science_qa", "run",
         "--config", str(tmp_path / "qa.yaml"),
         "--table", str(tmp_path / "t.parquet"),
         "--report-dir", str(tmp_path / "out")],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert (tmp_path / "out" / "qa_report.json").exists()  # report written BEFORE exit


def test_cli_run_no_strict_exits_zero(tmp_path):
    _setup(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "science_qa", "run",
         "--config", str(tmp_path / "qa.yaml"),
         "--table", str(tmp_path / "t.parquet"),
         "--report-dir", str(tmp_path / "out"), "--no-strict"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0


def test_cli_run_missing_config_exits_2(tmp_path):
    pd.DataFrame({"SUBJECT_ID": [1]}).to_parquet(tmp_path / "t.parquet")
    result = subprocess.run(
        [sys.executable, "-m", "science_qa", "run",
         "--config", str(tmp_path / "nope.yaml"),
         "--table", str(tmp_path / "t.parquet"),
         "--report-dir", str(tmp_path / "out")],
        capture_output=True, text=True,
    )
    assert result.returncode == 2


def test_cli_run_absent_column_exits_2_with_message(tmp_path):
    pd.DataFrame({"OTHER": [1]}).to_parquet(tmp_path / "t.parquet")
    (tmp_path / "qa.yaml").write_text("qa:\n  program: scrna-qc-table\n  unique_key: SUBJECT_ID\n")
    result = subprocess.run(
        [sys.executable, "-m", "science_qa", "run",
         "--config", str(tmp_path / "qa.yaml"),
         "--table", str(tmp_path / "t.parquet"),
         "--report-dir", str(tmp_path / "out")],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "SUBJECT_ID" in (result.stderr + result.stdout)


def _write_dp(tmp_path, resource, df):
    df.to_parquet(tmp_path / resource["path"])
    (tmp_path / "datapackage.json").write_text(json.dumps({"name": "p", "resources": [resource]}))


def test_cli_datapackage_non_scrna_table_runs_clean(tmp_path):
    # the dogfood regression: an ordinary (non-scRNA) table must NOT trip build-fatal flags
    res = {"name": "obs", "path": "obs.parquet",
           "schema": {"fields": [{"name": "cluster", "type": "integer"},
                                 {"name": "label", "type": "string"}]}}
    _write_dp(tmp_path, res, pd.DataFrame({"cluster": [0, 1, 2], "label": ["a", "b", "c"]}))
    result = subprocess.run(
        [sys.executable, "-m", "science_qa", "run",
         "--datapackage", str(tmp_path / "datapackage.json"), "--resource", "obs",
         "--report-dir", str(tmp_path / "out")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "out" / "qa_report.json").exists()


def test_cli_datapackage_bounds_violation_exits_1(tmp_path):
    res = {"name": "obs", "path": "obs.parquet",
           "schema": {"fields": [{"name": "p", "type": "number", "constraints": {"minimum": 0}}]}}
    _write_dp(tmp_path, res, pd.DataFrame({"p": [-1.0, 1.0]}))
    result = subprocess.run(
        [sys.executable, "-m", "science_qa", "run",
         "--datapackage", str(tmp_path / "datapackage.json"), "--resource", "obs",
         "--report-dir", str(tmp_path / "out")],
        capture_output=True, text=True,
    )
    assert result.returncode == 1


def test_cli_datapackage_requires_resource(tmp_path):
    res = {"name": "obs", "path": "obs.parquet", "schema": {"fields": [{"name": "id"}]}}
    _write_dp(tmp_path, res, pd.DataFrame({"id": [1]}))
    result = subprocess.run(
        [sys.executable, "-m", "science_qa", "run",
         "--datapackage", str(tmp_path / "datapackage.json"),
         "--report-dir", str(tmp_path / "out")],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "resource" in (result.stderr + result.stdout).lower()


def test_cli_table_and_datapackage_mutually_exclusive(tmp_path):
    res = {"name": "obs", "path": "obs.parquet", "schema": {"fields": [{"name": "id"}]}}
    _write_dp(tmp_path, res, pd.DataFrame({"id": [1]}))
    result = subprocess.run(
        [sys.executable, "-m", "science_qa", "run",
         "--datapackage", str(tmp_path / "datapackage.json"), "--resource", "obs",
         "--table", str(tmp_path / "obs.parquet"),
         "--report-dir", str(tmp_path / "out")],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
