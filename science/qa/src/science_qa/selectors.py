from __future__ import annotations

import re

import pandas as pd


class SelectorError(Exception):
    """Raised on an unknown selector kind, an undeclared named-set, or absent explicit columns."""


def resolve_columns(spec, table: pd.DataFrame, *, column_sets: dict) -> list[str]:
    """Resolve a selector spec to an ordered list of existing column names (may be empty).

    Selector forms:
      - list[str]            -> explicit names (must all exist)
      - {"dtype": "numeric"} -> numeric-dtype columns
      - {"dtype": "all"}     -> every column
      - {"regex": "..."}     -> columns whose name matches
      - {"named_set": name}  -> resolve the spec stored under column_sets[name]
    """
    if isinstance(spec, list):
        missing = [c for c in spec if c not in table.columns]
        if missing:
            raise SelectorError(f"explicit column-set names missing from table: {missing}")
        return list(spec)
    if not isinstance(spec, dict) or len(spec) != 1:
        raise SelectorError(f"unknown selector spec: {spec!r}")
    (kind, arg), = spec.items()
    if kind == "named_set":
        if arg not in column_sets:
            raise SelectorError(f"named_set references undeclared column-set {arg!r}")
        return resolve_columns(column_sets[arg], table, column_sets=column_sets)
    if kind == "dtype":
        if arg == "all":
            return list(table.columns)
        if arg == "numeric":
            return [c for c in table.columns if pd.api.types.is_numeric_dtype(table[c])]
        raise SelectorError(f"unknown dtype selector {arg!r}")
    if kind == "regex":
        pattern = re.compile(arg)
        return [c for c in table.columns if pattern.search(c)]
    raise SelectorError(f"unknown selector kind {kind!r}")
