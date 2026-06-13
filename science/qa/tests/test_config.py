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
