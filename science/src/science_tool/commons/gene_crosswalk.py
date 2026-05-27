"""Resolver over the gene_key-keyed HGNC gene crosswalk (Pillar C, sub-phase C2).

Third instance of the reference-collection primitive (after gene-sets D and the
assembly registry C1): a ``dataset`` whose member rows are keyed by an opaque
composite ``gene_key`` ``"<taxon>|<namespace>|<id>"`` (e.g. ``9606|hgnc|HGNC:5``).
The key uses ``|`` as its field delimiter so the id field keeps its native CURIE
(``HGNC:5``) intact; **the key is opaque — never split — by everything except**
``make_gene_key`` (RCM-D6: byte-equality is identity). Taxon scoping is done with
the ``taxon`` parameter (``_HUMAN_TAXON``), never by parsing the key; multi-species
support will add an explicit ``taxon`` column rather than derive it from the key.
Pure over pinned, sha256-verified inputs (no network). The public API is
species-aware and namespace-explicit (taxon + namespace on every call; no bare
gene id, C-D1 d6). Deprecated/merged/withdrawn rows are mapped through WITH
provenance (``status`` + ``replacement_gene_key``), never silently returned as
canonical; an ambiguous input returns a distinct ``AmbiguousGeneMatch`` with no
``gene_key`` so a caller cannot misuse an unresolved identity (RCM-D6: never
collapse distinct keys). See
docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md (C-D1/§5).
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.commons.resolver import resolve

GENE_CROSSWALK_ID = "dataset:gene-crosswalk-hgnc"
GENE_CROSSWALK_RESOURCE = "crosswalk.csv"
MEMBER_KEY_COLUMN = "gene_key"
SUPPORTED_GENE_NAMESPACES = frozenset({"hgnc_id", "hgnc_symbol", "entrez", "ensembl"})

_HUMAN_TAXON = 9606  # v1 crosswalk is human-only
_VALID_STATUS = frozenset({"approved", "withdrawn", "merged", "split"})
_MULTIVALUE_SEP = ";"  # within-cell separator; NOT '|' (gene_key uses '|' internally)


class GeneCrosswalkError(ValueError):
    """A crosswalk row violates the reference-collection contract, or an
    unsupported namespace was requested (fail early; RCM-D1/D6)."""


def make_gene_key(taxon: int, hgnc_id: str) -> str:
    """Construct the opaque composite member key ``"<taxon>|hgnc|<hgnc_id>"``.

    The single canonical builder. ``hgnc_id`` keeps its native ``HGNC:`` CURIE; the
    ``|`` field delimiter never collides with it. The result is opaque downstream.
    """
    hgnc_id = hgnc_id.strip()
    if not hgnc_id.startswith("HGNC:"):
        raise GeneCrosswalkError(f"hgnc_id must be a 'HGNC:' CURIE, got {hgnc_id!r}")
    return f"{taxon}|hgnc|{hgnc_id}"


@dataclass(frozen=True, slots=True)
class CrosswalkRow:
    """One crosswalk row. Multi-value fields are already split on ';'."""

    gene_key: str
    symbol: str
    entrez_id: str
    ensembl_gene_id: str
    alias_symbol: tuple[str, ...]
    prev_symbol: tuple[str, ...]
    status: str
    replacement_gene_keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResolvedGeneMatch:
    """An input that resolves to exactly one canonical gene, with lifecycle
    provenance. ``status != 'approved'`` means the row is deprecated; follow
    ``replacement_gene_key`` explicitly (the resolver never auto-follows)."""

    gene_key: str
    symbol: str
    entrez_id: str | None
    ensembl_gene_id: str | None
    match_type: str  # how the input matched: exact | prev_symbol | alias_symbol
    status: str  # row lifecycle: approved | withdrawn | merged | split
    replacement_gene_key: str | None


@dataclass(frozen=True, slots=True)
class AmbiguousGeneMatch:
    """An input mapping to >1 candidate (a shared symbol/id, or a split entry's
    forward targets). It deliberately has NO ``gene_key``: the caller must not
    pick one (RCM-D6 — never collapse distinct identities)."""

    query: str
    candidates: tuple[str, ...]


GeneMatch = ResolvedGeneMatch | AmbiguousGeneMatch


def _split_multi(cell: str) -> tuple[str, ...]:
    return tuple(part for part in (cell or "").split(_MULTIVALUE_SEP) if part)


def _parse_crosswalk_rows(rows: Iterable[dict[str, Any]]) -> list[CrosswalkRow]:
    """Validate + parse raw CSV rows; fail early on a broken collection (RCM-D1/D6).

    Every row needs a present, non-blank, UNIQUE ``gene_key`` (a duplicate key is
    two rows claiming one identity) and a known ``status``. Pure (no I/O).
    """
    out: list[CrosswalkRow] = []
    seen: set[str] = set()
    for i, row in enumerate(rows):
        if MEMBER_KEY_COLUMN not in row:
            raise GeneCrosswalkError(f"row {i}: missing required column {MEMBER_KEY_COLUMN!r}")
        key = (row.get(MEMBER_KEY_COLUMN) or "").strip()
        if not key:
            raise GeneCrosswalkError(f"row {i}: blank {MEMBER_KEY_COLUMN} (member key)")
        if key in seen:
            raise GeneCrosswalkError(f"duplicate member key {MEMBER_KEY_COLUMN}={key!r}")
        seen.add(key)
        status = (row.get("status") or "").strip()
        if status not in _VALID_STATUS:
            raise GeneCrosswalkError(f"row {i}: invalid status {status!r} (expected one of {sorted(_VALID_STATUS)})")
        replacements = _split_multi(row.get("replacement_gene_keys", ""))
        # The lifecycle status must match its forward-pointer count, or the
        # resolver's contract breaks: a 'split' with <2 targets would silently
        # resolve as a single canonical gene instead of AmbiguousGeneMatch, and a
        # 'merged' is by definition a one-to-one redirect (RCM-D6: distinct keys
        # related with provenance, never collapsed by guesswork).
        if status == "split" and len(replacements) < 2:
            raise GeneCrosswalkError(
                f"row {i}: status 'split' requires >=2 replacement_gene_keys, got {len(replacements)}"
            )
        if status == "merged" and len(replacements) != 1:
            raise GeneCrosswalkError(
                f"row {i}: status 'merged' requires exactly 1 replacement_gene_key, got {len(replacements)}"
            )
        out.append(
            CrosswalkRow(
                gene_key=key,
                symbol=(row.get("symbol") or "").strip(),
                entrez_id=(row.get("entrez_id") or "").strip(),
                ensembl_gene_id=(row.get("ensembl_gene_id") or "").strip(),
                alias_symbol=_split_multi(row.get("alias_symbol", "")),
                prev_symbol=_split_multi(row.get("prev_symbol", "")),
                status=status,
                replacement_gene_keys=replacements,
            )
        )
    return out


def load_gene_crosswalk(
    *,
    registry_id: str = GENE_CROSSWALK_ID,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> list[CrosswalkRow]:
    """Load + sha256-verify the crosswalk rows. Raises CommonsError if absent,
    GeneCrosswalkError if a row violates the collection contract."""
    resolved = resolve(registry_id, GENE_CROSSWALK_RESOURCE, commons_root=commons_root, data_root=data_root)
    with resolved.path.open(encoding="utf-8", newline="") as fh:
        return _parse_crosswalk_rows(csv.DictReader(fh))


def available_gene_keys(
    *,
    registry_id: str = GENE_CROSSWALK_ID,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> set[str]:
    """The set of gene_key member keys for `registry_id` (used by downstream
    payload-resolution audits; check 2 does not call this)."""
    return {
        r.gene_key for r in load_gene_crosswalk(registry_id=registry_id, commons_root=commons_root, data_root=data_root)
    }


def _match_rows(rows: list[CrosswalkRow], taxon: int, namespace: str, gene_id: str) -> tuple[list[CrosswalkRow], str]:
    """Return (matched_rows, match_type). Pure; `namespace` already validated.

    The v1 crosswalk is human-only; a non-human taxon matches nothing. We gate on
    the `taxon` parameter rather than parse it out of the opaque gene_key.
    """
    if taxon != _HUMAN_TAXON:
        return [], "exact"
    if namespace == "hgnc_id":
        target = make_gene_key(taxon, gene_id)
        return [r for r in rows if r.gene_key == target], "exact"
    if namespace == "entrez":
        return [r for r in rows if r.entrez_id and r.entrez_id == gene_id], "exact"
    if namespace == "ensembl":
        return [r for r in rows if r.ensembl_gene_id and r.ensembl_gene_id == gene_id], "exact"
    # hgnc_symbol: current symbol, then prev_symbol, then alias_symbol (staged).
    by_symbol = [r for r in rows if r.symbol and r.symbol == gene_id]
    if by_symbol:
        return by_symbol, "exact"
    by_prev = [r for r in rows if gene_id in r.prev_symbol]
    if by_prev:
        return by_prev, "prev_symbol"
    return [r for r in rows if gene_id in r.alias_symbol], "alias_symbol"


def to_canonical(
    *,
    taxon: int,
    namespace: str,
    gene_id: str,
    registry_id: str = GENE_CROSSWALK_ID,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> GeneMatch | None:
    """Resolve a gene id in `namespace` to its canonical gene (RCM-D6).

    Returns ``ResolvedGeneMatch`` for a unique hit (carrying lifecycle ``status``
    + ``replacement_gene_key`` provenance), ``AmbiguousGeneMatch`` when the input
    maps to >1 candidate or to a split entry's forward targets (no ``gene_key`` —
    the caller must not guess), or ``None`` when nothing matches. Raises
    ``GeneCrosswalkError`` for an unsupported namespace (fail early). `gene_id` is
    named to avoid shadowing the ``id`` builtin (ruff A002)."""
    if namespace not in SUPPORTED_GENE_NAMESPACES:
        raise GeneCrosswalkError(
            f"unsupported gene namespace {namespace!r}; expected one of {sorted(SUPPORTED_GENE_NAMESPACES)}"
        )
    rows = load_gene_crosswalk(registry_id=registry_id, commons_root=commons_root, data_root=data_root)
    matched, match_type = _match_rows(rows, taxon, namespace, gene_id)
    if not matched:
        return None
    if len(matched) > 1:
        return AmbiguousGeneMatch(query=gene_id, candidates=tuple(sorted(r.gene_key for r in matched)))
    row = matched[0]
    if row.status == "split" and len(row.replacement_gene_keys) >= 2:
        return AmbiguousGeneMatch(query=gene_id, candidates=row.replacement_gene_keys)
    return ResolvedGeneMatch(
        gene_key=row.gene_key,
        symbol=row.symbol,
        entrez_id=row.entrez_id or None,
        ensembl_gene_id=row.ensembl_gene_id or None,
        match_type=match_type,
        status=row.status,
        replacement_gene_key=(row.replacement_gene_keys[0] if row.replacement_gene_keys else None),
    )
