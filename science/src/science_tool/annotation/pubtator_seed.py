"""Phase 2a: PubTator3 entity-mention seeder.

Convert PubTator3 BioC entity mentions into oa:TextQuoteSelector annotations
anchored in an existing `<citekey>.source.md`, written to the
`<citekey>.source.anno.trig` sidecar via the existing annotation machinery.

See docs/plans/2026-06-15-pubtator-seeder-phase2a-design.md.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from science_tool.annotation.audit import merge_planned
from science_tool.annotation.io import (
    atomic_write_text,
    read_sidecar,
    serialize_sidecar,
    sidecar_for_markdown,
)
from science_tool.annotation.model import (
    IriBody,
    Motivation,
    Sidecar,
    SpecificResource,
    TextQuoteSelector,
)
from science_tool.annotation.source_text import (
    PUBTATOR3_API_VERSION,
    SourcePassages,
    SourceTextError,
    fetch_bioc_record,
    normalize_doi,
    normalize_pmid,
    parse_bioc_passages,
    resolve_paper_entity,
)
from science_tool.annotation.sources.base import PlannedAnnotation
from science_tool.commons.frontmatter import raw_frontmatter
from science_tool.paper_fetch import FetchConfig, RateLimiter

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


@dataclass(frozen=True)
class BiocRelation:
    """One PubTator document-level relation: subject/object concept (type+id),
    predicate type, and optional model confidence."""

    subject_type: str
    subject_id: str
    object_type: str
    object_id: str
    rel_type: str
    score: float | None


def _parse_score(raw: Any) -> float | None:
    """PubTator stores `infons.score` as a stringified float; non-numeric -> None."""
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    if isinstance(raw, str):
        try:
            return float(raw)
        except ValueError:
            return None
    return None


def parse_bioc_relations(
    record: dict[str, Any],
) -> tuple[list[BiocRelation], dict[str, int]]:
    """Flatten the document-level `relations` into ordered rows + a drop-count map.

    Returns `(relations, dropped)`. A relation missing/invalid `role1`/`role2`/`type`
    (or non-dict) is counted under "malformed-bioc-relation" (nothing silent); the
    orchestrator folds this into the report's relation skips.
    """
    dropped: Counter[str] = Counter()
    docs = record.get("PubTator3") or record.get("documents")
    if not isinstance(docs, list) or not docs:
        return [], {}
    doc = docs[0]
    if not isinstance(doc, dict):
        return [], {}
    raw_rels = doc.get("relations")
    if not isinstance(raw_rels, list):
        return [], {}

    relations: list[BiocRelation] = []
    for rel in raw_rels:
        if not isinstance(rel, dict):
            dropped["malformed-bioc-relation"] += 1
            continue
        infons = rel.get("infons")
        infons = infons if isinstance(infons, dict) else {}
        role1, role2 = infons.get("role1"), infons.get("role2")
        rtype = infons.get("type")
        if not isinstance(role1, dict) or not isinstance(role2, dict) or not isinstance(rtype, str) or not rtype:
            dropped["malformed-bioc-relation"] += 1
            continue
        s_type, s_id = role1.get("type"), role1.get("identifier")
        o_type, o_id = role2.get("type"), role2.get("identifier")
        if not (isinstance(s_type, str) and isinstance(s_id, str) and isinstance(o_type, str) and isinstance(o_id, str)):
            dropped["malformed-bioc-relation"] += 1
            continue
        relations.append(
            BiocRelation(
                subject_type=s_type,
                subject_id=s_id,
                object_type=o_type,
                object_id=o_id,
                rel_type=rtype,
                score=_parse_score(infons.get("score")),
            )
        )
    return relations, dict(dropped)


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


# --- Relation type -> predicate CURIE ----------------------------------------

# PubTator3 uses the fixed BioRED 8-type relation set. Clean Biolink predicate where
# one exists, else a `sci:` project predicate. Keys are matched case-insensitively
# (lowercased). See docs/conventions/annotation-tokens.md.
RELATION_PREDICATES: dict[str, tuple[str, str]] = {
    "association": ("biolink:associated_with", "biolink"),
    "positive_correlation": ("biolink:positively_correlated_with", "biolink"),
    "negative_correlation": ("biolink:negatively_correlated_with", "biolink"),
    "bind": ("biolink:directly_physically_interacts_with", "biolink"),
    "drug_interaction": ("biolink:interacts_with", "biolink"),
    "cotreatment": ("sci:cotreatment", "sci"),
    "comparison": ("sci:comparison", "sci"),
    "conversion": ("sci:conversion", "sci"),
}

_PRED_SLUG_BAD = re.compile(r"[^a-z0-9_]")


def predicate_for(rel_type: str) -> tuple[str, str, str | None]:
    """Map a PubTator relation type to (predicate_curie, predicate_source, raw_or_None).

    Known BioRED types return (curie, "biolink"|"sci", None). An unexpected type is
    NOT dropped: it returns ("sci:pubtator_<slug>", "sci", <verbatim raw type>) where
    <slug> lowercases the raw type and replaces every non-[a-z0-9_] char with "_", so
    the data is preserved without pretending it is a curated project predicate.
    """
    mapped = RELATION_PREDICATES.get(rel_type.strip().lower())
    if mapped is not None:
        return mapped[0], mapped[1], None
    slug = _PRED_SLUG_BAD.sub("_", rel_type.strip().lower())
    return f"sci:pubtator_{slug}", "sci", rel_type


def relation_body_json(
    *,
    subject_iri: str,
    object_iri: str,
    predicate: str,
    predicate_source: str,
    raw_predicate_type: str | None,
    score: float | None,
) -> str:
    """Build the deterministic JSON for a relation's TextualBody.

    Always carries subject / predicate / object / predicate_source. `raw_predicate_type`
    is included only for unmapped types; `score` only when PubTator supplied a numeric
    confidence. Serialized with sorted keys + compact separators so re-runs are
    byte-stable (stable content_hash, no sidecar churn).
    """
    obj: dict[str, Any] = {
        "subject": subject_iri,
        "predicate": predicate,
        "object": object_iri,
        "predicate_source": predicate_source,
    }
    if raw_predicate_type is not None:
        obj["raw_predicate_type"] = raw_predicate_type
    if score is not None:
        obj["score"] = score
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


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


# --- Mention -> PlannedAnnotation conversion ----------------------------------

# Prefix/suffix context window (chars), clamped to the passage bounds.
_CONTEXT = 60


def _containing(paired: list[PairedPassage], offset: int, length: int) -> PairedPassage | None:
    end = offset + length
    for pp in paired:
        if pp.bioc_offset <= offset and end <= pp.bioc_offset + pp.bioc_len:
            return pp
    return None


def plan_mention(
    file_text: str,
    paired: list[PairedPassage],
    mention: BiocMention,
    *,
    release: str,
    source_md_name: str,
) -> tuple[PlannedAnnotation | None, str | None]:
    """Convert a BiocMention to a PlannedAnnotation, or (None, skip_reason).

    Skip reasons: "unsupported-type", "non-persisted-passage", "unnormalized-concept".
    A mention whose mapped file slice does not equal its reported text is a hard
    SourceTextError (never a silently mis-placed anchor).
    """
    annotation_type = annotation_type_for(mention.pubtator_type)
    if annotation_type is None:
        return None, "unsupported-type"

    pp = _containing(paired, mention.offset, mention.length)
    if pp is None:
        return None, "non-persisted-passage"

    concept_iri = concept_iri_for(mention.pubtator_type, mention.identifier)
    if concept_iri is None:
        return None, "unnormalized-concept"

    file_idx = pp.file_char_base + (mention.offset - pp.bioc_offset)
    exact = file_text[file_idx : file_idx + mention.length]
    if exact != mention.text:
        raise SourceTextError(
            f"offset slice {exact!r} != BioC mention text {mention.text!r} "
            f"at file index {file_idx} (offset drift); aborting"
        )

    passage_start = pp.file_char_base
    passage_end = pp.file_char_base + pp.bioc_len
    prefix_start = max(passage_start, file_idx - _CONTEXT)
    suffix_end = min(passage_end, file_idx + mention.length + _CONTEXT)
    selector = TextQuoteSelector(
        exact=exact,
        prefix=file_text[prefix_start:file_idx],
        suffix=file_text[file_idx + mention.length : suffix_end],
    )

    match_text = f"{annotation_type}|{concept_iri}|{file_idx}:{mention.length}|{exact}"
    planned = PlannedAnnotation(
        target=SpecificResource(source=source_md_name, selector=selector),
        annotation_type=annotation_type,
        motivation=Motivation.IDENTIFYING,
        body=IriBody(iri=concept_iri),
        match_text=match_text,
        source_name=f"pubtator3:{release}:seeder-v1",
    )
    return planned, None


# --- Orchestrator -------------------------------------------------------------


@dataclass(frozen=True)
class SeedReport:
    entity_written: int
    entity_skipped: dict[str, int]
    relation_written: int
    relation_skipped: dict[str, int]
    note: str | None = None


def seed_pubtator(
    *,
    project_root: Path,
    identifier: str,
    cfg: FetchConfig,
    actor: str,
    now: datetime,
    http: httpx.Client | None = None,
) -> SeedReport:
    """Seed PubTator3 entity-mention annotations into `<citekey>.source.anno.trig`.

    Requires an existing `<citekey>.source.md` (fail loud otherwise). Re-fetches the
    raw BioC record for the entity's PMID, converts each entity mention, and merges
    the planned rows idempotently. PubMed-only: no PMID / no BioC record -> no-op.
    """
    doi = normalize_doi(identifier)
    pmid = None if doi else normalize_pmid(identifier)
    resolved = resolve_paper_entity(project_root, doi=doi, pmid=pmid)

    source_md = resolved.directory / f"{resolved.citekey}.source.md"
    if not source_md.is_file():
        raise SourceTextError(
            f"{source_md} not found; run `science paper persist-source {identifier}` first."
        )
    file_text, persisted = load_persisted_passages(source_md)

    skipped: Counter[str] = Counter()
    if not resolved.pmid:
        return SeedReport(entity_written=0, entity_skipped={}, relation_written=0, relation_skipped={}, note="no PMID; PubTator3 is PubMed-only")

    owns = http is None
    client = http or httpx.Client(
        timeout=cfg.http_timeout, headers={"User-Agent": f"science/0.1 (mailto:{cfg.email})"}
    )
    try:
        limiter = RateLimiter(cfg)
        record, err = fetch_bioc_record(resolved.pmid, client, limiter, cfg)
    finally:
        if owns:
            client.close()

    if not record:
        return SeedReport(entity_written=0, entity_skipped={}, relation_written=0, relation_skipped={}, note=f"no PubTator3 record ({err or 'no record'})")

    parsed = parse_bioc_passages(record)
    if parsed is None:
        return SeedReport(entity_written=0, entity_skipped={}, relation_written=0, relation_skipped={}, note="PubTator3 record had no usable passages")

    release = parsed.release or PUBTATOR3_API_VERSION
    paired = pair_passages(file_text, persisted, parsed)
    mentions, parse_drops = parse_bioc_entity_annotations(record)
    skipped.update(parse_drops)  # malformed-bioc / multi-location surfaced, not silent

    planned = []
    for m in mentions:
        p, reason = plan_mention(
            file_text, paired, m, release=release, source_md_name=source_md.name
        )
        if p is not None:
            planned.append(p)
        elif reason is not None:
            skipped[reason] += 1

    sidecar_path = sidecar_for_markdown(source_md)
    sidecar = read_sidecar(sidecar_path) if sidecar_path.exists() else Sidecar()
    new_sidecar, written = merge_planned(sidecar, planned, actor=actor, now=now)
    if written:
        atomic_write_text(sidecar_path, serialize_sidecar(new_sidecar))

    return SeedReport(
        entity_written=len(written),
        entity_skipped=dict(skipped),
        relation_written=0,
        relation_skipped={},
        note=None,
    )
