"""Resolver over the protein_key-keyed UniProt protein crosswalk (Pillar C, sub-phase C3).

Fourth instance of the reference-collection primitive (after gene-sets D, the
assembly registry C1, and the gene crosswalk C2): a ``dataset`` whose member rows
are keyed by an opaque composite ``protein_key`` ``"<taxon>|uniprot|<accession>"``
(e.g. ``9606|uniprot|P04217``). The key uses ``|`` as its field delimiter; UniProt
accessions are ``[A-Z0-9]`` only, so the delimiter never collides. **The key is
opaque — never split — by everything except** ``make_protein_key`` (RCM-D6:
byte-equality is identity). Taxon scoping uses the ``taxon`` parameter
(``_HUMAN_TAXON``), never by parsing the key. Pure over pinned, sha256-verified
inputs (no network). The public API is species-aware and namespace-explicit
(taxon + namespace on every call; C-D1). An **isoform** input (``P12345-2``)
surfaces the canonical member with ``match_type='isoform'`` and the queried isoform
preserved (decision d5: isoforms are a distinct lower-level identity, NOT
collapsed). A **merged** secondary accession surfaces ``status='merged'`` +
``replacement_protein_key`` (never auto-followed). An ambiguous input returns a
distinct ``AmbiguousProteinMatch`` with no ``protein_key``. Each row carries the
C2 ``gene_key`` (protein->gene join pointer). See
docs/plans/historical/2026-05-26-bio-identity-and-reference-genome-design.md (C-D1/§8 C3).
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.commons.resolver import resolve

PROTEIN_CROSSWALK_ID = "dataset:protein-crosswalk-uniprot"
PROTEIN_CROSSWALK_RESOURCE = "crosswalk.csv"
MEMBER_KEY_COLUMN = "protein_key"
SUPPORTED_PROTEIN_NAMESPACES = frozenset({"uniprot", "uniprot_entry_name", "ensembl_protein", "refseq_protein"})

_HUMAN_TAXON = 9606  # v1 crosswalk is human-only
_VALID_STATUS = frozenset({"approved", "merged"})
_MULTIVALUE_SEP = ";"  # within-cell separator; NOT '|' (protein_key uses '|' internally)


class ProteinCrosswalkError(ValueError):
    """A crosswalk row violates the reference-collection contract, or an
    unsupported namespace/accession was requested (fail early; RCM-D1/D6)."""


def make_protein_key(taxon: int, accession: str) -> str:
    """Construct the opaque composite member key ``"<taxon>|uniprot|<accession>"``.

    The single canonical builder. ``accession`` must be a non-blank UniProt
    accession (no ``|``, which is the field delimiter). The result is opaque
    downstream. Isoform-suffixed inputs (``P12345-2``) are NOT keys: the resolver
    strips the suffix before building the canonical key.
    """
    accession = accession.strip()
    if not accession or "|" in accession:
        raise ProteinCrosswalkError(f"invalid UniProt accession {accession!r}")
    return f"{taxon}|uniprot|{accession}"


@dataclass(frozen=True, slots=True)
class CrosswalkRow:
    """One crosswalk row. Multi-value fields are already split on ';'."""

    protein_key: str
    entry_name: str
    ensembl_protein: tuple[str, ...]
    refseq_protein: tuple[str, ...]
    gene_key: tuple[str, ...]
    status: str
    replacement_protein_keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResolvedProteinMatch:
    """An input that resolves to exactly one canonical protein, with provenance.

    ``status == 'merged'`` means the matched row is a deprecated secondary
    accession; follow ``replacement_protein_key`` explicitly (never auto-followed).
    ``match_type == 'isoform'`` means an isoform accession was queried; ``isoform``
    holds it and ``protein_key`` is the canonical (not collapsed — both surfaced).
    """

    protein_key: str
    entry_name: str
    ensembl_protein: tuple[str, ...]
    refseq_protein: tuple[str, ...]
    gene_key: tuple[str, ...]
    match_type: str  # exact | entry_name | ensembl_protein | refseq_protein | isoform
    isoform: str | None  # the queried isoform accession when match_type == 'isoform', else None
    status: str  # row lifecycle: approved | merged
    replacement_protein_key: str | None


@dataclass(frozen=True, slots=True)
class AmbiguousProteinMatch:
    """An input mapping to >1 candidate (e.g. a RefSeq/Ensembl-protein id shared by
    >1 UniProt entry). It deliberately has NO ``protein_key``: the caller must not
    pick one (RCM-D6 — never collapse distinct identities)."""

    query: str
    candidates: tuple[str, ...]


ProteinMatch = ResolvedProteinMatch | AmbiguousProteinMatch


def _split_multi(cell: str) -> tuple[str, ...]:
    return tuple(part for part in (cell or "").split(_MULTIVALUE_SEP) if part)


def _parse_crosswalk_rows(rows: Iterable[dict[str, Any]]) -> list[CrosswalkRow]:
    """Validate + parse raw CSV rows; fail early on a broken collection (RCM-D1/D6).

    Every row needs a present, non-blank, UNIQUE ``protein_key`` and a known
    ``status``. A ``merged`` row must carry exactly one replacement (a secondary
    accession is a one-to-one redirect). Pure (no I/O).
    """
    out: list[CrosswalkRow] = []
    seen: set[str] = set()
    for i, row in enumerate(rows):
        if MEMBER_KEY_COLUMN not in row:
            raise ProteinCrosswalkError(f"row {i}: missing required column {MEMBER_KEY_COLUMN!r}")
        key = (row.get(MEMBER_KEY_COLUMN) or "").strip()
        if not key:
            raise ProteinCrosswalkError(f"row {i}: blank {MEMBER_KEY_COLUMN} (member key)")
        if key in seen:
            raise ProteinCrosswalkError(f"duplicate member key {MEMBER_KEY_COLUMN}={key!r}")
        seen.add(key)
        status = (row.get("status") or "").strip()
        if status not in _VALID_STATUS:
            raise ProteinCrosswalkError(f"row {i}: invalid status {status!r} (expected one of {sorted(_VALID_STATUS)})")
        replacements = _split_multi(row.get("replacement_protein_keys", ""))
        if status == "merged" and len(replacements) != 1:
            raise ProteinCrosswalkError(
                f"row {i}: status 'merged' requires exactly 1 replacement_protein_key, got {len(replacements)}"
            )
        out.append(
            CrosswalkRow(
                protein_key=key,
                entry_name=(row.get("entry_name") or "").strip(),
                ensembl_protein=_split_multi(row.get("ensembl_protein", "")),
                refseq_protein=_split_multi(row.get("refseq_protein", "")),
                gene_key=_split_multi(row.get("gene_key", "")),
                status=status,
                replacement_protein_keys=replacements,
            )
        )
    return out


def load_protein_crosswalk(
    *,
    registry_id: str = PROTEIN_CROSSWALK_ID,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> list[CrosswalkRow]:
    """Load + sha256-verify the crosswalk rows. Raises CommonsError if absent,
    ProteinCrosswalkError if a row violates the collection contract."""
    resolved = resolve(registry_id, PROTEIN_CROSSWALK_RESOURCE, commons_root=commons_root, data_root=data_root)
    with resolved.path.open(encoding="utf-8", newline="") as fh:
        return _parse_crosswalk_rows(csv.DictReader(fh))


def available_protein_keys(
    *,
    registry_id: str = PROTEIN_CROSSWALK_ID,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> set[str]:
    """The set of protein_key member keys for `registry_id` (used by downstream
    payload-resolution audits; the validate check does not call this)."""
    return {
        r.protein_key
        for r in load_protein_crosswalk(registry_id=registry_id, commons_root=commons_root, data_root=data_root)
    }


def _match_rows(
    rows: list[CrosswalkRow], taxon: int, namespace: str, protein_id: str
) -> tuple[list[CrosswalkRow], str, str | None]:
    """Return (matched_rows, match_type, isoform). Pure; `namespace` already validated.

    The v1 crosswalk is human-only; a non-human taxon matches nothing. We gate on
    the `taxon` parameter rather than parse it out of the opaque protein_key.
    """
    if taxon != _HUMAN_TAXON:
        return [], "exact", None
    if namespace == "uniprot":
        if "-" in protein_id:  # isoform accession, e.g. P12345-2
            canonical = protein_id.split("-", 1)[0]
            target = make_protein_key(taxon, canonical)
            return [r for r in rows if r.protein_key == target], "isoform", protein_id
        target = make_protein_key(taxon, protein_id)
        return [r for r in rows if r.protein_key == target], "exact", None
    if namespace == "uniprot_entry_name":
        return [r for r in rows if r.entry_name and r.entry_name == protein_id], "entry_name", None
    if namespace == "ensembl_protein":
        return [r for r in rows if protein_id in r.ensembl_protein], "ensembl_protein", None
    # refseq_protein
    return [r for r in rows if protein_id in r.refseq_protein], "refseq_protein", None


def to_canonical(
    *,
    taxon: int,
    namespace: str,
    protein_id: str,
    registry_id: str = PROTEIN_CROSSWALK_ID,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> ProteinMatch | None:
    """Resolve a protein id in `namespace` to its canonical protein (RCM-D6).

    Returns ``ResolvedProteinMatch`` for a unique hit (carrying ``status`` +
    ``replacement_protein_key`` + ``isoform`` provenance and the ``gene_key``
    join), ``AmbiguousProteinMatch`` when the input maps to >1 candidate (no
    ``protein_key`` — the caller must not guess), or ``None`` when nothing matches.
    Raises ``ProteinCrosswalkError`` for an unsupported namespace (fail early).
    `protein_id` is named to avoid shadowing the ``id`` builtin (ruff A002)."""
    if namespace not in SUPPORTED_PROTEIN_NAMESPACES:
        raise ProteinCrosswalkError(
            f"unsupported protein namespace {namespace!r}; expected one of {sorted(SUPPORTED_PROTEIN_NAMESPACES)}"
        )
    rows = load_protein_crosswalk(registry_id=registry_id, commons_root=commons_root, data_root=data_root)
    matched, match_type, isoform = _match_rows(rows, taxon, namespace, protein_id)
    if not matched:
        return None
    if len(matched) > 1:
        return AmbiguousProteinMatch(query=protein_id, candidates=tuple(sorted(r.protein_key for r in matched)))
    row = matched[0]
    return ResolvedProteinMatch(
        protein_key=row.protein_key,
        entry_name=row.entry_name,
        ensembl_protein=row.ensembl_protein,
        refseq_protein=row.refseq_protein,
        gene_key=row.gene_key,
        match_type=match_type,
        isoform=isoform,
        status=row.status,
        replacement_protein_key=(row.replacement_protein_keys[0] if row.replacement_protein_keys else None),
    )
