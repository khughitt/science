from __future__ import annotations

from typing import cast

import pandas as pd

from science_qa.context import TableContext
from science_qa.flags import SEVERITY_DISTRIBUTION, SEVERITY_STRUCTURAL, Flag

ASPECT = "numeric-column"


def zero_fraction(ctx: TableContext, params: dict) -> list[Flag]:
    flags: list[Flag] = []
    for col in ctx.columns:
        series = ctx.table[col]
        if len(series) and int((series == 0).sum()) == len(series):
            flags.append(Flag(ASPECT, "zero_fraction", col, None, SEVERITY_DISTRIBUTION,
                              "1.0", "<1.0", f"{col} is entirely zero"))
    return flags


def low_variance(ctx: TableContext, params: dict) -> list[Flag]:
    flags: list[Flag] = []
    for col in ctx.columns:
        series = cast("pd.Series", pd.to_numeric(ctx.table[col], errors="coerce")).dropna()
        if len(series) > 1 and float(series.var()) == 0.0:
            flags.append(Flag(ASPECT, "low_variance", col, None, SEVERITY_DISTRIBUTION,
                              "0.0", ">0", f"{col} has zero variance (constant)"))
    return flags


def polarity(ctx: TableContext, params: dict) -> list[Flag]:
    col = ctx.columns[0]
    n = int((ctx.table[col] < 0).sum())
    if n:
        return [Flag(ASPECT, "polarity", col, None, SEVERITY_STRUCTURAL,
                     str(n), "0", f"{n} negative value(s) in {col} (expected non-negative)")]
    return []


def ranges(ctx: TableContext, params: dict) -> list[Flag]:
    col = ctx.columns[0]
    bounds = params["bounds"]
    series = cast("pd.Series", pd.to_numeric(ctx.table[col], errors="coerce")).dropna()
    flags: list[Flag] = []
    if "min" in bounds:
        below = int((series < bounds["min"]).sum())
        if below:
            flags.append(Flag(ASPECT, "range", col, "min", SEVERITY_DISTRIBUTION,
                              str(below), str(bounds["min"]), f"{below} value(s) below min"))
    if "max" in bounds:
        above = int((series > bounds["max"]).sum())
        if above:
            flags.append(Flag(ASPECT, "range", col, "max", SEVERITY_DISTRIBUTION,
                              str(above), str(bounds["max"]), f"{above} value(s) above max"))
    return flags


def missing_sentinels(ctx: TableContext, params: dict) -> list[Flag]:
    sentinels = list(params["sentinels"])
    flags: list[Flag] = []
    for col in ctx.columns:
        if not pd.api.types.is_numeric_dtype(ctx.table[col]):
            continue
        survivors = int(ctx.table[col].isin(sentinels).sum())
        if survivors:
            flags.append(Flag(ASPECT, "missing_sentinel", col, None, SEVERITY_STRUCTURAL,
                              str(survivors), "0", f"{survivors} surviving missing-sentinel value(s)"))
    return flags
