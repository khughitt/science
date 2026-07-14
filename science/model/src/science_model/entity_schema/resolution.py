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

# ☠️ THIS MODULE ASKS ABOUT LINEAGE, AND IT KEYS ON LINEAGE.
#
# It used to key on `status in {"superseded"}` -- a proxy for "this record has a successor" -- and a
# proxy is wrong in BOTH directions:
#
#   * A record with a DANGLING successor and a non-terminal status was never checked at all. An
#     `active` hypothesis could carry `resynthesized_into: [hypothesis:9999-nope]` and pass every
#     gate, which is the precise fault this module exists to catch, sailing through on a status.
#   * A `superseded` record discharged by `closure_basis` -- no successor, nothing to resolve -- was
#     handed to a resolver anyway. That is not merely wasted work: building one RAISES on a corpus
#     with a duplicated alias, so an unrelated `--title` edit was blocked by a collision between two
#     other entities, over lineage the record does not have.
#
# The forward implication -- a `superseded` record must name SOMETHING (a successor or a basis) --
# is SHAPE, it is one record's business, and it is the schema's. The reverse (lineage present =>
# status superseded) is shape too, and now the schema says that as well. Neither belongs here.
# This module answers the one question a schema structurally cannot: does the reference RESOLVE?


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
    @property
    def status(self) -> str:
        """Resolution state: resolved, unresolved, scope_ambiguous, ambiguous, or tag."""
        ...

    @property
    def canonical_id(self) -> str | None: ...

    @property
    def candidates(self) -> tuple[str, ...]: ...


class LineageTargets(Protocol):
    """What this module needs of a resolver. `ReferenceResolver` satisfies it as-is."""

    def resolve(self, raw: str) -> Resolved: ...


def has_lineage_to_resolve(entity: dict[str, Any]) -> bool:
    """Whether this record names a successor at all. Needs NO resolver.

    Exists so a caller can decide whether BUILDING one is worth it without restating the rule that
    decides. That is not a micro-optimization: `ReferenceResolver.from_entities` RAISES on a corpus
    with a duplicated alias, so a caller that constructed one for a record with NO lineage would
    turn a reportable fault into an unwritable project — an alias collision between two OTHER
    entities blocking an edit to this one.
    """
    return bool(_lineage_refs(entity))


def check_resolution(
    entity: dict[str, Any], *, targets: LineageTargets, live_hypotheses: set[str]
) -> list[ResolutionViolation]:
    """Cross-record LINEAGE violations. Empty == clean.

    RESOLUTION only, and asked of every record that NAMES a successor — whatever its status. A
    dangling successor is a dangling successor on an `active` record too, and reading the status to
    decide whether to look was how one sailed through (see the module header).

    Whether a basis is PRESENT and NON-EMPTY is shape, and shape is the schema's (`minItems: 1`,
    `pattern: "\\S"`). Re-checking it here would be a second authority for the same fact, which is
    the collapse this arc exists to undo.

    RESOLVE, then CHECK -- in that order, and never `raw in some_set`. Raw string membership fails
    in BOTH directions: it calls a valid alias dangling (blocking a correct corpus), and it misses
    an alias that resolves back to the entity itself (a closed loop wearing the check's green).

    ☠️ `live_hypotheses` is the set of LOCAL, LIVE **hypothesis** canonical ids -- NOT every loaded
    entity. It was `live_ids` (all of them), and the name is what invited the bug: the schema
    constrains only the AUTHORED spelling (`pattern: "^hypothesis:"`), and an alias is free to point
    anywhere. So `superseded_by: hypothesis:looks-valid` could RESOLVE to `dataset:0002`, find it in
    the all-entities set, and report CLEAN -- a hypothesis superseded by a dataset. A successor must
    be a hypothesis; the caller passes only those, and the type of the argument says so.
    """
    if not has_lineage_to_resolve(entity):
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
        elif resolution.canonical_id not in live_hypotheses:
            # Resolvable is not enough, and neither is EXISTING. Two distinct failures land here:
            #   * an ARCHIVED successor -- resolves perfectly, and names an entity that is dead;
            #   * a CROSS-KIND alias -- resolves perfectly, and names a live DATASET (or topic, or
            #     paper). The schema cannot catch it: it constrains the authored `^hypothesis:`
            #     spelling, and an alias may point at anything.
            # Both are the same sentence: what it names is not a live hypothesis here.
            message = (
                f"{raw_id}: {field} -> {ref!r} resolves to {resolution.canonical_id}, which is not "
                f"a live hypothesis in this project; a closed hypothesis's successor must be one"
            )
        else:
            continue
        violations.append(
            ResolutionViolation(entity_id=raw_id, field=field, ref=ref, message=message)
        )

    return violations
