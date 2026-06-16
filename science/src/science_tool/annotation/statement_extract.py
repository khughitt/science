"""Phase 3a: agent statement-extraction persistence.

Turn an LLM agent's candidate proposition/question/hypothesis spans into
oa:TextQuoteSelector annotations anchored in an existing `<citekey>.source.md`,
written to its `.source.anno.trig` sidecar via the existing annotation machinery.
The agent decides; this module owns anchoring, section derivation, grounding
verification, dedup, and document-level idempotency.

See docs/plans/2026-06-15-paper-annotate-phase3a-design.md.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from science_tool.annotation.audit import merge_planned
from science_tool.annotation.io import (
    atomic_write_text,
    read_sidecar,
    serialize_sidecar,
    sidecar_for_markdown,
)
from science_tool.annotation.ledger import (
    find_or_create_ledger,
    ledger_set_source_text_hash,
)
from science_tool.annotation.model import (
    IriBody,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.pubtator_seed import (
    PersistedPassage,
    load_persisted_passages,
    _CONTEXT,
)
from science_tool.annotation.source_text import SourceTextError
from science_tool.annotation.sources.base import PlannedAnnotation
from science_tool.commons.frontmatter import raw_frontmatter

# --- Section normalization ----------------------------------------------------

CANONICAL_SECTIONS: frozenset[str] = frozenset({
    "title", "abstract", "introduction", "methods", "results",
    "discussion", "conclusion", "figure", "table", "other",
})

# Raw BioC `infons.type` (lowercased) -> canonical section. Anything absent -> "other".
_SECTION_NORMALIZE: dict[str, str] = {
    "title": "title",
    "abstract": "abstract",
    "intro": "introduction",
    "introduction": "introduction",
    "methods": "methods",
    "method": "methods",
    "materials and methods": "methods",
    "results": "results",
    "result": "results",
    "discuss": "discussion",
    "discussion": "discussion",
    "concl": "conclusion",
    "conclusion": "conclusion",
    "conclusions": "conclusion",
    "fig": "figure",
    "figure": "figure",
    "table": "table",
}


def normalize_section(raw: str) -> str:
    """Map a raw `.source.md` passage section to the closed canonical vocabulary."""
    return _SECTION_NORMALIZE.get(raw.strip().lower(), "other")


def _containing_passage(
    persisted: list[PersistedPassage], file_idx: int, length: int
) -> PersistedPassage | None:
    """The persisted passage wholly containing [file_idx, file_idx+length), or None.

    None means the span anchored outside every passage body (e.g. a heading or
    frontmatter) or straddles a passage boundary — the caller skips it.
    """
    end = file_idx + length
    for pp in persisted:
        if pp.file_char_base <= file_idx and end <= pp.file_char_base + pp.length:
            return pp
    return None


# --- Candidate parsing (strict, fail-loud) ------------------------------------

STATEMENT_TYPES: frozenset[str] = frozenset({"proposition", "question", "hypothesis"})
FIGURATIVE_TYPES: frozenset[str] = frozenset({"metaphor", "analogy"})
STANCES: frozenset[str] = frozenset({"asserted", "negated", "hypothesized", "open"})
MAX_CANDIDATES = 500
MAX_FIELD_CHARS = 2000

_STATEMENT_ALLOWED_KEYS = frozenset({
    "type", "exact", "prefix", "suffix", "stance",
    "subject", "object", "subject_concept", "object_concept",
})
_STATEMENT_REQUIRED_KEYS = frozenset({"type", "exact", "prefix", "suffix", "stance"})

_FIGURATIVE_ALLOWED_KEYS = frozenset({
    "type", "exact", "prefix", "suffix",
    "source_domain", "target_domain", "mapping", "cue",
})
_FIGURATIVE_REQUIRED_KEYS = frozenset({
    "type", "exact", "prefix", "suffix", "source_domain", "target_domain",
})


class CandidateError(ValueError):
    """A candidates.json file that is structurally invalid. Fail loud; write nothing."""


@dataclass(frozen=True)
class StatementCandidate:
    type: str
    exact: str
    prefix: str
    suffix: str
    stance: str
    subject: str | None = None
    object: str | None = None
    subject_concept: str | None = None
    object_concept: str | None = None


@dataclass(frozen=True)
class FigurativeCandidate:
    type: str
    exact: str
    prefix: str
    suffix: str
    source_domain: str
    target_domain: str
    mapping: str | None = None
    cue: str | None = None


def _field_len_ok(idx: int, name: str, val: str) -> str:
    if len(val) > MAX_FIELD_CHARS:
        raise CandidateError(f"candidate[{idx}].{name} exceeds {MAX_FIELD_CHARS} chars")
    return val


def _req_str(item: dict[str, Any], idx: int, name: str) -> str:
    val = item[name]
    if not isinstance(val, str):
        raise CandidateError(f"candidate[{idx}].{name} must be a string")
    return _field_len_ok(idx, name, val)


def _opt_str(item: dict[str, Any], idx: int, name: str) -> str | None:
    if name not in item or item[name] is None:
        return None
    val = item[name]
    if not isinstance(val, str):
        raise CandidateError(f"candidate[{idx}].{name} must be a string or null")
    return _field_len_ok(idx, name, val)


def _req_nonblank(item: dict[str, Any], idx: int, name: str) -> str:
    """A required figurative content field: string, in-bounds, non-empty after trim. Stored trimmed."""
    s = _req_str(item, idx, name).strip()
    if not s:
        raise CandidateError(f"candidate[{idx}].{name} must be non-empty")
    return s


def _opt_nonblank(item: dict[str, Any], idx: int, name: str) -> str | None:
    """An optional figurative content field: omit, or string non-empty after trim. Stored trimmed.

    A present-but-blank optional is a defect (a low-value placeholder), not 'absent' — fail loud.
    """
    if name not in item or item[name] is None:
        return None
    s = _req_str(item, idx, name).strip()
    if not s:
        raise CandidateError(f"candidate[{idx}].{name} must be non-empty when present (omit it instead)")
    return s


def parse_candidates(raw: str) -> list[StatementCandidate | FigurativeCandidate]:
    """Parse + strictly validate a candidates.json string into candidate rows.

    Any structural problem (bad JSON, unknown key, unknown type/stance, wrong field
    type, over-count, over-length, empty exact) raises CandidateError — no silent
    coercion, no partial acceptance.
    """
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CandidateError(f"candidates input is not valid JSON: {exc}") from exc
    if not isinstance(doc, dict):
        raise CandidateError("candidates input must be a JSON object with a 'candidates' array")
    extra = set(doc) - {"candidates"}
    if extra:
        raise CandidateError(f"unknown top-level keys: {sorted(extra)}")
    items = doc.get("candidates")
    if not isinstance(items, list):
        raise CandidateError("'candidates' must be a JSON array")
    if len(items) > MAX_CANDIDATES:
        raise CandidateError(f"too many candidates ({len(items)} > {MAX_CANDIDATES})")
    return [_parse_one(item, idx) for idx, item in enumerate(items)]


def _parse_one(item: Any, idx: int) -> StatementCandidate | FigurativeCandidate:
    if not isinstance(item, dict):
        raise CandidateError(f"candidate[{idx}] must be a JSON object")
    ctype = item.get("type")
    if not isinstance(ctype, str):
        raise CandidateError(f"candidate[{idx}].type must be a string")
    if ctype in STATEMENT_TYPES:
        return _parse_statement(item, idx)
    if ctype in FIGURATIVE_TYPES:
        return _parse_figurative(item, idx)
    raise CandidateError(
        f"candidate[{idx}].type {ctype!r} not in "
        f"{sorted(STATEMENT_TYPES | FIGURATIVE_TYPES)}"
    )


def _parse_statement(item: dict[str, Any], idx: int) -> StatementCandidate:
    extra = set(item) - _STATEMENT_ALLOWED_KEYS
    if extra:
        raise CandidateError(f"candidate[{idx}] unknown fields: {sorted(extra)}")
    missing = _STATEMENT_REQUIRED_KEYS - set(item)
    if missing:
        raise CandidateError(f"candidate[{idx}] missing required fields: {sorted(missing)}")
    exact = _req_str(item, idx, "exact")
    if not exact:
        raise CandidateError(f"candidate[{idx}].exact must be non-empty")
    stance = _req_str(item, idx, "stance")
    if stance not in STANCES:
        raise CandidateError(f"candidate[{idx}].stance {stance!r} not in {sorted(STANCES)}")
    return StatementCandidate(
        type=item["type"],
        exact=exact,
        prefix=_req_str(item, idx, "prefix"),
        suffix=_req_str(item, idx, "suffix"),
        stance=stance,
        subject=_opt_str(item, idx, "subject"),
        object=_opt_str(item, idx, "object"),
        subject_concept=_opt_str(item, idx, "subject_concept"),
        object_concept=_opt_str(item, idx, "object_concept"),
    )


def _parse_figurative(item: dict[str, Any], idx: int) -> FigurativeCandidate:
    extra = set(item) - _FIGURATIVE_ALLOWED_KEYS
    if extra:
        raise CandidateError(f"candidate[{idx}] unknown fields: {sorted(extra)}")
    missing = _FIGURATIVE_REQUIRED_KEYS - set(item)
    if missing:
        raise CandidateError(f"candidate[{idx}] missing required fields: {sorted(missing)}")
    exact = _req_str(item, idx, "exact")
    if not exact:
        raise CandidateError(f"candidate[{idx}].exact must be non-empty")
    return FigurativeCandidate(
        type=item["type"],
        exact=exact,
        prefix=_req_str(item, idx, "prefix"),
        suffix=_req_str(item, idx, "suffix"),
        source_domain=_req_nonblank(item, idx, "source_domain"),
        target_domain=_req_nonblank(item, idx, "target_domain"),
        mapping=_opt_nonblank(item, idx, "mapping"),
        cue=_opt_nonblank(item, idx, "cue"),
    )


# --- Statement body JSON ------------------------------------------------------


def statement_body_json(
    *,
    section: str,
    stance: str,
    subject: str | None,
    object_: str | None,
    subject_concept: str | None,
    object_concept: str | None,
) -> str:
    """Build the deterministic JSON for a statement's TextualBody.

    Always carries section + stance. Optional subject/object phrases and verified
    concept IRIs are included only when present. Sorted keys + compact separators +
    allow_nan=False guarantee finite, byte-stable serialization (clean diffs).
    """
    obj: dict[str, Any] = {"section": section, "stance": stance}
    if subject is not None:
        obj["subject"] = subject
    if object_ is not None:
        obj["object"] = object_
    if subject_concept is not None:
        obj["subject_concept"] = subject_concept
    if object_concept is not None:
        obj["object_concept"] = object_concept
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)


def figurative_body_json(
    *,
    section: str,
    source_domain: str,
    target_domain: str,
    mapping: str | None,
    cue: str | None,
) -> str:
    """Build the deterministic JSON for a figurative annotation's TextualBody.

    Always carries section + source_domain + target_domain. Optional mapping/cue are
    included only when present. Sorted keys + compact separators + allow_nan=False give
    finite, byte-stable serialization (clean diffs). No grounding/concept fields.
    """
    obj: dict[str, Any] = {
        "section": section,
        "source_domain": source_domain,
        "target_domain": target_domain,
    }
    if mapping is not None:
        obj["mapping"] = mapping
    if cue is not None:
        obj["cue"] = cue
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)


# --- Anchoring ----------------------------------------------------------------


def find_qualified_spans(
    file_text: str, exact: str, prefix: str, suffix: str
) -> list[int]:
    """Return the start indices of every occurrence of `exact` in `file_text`
    whose immediately-preceding text ends with `prefix` and whose immediately-
    following text starts with `suffix`.

    Empty prefix/suffix impose no constraint on that side. The caller treats
    0 matches as `extract-quote-not-found` and >1 as `extract-quote-ambiguous`.
    """
    if not exact:
        return []
    out: list[int] = []
    start = 0
    while True:
        i = file_text.find(exact, start)
        if i == -1:
            break
        start = i + 1
        if prefix and not file_text[:i].endswith(prefix):
            continue
        if suffix and not file_text[i + len(exact):].startswith(suffix):
            continue
        out.append(i)
    return out


# --- Grounding + planning -----------------------------------------------------


def _llm_annot_source_name(model: str) -> str:
    """The Phase-3a source identity. The `paper-annotate-v1` segment bumps when the
    prompt or body schema changes (see annotation-tokens.md)."""
    return f"llm-annot:{model}:paper-annotate-v1"


def _normalize_text(text: str) -> str:
    """Whitespace-collapsed form used in match_text (stable across trivial respacing)."""
    return " ".join(text.split())


def active_entity_iris(sidecar: Sidecar) -> set[str]:
    """Concept IRIs of all ACTIVE (open|ack) `entity-*` annotations in the sidecar.

    Dismissed/superseded entity annotations are excluded — the same active-set policy
    the agent is told to pass to `annotate list --status open --status ack`.
    """
    out: set[str] = set()
    for a in sidecar.annotations:
        if not a.annotation_type.startswith("entity-"):
            continue
        if a.status not in (Status.OPEN, Status.ACK):
            continue
        for body in a.bodies:
            if isinstance(body, IriBody):
                out.add(body.iri)
    return out


def _anchor_candidate(
    file_text: str,
    persisted: list[PersistedPassage],
    exact: str,
    prefix: str,
    suffix: str,
) -> tuple[int, int, PersistedPassage, TextQuoteSelector] | str:
    """Locate `exact` (bounded by prefix/suffix) at a unique in-passage offset.

    Returns either a skip reason string ("extract-quote-not-found" /
    "extract-quote-ambiguous" / "extract-anchored-outside-passage") or the anchored locus
    `(file_idx, length, containing_passage, passage-clamped selector)`. Kind-agnostic: the
    caller builds match_text + body. `match_text` is NOT built here because its discriminator
    differs per kind.
    """
    spans = find_qualified_spans(file_text, exact, prefix, suffix)
    if not spans:
        return "extract-quote-not-found"
    if len(spans) > 1:
        return "extract-quote-ambiguous"
    file_idx = spans[0]
    length = len(exact)
    pp = _containing_passage(persisted, file_idx, length)
    if pp is None:
        return "extract-anchored-outside-passage"
    passage_start = pp.file_char_base
    passage_end = pp.file_char_base + pp.length
    prefix_start = max(passage_start, file_idx - _CONTEXT)
    suffix_end = min(passage_end, file_idx + length + _CONTEXT)
    selector = TextQuoteSelector(
        exact=exact,
        prefix=file_text[prefix_start:file_idx],
        suffix=file_text[file_idx + length:suffix_end],
    )
    return (file_idx, length, pp, selector)


def plan_statement(
    file_text: str,
    persisted: list[PersistedPassage],
    candidate: StatementCandidate,
    *,
    active_iris: set[str],
    model: str,
    source_md_name: str,
) -> tuple[PlannedAnnotation | None, str | None, int]:
    """Convert a StatementCandidate to (PlannedAnnotation | None, skip_reason | None, dropped).

    skip reasons: "extract-quote-not-found", "extract-quote-ambiguous",
    "extract-anchored-outside-passage". `dropped` counts unverified concept fields
    removed (the statement is still planned — grounding is a bonus, never a gate).
    """
    anchored = _anchor_candidate(
        file_text, persisted, candidate.exact, candidate.prefix, candidate.suffix
    )
    if isinstance(anchored, str):
        return None, anchored, 0
    file_idx, length, pp, selector = anchored
    section = normalize_section(pp.section)

    dropped = 0
    subject_concept = candidate.subject_concept
    if subject_concept is not None and subject_concept not in active_iris:
        subject_concept = None
        dropped += 1
    object_concept = candidate.object_concept
    if object_concept is not None and object_concept not in active_iris:
        object_concept = None
        dropped += 1

    body = statement_body_json(
        section=section,
        stance=candidate.stance,
        subject=candidate.subject,
        object_=candidate.object,
        subject_concept=subject_concept,
        object_concept=object_concept,
    )

    # The `type|file_idx:length` prefix is already unique per anchored position (one
    # start index per occurrence), so it carries the dedup identity; the normalized-text
    # tail is descriptive (human-readable), not discriminating.
    match_text = (
        f"{candidate.type}|{file_idx}:{length}|{_normalize_text(candidate.exact)}"
    )
    planned = PlannedAnnotation(
        target=SpecificResource(source=source_md_name, selector=selector),
        annotation_type=candidate.type,
        motivation=Motivation.CLASSIFYING,
        body=TextualBody(value=body, format="application/json"),
        match_text=match_text,
        source_name=_llm_annot_source_name(model),
    )
    return planned, None, dropped


def plan_figurative(
    file_text: str,
    persisted: list[PersistedPassage],
    candidate: FigurativeCandidate,
    *,
    model: str,
    source_md_name: str,
) -> tuple[PlannedAnnotation | None, str | None, int]:
    """Convert a FigurativeCandidate to (PlannedAnnotation | None, skip_reason | None, 0).

    No grounding (figurative domains are free-text), so the dropped count is always 0. The
    dedup match_text JSON-encodes the (source_domain, target_domain) pair so two same-span
    figures with different required domains stay distinct AND a literal '|' inside a domain
    cannot create a cross-field collision.
    """
    anchored = _anchor_candidate(
        file_text, persisted, candidate.exact, candidate.prefix, candidate.suffix
    )
    if isinstance(anchored, str):
        return None, anchored, 0
    file_idx, length, pp, selector = anchored
    section = normalize_section(pp.section)

    body = figurative_body_json(
        section=section,
        source_domain=candidate.source_domain,
        target_domain=candidate.target_domain,
        mapping=candidate.mapping,
        cue=candidate.cue,
    )
    # JSON-array the domain pair, NOT '|'-join: keeps the two free-text domains
    # delimiter-safe (a literal '|' inside a domain can't collide) and distinct.
    identity = json.dumps(
        [_normalize_text(candidate.source_domain), _normalize_text(candidate.target_domain)],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    match_text = f"{candidate.type}|{file_idx}:{length}|{identity}"
    planned = PlannedAnnotation(
        target=SpecificResource(source=source_md_name, selector=selector),
        annotation_type=candidate.type,
        motivation=Motivation.CLASSIFYING,
        body=TextualBody(value=body, format="application/json"),
        match_text=match_text,
        source_name=_llm_annot_source_name(model),
    )
    return planned, None, 0


# --- Orchestrator -------------------------------------------------------------


@dataclass(frozen=True)
class ExtractReport:
    written: int
    skipped: dict[str, int]
    grounding_dropped: int
    source_text_hash_recorded: bool
    note: str | None = None


def _read_text_sha256(source_md: Path) -> str:
    fm = raw_frontmatter(source_md)
    value = fm.get("text_sha256")
    if not isinstance(value, str) or not value:
        raise SourceTextError(
            f"{source_md} has no `text_sha256` frontmatter; re-run `persist-source`."
        )
    return value


def extract_candidates(
    *,
    source_md: Path,
    model: str,
    candidates: list[StatementCandidate],
    now: datetime,
    actor: str,
) -> ExtractReport:
    """Anchor + persist statement candidates into `<citekey>.source.anno.trig`.

    Document idempotency: the source_text_hash is advanced only when the document was
    FULLY processed (no candidate hit an anchoring failure) — incl. empty / all-duplicate
    runs — but NOT when any candidate failed to anchor (a defective set worth re-running,
    even if other candidates persisted).
    """
    if not source_md.is_file():
        raise SourceTextError(f"{source_md} not found.")
    file_text, persisted = load_persisted_passages(source_md)

    sidecar_path = sidecar_for_markdown(source_md)
    sidecar = read_sidecar(sidecar_path) if sidecar_path.exists() else Sidecar()
    active = active_entity_iris(sidecar)

    skipped: Counter[str] = Counter()
    grounding_dropped = 0
    planned: list[PlannedAnnotation] = []
    for cand in candidates:
        p, reason, dropped = plan_statement(
            file_text, persisted, cand,
            active_iris=active, model=model, source_md_name=source_md.name,
        )
        grounding_dropped += dropped
        if p is not None:
            planned.append(p)
        elif reason is not None:
            skipped[reason] += 1

    new_sidecar, written = merge_planned(sidecar, planned, actor=actor, now=now)

    # Valid no-op vs failed no-op: advance the hash only when the document was FULLY
    # processed — i.e. NO candidate hit an anchoring failure. Every skip reason
    # (quote-not-found / ambiguous / anchored-outside-passage) is a locatability defect,
    # so `not skipped` means every candidate either persisted or cleanly deduped. A
    # partial run (some anchored, some failed) does NOT advance: re-running is idempotent
    # (written rows dedupe) and gives the failed candidates another shot. Empty and
    # all-duplicate runs have no skips, so they advance.
    advance = not skipped
    hash_recorded = False
    if advance:
        text_sha = _read_text_sha256(source_md)
        source_name = _llm_annot_source_name(model)
        new_sidecar, ledger = find_or_create_ledger(new_sidecar, source_name, now=now)
        updated = ledger_set_source_text_hash(ledger, text_sha, now=now)
        new_sidecar = replace(
            new_sidecar,
            ledgers=tuple(
                updated if led.id == updated.id else led
                for led in new_sidecar.ledgers
            ),
        )
        hash_recorded = True

    if written or new_sidecar != sidecar:
        atomic_write_text(sidecar_path, serialize_sidecar(new_sidecar))

    # Surface WHY the document was not marked processed, so the agent/CLI knows a
    # corrected re-run is expected (rather than silently leaving the hash unadvanced).
    note = (
        None if advance
        else f"source_text_hash not advanced: {sum(skipped.values())} "
        "candidate(s) failed to anchor; fix and re-run"
    )
    return ExtractReport(
        written=len(written),
        skipped=dict(skipped),
        grounding_dropped=grounding_dropped,
        source_text_hash_recorded=hash_recorded,
        note=note,
    )


def check_source_changed(*, source_md: Path, model: str) -> bool:
    """True if the agent should run: the `.source.md` text differs from the last
    value processed for this source (or no sidecar/ledger exists yet)."""
    current = _read_text_sha256(source_md)
    sidecar_path = sidecar_for_markdown(source_md)
    if not sidecar_path.exists():
        return True
    sidecar = read_sidecar(sidecar_path)
    source_name = _llm_annot_source_name(model)
    for led in sidecar.ledgers:
        if led.source == source_name:
            return led.source_text_hash != current
    return True
