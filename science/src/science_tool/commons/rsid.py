"""Pinned dbSNP rsID resolver for C4c variant-label inputs."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from science_tool.commons.resolver import resolve

_DEFAULT_DATASET = "dataset:variant-labels-dbsnp-human"
SQLITE_RESOURCE = "rsid_mappings.sqlite"
_RSID = re.compile(r"^rs[1-9][0-9]*$")


@dataclass(frozen=True, slots=True)
class RsidMatch:
    rsid: str
    seqcol_digest: str
    contig: str
    pos0: int
    ref: str
    alt: str
    source_vcf: str
    allele_index: int


@dataclass(frozen=True, slots=True)
class RsidDefect:
    query: str
    reason: str
    detail: str


def normalize_rsid(query: str) -> str | RsidDefect:
    value = query.strip().lower()
    if _RSID.fullmatch(value) is None:
        return RsidDefect(query, "malformed-rsid", "expected rs followed by digits")
    return value


def _sqlite_for_registry(
    registry: str,
    *,
    commons_root: Path | str | None,
    data_root: Path | str | None,
) -> Path:
    resolved = resolve(
        registry,
        SQLITE_RESOURCE,
        commons_root=None if commons_root is None else Path(commons_root),
        data_root=None if data_root is None else Path(data_root),
    )
    return resolved.path


def resolve_rsid(
    query: str,
    *,
    assembly_seqcol: str,
    registry: str = _DEFAULT_DATASET,
    sqlite_path: Path | str | None = None,
    ref: str | None = None,
    alt: str | None = None,
    commons_root: Path | str | None = None,
    data_root: Path | str | None = None,
) -> RsidMatch | RsidDefect:
    rsid = normalize_rsid(query)
    if isinstance(rsid, RsidDefect):
        return rsid

    db_path = Path(sqlite_path) if sqlite_path is not None else _sqlite_for_registry(
        registry,
        commons_root=commons_root,
        data_root=data_root,
    )
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        conn.row_factory = sqlite3.Row
        rows = list(
            conn.execute(
                """
                SELECT rsid, seqcol_digest, contig, pos0, ref, alt, source_vcf, allele_index
                FROM rsid_alleles
                WHERE rsid = ? AND seqcol_digest = ?
                ORDER BY contig, pos0, ref, alt, source_vcf, allele_index
                """,
                (rsid, assembly_seqcol),
            )
        )

    if not rows:
        return RsidDefect(rsid, "rsid-assembly-mismatch", f"no allele for declared assembly {assembly_seqcol}")

    if ref is not None or alt is not None:
        ref_filter = None if ref is None else ref.upper()
        alt_filter = None if alt is None else alt.upper()
        rows = [
            row
            for row in rows
            if (ref_filter is None or row["ref"] == ref_filter) and (alt_filter is None or row["alt"] == alt_filter)
        ]
        if not rows:
            return RsidDefect(rsid, "rsid-allele-mismatch", "no candidate matches supplied REF/ALT")

    if len(rows) > 1:
        return RsidDefect(rsid, "ambiguous-rsid", f"{len(rows)} candidate alleles for {assembly_seqcol}")

    row = rows[0]
    return RsidMatch(
        rsid=row["rsid"],
        seqcol_digest=row["seqcol_digest"],
        contig=row["contig"],
        pos0=int(row["pos0"]),
        ref=row["ref"],
        alt=row["alt"],
        source_vcf=row["source_vcf"],
        allele_index=int(row["allele_index"]),
    )
