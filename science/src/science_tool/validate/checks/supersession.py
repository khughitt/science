"""The supersession lineage, as `validate` sees it — the outcomes it OWNS.

`mark_superseded` refuses every one of these, but it is an **opt-in** command: a corpus can carry a
broken lineage indefinitely without anyone ever running it. `validate` is the pass everyone runs, so
what blocks the operation has to be visible here too, or it is visible nowhere.

WHAT THIS CHECK DOES *NOT* CLAIM: it is not the whole blocking set. `mark_superseded` also blocks on
an endpoint that resolves nowhere, and that one is **already owned** — the graph audit reports it
(`graph`, ERROR, `unresolved_reference ... subject -> <id>`) for every authored relation in the
project. Re-reporting it here would put two voices on one defect. Two authorities, one rule each.

TWO SEVERITY TIERS, ON TWO DIFFERENT AXES — and conflating them is the whole lesson of the
status-vocabulary incident (severity graded on the wrong axis):

* `supersession.self-referential`, `supersession.illegal-kind-pair` and `supersession.cycle` are
  **ERROR**, and their names are **FLAT**. These are RELATION-VALIDITY failures: `materialize`
  *raises* on all three (`self-referential authored relation`, the endpoint check, and
  `cycle in amendment/supersession relations`), so a corpus carrying any of them cannot build a
  graph AT ALL. That verdict is handed down by the relation model, which already says which pairs
  are legal and that the lineage is acyclic — it owes nothing to any per-kind status certification,
  so these must NOT wait on Task 12's ratchet and must NOT be kind-scoped. They are the same defect
  whatever kind authors them.

* `<kind>.unbacked-inverse` is **WARN**, and its name IS kind-scoped. That one is about a *status
  vocabulary* — whether a kind's `superseded` terminal is certified — and `gated_findings` filters on
  `Result.rule` **alone**, never on severity. A single generic `supersession.unbacked-inverse` in a
  gate tier would gate every UNCERTIFIED kind's findings too, promoting the whole vocabulary the
  moment one kind earned it. Kind-scoped names let the gate advance one certified kind at a time.
  Task 12 owes the flip to `severity_for_kind(kind)`.

A cycle is reported ONCE PER AUTHORED EDGE, against the file that authored it, because breaking any
edge on the cycle breaks the cycle — there is no single "offending" one to blame.

KNOWN GAP, stated rather than papered over: a self-edge or an illegal endpoint on a bare `sci:amends`
relation also refuses to materialize, and nothing reports it. `amends` reaches this module only
through the ACYCLICITY question, which `materialize` asks of the two predicates jointly. Its
per-edge validity is a different check's to own — and the general form of that check ("every
authored relation materializes") would subsume all three ERROR rules here.

IT CONSUMES THE GRAPH; it does not re-derive edges. `build_supersedes_graph` is the sole authority on
what an edge is, and a check that recomputed them could disagree with the thing it is checking.
"""

from __future__ import annotations

from collections.abc import Iterator

from science_tool.consolidation import build_supersedes_graph, load_supersession_inputs
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


@Check(section="supersession lineage", order=29)
def check_supersession(ctx: ValidateContext) -> Iterator[Result]:
    graph = build_supersedes_graph(load_supersession_inputs(ctx.project_root))

    # THE EDGES THAT ARE NOT EDGES -- reported against the file that AUTHORED them, which is NOT
    # necessarily the superseder's markdown: `relations.yaml` carries edges whose subject may have no
    # markdown record in this project at all. `path` comes off `SourceRelation.source_path`, so the
    # finding always names a file with the offending line in it. The message names the SUBJECT for
    # the same reason -- one `relations.yaml` holds many edges, and "the file" is not the locator.
    for rule, outcomes in (
        ("supersession.self-referential", graph.self_referential),
        ("supersession.illegal-kind-pair", graph.mismatched),
        ("supersession.cycle", graph.cycles),
    ):
        for bad in outcomes:
            yield Result(
                Severity.ERROR,
                ctx.project_root / bad["path"],
                None,
                f"{bad['superseder']} -> {bad['id']}: {bad['reason']}",
                rule,
                None,
            )

    for unbacked in graph.unbacked_inverses:
        entity_id = unbacked["id"]
        kind = graph.kind_by_id[entity_id]
        yield Result(
            # WARN, and Task 12 owes the flip to `severity_for_kind(kind)`. Severity is EARNED:
            # this phase changes no meaning -- and the corpus is NOT clean here. Four live records
            # (one `3d-attention-bias` interpretation, three `natural-systems`) author a
            # `superseded_by` with no edge behind it, because their real lineage is written in the
            # WITHDRAWN top-level `supersedes:` spelling the Entity model silently drops. That is
            # this rule's finding, on disk, today -- and Task 9's migration input. ERROR would break
            # `validate` in two projects for a defect they have no migration for yet.
            Severity.WARN,
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
