"""Phase 2a: PubTator3 entity-mention seeder.

Convert PubTator3 BioC entity mentions into oa:TextQuoteSelector annotations
anchored in an existing `<citekey>.source.md`, written to the
`<citekey>.source.anno.trig` sidecar via the existing annotation machinery.

See docs/plans/2026-06-15-pubtator-seeder-phase2a-design.md.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.annotation.source_text import (
    SourcePassages,
    SourceTextError,
)
from science_tool.commons.frontmatter import raw_frontmatter

# --- BioC entity mention dataclass + parser -----------------------------------


@dataclass(frozen=True)
class BiocMention:
    """One PubTator entity mention: type, normalized id, surface text, and the
    document-global BioC char offset+length of its span."""

    pubtator_type: str
    identifier: str | None
    text: str
    offset: int
    length: int


def parse_bioc_entity_annotations(
    record: dict[str, Any],
) -> tuple[list[BiocMention], dict[str, int]]:
    """Flatten passage entity annotations into ordered rows + a drop-count map.

    Reads the same `PubTator3`/`documents` top-level shape as parse_bioc_passages.
    Returns `(mentions, dropped)` where `dropped` counts annotations skipped at parse
    time BY REASON (nothing silent — the orchestrator folds these into the report):
      - "malformed-bioc-annotation": missing/invalid `type`/`text`/`locations`/offset.
      - "multi-location-mention": a discontinuous span (len(locations) != 1) —
        out of Phase 2a scope; counted, not silently truncated to locations[0].
    Concept-id normalization happens later (concept_iri_for), not here.
    """
    dropped: Counter[str] = Counter()
    docs = record.get("PubTator3") or record.get("documents")
    if not isinstance(docs, list) or not docs:
        return [], {}
    doc = docs[0]
    if not isinstance(doc, dict):
        return [], {}
    passages = doc.get("passages")
    if not isinstance(passages, list):
        return [], {}

    mentions: list[BiocMention] = []
    for passage in passages:
        if not isinstance(passage, dict):
            continue
        anns = passage.get("annotations")
        if not isinstance(anns, list):
            continue
        for ann in anns:
            if not isinstance(ann, dict):
                dropped["malformed-bioc-annotation"] += 1
                continue
            infons = ann.get("infons")
            infons = infons if isinstance(infons, dict) else {}
            ptype = infons.get("type")
            text = ann.get("text")
            locations = ann.get("locations")
            if not isinstance(ptype, str) or not ptype or not isinstance(text, str) or not text:
                dropped["malformed-bioc-annotation"] += 1
                continue
            if not isinstance(locations, list) or not locations:
                dropped["malformed-bioc-annotation"] += 1
                continue
            if len(locations) != 1:
                dropped["multi-location-mention"] += 1
                continue
            loc = locations[0]
            if not isinstance(loc, dict):
                dropped["malformed-bioc-annotation"] += 1
                continue
            offset = loc.get("offset")
            length = loc.get("length")
            if not isinstance(offset, int) or not isinstance(length, int):
                dropped["malformed-bioc-annotation"] += 1
                continue
            identifier = infons.get("identifier")
            mentions.append(
                BiocMention(
                    pubtator_type=ptype,
                    identifier=identifier if isinstance(identifier, str) else None,
                    text=text,
                    offset=offset,
                    length=length,
                )
            )
    return mentions, dict(dropped)


# --- Entity type -> annotation_type ------------------------------------------

# PubTator BioC `infons.type` (lowercased) -> our kebab entity slug.
_TYPE_TO_ENTITY: dict[str, str] = {
    "gene": "gene",
    "disease": "disease",
    "chemical": "chemical",
    "species": "species",
    "cellline": "cellline",
    "variant": "variant",
    "mutation": "variant",
    "dnamutation": "variant",
    "proteinmutation": "variant",
    "snp": "variant",
}


def annotation_type_for(pubtator_type: str) -> str | None:
    """`entity-<slug>` for a supported PubTator type, else None (unsupported)."""
    slug = _TYPE_TO_ENTITY.get(pubtator_type.strip().lower())
    return f"entity-{slug}" if slug else None


# --- Concept identifier -> identifiers.org compact IRI ------------------------

_IDENTIFIERS_BASE = "https://identifiers.org"

_DIGITS = re.compile(r"^\d+$")
_MESH = re.compile(r"^[A-Z]\d{6,}$")  # MeSH descriptor/supplementary id: a letter + 6 or more digits (PubTator emits the canonical 6-digit form, e.g. D001943).
_RSID = re.compile(r"^rs\d+$")
_RS_HASH = re.compile(r"^RS#:(\d+)$")
_CVCL = re.compile(r"^CVCL_\w+$")


def _first_id(identifier: str | None) -> str:
    """First id of a possibly `;`-joined list, with a leading gene-namespace prefix (Gene:/NCBIGene:/Entrez:) stripped if present. MESH:/RS#: prefixes are left for the callers to handle."""
    if not identifier:
        return ""
    head = identifier.split(";")[0].strip()
    # Strip a leading source-namespace prefix PubTator sometimes prepends,
    # e.g. "Gene:672" / "NCBIGene:672". Keep "MESH:"/"RS#:" handling to callers.
    if ":" in head:
        prefix, rest = head.split(":", 1)
        if prefix.lower() in {"gene", "ncbigene", "entrez"}:
            return rest.strip()
    return head


def _compact(namespace: str, accession: str) -> str:
    return f"{_IDENTIFIERS_BASE}/{namespace}:{accession}"


def concept_iri_for(pubtator_type: str, identifier: str | None) -> str | None:
    """Build the identifiers.org concept IRI, or None if unnormalizable (skip).

    Only ids matching each namespace's expected shape are accepted; anything else
    (tmVar variant strings, OMIM disease ids, non-Cellosaurus cell lines, empty) is
    rejected so the seeder skips-and-counts rather than minting a junk anchor.
    """
    entity = _TYPE_TO_ENTITY.get(pubtator_type.strip().lower())
    if entity is None:
        return None
    raw = _first_id(identifier)
    if not raw:
        return None

    if entity == "gene":
        return _compact("ncbigene", raw) if _DIGITS.match(raw) else None
    if entity == "species":
        return _compact("taxonomy", raw) if _DIGITS.match(raw) else None
    if entity in ("disease", "chemical"):
        mesh = raw[5:] if raw.upper().startswith("MESH:") else raw
        return _compact("mesh", mesh) if _MESH.match(mesh) else None
    if entity == "variant":
        if _RSID.match(raw):
            return _compact("dbsnp", raw)
        m = _RS_HASH.match(raw)
        return _compact("dbsnp", f"rs{m.group(1)}") if m else None
    if entity == "cellline":
        return _compact("cellosaurus", raw) if _CVCL.match(raw) else None
    return None


# --- Offset-map loader + ordered passage bridge ------------------------------


@dataclass(frozen=True)
class PersistedPassage:
    """One persisted passage from `.source.md` frontmatter `passages` (render order)."""

    section: str
    file_char_base: int
    length: int


@dataclass(frozen=True)
class PairedPassage:
    """A persisted passage paired to its live BioC document offset base."""

    bioc_offset: int
    bioc_len: int
    file_char_base: int


def load_persisted_passages(source_md: Path) -> tuple[str, list[PersistedPassage]]:
    """Read `.source.md`: return (full file text, persisted passages in render order)."""
    file_text = source_md.read_text(encoding="utf-8")
    fm = raw_frontmatter(source_md)
    raw = fm.get("passages")
    if not isinstance(raw, list) or not raw:
        raise SourceTextError(
            f"{source_md} has no `passages` offset map; re-run `persist-source`."
        )
    persisted: list[PersistedPassage] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise SourceTextError(f"{source_md}: non-dict passages offset map entry {entry!r}")
        section = str(entry.get("section") or "passage")
        base = entry.get("file_char_base")
        length = entry.get("length")
        if not isinstance(base, int) or not isinstance(length, int):
            raise SourceTextError(f"{source_md}: malformed passages offset map entry {entry!r}")
        persisted.append(PersistedPassage(section=section, file_char_base=base, length=length))
    return file_text, persisted


def pair_passages(
    file_text: str,
    persisted: list[PersistedPassage],
    bioc: SourcePassages,
) -> list[PairedPassage]:
    """Pair persisted passages to live BioC offset bases by ordered occurrence.

    Iterate persisted entries in render order, advancing a single pointer through
    the BioC passage list to the next passage whose (section, text) matches the
    entry's section and file slice. Pairing is by (section, text) occurrence order:
    duplicate-text passages within the same section pair to successive BioC
    occurrences, and non-persisted BioC passages (including same-text passages
    with a different section) are skipped. A persisted passage with no remaining
    ordered match means the source text drifted -> fail loud.
    """
    paired: list[PairedPassage] = []
    j = 0
    bioc_passages = bioc.passages
    for e in persisted:
        slice_ = file_text[e.file_char_base : e.file_char_base + e.length]
        while j < len(bioc_passages) and not (
            bioc_passages[j].text == slice_ and bioc_passages[j].section == e.section
        ):
            j += 1
        if j >= len(bioc_passages):
            raise SourceTextError(
                f"persisted passage at {e.file_char_base} (section {e.section!r}) "
                "not found in re-fetched BioC (source text drift); re-run persist-source"
            )
        p = bioc_passages[j]
        paired.append(
            PairedPassage(bioc_offset=p.bioc_offset, bioc_len=e.length, file_char_base=e.file_char_base)
        )
        j += 1
    return paired
