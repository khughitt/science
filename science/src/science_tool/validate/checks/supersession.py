"""The one supersession outcome `validate` OWNS: an authored inverse with no edge behind it.

`superseded_by` is a PROJECTION of an authored `sci:supersedes` edge. A record that carries one with
no edge behind it is a record whose lineage claim is grounded in nothing — and nothing else catches
it: JSON Schema sees a non-empty string, `check_resolution` sees an id that resolves, and
reconciliation never looks, because the record is in no chain (there is no edge). Four nets, zero
coverage, for the exact failure that top-level `supersedes:` was withdrawn to prevent.

THIS CHECK IS DELIBERATELY SMALL. It used to also report self-edges, illegal kind pairs and lineage
cycles — RELATION-VALIDITY failures, which is to say: the graph builder's verdict, restated in a
hand-written ladder that turned out to be narrower than the builder six times running. Those live in
`relations.py` now, where they are asked once, by `materialize`'s own admission, over the whole
authored-relation stream. What is left here is the only question that is actually about a STATUS
VOCABULARY, and it is this module's alone:

    the record says it was superseded — by an edge that does not exist.

KIND-SCOPED, and KIND-GRADED via `severity_for_kind(kind)` — the other axis entirely, and conflating
the two is the whole lesson of the status-vocabulary incident (severity graded on the wrong axis).
`gated_findings` filters on `Result.rule` **alone**, never on severity, so a single generic
`supersession.unbacked-inverse` in a gate tier would gate every UNCERTIFIED kind's findings too,
promoting the whole vocabulary the moment one kind earned it. Kind-scoped names let the gate advance
one certified kind at a time: `hypothesis.unbacked-inverse` is gated (and ERROR), every other kind's
is a WARN that gates nothing.

IT CONSUMES THE GRAPH; it does not re-derive edges. `build_supersedes_graph` reads the audit's
admitted edges, and a check that recomputed them could disagree with the thing it is checking.
"""

from __future__ import annotations

from collections.abc import Iterator

from science_model.audit import FindingRule

from science_tool.validate.findings import validation_observation
from science_tool.consolidation import build_supersedes_graph, load_supersession_inputs
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.findings import (
    ValidationQualifiers,
    declare_validation_rules,
    rule_kind_segment,
)
from science_tool.validate.kind_severity import severity_for_kind


SECTION, RULES = declare_validation_rules(
    section_id="supersession",
    section_title="supersession",
    section_order=157,
    rule_ids=(),
    severities=frozenset({"error", "warn", "info"}),
)


def supersession_rules(active_kinds: frozenset[str]) -> tuple[FindingRule, ...]:
    segments = [rule_kind_segment(kind) for kind in active_kinds]
    if len(segments) != len(set(segments)):
        raise ValueError("active kind names collide after kebab rule normalization")
    return tuple(
        supersession_rule(kind, display_order=SECTION.section_order * 100 + index)
        for index, kind in enumerate(sorted(active_kinds), start=1)
    )


def supersession_rule(
    kind: str,
    *,
    display_order: int | None = None,
) -> FindingRule:
    return FindingRule(
        id=f"{rule_kind_segment(kind)}.unbacked-inverse",
        severities=frozenset({severity_for_kind(kind).value}),
        subject_types=frozenset({"path"}),
        qualifier_schema=ValidationQualifiers,
        identity_qualifiers=("key",),
        title=f"{kind} unbacked inverse",
        section=SECTION.id,
        display_order=display_order or SECTION.section_order * 100 + 1,
        default_visibility="visible",
    )


@Check(
    section=SECTION,
    order=29,
    producer_id="validate.supersession",
    rules=tuple(RULES.values()),
    kind_rule_factory=supersession_rules,
)
def check_supersession(ctx: ValidateContext) -> Iterator[CheckObservation]:
    graph = build_supersedes_graph(
        load_supersession_inputs(
            ctx.project_root,
            sources=ctx.project_sources(),
        )
    )

    for unbacked in graph.unbacked_inverses:
        entity_id = unbacked["id"]
        kind = graph.kind_by_id[entity_id]
        yield validation_observation(
            severity=severity_for_kind(kind),
            path=graph.path_by_id[entity_id],
            line=None,
            message=f"superseded_by: {unbacked['superseder']} has no canonical sci:supersedes edge behind it; author the edge on {unbacked['superseder']} or drop the field",
            rule=supersession_rule(kind),
            task=None,
            qualifiers={"key": []},
        )
