"""Every authored relation must MATERIALIZE — the check, asked in the graph builder's own words.

`materialize` raises on the first relation it cannot build, and it is not run on every pass.
`validate` is the pass everyone runs, so a corpus that has no graph has to be visible HERE, or it is
visible nowhere until someone happens to rebuild — and, worse, `mark_superseded --apply` will
cheerfully stamp derived lineage into it in the meantime.

This check DERIVES NOTHING. `audit_relations` calls `admit_authored_relation` — the graph builder's
own admission, on the same `SourceRelation` stream — and this file turns each refusal into a
`Result`. The rule name is the code the builder's own rejection carried:

    relation.unknown-subject          the subject is not a live loaded entity. NOT symmetric with
                                      the object: an archived record may be POINTED AT, never AUTHOR.
    relation.unknown-object           the object resolves to nothing (or to an id no record backs)
    relation.unknown-predicate        the predicate is not a CURIE/IRI this vocabulary resolves
    relation.unsupported-graph-layer  the edge is authored into a layer that does not exist
    relation.external-target          an external term where the predicate requires a project entity
    relation.self-referential         an entity related to ITSELF
    relation.illegal-kind-pair        a kind pair the relation model forbids
    relation.membership-role          a membership role on an edge that is not a membership
    relation.cycle                    the edge lies on a cycle in the {amends, supersedes} lineage

ERROR, and FLAT — never kind-scoped. These are RELATION-VALIDITY failures: the corpus does not build
a graph at all. That verdict comes from the relation model, which already says which pairs are legal,
which endpoints exist, and that the lineage is acyclic. It owes nothing to any per-kind status
certification, so it must NOT wait on the status-vocabulary ratchet and must NOT be scoped by kind.
The same defect is the same defect whatever kind authors it.

☠️ THE BLAST RADIUS IS NOT ZERO — an earlier draft of this docstring claimed it was, and the claim
was false. What is true is narrower and structural: `materialize` raises on every one of these, so a
project that BUILDS A GRAPH today cannot be carrying one. These rules fire only on a corpus that
already has no graph — and such a corpus exists. `3d-attention-bias` authors `sci:tests` from
`inquiry` and `workflow` subjects, which the relation model does not admit; `materialize_graph`
has been raising there, and `validate` said nothing. That is the failure this check exists for, so
finding it is the check working, not the check misfiring. "No project fails today" is a property of
the corpus, never a property of a rule, and a check whose value is argued from it has no value.

ONE OVERLAP, STATED RATHER THAN ENGINEERED AWAY: a relation endpoint that resolves NOWHERE is also
reported by the graph audit (`graph`, ERROR, `unresolved_reference`), which owns references of every
shape, not just relations. So a truly dangling endpoint draws two findings. That is a cosmetic cost,
and the alternative — teaching this check to stay silent about a defect the graph builder refuses —
is exactly the narrowing that put six defects in the module this one replaces. An authority that
reads a subset of what it validates does not validate.
"""

from __future__ import annotations

from collections.abc import Iterator

from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.graph.relation_audit import audit_relations
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


SECTION, RULES = declare_validation_rules(
    section_id="relations",
    section_title="relations",
    section_order=156,
    rule_ids=(
        "relation.cycle",
        "relation.external-target",
        "relation.illegal-kind-pair",
        "relation.membership-role",
        "relation.self-referential",
        "relation.unknown-object",
        "relation.unknown-predicate",
        "relation.unknown-subject",
        "relation.unsupported-graph-layer",
    ),
    severities=frozenset({"error", "warn", "info"}),
)

RELATION_RULES = {
    "unknown-subject": RULES["relation.unknown-subject"],
    "unknown-object": RULES["relation.unknown-object"],
    "unknown-predicate": RULES["relation.unknown-predicate"],
    "unsupported-graph-layer": RULES["relation.unsupported-graph-layer"],
    "external-target": RULES["relation.external-target"],
    "self-referential": RULES["relation.self-referential"],
    "illegal-kind-pair": RULES["relation.illegal-kind-pair"],
    "membership-role": RULES["relation.membership-role"],
    "cycle": RULES["relation.cycle"],
}


@Check(section=SECTION, order=28, producer_id="validate.relations", rules=tuple(RULES.values()))
def check_authored_relations(ctx: ValidateContext) -> Iterator[CheckObservation]:
    audit = audit_relations(ctx.project_root, ctx.project_sources())

    for defect in audit.defects:
        yield validation_observation(
            severity=Severity.ERROR,
            path=ctx.project_root / defect.path,
            line=None,
            message=defect.message,
            rule=RELATION_RULES[defect.code],
            task=None,
            qualifiers={
                "key": [defect.subject, defect.predicate, defect.object],
            },
        )
