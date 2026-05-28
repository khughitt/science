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
        sequence_name = (record.get("Sequence-Name") or "").strip()
        if not sequence_name:
            continue
        for column, alias_kind in _KINDS:
            alias = (record.get(column) or "").strip()
            if not alias or alias.lower() == "na":
                continue
            sequence_accession = alias if alias_kind in _ACCESSION_KINDS else ""
            rows.append(
                {
                    "sequence_name": sequence_name,
                    "alias": alias,
                    "alias_kind": alias_kind,
                    "sequence_accession": sequence_accession,
                }
            )
    return rows


def build_contig_alias_rows(
    *, contig_rows: list[dict[str, Any]], report_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    for contig in contig_rows:
        name = str(contig.get("name") or "").strip()
        if not name:
            raise ValueError("seqcol contig row has blank name")
        if name in by_name:
            raise ValueError(f"duplicate seqcol contig name {name!r}")
        by_name[name] = contig

    rows: list[dict[str, Any]] = []
    matched_names: set[str] = set()
    for report_row in report_rows:
        name = str(report_row.get("sequence_name") or "").strip()
        if name not in by_name:
            raise ValueError(f"assembly-report sequence name {name!r} has no seqcol contig row")
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
        raise ValueError(f"seqcol contig name {missing_names[0]!r} has no assembly-report row")
    return rows


def fetch_text(url: str) -> str:
    response = httpx.get(url, timeout=60.0, follow_redirects=True)
    response.raise_for_status()
    return response.text
