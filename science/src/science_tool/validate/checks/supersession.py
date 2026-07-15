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

from science_tool.consolidation import build_supersedes_graph, load_supersession_inputs
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.kind_severity import severity_for_kind
from science_tool.validate.result import Result


@Check(section="supersession lineage", order=29)
def check_supersession(ctx: ValidateContext) -> Iterator[Result]:
    graph = build_supersedes_graph(load_supersession_inputs(ctx.project_root))

    for unbacked in graph.unbacked_inverses:
        entity_id = unbacked["id"]
        kind = graph.kind_by_id[entity_id]
        yield Result(
            # PER FINDING -- `severity_for_kind(kind)`, not `severity_for_kind("hypothesis")`: this
            # emitter fires for EVERY kind, and only the certified ones may ERROR. `hypothesis` is
            # certified, so its unbacked inverses are ERROR and gated. The four live NON-hypothesis
            # records (one `3d-attention-bias` interpretation, three `natural-systems`) stay WARN and
            # ungated: their real lineage is written in the WITHDRAWN top-level `supersedes:` spelling
            # the Entity model silently drops, an uncertified kind's defect with no migration yet.
            severity_for_kind(kind),
            # `Result` reports a FILE -- it has no `entity_id` field -- which is why the graph
            # carries `path_by_id`: the check must not re-derive the canonicalization that produced
            # the key it looks up. An inverse is a field on a RECORD, not an edge in a carrier file,
            # so this one is located by id and not by `source_path`.
            graph.path_by_id[entity_id],
            None,
            f"superseded_by: {unbacked['superseder']} has no canonical sci:supersedes edge behind "
            f"it; author the edge on {unbacked['superseder']} or drop the field",
            f"{kind}.unbacked-inverse",
            None,
        )
