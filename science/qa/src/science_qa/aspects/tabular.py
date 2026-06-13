from __future__ import annotations

from pathlib import Path

import pandas as pd

from science_qa.context import TableContext
from science_qa.flags import SEVERITY_STRUCTURAL, Flag


class CategoricalSpecError(Exception):
    """Raised when a categorical spec has neither 'allowed' nor 'allowed_from'."""


def _allowed_values(spec: dict, base_dir: Path) -> set:
    if "allowed" in spec:
        return set(spec["allowed"])
    if "allowed_from" in spec:
        ref = str(spec["allowed_from"])
        file_part, _, column = ref.partition("#")
        path = (base_dir / file_part) if not Path(file_part).is_absolute() else Path(file_part)
        registry = pd.read_csv(path)
        return set(registry[column].dropna().tolist())
    raise CategoricalSpecError(f"categorical spec must have 'allowed' or 'allowed_from': {spec!r}")


def unique_key(ctx: TableContext, params: dict) -> list[Flag]:
    col = ctx.columns[0]
    dupes = int(ctx.table[col].duplicated().sum())
    if dupes:
        return [Flag("tabular", "unique_key", col, None, SEVERITY_STRUCTURAL,
                     str(dupes), "0", f"{dupes} duplicate key value(s)")]
    return []


def required_complete(ctx: TableContext, params: dict) -> list[Flag]:
    col = ctx.columns[0]
    missing = int(ctx.table[col].isna().sum())
    if missing:
        return [Flag("tabular", "required_complete", col, None, SEVERITY_STRUCTURAL,
                     str(missing), "0", f"{missing} missing value(s)")]
    return []


def categoricals(ctx: TableContext, params: dict) -> list[Flag]:
    col = ctx.columns[0]
    allowed = _allowed_values(params["spec"], Path(params.get("base_dir", ".")))
    illegal = set(ctx.table[col].dropna().unique()) - allowed
    if illegal:
        return [Flag("tabular", "allowed", col, None, SEVERITY_STRUCTURAL,
                     ",".join(map(str, sorted(map(str, illegal)))), "in allowed set",
                     f"{len(illegal)} value(s) outside allowed set")]
    return []


def exclusive_flags(ctx: TableContext, params: dict) -> list[Flag]:
    a, b = ctx.columns[0], ctx.columns[1]
    cooccur = int((ctx.table[a].astype(bool) & ctx.table[b].astype(bool)).sum())
    if cooccur:
        return [Flag("tabular", "exclusive_flags", f"{a}+{b}", None, SEVERITY_STRUCTURAL,
                     str(cooccur), "0", f"{cooccur} row(s) where {a} and {b} co-occur")]
    return []


def type_conformance(ctx: TableContext, params: dict) -> list[Flag]:
    col = ctx.columns[0]
    expected = params["expected"]
    is_numeric = pd.api.types.is_numeric_dtype(ctx.table[col])
    ok = is_numeric if expected == "numeric" else (not is_numeric)
    if not ok:
        return [Flag("tabular", "type_conformance", col, None, SEVERITY_STRUCTURAL,
                     str(ctx.table[col].dtype), expected, f"{col} dtype not {expected}")]
    return []
