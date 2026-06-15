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
STANCES: frozenset[str] = frozenset({"asserted", "negated", "hypothesized", "open"})
MAX_CANDIDATES = 500
MAX_FIELD_CHARS = 2000

_ALLOWED_KEYS = frozenset({
    "type", "exact", "prefix", "suffix", "stance",
    "subject", "object", "subject_concept", "object_concept",
})
_REQUIRED_KEYS = frozenset({"type", "exact", "prefix", "suffix", "stance"})


class CandidateError(ValueError):
    """A candidates.json file that is structurally invalid. Fail loud; write nothing."""


@dataclass(frozen=True)
class Candidate:
    type: str
    exact: str
    prefix: str
    suffix: str
    stance: str
    subject: str | None = None
    object: str | None = None
    subject_concept: str | None = None
    object_concept: str | None = None


def parse_candidates(raw: str) -> list[Candidate]:
    """Parse + strictly validate a candidates.json string into Candidate rows.

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


def _parse_one(item: Any, idx: int) -> Candidate:
    if not isinstance(item, dict):
        raise CandidateError(f"candidate[{idx}] must be a JSON object")
    keys = set(item)
    extra = keys - _ALLOWED_KEYS
    if extra:
        raise CandidateError(f"candidate[{idx}] unknown fields: {sorted(extra)}")
    missing = _REQUIRED_KEYS - keys
    if missing:
        raise CandidateError(f"candidate[{idx}] missing required fields: {sorted(missing)}")

    def _checked(name: str, val: str) -> str:
        if len(val) > MAX_FIELD_CHARS:
            raise CandidateError(
                f"candidate[{idx}].{name} exceeds {MAX_FIELD_CHARS} chars"
            )
        return val

    def _req(name: str) -> str:
        val = item[name]
        if not isinstance(val, str):
            raise CandidateError(f"candidate[{idx}].{name} must be a string")
        return _checked(name, val)

    def _opt(name: str) -> str | None:
        if name not in item or item[name] is None:
            return None
        val = item[name]
        if not isinstance(val, str):
            raise CandidateError(f"candidate[{idx}].{name} must be a string or null")
        return _checked(name, val)

    ctype = _req("type")
    if ctype not in STATEMENT_TYPES:
        raise CandidateError(
            f"candidate[{idx}].type {ctype!r} not in {sorted(STATEMENT_TYPES)}"
        )
    exact = _req("exact")
    if not exact:
        raise CandidateError(f"candidate[{idx}].exact must be non-empty")
    stance = _req("stance")
    if stance not in STANCES:
        raise CandidateError(
            f"candidate[{idx}].stance {stance!r} not in {sorted(STANCES)}"
        )
    return Candidate(
        type=ctype,
        exact=exact,
        prefix=_req("prefix"),
        suffix=_req("suffix"),
        stance=stance,
        subject=_opt("subject"),
        object=_opt("object"),
        subject_concept=_opt("subject_concept"),
        object_concept=_opt("object_concept"),
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
