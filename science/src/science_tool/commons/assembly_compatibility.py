"""Parse pinned assembly compatibility relations."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from science_tool.commons.resolver import resolve

RelationKind = Literal["liftover_possible"]
RelationMethod = Literal["ucsc_chain"]
RelationDirection = Literal["forward"]

COMPATIBILITY_RESOURCE = "compatibility_relations"
_COLUMNS = (
    "source_seqcol_digest",
    "target_seqcol_digest",
    "relation",
    "method",
    "chain_resource",
    "direction",
    "source_label",
    "target_label",
    "source_url",
    "chain_sha256",
)
_SHA256_PREFIX = "sha256:"
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


class AssemblyCompatibilityError(ValueError):
    """A compatibility relation row violates the pinned relation contract."""


@dataclass(frozen=True, slots=True)
class CompatibilityRelation:
    source_seqcol_digest: str
    target_seqcol_digest: str
    relation: RelationKind
    method: RelationMethod
    chain_resource: str
    direction: RelationDirection
    source_label: str
    target_label: str
    source_url: str
    chain_sha256: str


def _required(row: dict[str, str], row_number: int, column: str) -> str:
    if column not in row:
        raise AssemblyCompatibilityError(f"row {row_number}: missing required column {column!r}")

    value = row[column]
    if not isinstance(value, str):
        raise AssemblyCompatibilityError(f"row {row_number}: column {column!r} must be a string")
    if value != value.strip():
        raise AssemblyCompatibilityError(f"row {row_number}: column {column!r} has leading/trailing whitespace")
    if not value:
        raise AssemblyCompatibilityError(f"row {row_number}: column {column!r} must be non-empty")
    return value


def _validate_row_columns(row: dict[str, str], row_number: int) -> None:
    actual = set(row)
    expected = set(_COLUMNS)
    if actual == expected:
        return
    details: list[str] = []
    unexpected = sorted(actual - expected)
    missing = sorted(expected - actual)
    if unexpected:
        details.append(f"unexpected columns {unexpected!r}")
    if missing:
        details.append(f"missing columns {missing!r}")
    raise AssemblyCompatibilityError(f"row {row_number}: malformed compatibility row with {', '.join(details)}")


def parse_compatibility_rows(rows: list[dict[str, str]]) -> list[CompatibilityRelation]:
    relations: list[CompatibilityRelation] = []
    seen: set[tuple[str, str, str]] = set()

    for row_number, row in enumerate(rows, start=1):
        _validate_row_columns(row, row_number)
        values = {column: _required(row, row_number, column) for column in _COLUMNS}

        source_seqcol_digest = values["source_seqcol_digest"]
        target_seqcol_digest = values["target_seqcol_digest"]
        relation = values["relation"]
        method = values["method"]
        direction = values["direction"]
        chain_sha256 = values["chain_sha256"]

        if source_seqcol_digest == target_seqcol_digest:
            raise AssemblyCompatibilityError(f"row {row_number}: source_seqcol_digest and target_seqcol_digest must differ")
        if relation != "liftover_possible":
            raise AssemblyCompatibilityError(f"row {row_number}: unsupported relation {relation!r}")
        if method != "ucsc_chain":
            raise AssemblyCompatibilityError(f"row {row_number}: unsupported method {method!r}")
        if direction != "forward":
            raise AssemblyCompatibilityError(f"row {row_number}: unsupported direction {direction!r}")

        key = (source_seqcol_digest, target_seqcol_digest, relation)
        if key in seen:
            raise AssemblyCompatibilityError(f"row {row_number}: duplicate compatibility relation {key!r}")
        seen.add(key)

        _validate_chain_sha256(chain_sha256, row_number)

        relations.append(
            CompatibilityRelation(
                source_seqcol_digest=source_seqcol_digest,
                target_seqcol_digest=target_seqcol_digest,
                relation=cast(RelationKind, relation),
                method=cast(RelationMethod, method),
                chain_resource=values["chain_resource"],
                direction=cast(RelationDirection, direction),
                source_label=values["source_label"],
                target_label=values["target_label"],
                source_url=values["source_url"],
                chain_sha256=chain_sha256,
            )
        )

    return relations


def _validate_chain_sha256(chain_sha256: str, row_number: int) -> None:
    if not chain_sha256.startswith(_SHA256_PREFIX):
        raise AssemblyCompatibilityError(f"row {row_number}: chain_sha256 must start with 'sha256:'")

    digest = chain_sha256.removeprefix(_SHA256_PREFIX)
    if len(digest) != 64:
        raise AssemblyCompatibilityError(f"row {row_number}: chain_sha256 digest must be 64 hex characters")
    if any(char not in _HEX_DIGITS for char in digest):
        raise AssemblyCompatibilityError(f"row {row_number}: chain_sha256 digest must be hexadecimal")


def relation_for(
    relations: list[CompatibilityRelation],
    *,
    source_seqcol_digest: str,
    target_seqcol_digest: str,
) -> CompatibilityRelation | None:
    matches = [
        relation
        for relation in relations
        if relation.source_seqcol_digest == source_seqcol_digest
        and relation.target_seqcol_digest == target_seqcol_digest
        and relation.relation == "liftover_possible"
    ]
    if len(matches) > 1:
        raise AssemblyCompatibilityError(
            f"multiple liftover_possible relations for {source_seqcol_digest!r} -> {target_seqcol_digest!r}"
        )
    return matches[0] if matches else None


def _validate_header(fieldnames: Sequence[str] | None) -> None:
    if tuple(fieldnames or ()) != _COLUMNS:
        raise AssemblyCompatibilityError("compatibility_relations.csv header does not match the pinned relation contract")


def load_compatibility_relations(
    *,
    dataset_id: str,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> list[CompatibilityRelation]:
    resolved = resolve(dataset_id, COMPATIBILITY_RESOURCE, commons_root=commons_root, data_root=data_root)
    with resolved.path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        _validate_header(reader.fieldnames)
        rows: list[dict[str, str]] = []
        for row_number, row in enumerate(reader, start=1):
            if None in row:
                raise AssemblyCompatibilityError(f"row {row_number}: unexpected extra CSV columns")
            rows.append(cast(dict[str, str], row))
    return parse_compatibility_rows(rows)
