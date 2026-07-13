"""Cross-record invariants — the D3 escape hatch, ENUMERATED.

JSON Schema is the authority for a record's SHAPE and for the PRESENCE of a structural basis.
It validates one record in isolation, so it structurally cannot answer the ONE cross-record
question this layer exists for: does this LINEAGE reference resolve to a real, live entity that
is not the entity itself?

That is the whole list. It is deliberately a CLOSED one rather than an open-ended second
authority (design §9, D3). Getting the split wrong re-opens the hole it was built to close: a
PRESENT but DANGLING `superseded_by:` satisfies the schema, closes the entity, and records no
real reason for the closure.

NOT HERE, and neither is an oversight:

  * "does an archive record exist?" -- there is NO SUCH RECORD to exist. `archive_ref` was
    deleted: the archive index is keyed by the archived entity's own id and mints no record
    identifier, so there is nothing on the other end of such a reference. `archived` is
    discharged by `closure_basis`, which is SHAPE, and shape is the schema's.
  * "does a verdict have qualifying evidence?" -- that needs the evidence-line EDGES, which
    exist only after materialization. It is a graph-time invariant and this runs at load time;
    it belongs to a graph check (`validate/checks/verdict_agreement.py`). Said plainly so nobody
    assumes it is covered here.
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel

# `superseded` is the ONLY terminal with resolvable structure (design §7.4, corrected 2026-07-13).
# `archived` was in this set for two revisions and had NO archive check behind it -- because none
# can be written: the archive index is keyed by the archived entity's own id and mints no record
# identifier, so there is nothing to resolve. A status listed here with no check is a promise the
# module does not keep. `retired` and `archived` are discharged by `closure_basis`, which is SHAPE,
# and shape is the schema's -- this module must not restate it.
_TERMINALS_WITH_STRUCTURE = frozenset({"superseded"})


class ResolutionViolation(BaseModel):
    """One cross-record failure, typed -- the contract between checker, loader and validation.

    A bare `list[str]` would have forced `validate/` to re-parse a sentence to recover the id and
    the field it needs for a `Result`. The message is for humans; these fields are for code.
    """

    entity_id: str
    field: str  # "superseded_by" | "resynthesized_into"
    ref: str
    message: str


def _lineage_refs(entity: dict[str, Any]) -> list[tuple[str, str]]:
    """(field, ref) pairs. `superseded_by` is scalar; `resynthesized_into` is a LIST."""
    refs: list[tuple[str, str]] = []
    scalar = entity.get("superseded_by")
    if isinstance(scalar, str) and scalar:
        refs.append(("superseded_by", scalar))
    listed = entity.get("resynthesized_into")
    if isinstance(listed, list):
        refs.extend(("resynthesized_into", r) for r in listed if isinstance(r, str) and r)
    return refs


# ⚠️ LAYERING. `ReferenceResolver` lives in `science_tool.graph.reference_resolution`, and
# `science_tool` depends on `science_model` -- NOT the other way round. Importing it here would
# invert the package dependency and make the two cyclic. So this module states what it NEEDS,
# structurally, and `science_tool` passes the real resolver in. `ReferenceResolver` satisfies both
# protocols as-is (extra keyword-only params with defaults are compatible), so there is nothing to
# adapt and no second implementation to keep in step.
class Resolved(Protocol):
    status: str  # "resolved" | "unresolved" | "scope_ambiguous" | "ambiguous" | "tag"
    canonical_id: str | None
    candidates: tuple[str, ...]


class LineageTargets(Protocol):
    """What this module needs of a resolver. `ReferenceResolver` satisfies it as-is."""

    def resolve(self, raw: str) -> Resolved: ...


def check_resolution(
    entity: dict[str, Any], *, targets: LineageTargets, live_ids: set[str]
) -> list[ResolutionViolation]:
    """Cross-record terminal violations. Empty == clean.

    RESOLUTION only. Whether a basis is PRESENT and NON-EMPTY is shape, and shape is the schema's
    (`minItems: 1`, `pattern: "\\S"`). Re-checking it here would be a second authority for the same
    fact, which is the collapse this arc exists to undo.

    RESOLVE, then CHECK -- in that order, and never `raw in some_set`. Raw string membership fails
    in BOTH directions: it calls a valid alias dangling (blocking a correct corpus), and it misses
    an alias that resolves back to the entity itself (a closed loop wearing the check's green).
    """
    if entity.get("status") not in _TERMINALS_WITH_STRUCTURE:
        return []

    raw_id = str(entity.get("id") or "<unknown>")
    # The entity's OWN id must go through the same resolver, or a self-reference written in any
    # spelling other than the canonical one slips past the identity check below.
    self_res = targets.resolve(raw_id)
    self_canonical = self_res.canonical_id if self_res.status == "resolved" else raw_id

    violations: list[ResolutionViolation] = []

    for field, ref in _lineage_refs(entity):
        resolution = targets.resolve(ref)

        if resolution.status == "scope_ambiguous":
            message = (
                f"{raw_id}: {field} -> {ref!r} is owned in more than one loaded scope "
                f"({', '.join(resolution.candidates)}); a scoped form is required"
            )
        elif resolution.status != "resolved" or resolution.canonical_id is None:
            message = (
                f"{raw_id}: {field} -> {ref!r} does not resolve to any known entity; "
                f"the entity is closed and the reason it closed does not exist"
            )
        elif resolution.canonical_id == self_canonical:
            # Catches BOTH the literal self-reference and the alias that resolves BACK to the
            # entity itself -- which reads as a valid successor and is a closed loop.
            message = (
                f"{raw_id}: {field} -> {ref!r} resolves to the entity itself "
                f"({self_canonical}); an entity cannot be its own successor"
            )
        elif resolution.canonical_id not in live_ids:
            # Resolvable is not enough. An ARCHIVED successor resolves perfectly well and is still
            # not a reason: the entity it points at is no longer part of the live corpus.
            message = (
                f"{raw_id}: {field} -> {ref!r} resolves to {resolution.canonical_id}, which is not "
                f"a live entity in this project; a closed entity's successor must be one that exists"
            )
        else:
            continue
        violations.append(
            ResolutionViolation(entity_id=raw_id, field=field, ref=ref, message=message)
        )

    return violations
