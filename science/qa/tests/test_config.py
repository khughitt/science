from pathlib import Path

import pytest

from science_qa.config import QAConfig, QAConfigError


def _write(tmp_path, body: str) -> Path:
    p = tmp_path / "qa.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def test_loads_program_and_parameterization(tmp_path):
    cfg = QAConfig.from_file(_write(tmp_path, """
qa:
  program: scrna-qc-table
  unique_key: cell_id
  ranges: {pct_counts_ribo: {min: 0, max: 60}}
  column_sets: {numeric: {dtype: numeric}}
  aspect_params: {scrna-qc-table: {max_mito_pct: 20}}
  polarity: [total_counts]
  expected_types: {cell_id: numeric}
  project_local: ["pkg.mod:check"]
"""))
    assert cfg.program == "scrna-qc-table"
    assert cfg.column_sets == {"numeric": {"dtype": "numeric"}}
    assert cfg.aspect_params["scrna-qc-table"]["max_mito_pct"] == 20
    assert cfg.polarity == ["total_counts"]
    assert cfg.expected_types == {"cell_id": "numeric"}
    assert cfg.project_local == ["pkg.mod:check"]
    assert cfg.base_dir == tmp_path


def test_missing_program_key_errors(tmp_path):
    with pytest.raises(QAConfigError, match="program"):
        QAConfig.from_file(_write(tmp_path, "qa:\n  unique_key: id\n"))


def test_missing_qa_block_is_error(tmp_path):
    with pytest.raises(QAConfigError, match="block"):
        QAConfig.from_file(_write(tmp_path, "other: 1\n"))


def test_absent_file_is_error(tmp_path):
    with pytest.raises(QAConfigError, match="not found"):
        QAConfig.from_file(tmp_path / "nope.yaml")


def test_new_fields_default_empty():
    cfg = QAConfig(program="tabular")
    assert cfg.bounds == {} and cfg.unique_keys == []


def test_require_program_false_allows_missing_program(tmp_path):
    cfg = QAConfig.from_file(_write(tmp_path, "qa:\n  polarity: [x]\n"), require_program=False)
    assert cfg.program == "" and cfg.polarity == ["x"]


def test_require_program_true_is_default(tmp_path):
    with pytest.raises(QAConfigError, match="program"):
        QAConfig.from_file(_write(tmp_path, "qa:\n  polarity: [x]\n"))
