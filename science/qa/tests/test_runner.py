import pandas as pd

from science_qa.runner import run_qa


def _table(tmp_path):
    path = tmp_path / "analysis.parquet"
    pd.DataFrame({
        "SUBJECT_ID": [1, 2, 3],
        "total_counts": [1000, 1000, 1000],
        "n_genes_by_counts": [500, 500, 500],
        "pct_counts_mt": [5.0, 40.0, 6.0],
    }).to_parquet(path)
    return path


def _config(tmp_path):
    path = tmp_path / "qa.yaml"
    path.write_text(
        "qa:\n"
        "  unique_key: SUBJECT_ID\n"
        "  packs: [scrna]\n"
        "  pack_params: {scrna: {max_mito_pct: 20}}\n"
    )
    return path


def test_run_qa_writes_artifacts_and_reconciles(tmp_path):
    out = tmp_path / "out"
    result = run_qa(_config(tmp_path), _table(tmp_path), out)
    assert (out / "qa_report.json").exists()
    assert (out / "qa_report.md").exists()
    assert (out / "qa_dispositions.yaml").exists()
    assert result.structural_failed is False
    assert any(f.flag_id == "scrna/threshold/pct_counts_mt/max" for f in result.flags)


def test_structural_failure_sets_flag(tmp_path):
    path = tmp_path / "dups.parquet"
    pd.DataFrame({"SUBJECT_ID": [1, 1],
                  "total_counts": [1, 1], "n_genes_by_counts": [1, 1], "pct_counts_mt": [1.0, 1.0]}
                 ).to_parquet(path)
    cfg = tmp_path / "qa.yaml"
    cfg.write_text("qa:\n  unique_key: SUBJECT_ID\n")
    result = run_qa(cfg, path, tmp_path / "out")
    assert result.structural_failed is True
