from __future__ import annotations

from science_qa.context import TableContext
from science_qa.flags import SEVERITY_DISTRIBUTION, SEVERITY_STRUCTURAL, Flag


def non_empty(ctx: TableContext, params: dict) -> list[Flag]:
    if len(ctx.table) == 0:
        return [Flag("general", "non_empty", "table", None, SEVERITY_STRUCTURAL,
                     "0", ">0", "analysis substrate has zero rows")]
    return []


def missing_fraction(ctx: TableContext, params: dict) -> list[Flag]:
    threshold = params.get("max_missing_fraction")
    if threshold is None:
        return []
    total = ctx.table.size
    if total == 0:
        return []
    frac = float(ctx.table.isna().sum().sum()) / total
    if frac > threshold:
        return [Flag("general", "missing_fraction", "table", None, SEVERITY_DISTRIBUTION,
                     f"{frac:.4f}", str(threshold), f"overall missing fraction {frac:.4f} exceeds {threshold}")]
    return []
