"""`<kind>.unbacked-inverse` — a `superseded_by` with no canonical edge behind it.

`mark_superseded` blocks on an unbacked inverse, but it is an **opt-in** command: a corpus can carry
a groundless lineage indefinitely without anyone ever running it. `validate` is the pass everyone
runs.

THE RULE NAME IS KIND-SCOPED — `hypothesis.unbacked-inverse`, `interpretation.unbacked-inverse` —
and not for symmetry's sake. `gated_findings` filters on `Result.rule` **alone**; it never looks at
severity. So a single generic `supersession.unbacked-inverse` placed in a gate tier would gate the
findings of every UNCERTIFIED kind too, promoting the whole vocabulary the moment one kind earned
it. That is precisely the status-vocabulary incident: severity graded on the wrong axis. Kind-scoped
names let the gate advance one certified kind at a time.

IT CONSUMES THE GRAPH; it does not re-derive edges. `build_supersedes_graph` is the sole authority on
what an edge is, and a check that recomputed them could disagree with the thing it is checking.
"""

from __future__ import annotations

from collections.abc import Iterator

from science_tool.consolidation import (
    _id_resolution,
    build_supersedes_graph,
    iter_entity_frontmatter,
)
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


@Check(section="supersession lineage", order=29)
def check_supersession(ctx: ValidateContext) -> Iterator[Result]:
    entries = iter_entity_frontmatter(ctx.project_root)
    graph = build_supersedes_graph(entries, _id_resolution(ctx.project_root, entries))

    for unbacked in graph.unbacked_inverses:
        entity_id = unbacked["id"]
        kind = graph.kind_by_id[entity_id]
        yield Result(
            # WARN, and Task 12 owes the flip to `severity_for_kind(kind)`. Severity is EARNED:
            # this phase changes no meaning. The certified roster authors zero `superseded_by`
            # today, so the WARN tier is not a concession to a noisy corpus -- it exists to catch a
            # corpus that has MOVED since the roster was derived.
            Severity.WARN,
            # `Result` reports a FILE -- it has no `entity_id` field -- which is why the graph
            # carries `path_by_id`: the check must not re-derive the canonicalization that produced
            # the key it looks up.
            graph.path_by_id[entity_id],
            None,
            f"superseded_by: {unbacked['superseder']} has no canonical sci:supersedes edge behind "
            f"it; author the edge on {unbacked['superseder']} or drop the field",
            f"{kind}.unbacked-inverse",
            None,
        )
