"""Resolver over the seqcol-keyed assembly registry (C-D2, second primitive instance).

Pure over pinned, sha256-verified inputs (no network): reads the registry's
data resource through the commons resolver and exposes the seqcol-digest key
set + a label/digest lookup. Exact ``seqcol_digest`` equality is identity
(RCM-D6); ``label`` is an advisory alias. See
docs/plans/historical/2026-05-26-bio-identity-and-reference-genome-design.md (C-D2).
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.commons.resolver import resolve

ASSEMBLY_REGISTRY_ID = "dataset:assembly-registry"
ASSEMBLY_RESOURCE = "assemblies.csv"


class AssemblyRegistryError(ValueError):
    """A registry row violates the reference-collection contract (RCM-D1/D6)."""


@dataclass(frozen=True, slots=True)
class AssemblyEntry:
    """One registry row: the seqcol digest (member key) + advisory aliases."""

    seqcol_digest: str
    label: str
    aliases: tuple[str, ...] = ()
    accession: str = ""
    n_sequences: int | None = None
    naming: str = ""
    source_collection_url: str = ""
    source_url: str = ""


def _optional_clean_text(row: dict[str, Any], column: str) -> str:
    raw = row.get(column)
    if raw is None:
        return ""
    return str(raw).strip()


def _parse_aliases(raw: Any, *, row_index: int) -> tuple[str, ...]:
    if raw is None:
        return ()
    text = str(raw).strip()
    if not text:
        return ()

    aliases: list[str] = []
    seen: set[str] = set()
    for part in text.split("|"):
        alias = part.strip()
        if not alias:
            raise AssemblyRegistryError(f"row {row_index}: blank assembly alias")
        if alias in seen:
            raise AssemblyRegistryError(f"row {row_index}: duplicate assembly alias {alias!r}")
        seen.add(alias)
        aliases.append(alias)
    return tuple(aliases)


def _parse_optional_positive_int(raw: Any, *, row_index: int, column: str) -> int | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if not text.isdecimal():
        raise AssemblyRegistryError(f"row {row_index}: invalid {column}: expected positive decimal integer")
    value = int(text)
    if value <= 0:
        raise AssemblyRegistryError(f"row {row_index}: invalid {column}: expected positive decimal integer")
    return value


def _parse_registry_rows(rows: Iterable[dict[str, Any]]) -> list[AssemblyEntry]:
    """Validate + parse raw CSV rows into entries; fail early on a broken collection.

    A keyed reference collection must have a present, non-blank member key on
    every row and **unique** member keys (RCM-D6: exact equality is identity, so
    a duplicate key is two rows claiming one identity). Pure (no I/O) so it is
    unit-testable with in-memory dicts.
    """
    entries: list[AssemblyEntry] = []
    seen_digests: set[str] = set()
    seen_labels: dict[str, int] = {}
    seen_aliases: dict[str, int] = {}
    for i, row in enumerate(rows):
        if "seqcol_digest" not in row:
            raise AssemblyRegistryError(f"row {i}: missing required column 'seqcol_digest'")
        digest = _optional_clean_text(row, "seqcol_digest")
        if not digest:
            raise AssemblyRegistryError(f"row {i}: blank seqcol_digest (member key)")
        if digest in seen_digests:
            raise AssemblyRegistryError(f"duplicate member key seqcol_digest={digest!r}")
        seen_digests.add(digest)

        label = _optional_clean_text(row, "label")
        aliases = _parse_aliases(row.get("aliases"), row_index=i)
        if label and label in aliases:
            raise AssemblyRegistryError(f"row {i}: duplicate assembly label or alias {label!r}")
        if label and label in seen_labels:
            raise AssemblyRegistryError(f"duplicate assembly label {label!r}")
        if label and label in seen_aliases:
            raise AssemblyRegistryError(f"duplicate assembly label or alias {label!r}")

        for alias in aliases:
            if alias in seen_labels:
                raise AssemblyRegistryError(f"duplicate assembly label or alias {alias!r}")
            if alias in seen_aliases:
                raise AssemblyRegistryError(f"duplicate assembly alias {alias!r}")

        if label:
            seen_labels[label] = i
        for alias in aliases:
            seen_aliases[alias] = i

        entries.append(
            AssemblyEntry(
                seqcol_digest=digest,
                label=label,
                aliases=aliases,
                accession=_optional_clean_text(row, "accession"),
                n_sequences=_parse_optional_positive_int(row.get("n_sequences"), row_index=i, column="n_sequences"),
                naming=_optional_clean_text(row, "naming"),
                source_collection_url=_optional_clean_text(row, "source_collection_url"),
                source_url=_optional_clean_text(row, "source_url"),
            )
        )
    return entries


def load_assembly_registry(
    *,
    registry_id: str = ASSEMBLY_REGISTRY_ID,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> list[AssemblyEntry]:
    """Load + sha256-verify the registry rows. Raises CommonsError if absent,
    AssemblyRegistryError if a row violates the collection contract."""
    resolved = resolve(registry_id, ASSEMBLY_RESOURCE, commons_root=commons_root, data_root=data_root)
    with resolved.path.open(encoding="utf-8", newline="") as fh:
        return _parse_registry_rows(csv.DictReader(fh))


def available_assembly_keys(
    *,
    registry_id: str = ASSEMBLY_REGISTRY_ID,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> set[str]:
    """The set of seqcol-digest member keys for `registry_id` — the `available_keys`
    fed to `evaluate_key_resolution` (RCM-D2). The caller passes the registry id
    declared on the dataset; there is no hard-coded default fallback in the check."""
    return {
        e.seqcol_digest
        for e in load_assembly_registry(registry_id=registry_id, commons_root=commons_root, data_root=data_root)
    }


def resolve_assembly(
    label_or_digest: str,
    *,
    registry_id: str = ASSEMBLY_REGISTRY_ID,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> AssemblyEntry | None:
    """Resolve a seqcol digest (exact equality, RCM-D6) or an advisory label alias."""
    entries = load_assembly_registry(registry_id=registry_id, commons_root=commons_root, data_root=data_root)
    for entry in entries:
        if entry.seqcol_digest == label_or_digest:
            return entry
    label_matches = [e for e in entries if e.label and e.label == label_or_digest]
    if len(label_matches) == 1:
        return label_matches[0]
    if len(label_matches) > 1:
        raise AssemblyRegistryError(f"duplicate assembly label {label_or_digest!r}")

    alias_matches = [e for e in entries if label_or_digest in e.aliases]
    if len(alias_matches) == 1:
        return alias_matches[0]
    if len(alias_matches) > 1:
        raise AssemblyRegistryError(f"duplicate assembly alias {label_or_digest!r}")
    return None
