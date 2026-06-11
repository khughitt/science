import pandas as pd
import pytest

from science_qa.packs import PACKS, resolve_pack, UnknownPackError
from science_qa.packs import scrna


def _ids(flags):
    return sorted(f.flag_id for f in flags)


def test_registry_exposes_scrna():
    assert "scrna" in PACKS
    assert resolve_pack("scrna") is scrna.run


def test_unknown_pack_raises():
    with pytest.raises(UnknownPackError, match="bogus"):
        resolve_pack("bogus")


def test_missing_required_column_is_structural():
    table = pd.DataFrame({"total_counts": [1000]})  # missing pct_counts_mt, n_genes_by_counts
    flags = scrna.run(table, {})
    assert "scrna/required_column/pct_counts_mt/-" in _ids(flags)
    assert all(f.severity == "structural" for f in flags if f.check == "required_column")


def test_high_mito_is_distribution():
    table = pd.DataFrame({
        "total_counts": [1000, 1000],
        "n_genes_by_counts": [500, 500],
        "pct_counts_mt": [5.0, 40.0],
    })
    flags = scrna.run(table, {"max_mito_pct": 20})
    mito = [f for f in flags if f.flag_id == "scrna/threshold/pct_counts_mt/max"]
    assert mito and mito[0].severity == "distribution"


def test_low_gene_count_distribution_uses_default_param():
    table = pd.DataFrame({
        "total_counts": [1000, 1000],
        "n_genes_by_counts": [50, 500],   # 50 < default min_genes 200
        "pct_counts_mt": [5.0, 5.0],
    })
    flags = scrna.run(table, {})
    assert "scrna/threshold/n_genes_by_counts/min" in _ids(flags)
