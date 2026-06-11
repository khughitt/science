from __future__ import annotations

import pandas as pd

from science_qa.flags import SEVERITY_DISTRIBUTION, SEVERITY_STRUCTURAL, Flag

REQUIRED_COLUMNS = ("total_counts", "n_genes_by_counts", "pct_counts_mt")
DEFAULTS = {"max_mito_pct": 20, "min_genes": 200, "max_genes": 8000, "min_counts": 500, "max_doublet": 0.3}


def run(table: pd.DataFrame, params: dict) -> list[Flag]:
    p = {**DEFAULTS, **(params or {})}
    flags: list[Flag] = []

    missing = [c for c in REQUIRED_COLUMNS if c not in table.columns]
    for column in missing:
        flags.append(Flag("scrna", "required_column", column, None, SEVERITY_STRUCTURAL,
                          "absent", "present", f"required scRNA QC column {column!r} missing"))
    if missing:
        return flags  # cannot run distribution checks without the metric columns

    def _count(mask) -> int:
        return int(mask.sum())

    def _gate(column: str, side: str, mask, threshold) -> None:
        n = _count(mask)
        if n:
            flags.append(Flag("scrna", "threshold", column, side, SEVERITY_DISTRIBUTION,
                              str(n), str(threshold), f"{n} cell(s) failing {column} {side} gate"))

    _gate("pct_counts_mt", "max", table["pct_counts_mt"] > p["max_mito_pct"], p["max_mito_pct"])
    _gate("n_genes_by_counts", "min", table["n_genes_by_counts"] < p["min_genes"], p["min_genes"])
    _gate("n_genes_by_counts", "max", table["n_genes_by_counts"] > p["max_genes"], p["max_genes"])
    _gate("total_counts", "min", table["total_counts"] < p["min_counts"], p["min_counts"])
    if "doublet_score" in table.columns:
        _gate("doublet_score", "max", table["doublet_score"] > p["max_doublet"], p["max_doublet"])
    return flags
