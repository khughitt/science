"""Phase 4c — proposition reasoning synthesis (scaffold + two-pass apply).

Fills predicate/polarity/claim_layer (and refines subject/object) on the propositions
Phase 4a promoted, from an agent-proposed candidates file. Brain/hands split: the agent
proposes (untrusted), this module validates the proposition interlocks and persists.

See docs/plans/2026-06-16-proposition-synthesis-phase4c-design.md.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from science_model.propositions import PropositionEntity
from science_model.reasoning import (
    SIGN_MEANINGFUL_PREDICATES,
    ClaimLayer,
    Polarity,
    Predicate,
)

from science_tool.annotation.model import Annotation, Sidecar, TextualBody
from science_tool.annotation.promote import entity_dest
from science_tool.annotation.statement_extract import find_qualified_spans
from science_tool.entities import _parse_markdown_file, write_entity_file

SYNTH_SOURCE_RE = re.compile(r"^llm-synth:[A-Za-z0-9._-]+:proposition-synthesize-v1$")
SYNTH_FIELDS: tuple[str, ...] = ("subject", "object", "predicate", "polarity", "claim_layer")
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


NOT_APPLICABLE = Polarity.NOT_APPLICABLE.value


@dataclass(frozen=True)
class WritePlan:
    writes: dict[str, str]          # field -> value to persist (synthesis-owned only)
    blocked: tuple[str, ...]        # proposed fields blocked by an existing differing value


def _effective(current: dict[str, Any], writes: dict[str, str], field_name: str) -> Any:
    if field_name in writes:
        return writes[field_name]
    val = current.get(field_name)
    return None if val is None else str(val)


def plan_writes(current: dict[str, Any], cand: SynthesisCandidate) -> WritePlan:
    """Pure fill-only-unset + override + sign-less-canonicalization plan. No validation."""
    writes: dict[str, str] = {}
    blocked: list[str] = []
    for f in SYNTH_FIELDS:
        if f not in cand.fields:
            continue                                  # omitted → leave unset/unchanged
        proposed = cand.fields[f]
        cur = current.get(f)
        if cur is None:
            writes[f] = proposed                      # unset → fill
        elif str(cur) == proposed:
            continue                                  # already equal → nothing to do
        elif f in cand.override:
            writes[f] = proposed                      # curator-authorised replace
        else:
            blocked.append(f)                         # existing value blocks default apply
    # Sign-less predicate ⇒ canonicalize an omitted polarity to not_applicable (validate-clean).
    eff_pred = _effective(current, writes, "predicate")
    if eff_pred is not None and eff_pred not in _SIGN_MEANINGFUL_VALUES:
        if _effective(current, writes, "polarity") is None:
            writes["polarity"] = NOT_APPLICABLE
    return WritePlan(writes=writes, blocked=tuple(blocked))


def validate_candidate(current: dict[str, Any], cand: SynthesisCandidate) -> WritePlan:
    """Validate one candidate against current frontmatter; return its WritePlan.

    Enforces the design §7 contracts on the *effective* (post-write) state and the model's
    own relational interlocks. Raises SynthesisOverrideError (override of a currently-unset
    field) or SynthesisApplyError (operand/polarity/interlock). Pure (no writes).
    """
    # override may only target a field that is CURRENTLY set (design §6/§7). The parser
    # checks present-in-patch; the currently-set check needs `current`, so it lives here.
    for name in cand.override:
        if current.get(name) is None:
            raise SynthesisOverrideError(
                f"{cand.proposition}: override names {name!r} but it is currently unset "
                f"(nothing to override — omit it to fill normally)"
            )
    plan = plan_writes(current, cand)
    eff = {f: _effective(current, plan.writes, f) for f in SYNTH_FIELDS}

    # predicate → operands contract (effective subject AND object must exist)
    if "predicate" in cand.fields:
        if eff["subject"] is None or eff["object"] is None:
            raise SynthesisApplyError(
                f"{cand.proposition}: predicate {cand.fields['predicate']!r} requires an "
                f"effective subject and object"
            )
    # polarity → predicate contract (no bare polarity)
    if "polarity" in cand.fields and eff["predicate"] is None:
        raise SynthesisApplyError(
            f"{cand.proposition}: polarity requires an effective predicate"
        )
    # interlocks: construct the would-be entity and let the model validator run
    try:
        PropositionEntity(
            id=cand.proposition, title=str(current.get("title") or ""),
            subject=eff["subject"], object=eff["object"], predicate=eff["predicate"],
            polarity=eff["polarity"], claim_layer=eff["claim_layer"],
        )
    except ValidationError as exc:
        raise SynthesisApplyError(f"{cand.proposition}: {exc}") from exc
    return plan


@dataclass
class SynthReport:
    updated: int = 0
    skipped: Counter = field(default_factory=Counter)
    written_paths: list[str] = field(default_factory=list)


def apply_synthesis(
    candidates: list[SynthesisCandidate],
    *,
    current: dict[str, dict[str, Any]],
    project_root: Path,
    source: str,
    in_scope: set[str],
    as_of: date | None = None,
) -> SynthReport:
    """Two-pass apply. Pass 1 validates every candidate (raises ⇒ nothing written); Pass 2
    writes with fill-only-unset, sign-less canonicalization, body preservation, and stamps
    `reasoning_source` only on a real write. Uncovered in-scope props are counted, not failed.
    """
    # Pass 1 — validate everything (no writes). plans[i] aligns with candidates[i].
    plans: list[WritePlan] = [
        validate_candidate(current[c.proposition], c) for c in candidates
    ]

    # Pass 2 — apply.
    report = SynthReport()
    for cand, plan in zip(candidates, plans):
        if plan.blocked:
            # Count every proposed field blocked by an existing differing value, even when
            # other fields on the same candidate are written. This keeps curator-visible
            # conflict reporting from disappearing in mixed write/skip patches.
            report.skipped["synthesize-existing-value-blocks"] += len(plan.blocked)
        if not plan.writes:
            if not plan.blocked:
                report.skipped["synthesize-nothing-to-fill"] += 1
            continue
        fm = dict(current[cand.proposition])
        fm.update(plan.writes)
        fm["reasoning_source"] = source            # a synthesis-owned write (stamped on real change)
        _write_proposition(cand.proposition, fm, project_root, as_of)
        report.updated += 1
        report.written_paths.append(str(entity_dest(cand.proposition, project_root)))

    covered = {c.proposition for c in candidates}
    for prop_ref in in_scope:
        if prop_ref not in covered:
            report.skipped["synthesize-proposition-uncovered"] += 1
    return report


def _write_proposition(
    prop_ref: str, merged_fm: dict[str, Any], project_root: Path, as_of: date | None
) -> None:
    """Body-preserving frontmatter write: reconstruct the typed entity, keep the prose body.

    The existing (possibly curated) markdown body is read and passed back verbatim; only
    frontmatter fields change. `write_entity_file` preserves `created` and advances `updated`.
    """
    dest = entity_dest(prop_ref, project_root)
    _, body = _parse_markdown_file(dest)
    prop = PropositionEntity(**merged_fm)          # re-runs interlock validator; extra keys ignored
    write_entity_file(prop, project_root=project_root, body=body, as_of=as_of)
