"""Phase 4c — proposition reasoning synthesis (scaffold + two-pass apply).

Fills predicate/polarity/claim_layer (and refines subject/object) on the propositions
Phase 4a promoted, from an agent-proposed candidates file. Brain/hands split: the agent
proposes (untrusted), this module validates the proposition interlocks and persists.

See docs/plans/2026-06-16-proposition-synthesis-phase4c-design.md.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from science_model.reasoning import (
    ClaimLayer, Polarity, Predicate, SIGN_MEANINGFUL_PREDICATES,
)

from science_tool.annotation.model import Annotation, Sidecar, TextualBody
from science_tool.annotation.statement_extract import find_qualified_spans


SYNTH_SOURCE_RE = re.compile(r"^llm-synth:[A-Za-z0-9._-]+:proposition-synthesize-v1$")
SYNTH_FIELDS: tuple[str, ...] = ("subject", "object", "predicate", "polarity", "claim_layer")
_ENUM_FIELDS: tuple[str, ...] = ("predicate", "polarity", "claim_layer")
_CANDIDATE_KEYS = frozenset({"proposition", "annotation", "override", *SYNTH_FIELDS})
_PREDICATE_VALUES = frozenset(p.value for p in Predicate)
_POLARITY_VALUES = frozenset(p.value for p in Polarity)
_CLAIM_LAYER_VALUES = frozenset(v.value for v in ClaimLayer)
_SIGN_MEANINGFUL_VALUES = frozenset(p.value for p in SIGN_MEANINGFUL_PREDICATES)
_ENUM_VALUES: dict[str, frozenset[str]] = {
    "predicate": _PREDICATE_VALUES,
    "polarity": _POLARITY_VALUES,
    "claim_layer": _CLAIM_LAYER_VALUES,
}

_PROP_PREFIX = "proposition:"


def in_scope_propositions(sidecar: Sidecar) -> dict[str, list[Annotation]]:
    """Map each promoted `proposition:<slug>` to its supporting statement annotations.

    In scope = the propositions reachable from THIS sidecar via the `sci:promotedTo`
    backlink (Phase 4a sets `promoted_to`). Questions/hypotheses are excluded — only the
    proposition kind carries reasoning fields. Insertion order preserved (stable scaffold).
    """
    scope: dict[str, list[Annotation]] = {}
    for ann in sidecar.annotations:
        pt = ann.promoted_to
        if pt is not None and pt.startswith(_PROP_PREFIX):
            scope.setdefault(pt, []).append(ann)
    return scope


def _statement_body(ann: Annotation) -> dict[str, Any]:
    for body in ann.bodies:
        if isinstance(body, TextualBody) and body.format == "application/json":
            data = json.loads(body.value)
            if isinstance(data, dict):
                return data
    return {}


def statement_context(ann: Annotation, ref: str) -> dict[str, Any]:
    """One supporting-statement context object for the scaffold (exact + body fields)."""
    data = _statement_body(ann)
    ctx: dict[str, Any] = {
        "annotation": ref,
        "exact": ann.target.selector.exact,
        "section": data.get("section", ""),
        "stance": data.get("stance", ""),
    }
    for key in ("subject", "object", "subject_concept", "object_concept"):
        if key in data:
            ctx[key] = data[key]
    return ctx


SCAFFOLD_SOURCE_PLACEHOLDER = "llm-synth:<MODEL>:proposition-synthesize-v1"
RELATION_TYPE = "relation"


def _resolve_range(file_text: str, ann: Annotation) -> tuple[int, int] | None:
    """Unique [start, end) of an annotation's quote selector in `file_text`, else None."""
    sel = ann.target.selector
    spans = find_qualified_spans(file_text, sel.exact, sel.prefix, sel.suffix)
    if len(spans) != 1:
        return None
    return spans[0], spans[0] + len(sel.exact)


def _overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _relation_predicate(ann: Annotation) -> dict[str, Any] | None:
    data = _statement_body(ann)
    pred = data.get("predicate")
    if not isinstance(pred, str):
        return None
    return {
        "annotation_frag": ann.id,
        "predicate": pred,
        "subject": data.get("subject"),
        "object": data.get("object"),
    }


def relation_hints(
    file_text: str, statements: list[Annotation], relations: list[Annotation]
) -> tuple[list[dict[str, Any]], int]:
    """Predicate hints from relation annotations co-located with any supporting statement.

    Co-located = overlapping resolved [start,end) ranges. A statement or relation whose
    selector does not resolve uniquely is counted once as unresolved and skipped (never
    fatal). Each qualifying relation appears at most once (first overlap wins).
    """
    unresolved = 0
    stmt_ranges: list[tuple[int, int]] = []
    for s in statements:
        r = _resolve_range(file_text, s)
        if r is None:
            unresolved += 1
        else:
            stmt_ranges.append(r)
    hints: list[dict[str, Any]] = []
    for rel in relations:
        rr = _resolve_range(file_text, rel)
        if rr is None:
            unresolved += 1
            continue
        if any(_overlaps(rr, sr) for sr in stmt_ranges):
            hint = _relation_predicate(rel)
            if hint is not None:
                hints.append(hint)
    return hints, unresolved


def build_scaffold(
    sidecar: Sidecar,
    file_text: str,
    current: dict[str, dict[str, Any]],
    *,
    ref_for,
) -> tuple[dict[str, Any], int]:
    """Assemble the read-only scaffold object + total unresolved-hint count.

    `current[prop_ref]` is that proposition's current frontmatter (subject/object/predicate/
    polarity/claim_layer/title); missing keys are simply absent. `ref_for(frag)` builds the
    `annotation:<relpath>#<frag>` ref for a sidecar annotation. Per design §5 the scaffold
    shows EVERY synthesis field in `current` (unset → `null`) so the agent sees explicitly
    which fields are already set vs available.
    """
    scope = in_scope_propositions(sidecar)
    relations = [a for a in sidecar.annotations if a.annotation_type == RELATION_TYPE]
    entries: list[dict[str, Any]] = []
    total_unresolved = 0
    for prop_ref, statements in scope.items():
        fm = current.get(prop_ref, {})
        cur = {f: fm.get(f) for f in SYNTH_FIELDS}   # all 5 fields; unset → None (design §5)
        hints, unresolved = relation_hints(file_text, statements, relations)
        total_unresolved += unresolved
        entries.append({
            "proposition": prop_ref,
            "title": fm.get("title", ""),
            "current": cur,
            "statements": [statement_context(a, ref_for(a.id)) for a in statements],
            "relation_hints": hints,
        })
    return {"source": SCAFFOLD_SOURCE_PLACEHOLDER, "propositions": entries}, total_unresolved


class SynthesisReadError(Exception):
    """Malformed candidates file / bad source / scope / annotation (fail loud)."""


class SynthesisApplyError(Exception):
    """Interlock / operand / polarity-without-predicate / write-boundary failure (fail loud)."""


class SynthesisOverrideError(SynthesisReadError):
    """Illegal override: unknown field, field not in patch, currently-unset, or reasoning_source.

    Subclasses SynthesisReadError so the CLI catch and `pytest.raises(SynthesisReadError)`
    cover it; the dedicated type matches design §10's three-class taxonomy.
    """


@dataclass(frozen=True)
class SynthesisCandidate:
    proposition: str
    annotation: str
    fields: dict[str, str] = field(default_factory=dict)   # proposed SYNTH_FIELDS (non-null)
    override: frozenset[str] = frozenset()


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise SynthesisReadError(msg)


def _require_override(cond: bool, msg: str) -> None:
    if not cond:
        raise SynthesisOverrideError(msg)


def parse_candidates_doc(
    doc: Any, scope: dict[str, set[str]]
) -> tuple[str, list[SynthesisCandidate]]:
    """Parse + structurally validate a candidates document against the in-scope set.

    `scope[prop_ref]` is the set of that proposition's supporting-statement refs. Returns
    `(validated_source, candidates)`. Raises SynthesisReadError on any structural defect.
    """
    _require(isinstance(doc, dict), "candidates input must be a JSON object")
    extra = set(doc) - {"source", "candidates"}
    _require(not extra, f"unknown top-level keys: {sorted(extra)}")
    source = doc.get("source")
    _require(isinstance(source, str) and bool(SYNTH_SOURCE_RE.match(source)),
             f"top-level 'source' must match {SYNTH_SOURCE_RE.pattern!r} (got {source!r})")
    items = doc.get("candidates")
    _require(isinstance(items, list), "'candidates' must be a JSON array")

    seen: set[str] = set()
    out: list[SynthesisCandidate] = []
    for i, item in enumerate(items):
        out.append(_parse_candidate(item, i, scope, seen))
    return source, out


def _parse_candidate(
    item: Any, idx: int, scope: dict[str, set[str]], seen: set[str]
) -> SynthesisCandidate:
    _require(isinstance(item, dict), f"candidate[{idx}] must be a JSON object")
    extra = set(item) - _CANDIDATE_KEYS
    _require(not extra, f"candidate[{idx}] unknown fields: {sorted(extra)}")

    prop = item.get("proposition")
    _require(isinstance(prop, str) and prop in scope,
             f"candidate[{idx}].proposition {prop!r} is not an in-scope proposition")
    _require(prop not in seen, f"duplicate candidate for proposition {prop!r}")
    seen.add(prop)

    ann = item.get("annotation")
    _require(isinstance(ann, str) and ann in scope[prop],
             f"candidate[{idx}].annotation {ann!r} is not a supporting statement of {prop!r}")

    fields: dict[str, str] = {}
    for f in SYNTH_FIELDS:
        if f not in item:
            continue
        val = item[f]
        _require(isinstance(val, str) and val != "",
                 f"candidate[{idx}].{f} must be a non-empty string (omit it to leave unset; "
                 f"null is not allowed)")
        if f in _ENUM_VALUES:
            _require(val in _ENUM_VALUES[f],
                     f"candidate[{idx}].{f} {val!r} not in {sorted(_ENUM_VALUES[f])}")
        fields[f] = val

    override = item.get("override", [])
    _require_override(isinstance(override, list) and all(isinstance(x, str) for x in override),
                      f"candidate[{idx}].override must be a list of field names")
    for name in override:
        _require_override(name in SYNTH_FIELDS,
                          f"candidate[{idx}].override {name!r} not in {sorted(SYNTH_FIELDS)} "
                          f"(reasoning_source is never overrideable)")
        _require_override(name in fields,
                          f"candidate[{idx}].override names {name!r} which is not present in the patch")
    return SynthesisCandidate(
        proposition=prop, annotation=ann, fields=fields, override=frozenset(override),
    )
