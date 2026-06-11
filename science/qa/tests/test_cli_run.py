import subprocess
import sys

import pandas as pd


def _setup(tmp_path):
    pd.DataFrame({"SUBJECT_ID": [1, 1]}).to_parquet(tmp_path / "t.parquet")
    (tmp_path / "qa.yaml").write_text("qa:\n  unique_key: SUBJECT_ID\n")


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
    (tmp_path / "qa.yaml").write_text("qa:\n  unique_key: SUBJECT_ID\n")
    result = subprocess.run(
        [sys.executable, "-m", "science_qa", "run",
         "--config", str(tmp_path / "qa.yaml"),
         "--table", str(tmp_path / "t.parquet"),
         "--report-dir", str(tmp_path / "out")],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "SUBJECT_ID" in (result.stderr + result.stdout)
