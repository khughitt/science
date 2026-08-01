"""Context-budget boundary guards (slice 1a).

Scope is DERIVED: guard 1 walks the live Click tree, so a new command fails until
classified; guard 2 locates each budgeted command's own callback in the AST rather than
grepping its module.

Known gap, stated rather than hidden: guard 2 proves the callback CONSTRUCTS a sink, not
that every branch inside it routes through one. ``tests/test_budget_regression.py`` is
what checks actual emitted sizes, and Task 11 Step 5 carries a grep for stray
``console.print`` / ``click.echo`` in the health renderer. This is a ratchet, not a
sandbox -- the same candid limit ``test_output_boundary.py`` documents.
"""

from __future__ import annotations

import ast
import inspect

import click

from science_tool.budget.registry import BUDGETS, DEFERRED, EXEMPTIONS
from science_tool.cli import main

EXPECTED_CLASSIFICATION_COUNTS = {
    "budgeted": 69,
    "exempt": 122,
    "deferred": 103,
}


def _leaf_commands(cmd: click.Command, path: list[str]) -> list[tuple[str, click.Command]]:
    if isinstance(cmd, click.Group):
        found: list[tuple[str, click.Command]] = []
        for name, sub in sorted(cmd.commands.items()):
            found.extend(_leaf_commands(sub, [*path, name]))
        return found
    return [(" ".join(path), cmd)]


def test_every_leaf_command_is_classified() -> None:
    """Every command is budgeted, exempt, or explicitly deferred -- no silent third state."""
    live = {path for path, _ in _leaf_commands(main, [])}
    classified = set(BUDGETS) | set(EXEMPTIONS) | set(DEFERRED)
    unclassified = sorted(live - classified)
    assert not unclassified, (
        f"{len(unclassified)} command(s) carry no budget, exemption, or deferral:\n  "
        + "\n  ".join(unclassified)
        + "\n\nAdd a CommandBudget (wired), an EXEMPTIONS reason (cannot grow), or a "
        "DeferredCommand (measured over budget, wiring scheduled)."
    )
    stale = sorted(classified - live)
    assert not stale, "Classification tables name commands absent from the live CLI tree:\n  " + "\n  ".join(stale)


def test_classification_partition_has_the_audited_cardinality() -> None:
    """Lock the audited partition, not only its absence of unclassified leaves.

    Task 1 supplied 4 budgeted, 3 exempt, and 11 deferred paths. Task 13's RED
    surfaced 258 more, classified as 65 exempt and 193 deferred. Review then
    corrected tasks summary from exempt to deferred because its distinct type/group
    keys are unbounded. The post-merge belief-basis command adds one deferred leaf
    because compare mode emits one row per changed entity. The skills coverage
    command adds one deferred leaf because its report grows with registered projects,
    occurrences, diagnostics, candidates, and skipped projects. Slice 1b-1 then wired
    six ROWS offenders (entity list, feedback list, questions/interpretations/
    discussions list, entity needs-review), moving them from deferred to budgeted. The
    autonomy path-gate command adds one deferred leaf because it emits one row per
    denial, which grows with the run's change set. Slice 1b-2 then wired curate
    inventory (DOCUMENT), prose lint (REPORT), curate consolidation-candidates
    (REPORT), and validate (REPORT), moving four more deferred leaves to budgeted. The
    2026-07-25 slice 1b-3 audit then reclassified 44 commands from deferred to exempt
    (fixed-shape output), leaving 154 deferred. Slice 1b-3 batch W1a then wired the 11
    graph ROWS summary commands (attention-rank, attention-sample, audit, dashboard-
    summary, diff, gaps, inquiry-summary, neighborhood-summary, question-summary,
    rehoming-debt, uncertainty), moving them from deferred to budgeted. Batch W1b then
    wired 9 more ROWS-via-emit-query-rows commands (datasets files/search/validate,
    entity rotation, feedback regression-candidates/targets, inquiry list, project
    index, tasks archive), moving them from deferred to budgeted. Batch W2 then wired 7
    more ROWS-via-emit commands (annotate promote, big-picture resolve-questions,
    book-split, dataset reconcile-links, qa-audit, skills lint, tasks blockers), moving
    them from deferred to budgeted. Batch W3 then wired 7 of its 8 candidate ROWS-via-
    echo commands (annotate list, big-picture validate, dataset register-run, datasets
    download, research-package build, sync projects, tasks fix-blockers), moving them
    from deferred to budgeted; `feedback add` was DROPPED from the batch and stays
    deferred -- its only growable output is `find_similar_open`'s whole-open-backlog
    fuzzy-duplicate scan, a write-audit-leak shape (a corpus-wide side dump triggered
    by, but not scaling with, the write), scheduled for the separate write-leak plan
    rather than forced into ROWS projection. Batch W4a then wired the first 6 REPORT
    commands (annotate synthesize, benchmark list, dataset prioritize, explore-ideas
    apply/gaps/resolve-anchors), moving them from deferred to budgeted; explore-ideas
    apply needed a bespoke multi-list projector (`explore_ideas_projection.py`) because
    its payload carries several independently growable lists (created/to_create,
    skipped_applied, skipped_other, manual, folds, failures) at once, while the other
    five fit the shared summary+one-list `project_single_list_report` helper. Batch W4b
    then wired 7 more REPORT commands (dag audit/validate, inquiry show/validate, peers
    list, refs check, research-package validate), moving them from deferred to budgeted.
    dag audit needed a bespoke projector (`dag/audit_projection.py`) for its two
    independently growable lists (validation.findings, nested; mutations, top-level);
    inquiry show needed one (`inquiry_show_projection.py`) for four independently
    growable lists (related, boundary_in, boundary_out, edges); refs check needed one
    (`refs_projection.py`) for its two independently growable lists (broken, markers).
    dag validate, peers list, and research-package validate fit the shared
    summary+one-list `project_single_list_report` helper; inquiry validate was
    restructured from a bare JSON list into a summary+one-list `results` payload to fit
    the same helper. Batch W4c then wired 6 of its 7 candidate REPORT commands (sync
    run/rebuild/status, tasks summary, wander, project topic-coverage), moving them from
    deferred to budgeted; sync run/rebuild/status and project topic-coverage fit the
    shared summary+one-list `project_single_list_report` helper (drift_warnings, pruned,
    projects, and topics respectively), while tasks summary needed a bespoke projector
    (`tasks_summary_projection.py`) for its four independently growable breakdown
    mappings (by_status, by_type, by_priority, by_group). `commons promote dataset` was
    DROPPED from the batch and stays deferred: its shared `_promote_kind_cmd`
    implementation is a multi-branch narrative of `click.echo` calls with no existing
    JSON payload, and the AST sink-ownership guard requires `BoundedSink` construction
    inside the registered command's own callback -- retrofitting a structured payload
    across five early-return branches of a side-effecting (git-committing) promote
    workflow is a bigger, riskier change than this wiring batch, so it is left for a
    dedicated follow-up. Batch W5 then wired the final DOCUMENT command, `inquiry
    export-pgmpy`, routing its generated script through a `BoundedSink` that refuses
    past budget on stdout and writes the complete script to `--output`; `inquiry
    export-chirho` was left deferred (unwired). The write-audit-leak fix then closed
    the side channel `feedback add` was dropped from W3 for, and generalized the
    `dataset verify-access` precedent (fb-2026-06-28-015) to the rest of the entity/
    dataset write surface: `emit_entity_warnings`/`summarize_preexisting_warnings`
    (science_tool.output) now summarize -- rather than dump -- pre-existing whole-
    corpus audit warnings by default on `entity create/edit/note`, `entities import`,
    and `dataset add/verify-access` (each gaining `--show-preexisting` to list them),
    while `feedback add` caps its near-duplicate scan to the top
    `_SIMILAR_NEIGHBORS_DISPLAY_LIMIT` entries plus a count; this moved all 7 from
    deferred to exempt, taking the partition to 68/118/93 = 279.

    The autonomy supervisor then added two deferred leaves: `autonomy start` emits one
    fixed summary record, and `autonomy finish` emits one row per basis delta, gate
    denial, and commit-mark issue. The task-storage migrator adds one budgeted ROWS
    leaf, then retiring `tasks archive` removes its former budgeted leaf. That leaves
    the partition at 68/118/95 = 281.

    Batch R then added `explore-ideas seed-coverage` (fb-2026-07-25-004), BUDGETED
    rather than exempt: it carries the same per-topic `topics` list as `project
    topic-coverage`, so it grows with the project's topic count. `entity kinds` and
    `project spec-path` add two exempt leaves, taking the partition to 69/120/95 = 284.

    The coding-agent support work then added two exempt leaves. `agents generate`
    reports only the generated skill and OpenCode-command counts, while `agents
    install` reports only installed and already-current link counts. Both counts are
    bounded by the toolkit's shipped distribution rather than project size, taking the
    partition to 69/122/95 = 286.

    The VCS storage boundary then adds three deferred
    leaves: `boundary check` emits one warning per unanchored unmanaged rule, `boundary
    init` emits one proposal entry per discovered candidate root, and `boundary sync
    --verify-current-tree` emits one row per changed filesystem or synthetic-probe ignore
    decision, taking the partition to 69/122/98 = 289.

    The audit-case command family adds two deferred leaves. `findings list` emits one
    row per stored audit case, while `findings ingest` can emit untrusted validation
    text that grows with the input report. The live partition is therefore
    69/122/100 = 291.

    Skill-coverage curation then adds one deferred leaf. `skills curate` emits one
    row per uncovered candidate and can include growable occurrence evidence and
    skipped-project context, taking the live partition to 69/122/101 = 292.

    Finding Convergence Plan 3 then adds `findings migrate-acceptances` as one
    deferred leaf: its `entries` payload has one output row per configured
    validation acceptance, taking the partition to 69/122/102 = 293. Validation
    sidecar retirement removes the fixed-output `project artifacts
    port-validate-sidecar` leaf and its exemption, leaving the live partition at
        69/121/102 = 292. Evidence Broker Plan 3 then adds the fixed four-field
        `evidence serve` receipt as one exempt leaf; served bytes never reach stdout and
        its target/path strings are model-bounded, taking the partition to
        69/122/102 = 293.
    """
    actual = {
        "budgeted": len(BUDGETS),
        "exempt": len(EXEMPTIONS),
        "deferred": len(DEFERRED),
    }
    assert actual == EXPECTED_CLASSIFICATION_COUNTS
    assert sum(actual.values()) == len(_leaf_commands(main, []))


def test_findings_ingest_is_deferred_because_validation_text_can_grow():
    assert "findings ingest" not in EXEMPTIONS
    assert "validation" in DEFERRED["findings ingest"].growth_reason
    assert "report" in DEFERRED["findings ingest"].growth_reason


def test_acceptance_migration_is_deferred_because_entries_can_grow() -> None:
    command = "findings migrate-acceptances"
    assert command not in EXEMPTIONS
    assert "acceptance" in DEFERRED[command].growth_reason


def test_belief_basis_is_deferred_because_compare_emits_one_row_per_delta() -> None:
    assert "graph belief-basis" in DEFERRED


def _callback_source(cmd: click.Command) -> str | None:
    callback = cmd.callback
    if callback is None:
        return None
    unwrapped = inspect.unwrap(callback)
    try:
        return inspect.getsource(unwrapped)
    except (OSError, TypeError):
        return None


_NESTED_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def _callback_constructs_bounded_sink(source: str) -> bool:
    """Whether the callback body itself constructs a sink.

    Calls inside a nested function, lambda, or class belong to that nested scope and
    cannot establish that the Click callback owns its payload channel.
    """
    tree = ast.parse(inspect.cleandoc(source))
    callbacks = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if len(callbacks) != 1:
        return False

    def _owned_nodes(node: ast.AST):
        if isinstance(node, _NESTED_SCOPES):
            return
        yield node
        for child in ast.iter_child_nodes(node):
            yield from _owned_nodes(child)

    return any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "BoundedSink"
        for statement in callbacks[0].body
        for node in _owned_nodes(statement)
    )


def test_nested_sink_construction_does_not_establish_callback_ownership() -> None:
    source = """
def callback() -> None:
    def nested() -> None:
        BoundedSink(None)

    deferred = lambda: BoundedSink(None)

    class Factory:
        sink = BoundedSink(None)
"""
    assert _callback_constructs_bounded_sink(source) is False


def test_every_budgeted_command_constructs_its_own_sink() -> None:
    by_path = dict(_leaf_commands(main, []))
    missing: list[str] = []
    for command_path in sorted(BUDGETS):
        cmd = by_path.get(command_path)
        if cmd is None:
            missing.append(f"{command_path} (absent from the CLI tree)")
            continue
        source = _callback_source(cmd)
        if source is None:
            missing.append(f"{command_path} (callback source unavailable)")
            continue
        if not _callback_constructs_bounded_sink(source):
            missing.append(command_path)
    assert not missing, "Budgeted commands whose callback never constructs a BoundedSink:\n  " + "\n  ".join(missing)


def test_every_budgeted_command_offers_the_output_escape() -> None:
    by_path = dict(_leaf_commands(main, []))
    missing = [
        path
        for path in sorted(BUDGETS)
        if by_path.get(path) is None
        or not any("--output" in param.opts for param in by_path[path].params if isinstance(param, click.Option))
    ]
    assert not missing, "Budgeted commands with no --output escape:\n  " + "\n  ".join(missing)


def test_deferred_commands_are_real_cli_commands() -> None:
    known = {path for path, _ in _leaf_commands(main, [])}
    stale = sorted(set(DEFERRED) - known)
    assert not stale, "DEFERRED names commands that no longer exist:\n  " + "\n  ".join(stale)
