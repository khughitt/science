from __future__ import annotations

from science_qa.context import TableContext
from science_qa.flags import SEVERITY_DISTRIBUTION, Flag

ASPECT = "scrna-qc-table"
DEFAULTS = {"max_mito_pct": 20, "min_genes": 200, "max_genes": 8000, "min_counts": 500, "max_doublet": 0.3}


def _gate(flags: list[Flag], table, column: str, side: str, mask, threshold) -> None:
    n = int(mask.sum())
    if n:
        flags.append(Flag(ASPECT, "threshold", column, side, SEVERITY_DISTRIBUTION,
                          str(n), str(threshold), f"{n} cell(s) failing {column} {side} gate"))


def gates(ctx: TableContext, params: dict) -> list[Flag]:
    p = {**DEFAULTS, **(params or {})}
    t = ctx.table
    flags: list[Flag] = []
    _gate(flags, t, "pct_counts_mt", "max", t["pct_counts_mt"] > p["max_mito_pct"], p["max_mito_pct"])
    _gate(flags, t, "n_genes_by_counts", "min", t["n_genes_by_counts"] < p["min_genes"], p["min_genes"])
    _gate(flags, t, "n_genes_by_counts", "max", t["n_genes_by_counts"] > p["max_genes"], p["max_genes"])
    _gate(flags, t, "total_counts", "min", t["total_counts"] < p["min_counts"], p["min_counts"])
    return flags


def doublet_ceiling(ctx: TableContext, params: dict) -> list[Flag]:
    if "doublet_score" not in ctx.table.columns:
        return []
    p = {**DEFAULTS, **(params or {})}
    flags: list[Flag] = []
    _gate(flags, ctx.table, "doublet_score", "max",
          ctx.table["doublet_score"] > p["max_doublet"], p["max_doublet"])
    return flags
