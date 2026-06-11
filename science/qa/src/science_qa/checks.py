from __future__ import annotations

from pathlib import Path

import pandas as pd

from science_qa.config import QAConfig
from science_qa.flags import SEVERITY_DISTRIBUTION, SEVERITY_STRUCTURAL, Flag


class QACheckError(Exception):
    """Raised when a config clause references a column absent from the table."""


def _require_column(table: pd.DataFrame, column: str, *, clause: str) -> None:
    if column not in table.columns:
        raise QACheckError(f"{clause} references column {column!r} absent from table")


def _allowed_values(spec: dict, base_dir: Path) -> set:
    if "allowed" in spec:
        return set(spec["allowed"])
    if "allowed_from" in spec:
        ref = str(spec["allowed_from"])
        file_part, _, column = ref.partition("#")
        path = (base_dir / file_part) if not Path(file_part).is_absolute() else Path(file_part)
        registry = pd.read_csv(path)
        return set(registry[column].dropna().tolist())
    raise QACheckError(f"categorical spec must have 'allowed' or 'allowed_from': {spec!r}")


def run_structural_checks(table: pd.DataFrame, config: QAConfig, *, base_dir: Path | None = None) -> list[Flag]:
    base_dir = base_dir or Path(".")
    flags: list[Flag] = []

    if config.unique_key:
        _require_column(table, config.unique_key, clause="unique_key")
        if table[config.unique_key].duplicated().any():
            dupes = int(table[config.unique_key].duplicated().sum())
            flags.append(Flag("generic", "unique_key", config.unique_key, None,
                              SEVERITY_STRUCTURAL, str(dupes), "0", f"{dupes} duplicate key value(s)"))

    for column in config.required_complete:
        _require_column(table, column, clause="required_complete")
        missing = int(table[column].isna().sum())
        if missing:
            flags.append(Flag("generic", "required_complete", column, None,
                              SEVERITY_STRUCTURAL, str(missing), "0", f"{missing} missing value(s)"))

    for column, spec in config.categoricals.items():
        _require_column(table, column, clause="categoricals")
        allowed = _allowed_values(spec, base_dir)
        illegal = set(table[column].dropna().unique()) - allowed
        if illegal:
            flags.append(Flag("generic", "allowed", column, None,
                              SEVERITY_STRUCTURAL, ",".join(map(str, sorted(map(str, illegal)))),
                              "in allowed set", f"{len(illegal)} value(s) outside allowed set"))

    for pair in config.exclusive_flags:
        for column in pair:
            _require_column(table, column, clause="exclusive_flags")
        cooccur = int((table[pair[0]].astype(bool) & table[pair[1]].astype(bool)).sum())
        if cooccur:
            flags.append(Flag("generic", "exclusive_flags", "+".join(pair), None,
                              SEVERITY_STRUCTURAL, str(cooccur), "0",
                              f"{cooccur} row(s) where {pair[0]} and {pair[1]} co-occur"))

    if config.missing_sentinels:
        sentinels = list(config.missing_sentinels)
        for column in table.columns:
            if not pd.api.types.is_numeric_dtype(table[column]):
                continue
            survivors = int(table[column].isin(sentinels).sum())
            if survivors:
                flags.append(Flag("generic", "missing_sentinel", column, None,
                                  SEVERITY_STRUCTURAL, str(survivors), "0",
                                  f"{survivors} surviving missing-sentinel value(s)"))

    return flags


def run_distribution_checks(table: pd.DataFrame, config: QAConfig) -> list[Flag]:
    flags: list[Flag] = []
    for column, bounds in config.ranges.items():
        _require_column(table, column, clause="ranges")
        series = pd.to_numeric(table[column], errors="coerce").dropna()
        if "min" in bounds:
            below = int((series < bounds["min"]).sum())
            if below:
                flags.append(Flag("generic", "range", column, "min", SEVERITY_DISTRIBUTION,
                                  str(below), str(bounds["min"]), f"{below} value(s) below min"))
        if "max" in bounds:
            above = int((series > bounds["max"]).sum())
            if above:
                flags.append(Flag("generic", "range", column, "max", SEVERITY_DISTRIBUTION,
                                  str(above), str(bounds["max"]), f"{above} value(s) above max"))
    return flags


def per_variable_stats(table: pd.DataFrame) -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []
    total = len(table)
    for column in table.columns:
        series = table[column]
        n = int(series.notna().sum())
        pct_miss = round(100 * (total - n) / total, 1) if total else 0.0
        rows.append({"variable": column, "n": n, "pct_miss": f"{pct_miss}"})
    return rows
