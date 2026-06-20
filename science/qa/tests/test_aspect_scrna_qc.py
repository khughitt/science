import pandas as pd

from science_qa.aspects.scrna_qc import DEFAULTS, doublet_ceiling, gates
from science_qa.context import TableContext


def _ctx(df):
    return TableContext(table=df, columns=list(df.columns))


def test_gates_flag_mito_gene_and_total_thresholds():
    df = pd.DataFrame({
        "total_counts": [100, 1000],          # 100 < min_counts 500
        "n_genes_by_counts": [50, 500],        # 50 < min_genes 200
        "pct_counts_mt": [30.0, 5.0],          # 30 > max_mito_pct 20
    })
    flags = gates(_ctx(df), DEFAULTS)
    keyed = {(f.subject, f.side) for f in flags}
    assert ("pct_counts_mt", "max") in keyed
    assert ("n_genes_by_counts", "min") in keyed
    assert ("total_counts", "min") in keyed
    assert all(f.source == "scrna-qc-table" and f.check == "threshold" for f in flags)


def test_doublet_ceiling_flags_when_present():
    df = pd.DataFrame({"doublet_score": [0.5, 0.1]})
    flags = doublet_ceiling(_ctx(df), DEFAULTS)
    assert flags[0].subject == "doublet_score" and flags[0].side == "max"


def test_doublet_ceiling_returns_empty_when_column_absent():
    assert doublet_ceiling(_ctx(pd.DataFrame({"x": [1]})), DEFAULTS) == []
