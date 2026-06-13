from __future__ import annotations

from science_qa.context import TableContext
from science_qa.flags import SEVERITY_STRUCTURAL, Flag

ASPECT = "gene-expression-qc-table"
REQUIRED_COLUMNS = ("total_counts", "n_genes_by_counts", "pct_counts_mt")


def required_column(ctx: TableContext, params: dict) -> list[Flag]:
    return [Flag(ASPECT, "required_column", col, None, SEVERITY_STRUCTURAL,
                 "absent", "present", f"required QC column {col!r} missing")
            for col in REQUIRED_COLUMNS if col not in ctx.table.columns]


def library_size_positive(ctx: TableContext, params: dict) -> list[Flag]:
    n = int((ctx.table["total_counts"] <= 0).sum())
    if n:
        return [Flag(ASPECT, "library_size_positive", "total_counts", None, SEVERITY_STRUCTURAL,
                     str(n), "0", f"{n} cell(s) with non-positive library size")]
    return []


def degenerate_cell(ctx: TableContext, params: dict) -> list[Flag]:
    mask = (ctx.table["total_counts"] == 0) & (ctx.table["n_genes_by_counts"] == 0)
    n = int(mask.sum())
    if n:
        return [Flag(ASPECT, "degenerate_cell", "total_counts+n_genes_by_counts", None,
                     SEVERITY_STRUCTURAL, str(n), "0", f"{n} all-zero cell(s)")]
    return []
