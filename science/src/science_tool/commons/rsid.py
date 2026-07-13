"""Pinned dbSNP rsID resolver for C4c variant-label inputs."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import yaml

from science_tool.commons.errors import CommonsDatapackageError
from science_tool.commons.resolver import resolve

_DEFAULT_DATASET = "dataset:variant-labels-dbsnp-human"
MANIFEST_RESOURCE = "rsid-shards.yaml"
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
    value = query.lower()
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


def _manifest_for_registry(
    registry: str,
    *,
    commons_root: Path | str | None,
    data_root: Path | str | None,
) -> Path | None:
    try:
        resolved = resolve(
            registry,
            MANIFEST_RESOURCE,
            commons_root=None if commons_root is None else Path(commons_root),
            data_root=None if data_root is None else Path(data_root),
        )
    except CommonsDatapackageError as exc:
        if "no resource with logical path or name" in exc.reason and MANIFEST_RESOURCE in exc.reason:
            return None
        raise
    return resolved.path


def shard_id_for_rsid(rsid: str, *, shard_count: int) -> str:
    width = max(2, len(f"{shard_count - 1:x}"))
    return f"{int(rsid[2:]) % shard_count:0{width}x}"


def _candidate_sqlites_from_manifest(manifest_path: Path, *, rsid: str) -> list[Path]:
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{manifest_path}: expected YAML mapping")
    shard_count = raw.get("shard_count")
    if not isinstance(shard_count, int) or shard_count <= 0:
        raise ValueError(f"{manifest_path}: shard_count must be a positive integer")
    shard_id = shard_id_for_rsid(rsid, shard_count=shard_count)
    raw_shards = raw.get("shards")
    if not isinstance(raw_shards, list):
        raise ValueError(f"{manifest_path}: shards must be a list")

    paths: list[Path] = []
    for raw_shard in raw_shards:
        if not isinstance(raw_shard, dict):
            raise ValueError(f"{manifest_path}: shard entries must be mappings")
        if raw_shard.get("shard_id") != shard_id:
            continue
        raw_path = raw_shard.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            raise ValueError(f"{manifest_path}: shard path must be a non-empty string")
        path = Path(raw_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"{manifest_path}: shard path must be relative and stay within the dataset")
        paths.append(manifest_path.parent / path)
    if not paths:
        raise ValueError(f"{manifest_path}: no shard entries for shard_id {shard_id}")
    return paths


def _query_sqlites(paths: list[Path], *, rsid: str, assembly_seqcol: str) -> list[sqlite3.Row]:
    rows: list[sqlite3.Row] = []
    for db_path in paths:
        uri = f"{db_path.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as conn:
            conn.row_factory = sqlite3.Row
            rows.extend(
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
    rows.sort(key=lambda row: (row["contig"], row["pos0"], row["ref"], row["alt"], row["source_vcf"], row["allele_index"]))
    return rows


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

    if sqlite_path is not None:
        paths = [Path(sqlite_path)]
    else:
        manifest_path = _manifest_for_registry(
            registry,
            commons_root=commons_root,
            data_root=data_root,
        )
        if manifest_path is None:
            paths = [
                _sqlite_for_registry(
                    registry,
                    commons_root=commons_root,
                    data_root=data_root,
                )
            ]
        else:
            paths = _candidate_sqlites_from_manifest(manifest_path, rsid=rsid)
    rows = _query_sqlites(paths, rsid=rsid, assembly_seqcol=assembly_seqcol)

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
