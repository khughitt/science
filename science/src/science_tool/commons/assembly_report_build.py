"""Pure parser for NCBI assembly_report.txt contig alias rows for C4a.

NCBI assembly reports provide aliases that are not present in seqcol level-2
records, including RefSeq accessions, GenBank accessions, and UCSC names.
This module parses pinned report text into build-time alias rows. The only
network entry point is fetch_text(), which is intended for build-time use.
"""

from __future__ import annotations

import csv
import io
from typing import Any

import httpx

_KINDS = (
    ("Sequence-Name", "seqcol_name"),
    ("GenBank-Accn", "genbank_accession"),
    ("RefSeq-Accn", "refseq_accession"),
    ("UCSC-style-name", "ucsc"),
)
_ACCESSION_KINDS = {"genbank_accession", "refseq_accession"}
_REQUIRED_COLUMNS = {column for column, _alias_kind in _KINDS}
_REPORT_COLUMNS_KEY = "_assembly_report_columns"


def _header_index(report_text: str) -> tuple[list[str], list[str]]:
    header: list[str] | None = None
    data: list[str] = []
    for line in report_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            header = stripped.removeprefix("#").strip().split("\t")
            continue
        data.append(line)

    if header is None:
        raise ValueError("assembly report has no header")
    return header, data


def parse_assembly_report(report_text: str) -> list[dict[str, Any]]:
    header, data = _header_index(report_text)
    missing = sorted(_REQUIRED_COLUMNS - set(header))
    if missing:
        raise ValueError(f"assembly report header missing required columns: {', '.join(missing)}")
    reader = csv.DictReader(io.StringIO("\n".join(data)), fieldnames=header, delimiter="\t")
    rows: list[dict[str, Any]] = []
    for record in reader:
        source_columns = {column: (record.get(column) or "").strip() for column in header}
        sequence_name = source_columns["Sequence-Name"]
        if not sequence_name:
            continue
        for column, alias_kind in _KINDS:
            alias = source_columns[column]
            if not alias or alias.lower() == "na":
                continue
            sequence_accession = alias if alias_kind in _ACCESSION_KINDS else ""
            rows.append(
                {
                    **source_columns,
                    _REPORT_COLUMNS_KEY: tuple(header),
                    "sequence_name": sequence_name,
                    "alias": alias,
                    "alias_kind": alias_kind,
                    "sequence_accession": sequence_accession,
                }
            )
    return rows


def _available_report_columns(report_rows: list[dict[str, Any]]) -> set[str]:
    columns: set[str] = set()
    for report_row in report_rows:
        row_columns = report_row.get(_REPORT_COLUMNS_KEY)
        if isinstance(row_columns, (tuple, list)):
            columns.update(str(column) for column in row_columns)
    return columns


def _report_match_value(report_row: dict[str, Any], match_column: str) -> str:
    if match_column == "Sequence-Name":
        return str(report_row.get("Sequence-Name") or report_row.get("sequence_name") or "").strip()
    return str(report_row.get(match_column) or "").strip()


def _report_sequence_name(report_row: dict[str, Any]) -> str:
    return str(report_row.get("Sequence-Name") or report_row.get("sequence_name") or "").strip()


def _validate_report_match_keys(report_rows: list[dict[str, Any]], match_column: str) -> None:
    seen_sources_by_key: dict[str, str] = {}
    for report_row in report_rows:
        match_value = _report_match_value(report_row, match_column)
        source_name = _report_sequence_name(report_row)
        if not match_value or match_value.lower() == "na":
            raise ValueError(
                f"assembly-report {match_column} is missing/blank/na for "
                f"Sequence-Name {source_name!r}: {match_value!r}"
            )
        seen_source = seen_sources_by_key.get(match_value)
        if seen_source is not None and seen_source != source_name:
            raise ValueError(
                f"duplicate assembly-report {match_column} {match_value!r} "
                f"for Sequence-Name {seen_source!r} and {source_name!r}"
            )
        seen_sources_by_key[match_value] = source_name


def _match_column_label(match_column: str) -> str:
    if match_column == "Sequence-Name":
        return "sequence name"
    return match_column


def build_contig_alias_rows(
    *,
    contig_rows: list[dict[str, Any]],
    report_rows: list[dict[str, Any]],
    match_column: str = "Sequence-Name",
) -> list[dict[str, Any]]:
    available_columns = _available_report_columns(report_rows)
    if match_column != "Sequence-Name" and not available_columns:
        raise ValueError(
            f"assembly report match_column {match_column!r} is not available; "
            "report rows do not include assembly report columns"
        )
    if available_columns and match_column not in available_columns:
        raise ValueError(
            f"assembly report match_column {match_column!r} is not available; "
            f"available columns: {', '.join(sorted(available_columns))}"
        )
    if match_column != "Sequence-Name":
        _validate_report_match_keys(report_rows, match_column)

    by_name: dict[str, dict[str, Any]] = {}
    for contig in contig_rows:
        name = str(contig.get("name") or "").strip()
        if not name:
            raise ValueError("seqcol contig row has blank name")
        if name in by_name:
            if match_column == "Sequence-Name":
                raise ValueError(f"duplicate seqcol contig name {name!r}")
            raise ValueError(f"duplicate seqcol contig name for assembly-report {match_column} {name!r}")
        by_name[name] = contig

    rows: list[dict[str, Any]] = []
    matched_names: set[str] = set()
    for report_row in report_rows:
        name = _report_match_value(report_row, match_column)
        if name not in by_name:
            raise ValueError(
                f"assembly-report {_match_column_label(match_column)} {name!r} has no seqcol contig row"
            )
        matched_names.add(name)
        contig = by_name[name]
        rows.append(
            {
                "seqcol_digest": contig["seqcol_digest"],
                "refget_digest": contig["refget_digest"],
                "alias": report_row["alias"],
                "alias_kind": report_row["alias_kind"],
                "sequence_accession": report_row["sequence_accession"],
            }
        )
    missing_names = sorted(set(by_name) - matched_names)
    if missing_names:
        if match_column == "Sequence-Name":
            raise ValueError(f"seqcol contig name {missing_names[0]!r} has no assembly-report row")
        raise ValueError(
            f"seqcol contig name {missing_names[0]!r} has no assembly-report {match_column} row"
        )
    return rows


def fetch_text(url: str) -> str:
    response = httpx.get(url, timeout=60.0, follow_redirects=True)
    response.raise_for_status()
    return response.text
