import pandas as pd

from science_qa.aspects.gene_expression_qc import (
    REQUIRED_COLUMNS,
    degenerate_cell,
    library_size_positive,
    required_column,
)
from science_qa.context import TableContext


def _ctx(df):
    return TableContext(table=df, columns=list(df.columns))


def test_required_column_flags_each_absent_required_column():
    df = pd.DataFrame({"total_counts": [1]})  # missing n_genes_by_counts, pct_counts_mt
    flags = required_column(_ctx(df), {})
    subjects = sorted(f.subject for f in flags)
    assert subjects == ["n_genes_by_counts", "pct_counts_mt"]
    assert all(f.severity == "structural" and f.source == "gene-expression-qc-table" for f in flags)
    assert set(REQUIRED_COLUMNS) == {"total_counts", "n_genes_by_counts", "pct_counts_mt"}


def test_library_size_positive_flags_nonpositive_total_counts():
    df = pd.DataFrame({"total_counts": [0, 5]})
    flags = library_size_positive(_ctx(df), {})
    assert flags[0].check == "library_size_positive" and flags[0].severity == "structural"


def test_degenerate_cell_flags_all_zero_cells():
    df = pd.DataFrame({"total_counts": [0, 5], "n_genes_by_counts": [0, 3]})
    flags = degenerate_cell(_ctx(df), {})
    assert flags[0].check == "degenerate_cell" and flags[0].value == "1"
