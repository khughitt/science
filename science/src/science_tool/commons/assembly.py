"""Resolver over the seqcol-keyed assembly registry (C-D2, second primitive instance).

Pure over pinned, sha256-verified inputs (no network): reads the registry's
data resource through the commons resolver and exposes the seqcol-digest key
set + a label/digest lookup. Exact ``seqcol_digest`` equality is identity
(RCM-D6); ``label`` is an advisory alias. See
docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md (C-D2).
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
    accession: str


def _parse_registry_rows(rows: Iterable[dict[str, Any]]) -> list[AssemblyEntry]:
    """Validate + parse raw CSV rows into entries; fail early on a broken collection.

    A keyed reference collection must have a present, non-blank member key on
    every row and **unique** member keys (RCM-D6: exact equality is identity, so
    a duplicate key is two rows claiming one identity). Pure (no I/O) so it is
    unit-testable with in-memory dicts.
    """
    entries: list[AssemblyEntry] = []
    seen: set[str] = set()
    for i, row in enumerate(rows):
        if "seqcol_digest" not in row:
            raise AssemblyRegistryError(f"row {i}: missing required column 'seqcol_digest'")
        digest = (row.get("seqcol_digest") or "").strip()
        if not digest:
            raise AssemblyRegistryError(f"row {i}: blank seqcol_digest (member key)")
        if digest in seen:
            raise AssemblyRegistryError(f"duplicate member key seqcol_digest={digest!r}")
        seen.add(digest)
        entries.append(
            AssemblyEntry(
                seqcol_digest=digest,
                label=(row.get("label") or "").strip(),
                accession=(row.get("accession") or "").strip(),
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
    return label_matches[0] if len(label_matches) == 1 else None
