"""Runtime resolver for seqcol contigs and aliases.

The resolver is pure over the pinned assembly-registry CSV resources: it reads
through the commons data resolver, validates rows loudly, and resolves an input
contig alias within the caller-declared assembly.
"""

from __future__ import annotations

import csv
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

from science_tool.commons.assembly import ASSEMBLY_REGISTRY_ID
from science_tool.commons.resolver import resolve

CONTIGS_RESOURCE = "contigs.csv"
ALIASES_RESOURCE = "contig_aliases.csv"
_ALIAS_KINDS = frozenset({"seqcol_name", "genbank_accession", "refseq_accession", "ucsc", "ensembl"})
_ACCESSION_ALIAS_KINDS = frozenset({"genbank_accession", "refseq_accession"})
_CONTIG_COLUMNS = frozenset({"seqcol_digest", "sequence_index", "name", "refget_digest", "length"})
_ALIAS_COLUMNS = frozenset({"seqcol_digest", "refget_digest", "alias", "alias_kind", "sequence_accession"})

_T = TypeVar("_T")


class ContigError(ValueError):
    """The contig registry cannot resolve the requested contig unambiguously."""


@dataclass(frozen=True, slots=True)
class ContigMatch:
    refget_digest: str
    name: str
    length: int
    alias_kind: str


@dataclass(frozen=True, slots=True)
class AmbiguousContig:
    query: str
    candidates: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AccessionAssemblyMismatch:
    query: str
    found_seqcol_digest: str


ContigResolution = ContigMatch | AmbiguousContig | AccessionAssemblyMismatch


@dataclass(frozen=True, slots=True)
class _ContigRow:
    seqcol_digest: str
    sequence_index: int
    name: str
    refget_digest: str
    length: int


@dataclass(frozen=True, slots=True)
class _AliasRow:
    seqcol_digest: str
    refget_digest: str
    alias: str
    alias_kind: str
    sequence_accession: str


def _required_text(row: dict[str, Any], row_index: int, column: str) -> str:
    if column not in row:
        raise ContigError(f"row {row_index}: missing required column {column!r}")
    value = row[column]
    if not isinstance(value, str):
        raise ContigError(f"row {row_index}: column {column!r} must be a string")
    if not value:
        raise ContigError(f"row {row_index}: blank {column}")
    if value != value.strip():
        raise ContigError(f"row {row_index}: invalid whitespace in {column}={value!r}")
    return value


def _validate_columns(row: dict[str, Any], row_index: int, expected: frozenset[str]) -> None:
    if None in row:
        raise ContigError(f"row {row_index}: malformed CSV row with surplus columns")
    actual = set(row)
    if actual != expected:
        unexpected = sorted(actual - expected)
        missing = sorted(expected - actual)
        details: list[str] = []
        if unexpected:
            details.append(f"unexpected columns {unexpected!r}")
        if missing:
            details.append(f"missing columns {missing!r}")
        raise ContigError(f"row {row_index}: malformed CSV row with {', '.join(details)}")


def _validate_header(resource: str, fieldnames: Sequence[str] | None, expected: frozenset[str]) -> None:
    if fieldnames is None:
        raise ContigError(f"{resource}: missing CSV header")

    seen: set[str] = set()
    duplicate_columns: list[str] = []
    for fieldname in fieldnames:
        if fieldname in seen and fieldname not in duplicate_columns:
            duplicate_columns.append(fieldname)
        seen.add(fieldname)
    if duplicate_columns:
        raise ContigError(f"{resource}: duplicate columns {sorted(duplicate_columns)!r}")

    actual = set(fieldnames)
    if actual != expected:
        unexpected = sorted(actual - expected)
        missing = sorted(expected - actual)
        details: list[str] = []
        if unexpected:
            details.append(f"unexpected columns {unexpected!r}")
        if missing:
            details.append(f"missing columns {missing!r}")
        raise ContigError(f"{resource}: malformed CSV header with {', '.join(details)}")


def _optional_text(row: dict[str, Any], row_index: int, column: str) -> str:
    if column not in row:
        raise ContigError(f"row {row_index}: missing required column {column!r}")
    value = row[column]
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ContigError(f"row {row_index}: column {column!r} must be a string")
    if value != value.strip():
        raise ContigError(f"row {row_index}: invalid whitespace in {column}={value!r}")
    return value


def _required_positive_int(row: dict[str, Any], row_index: int, column: str) -> int:
    value = _required_text(row, row_index, column)
    if not value.isdecimal():
        raise ContigError(f"row {row_index}: invalid {column} {value!r}")
    parsed = int(value)
    if parsed <= 0:
        raise ContigError(f"row {row_index}: invalid {column} {value!r}")
    return parsed


def _required_nonnegative_int(row: dict[str, Any], row_index: int, column: str) -> int:
    value = _required_text(row, row_index, column)
    if not value.isdecimal():
        raise ContigError(f"row {row_index}: invalid {column} {value!r}")
    return int(value)


def _parse_contig_rows(rows: Iterable[dict[str, Any]]) -> list[_ContigRow]:
    contigs: list[_ContigRow] = []
    seen_names: set[tuple[str, str]] = set()
    seen_indexes: set[tuple[str, int]] = set()
    seen_contigs: set[tuple[str, str]] = set()

    for row_index, row in enumerate(rows):
        _validate_columns(row, row_index, _CONTIG_COLUMNS)
        seqcol_digest = _required_text(row, row_index, "seqcol_digest")
        sequence_index = _required_nonnegative_int(row, row_index, "sequence_index")
        name = _required_text(row, row_index, "name")
        refget_digest = _required_text(row, row_index, "refget_digest")
        length = _required_positive_int(row, row_index, "length")

        name_key = (seqcol_digest, name)
        if name_key in seen_names:
            raise ContigError(f"duplicate contig name {name!r} in {seqcol_digest!r}")
        seen_names.add(name_key)

        index_key = (seqcol_digest, sequence_index)
        if index_key in seen_indexes:
            raise ContigError(f"duplicate sequence_index {sequence_index!r} in {seqcol_digest!r}")
        seen_indexes.add(index_key)

        contig_key = (seqcol_digest, refget_digest)
        if contig_key in seen_contigs:
            raise ContigError(f"duplicate contig refget digest {refget_digest!r} in {seqcol_digest!r}")
        seen_contigs.add(contig_key)

        contigs.append(
            _ContigRow(
                seqcol_digest=seqcol_digest,
                sequence_index=sequence_index,
                name=name,
                refget_digest=refget_digest,
                length=length,
            )
        )

    return contigs


def _parse_alias_rows(rows: Iterable[dict[str, Any]]) -> list[_AliasRow]:
    aliases: list[_AliasRow] = []
    seen: set[tuple[str, str]] = set()

    for row_index, row in enumerate(rows):
        _validate_columns(row, row_index, _ALIAS_COLUMNS)
        seqcol_digest = _required_text(row, row_index, "seqcol_digest")
        refget_digest = _required_text(row, row_index, "refget_digest")
        alias = _required_text(row, row_index, "alias")
        alias_kind = _required_text(row, row_index, "alias_kind")
        sequence_accession = _optional_text(row, row_index, "sequence_accession")

        if alias_kind not in _ALIAS_KINDS:
            raise ContigError(f"row {row_index}: invalid alias_kind {alias_kind!r}")

        key = (seqcol_digest, alias)
        if key in seen:
            raise ContigError(f"duplicate alias {alias!r} in {seqcol_digest!r}")
        seen.add(key)

        aliases.append(
            _AliasRow(
                seqcol_digest=seqcol_digest,
                refget_digest=refget_digest,
                alias=alias,
                alias_kind=alias_kind,
                sequence_accession=sequence_accession,
            )
        )

    return aliases


def _load(
    resource: str,
    expected_columns: frozenset[str],
    parser: Callable[[Iterable[dict[str, Any]]], list[_T]],
    *,
    registry_id: str,
    commons_root: Path | None,
    data_root: Path | None,
) -> list[_T]:
    resolved = resolve(registry_id, resource, commons_root=commons_root, data_root=data_root)
    with resolved.path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        _validate_header(resource, reader.fieldnames, expected_columns)
        return parser(reader)


def _contigs_by_key(contigs: Iterable[_ContigRow]) -> dict[tuple[str, str], _ContigRow]:
    by_key: dict[tuple[str, str], _ContigRow] = {}
    for contig in contigs:
        by_key[(contig.seqcol_digest, contig.refget_digest)] = contig
    return by_key


def _validate_alias_contig_refs(aliases: Iterable[_AliasRow], contigs: dict[tuple[str, str], _ContigRow]) -> None:
    for alias in aliases:
        key = (alias.seqcol_digest, alias.refget_digest)
        if key not in contigs:
            raise ContigError(
                f"alias {alias.alias!r} in {alias.seqcol_digest!r} references missing contig "
                f"{alias.refget_digest!r}"
            )


def resolve_contig(
    query: str,
    *,
    seqcol_digest: str,
    registry_id: str = ASSEMBLY_REGISTRY_ID,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> ContigResolution:
    if not query or query != query.strip():
        raise ContigError(f"unknown contig {query!r}")
    if not seqcol_digest or seqcol_digest != seqcol_digest.strip():
        raise ContigError(f"invalid seqcol_digest {seqcol_digest!r}")

    contigs = _load(
        CONTIGS_RESOURCE,
        _CONTIG_COLUMNS,
        _parse_contig_rows,
        registry_id=registry_id,
        commons_root=commons_root,
        data_root=data_root,
    )
    contigs_by_key = _contigs_by_key(contigs)
    aliases = _load(
        ALIASES_RESOURCE,
        _ALIAS_COLUMNS,
        _parse_alias_rows,
        registry_id=registry_id,
        commons_root=commons_root,
        data_root=data_root,
    )
    _validate_alias_contig_refs(aliases, contigs_by_key)

    in_assembly = [alias for alias in aliases if alias.seqcol_digest == seqcol_digest and alias.alias == query]
    refget_candidates = {alias.refget_digest for alias in in_assembly}
    if len(refget_candidates) > 1:
        return AmbiguousContig(query=query, candidates=tuple(sorted(refget_candidates)))
    if len(refget_candidates) == 1:
        alias = in_assembly[0]
        contig = contigs_by_key[(seqcol_digest, alias.refget_digest)]
        return ContigMatch(
            refget_digest=contig.refget_digest,
            name=contig.name,
            length=contig.length,
            alias_kind=alias.alias_kind,
        )

    elsewhere = [
        alias
        for alias in aliases
        if alias.alias == query and alias.alias_kind in _ACCESSION_ALIAS_KINDS
    ]
    elsewhere_candidates = {
        f"{alias.seqcol_digest}:{alias.refget_digest}" for alias in elsewhere
    }
    if len(elsewhere_candidates) > 1:
        return AmbiguousContig(query=query, candidates=tuple(sorted(elsewhere_candidates)))
    if len(elsewhere_candidates) == 1:
        return AccessionAssemblyMismatch(query=query, found_seqcol_digest=elsewhere[0].seqcol_digest)

    raise ContigError(f"unknown contig {query!r} in assembly {seqcol_digest!r}")
