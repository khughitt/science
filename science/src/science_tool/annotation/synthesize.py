"""Phase 4c — proposition reasoning synthesis (scaffold + two-pass apply).

Fills predicate/polarity/claim_layer (and refines subject/object) on the propositions
Phase 4a promoted, from an agent-proposed candidates file. Brain/hands split: the agent
proposes (untrusted), this module validates the proposition interlocks and persists.

See docs/plans/2026-06-16-proposition-synthesis-phase4c-design.md.
"""

from __future__ import annotations

import json
import re
from typing import Any

from science_model.reasoning import (
    ClaimLayer, Polarity, Predicate, SIGN_MEANINGFUL_PREDICATES,
)

from science_tool.annotation.model import Annotation, Sidecar, TextualBody


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
