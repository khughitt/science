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
        if len(series) > 1 and float(cast("float", series.var())) == 0.0:
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
    band = params["bounds"]
    series = cast("pd.Series", pd.to_numeric(ctx.table[col], errors="coerce")).dropna()
    flags: list[Flag] = []
    if "min" in band:
        below = int((series < band["min"]).sum())
        if below:
            flags.append(Flag(ASPECT, "range", col, "min", SEVERITY_DISTRIBUTION,
                              str(below), str(band["min"]), f"{below} value(s) below min"))
    if "max" in band:
        above = int((series > band["max"]).sum())
        if above:
            flags.append(Flag(ASPECT, "range", col, "max", SEVERITY_DISTRIBUTION,
                              str(above), str(band["max"]), f"{above} value(s) above max"))
    return flags


def missing_sentinels(ctx: TableContext, params: dict) -> list[Flag]:
    sentinels = list(params["sentinels"])
    flags: list[Flag] = []
    for col in ctx.columns:
        if not pd.api.types.is_numeric_dtype(ctx.table[col]):
            continue
        survivors = int(cast("int", ctx.table[col].isin(sentinels).sum()))
        if survivors:
            flags.append(Flag(ASPECT, "missing_sentinel", col, None, SEVERITY_STRUCTURAL,
                              str(survivors), "0", f"{survivors} surviving missing-sentinel value(s)"))
    return flags


_BOUND_CHECKS = (
    ("minimum", lambda s, v: s < v),
    ("exclusiveMinimum", lambda s, v: s <= v),
    ("maximum", lambda s, v: s > v),
    ("exclusiveMaximum", lambda s, v: s >= v),
)


def bounds(ctx: TableContext, params: dict) -> list[Flag]:
    """Hard structural bounds from native Frictionless constraints (Spec 1 invariants).

    params["bounds"] is a subset of {minimum, maximum, exclusiveMinimum, exclusiveMaximum}.
    Bound values are numbers or ISO date/datetime strings. Emits one SEVERITY_STRUCTURAL
    Flag per violated bound. Distinct from numeric-column/range (distribution soft band).
    A column that cannot be coerced to the bound's kind raises ValueError (exit 2).
    """
    col = ctx.columns[0]
    spec = params["bounds"]
    numeric = all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in spec.values())
    raw = ctx.table[col]
    if numeric:
        series = cast("pd.Series", pd.to_numeric(raw, errors="coerce"))
        cmp_spec = dict(spec)
    else:
        series = cast("pd.Series", pd.to_datetime(raw, errors="coerce"))
        cmp_spec = {k: pd.Timestamp(v) for k, v in spec.items()}
    if len(raw) and series.isna().all():
        raise ValueError(f"numeric-column/bounds: column {col!r} cannot be coerced for bounds {spec}")
    series = series.dropna()
    flags: list[Flag] = []
    for key, op in _BOUND_CHECKS:
        if key in cmp_spec:
            n = int(op(series, cmp_spec[key]).sum())
            if n:
                # `side` is the exact bound key (minimum/exclusiveMinimum/maximum/
                # exclusiveMaximum) so each constraint gets a distinct flag_id — an
                # inclusive↔exclusive change is not silently the same disposition.
                flags.append(Flag(ASPECT, "bounds", col, key, SEVERITY_STRUCTURAL,
                                  str(n), str(spec[key]), f"{n} value(s) violate {key} {spec[key]}"))
    return flags
