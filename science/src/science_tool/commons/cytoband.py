"""Runtime reader for pinned cytoband reference rows."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.commons.resolver import resolve

CYTOBAND_HG19_ID = "dataset:cytoband-hg19"
CYTOBANDS_RESOURCE = "cytobands.csv"
_COLUMNS = ("chrom", "start", "end", "name", "gie_stain")
_COLUMN_SET = frozenset(_COLUMNS)


class CytobandError(ValueError):
    """The cytoband artifact cannot answer the requested lookup."""


@dataclass(frozen=True, slots=True)
class CytobandRow:
    chrom: str
    start: int
    end: int
    name: str
    gie_stain: str


def load_cytobands(
    dataset_id: str = CYTOBAND_HG19_ID,
    *,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> list[CytobandRow]:
    rows = _load_csv_rows(dataset_id=dataset_id, commons_root=commons_root, data_root=data_root)
    return _parse_rows(rows)


def bands_for_interval(rows: Sequence[CytobandRow], *, chrom: str, start: int, end: int) -> list[CytobandRow]:
    if start < 0 or end <= start:
        raise CytobandError(f"invalid interval {chrom}:{start}-{end}")
    known_chroms = {row.chrom for row in rows}
    if chrom not in known_chroms:
        raise CytobandError(f"unknown chromosome {chrom!r}")
    return [row for row in rows if row.chrom == chrom and row.start < end and start < row.end]


def _load_csv_rows(
    *,
    dataset_id: str,
    commons_root: Path | None,
    data_root: Path | None,
) -> list[dict[str, Any]]:
    resolved = resolve(dataset_id, CYTOBANDS_RESOURCE, commons_root=commons_root, data_root=data_root)
    with resolved.path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        _validate_header(CYTOBANDS_RESOURCE, reader.fieldnames)
        return list(reader)


def _parse_rows(rows: Iterable[dict[str, Any]]) -> list[CytobandRow]:
    parsed: list[CytobandRow] = []
    seen: set[tuple[str, int, int, str, str]] = set()
    for row_index, row in enumerate(rows):
        _validate_columns(row, row_index)
        chrom = _required_text(row, row_index, "chrom")
        start = _required_nonnegative_int(row, row_index, "start")
        end = _required_nonnegative_int(row, row_index, "end")
        name = _required_text(row, row_index, "name")
        gie_stain = _required_text(row, row_index, "gie_stain")
        if end <= start:
            raise CytobandError(f"row {row_index}: invalid interval {chrom}:{start}-{end}")
        key = (chrom, start, end, name, gie_stain)
        if key in seen:
            raise CytobandError(f"row {row_index}: duplicate cytoband row {key!r}")
        seen.add(key)
        parsed.append(CytobandRow(chrom=chrom, start=start, end=end, name=name, gie_stain=gie_stain))
    return parsed


def _validate_header(resource: str, fieldnames: Sequence[str] | None) -> None:
    if fieldnames is None:
        raise CytobandError(f"{resource}: missing CSV header")
    duplicate_columns = _duplicate_columns(fieldnames)
    if duplicate_columns:
        raise CytobandError(f"{resource}: duplicate columns {duplicate_columns!r}")
    if tuple(fieldnames) != _COLUMNS:
        raise CytobandError(f"{resource}: malformed CSV header with {_column_details(set(fieldnames))}")


def _validate_columns(row: dict[str, Any], row_index: int) -> None:
    if None in row:
        raise CytobandError(f"row {row_index}: malformed CSV row with surplus columns")
    actual = set(row)
    if actual != _COLUMN_SET:
        raise CytobandError(f"row {row_index}: malformed CSV row with {_column_details(actual)}")


def _required_text(row: dict[str, Any], row_index: int, column: str) -> str:
    value = row[column]
    if not isinstance(value, str):
        raise CytobandError(f"row {row_index}: column {column!r} must be a string")
    if not value:
        raise CytobandError(f"row {row_index}: blank {column}")
    if value != value.strip():
        raise CytobandError(f"row {row_index}: invalid whitespace in {column}={value!r}")
    return value


def _required_nonnegative_int(row: dict[str, Any], row_index: int, column: str) -> int:
    value = _required_text(row, row_index, column)
    if not value.isdecimal():
        raise CytobandError(f"row {row_index}: invalid {column} {value!r}")
    return int(value)


def _duplicate_columns(fieldnames: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for fieldname in fieldnames:
        if fieldname in seen and fieldname not in duplicates:
            duplicates.append(fieldname)
        seen.add(fieldname)
    return sorted(duplicates)


def _column_details(actual: set[str]) -> str:
    unexpected = sorted(actual - _COLUMN_SET)
    missing = sorted(_COLUMN_SET - actual)
    details: list[str] = []
    if unexpected:
        details.append(f"unexpected columns {unexpected!r}")
    if missing:
        details.append(f"missing columns {missing!r}")
    if not details:
        details.append(f"expected columns {list(_COLUMNS)!r}")
    return ", ".join(details)
