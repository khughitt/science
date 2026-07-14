"""The supersession lineage, as `validate` sees it — every outcome that BLOCKS, and the one that WARNS.

`mark_superseded` refuses all three of these, but it is an **opt-in** command: a corpus can carry a
broken lineage indefinitely without anyone ever running it. `validate` is the pass everyone runs, so
what blocks the operation has to be visible here too, or it is visible nowhere.

TWO SEVERITY TIERS, ON TWO DIFFERENT AXES — and conflating them is the whole lesson of the
status-vocabulary incident (severity graded on the wrong axis):

* `supersession.self-referential` / `supersession.illegal-kind-pair` are **ERROR**, and their names
  are **FLAT**. These are RELATION-VALIDITY failures: `materialize` *raises* on both (`ValueError:
  self-referential authored relation`, and the endpoint check), so a corpus carrying either cannot
  build a graph AT ALL. That verdict is handed down by the relation model, which already says which
  pairs are legal — it owes nothing to any per-kind status certification, so these must NOT wait on
  Task 12's ratchet and must NOT be kind-scoped. They are the same defect whatever kind authors them.

* `<kind>.unbacked-inverse` is **WARN**, and its name IS kind-scoped. That one is about a *status
  vocabulary* — whether a kind's `superseded` terminal is certified — and `gated_findings` filters on
  `Result.rule` **alone**, never on severity. A single generic `supersession.unbacked-inverse` in a
  gate tier would gate every UNCERTIFIED kind's findings too, promoting the whole vocabulary the
  moment one kind earned it. Kind-scoped names let the gate advance one certified kind at a time.
  Task 12 owes the flip to `severity_for_kind(kind)`.

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

    # THE EDGES THAT ARE NOT EDGES -- reported against the file that AUTHORED them, which is the
    # superseder: the target may be archived, or a commons record with no file in this project at
    # all, but the edge is a line in the superseder's own frontmatter and that is where it is fixed.
    for bad in graph.self_referential:
        yield Result(
            Severity.ERROR,
            graph.path_by_id[bad["superseder"]],
            None,
            f"sci:supersedes {bad['id']}: {bad['reason']}",
            "supersession.self-referential",
            None,
        )
    for bad in graph.mismatched:
        yield Result(
            Severity.ERROR,
            graph.path_by_id[bad["superseder"]],
            None,
            f"sci:supersedes {bad['id']}: {bad['reason']}",
            "supersession.illegal-kind-pair",
            None,
        )

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
