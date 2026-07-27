"""Single source of truth for per-command output ceilings and payload shapes.

Ceilings are in *visible* characters (ANSI stripped) at ``BUDGET_CONSOLE_WIDTH``. Values
come from the 2026-07-24 audit of ``~/d/natural-systems``, the largest adopting project.

Three tables, deliberately distinct:

- ``BUDGETS``   -- wired: the command owns a sink and honours a ceiling.
- ``EXEMPTIONS``-- a claim that the command's output CANNOT grow with project size.
- ``DEFERRED``  -- CAN grow with project size, not yet wired.

``DEFERRED`` is defined by growability, not by current size. An earlier draft required a
measurement above 20k, which left no truthful home for a command that grows but happens
to be small today -- ``tasks archive`` emits one row per archivable task
(``tasks_cli.py:333``) yet measures tiny on a freshly-archived project. Calling that
exempt would assert something false. Every non-budgeted command therefore carries a
justification string either way: ``EXEMPTIONS`` says why it cannot grow, ``DEFERRED``
says what makes it grow.

A command's OWN output growing with project size is not the only way it can leak: seven
write/action commands were reclassified ``DEFERRED`` -> ``EXEMPTIONS`` once a *side
channel* -- whole-corpus pre-existing audit warnings, or an uncapped near-duplicate scan
-- was bounded instead (slice 1b-3 write-audit-leak fix), so growability has to be
checked through every channel a command echoes, not just its primary payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from science_tool.cli_retirement import RETIREMENTS


class PayloadShape(StrEnum):
    """How a command's payload may be narrowed.

    ``ROWS``     -- a flat row list; project by dropping rows.
    ``REPORT``   -- a heterogeneous multi-section report; project per section.
    ``DOCUMENT`` -- a versioned document; REFUSE past budget, never partially emit.
    """

    ROWS = "rows"
    REPORT = "report"
    DOCUMENT = "document"


@dataclass(frozen=True)
class CommandBudget:
    max_chars: int
    shape: PayloadShape
    max_rows: int | None = None


@dataclass(frozen=True)
class DeferredCommand:
    """A command whose output grows with project size but is not yet wired.

    ``growth_reason`` states WHAT makes it grow -- the mirror of an exemption's reason.
    ``measured_chars`` records an observation, not a threshold for admission.
    """

    growth_reason: str
    target_slice: str
    measured_chars: int | None = None


BUDGETS: dict[str, CommandBudget] = {
    "tasks list": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "health": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
    "entities inventory": CommandBudget(max_chars=20_000, shape=PayloadShape.DOCUMENT),
    "data audit": CommandBudget(max_chars=20_000, shape=PayloadShape.DOCUMENT),
    "entity list": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "feedback list": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=20),
    "questions list": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "interpretations list": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "discussions list": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "entity needs-review": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "curate inventory": CommandBudget(max_chars=20_000, shape=PayloadShape.DOCUMENT),
    "prose lint": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
    "curate consolidation-candidates": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
    "validate": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
    "graph attention-rank": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "graph attention-sample": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "graph audit": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "graph dashboard-summary": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "graph diff": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "graph gaps": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "graph inquiry-summary": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "graph neighborhood-summary": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "graph question-summary": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "graph rehoming-debt": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "graph uncertainty": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "datasets files": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "datasets search": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "datasets validate": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "entity rotation": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "feedback regression-candidates": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "feedback targets": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "inquiry list": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "inquiry export-pgmpy": CommandBudget(max_chars=20_000, shape=PayloadShape.DOCUMENT),
    "project index": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "tasks archive": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "annotate promote": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "big-picture resolve-questions": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "book-split": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "dataset reconcile-links": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "qa-audit": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "skills lint": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "tasks blockers": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "annotate list": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "big-picture validate": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "dataset register-run": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "datasets download": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "research-package build": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "sync projects": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "tasks fix-blockers": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "annotate synthesize": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
    "benchmark list": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
    "dataset prioritize": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
    "explore-ideas apply": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
    "explore-ideas gaps": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
    "explore-ideas resolve-anchors": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
    "explore-ideas seed-coverage": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
    "dag audit": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
    "dag validate": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
    "inquiry show": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
    "inquiry validate": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
    "peers list": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
    "refs check": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
    "research-package validate": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
    "project topic-coverage": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
    "sync rebuild": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
    "sync run": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
    "sync status": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
    "tasks summary": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
    "wander": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
}

EXEMPTIONS: dict[str, str] = {
    "belief snapshot": "fixed-shape count summary after snapshot persistence",
    "bib add": "fixed-shape single-entry persistence result",
    "big-picture synthesis-path": "single resolved path",
    "commons data resolve": "fixed-shape single-resolution record",
    "commons dataset init": "fixed scaffold file set and two fixed next steps",
    "commons init": "single initialization confirmation",
    "commons reference-graph scaffold-member": "fixed-shape single-member scaffold result",
    "dag init": "fixed-shape initialization guidance",
    "dag number": "single completion summary, including all-DAG mode",
    "dag render": "single completion summary, including all-DAG mode",
    "dataset identity show": "fixed-shape identity-context record for one dataset",
    "dataset identity suggest": "fixed-shape identity-context scaffold for one dataset",
    "dataset link": "single link result",
    "dataset migrate-capabilities": "fixed-shape migration count summary",
    "datasets metadata": "fourteen hard-coded metadata fields for one external dataset",
    "distill openalex": "single snapshot-path confirmation",
    "distill pykeen": "single snapshot-path confirmation",
    "entities register-kind": "single registration result",
    "entity review": "single review result",
    "feedback scaffold-test": "three fixed guidance lines for one scaffold",
    "feedback update": "single update confirmation",
    "graph init": "at most three fixed initialization guidance lines",
    "graph stats": "measured 341 chars on 2026-07-24; fixed-shape summary",
    "inquiry import": "single imported-inquiry path",
    "inquiry init": "single scaffold path",
    "labnote export": "single export-path and warning-count summary",
    "paper persist-source": "single persisted-source path",
    "peers show": "five fixed fields for one peer",
    "project artifacts check": "fixed-shape status record for one artifact",
    "project artifacts install": "fixed-shape result with at most one backup path",
    "project artifacts pin": "single pin confirmation",
    "project artifacts port-validate-sidecar": "single generated-sidecar path",
    "project artifacts unpin": "single unpin confirmation",
    "project serialize": "fixed-shape file and payload count summary",
    "questions reserve": "fixed-shape single-reservation result",
    "research-package init": "single scaffold path",
    "tasks add": "single task-creation confirmation",
    "tasks defer": "single task-state confirmation",
    "tasks done": "single task-state confirmation",
    "tasks edit": "single task-edit confirmation",
    "tasks note": "single task-note confirmation",
    "tasks retire": "single task-state confirmation",
    "tasks unblock": "single task-state confirmation",
    "telemetry prune": "one fixed-shape prune summary row",
    "telemetry status": "measured 366 chars on 2026-07-24; fixed-shape summary",
}

# Reclassified from DEFERRED by the 2026-07-25 slice 1b-3 audit
# (docs/plans/2026-07-25-context-budget-1b3-audit.md): fixed-shape output that
# cannot grow with project size.
EXEMPTIONS.update({
    "annotate ack": "single-annotation-ID status mutation (open->ack)",
    "annotate dismiss": "single-annotation-ID status mutation (open->dismissed) via the shared _crud_invoke helper",
    "annotate extract": "single-paper extraction; fixed counts (written/skipped-by-reason/grounding_dropped) plus a note, no per-item loop",
    "annotate fix": "single-annotation-ID status mutation (open->fixed) via the shared _crud_invoke helper",
    "annotate promote-prose-decomposition": "promotes exactly one --unit (required, singular)",
    "annotate pubtator": "single-paper (identifier) PubTator seeding",
    "annotate stats": "aggregated counts by_status/by_source/by_type",
    "benchmark gap-calibration": "output is O(number of --project flags supplied), not project size; each yields one top-10-capped calibration summary",
    "commons dataset build": "Prints exactly one line: `snakemake exited {exit_code}`",
    "commons member-payload": "Resolves exactly one promoted virtual member (member_id) to its payload",
    "commons reference-graph resolve-member": "Resolves one (registry_id, member_key) pair to at most one GraphMemberMatch (or an 'unresolved' status record)",
    "commons show": "Prints exactly one entity by canonical id (optionally merged with one named project's overlay)",
    "dataset reconcile": "diffs at most 3 fixed cached fields between one dataset entity's frontmatter and its one datapackage.yaml",
    "dataset show": "fixed ~8-10 field block for the one resolved dataset entity, plus that entity's own body",
    "datasets hydrate-worktree": "iterates a hardcoded 3-tuple of data dirs (raw/processed/external); always three rows regardless of project size",
    "datasets sources": "enumerates the fixed code-defined set of packaged adapters; grows only when the toolkit ships a new adapter",
    "discussions create": "Echoes exactly one 'Created <id> at <path>' line plus the created entity's own validation warnings (emit_entity_warnings)",
    "discussions show": "Renders one entity's fixed field set (id, kind, title, status, path, related refs, source_refs, body)",
    "doi lookup": "hardcoded <=6-key metadata dict for one DOI (doi/title/publisher/source/issued/url), not a per-record list",
    "entity kinds": "one row per DECLARED kind -- the shipped profiles plus the project's own local manifest -- so it grows with the vocabulary, never with how many entities exist",
    "entity sections": "rows come from the kind's fixed template/schema, not per-entity project data",
    "entity show": "fixed field set for the one entity resolved by ref; related/source_refs are that entity's own authored lists",
    "evidence-lines create": "Echoes exactly one 'Created <id> at <path>' line plus the created entity's own validation warnings",
    "evidence-lines show": "Renders one entity's fixed field set",
    "graph build": "a handful of fixed confirmation lines plus ontology-suggestion lines bounded by the code-shipped ontology registry",
    "graph predicates": "returns the code-defined PREDICATE_REGISTRY verbatim; its docstring states it is not an instrument",
    "graph project-summary": "InstrumentResult with exactly one row -- a single project-wide rollup",
    "graph validate": "a fixed set of ~6 structural check rows (parseable_trig, provenance_completeness, etc.), not one per violation",
    "hypotheses create": "Echoes exactly one 'Created <id> at <path>' line plus the created entity's own validation warnings",
    "hypotheses show": "Renders one entity's fixed field set",
    "interpretations create": "Echoes exactly one 'Created <id> at <path>' line plus the created entity's own validation warnings",
    "interpretations show": "Renders one entity's fixed field set",
    "paper-fetch": "one FetchResult record for a single paper; tiers/errors bounded by the fixed fetch-strategy algorithm, not project size",
    "project artifacts diff": "Unified diff between ONE named artifact's canonical and installed bytes",
    "project artifacts exec": "os.execv() replaces the current process with the canonical artifact's own binary",
    "project artifacts list": "One line per artifact TYPE in the toolkit's static registry.yaml (currently exactly 1: validate.sh)",
    "project artifacts update": "Fixed confirmation for ONE named artifact update: from-version -> to-version, commit status, backup path",
    "project resolve-refs": "Output is one line per --query argument the CALLER supplies (a repeatable option), not per record in the project",
    "project spec-path": "Resolves ONE --slug to one path; the payload is a fixed three-field record (slug, path, layout) or a hard failure",
    "propositions create": "Echoes exactly one 'Created <id> at <path>' line plus the created entity's own validation warnings",
    "propositions show": "Renders one entity's fixed field set",
    "questions create": "Echoes exactly one 'Created <id> at <path>' line plus the created entity's own validation warnings",
    "questions show": "Renders one entity's fixed field set",
    "tasks block": "single task-state-change confirmation: one line naming the task and echoing back the user-supplied --by refs joined with commas",
    "tasks show": "renders one task's fixed fields plus that task's own readiness list -- O(1) in project size",
    "verdict parse": "parses exactly ONE named file argument into a single ParseResult document",
})

# Reclassified from DEFERRED by the 2026-07-26 slice 1b-3 write-audit-leak fix
# (docs/plans/2026-07-25-context-budget-1b3-audit.md, Write-audit-leak section): these
# write/action commands were growable only through a side channel -- pre-existing
# whole-corpus project-audit warnings (`_validate_prospective_write(s)`) or, for
# `feedback add`, an uncapped near-duplicate scan of the whole open backlog -- not
# through their own confirmation output. `emit_entity_warnings`/
# `summarize_preexisting_warnings` (science_tool.output) now summarize the former by
# default (`--show-preexisting` lists it); `feedback add` caps the latter to the top
# `_SIMILAR_NEIGHBORS_DISPLAY_LIMIT` neighbors plus a count. Both make the classification
# true rather than assumed.
EXEMPTIONS.update({
    "dataset add": "O(1) write confirmation; pre-existing audit warnings summarized by default (--show-preexisting to list)",
    "dataset verify-access": "O(1) write confirmation; pre-existing audit warnings summarized by default (--show-preexisting to list)",
    "entities import": "O(1) write confirmation; pre-existing audit warnings summarized by default (--show-preexisting to list)",
    "entity create": "O(1) write confirmation; pre-existing audit warnings summarized by default (--show-preexisting to list)",
    "entity edit": "O(1) write confirmation; pre-existing audit warnings summarized by default (--show-preexisting to list)",
    "entity note": "O(1) write confirmation; pre-existing audit warnings summarized by default (--show-preexisting to list)",
    "feedback add": "O(1) create confirmation; near-duplicate scan capped to top-K + count",
})

# Retired commands are exempt by construction: cli_retirement.RETIREMENTS owns which
# commands are retired, and a fixed error string cannot grow with project size. Listing
# them here as well would make this a second place the retired set could be edited.
#
# Deliberately RETIREMENTS only, not RETIRED_GROUPS: test_budget_boundary asserts that
# every classified path is live, where "live" comes from _leaf_commands -- which recurses
# through groups and yields only non-groups. An entry for `graph add` would fail as a
# table naming a command absent from the CLI tree.
EXEMPTIONS.update(dict.fromkeys(RETIREMENTS, "fixed retired-command error"))

DEFERRED: dict[str, DeferredCommand] = {
    # Growable but small on the audited project -- the case that has no truthful
    # exemption. Populated further by Task 13 Step 3.
    "graph belief-basis": DeferredCommand(
        "compare mode emits one MOVED row per changed pre-existing entity",
        "1b",
    ),
    "autonomy path-gate": DeferredCommand(
        "one output member per denial, which grows with the run's change set",
        "1b",
    ),
    "autonomy start": DeferredCommand(
        "one fixed summary record per invocation",
        "1b",
    ),
    "autonomy finish": DeferredCommand(
        "one output member per basis delta, gate denial, and commit-mark issue",
        "1b",
    ),
    "boundary check": DeferredCommand(
        "one warning per unanchored unmanaged ignore rule; the warning list is uncapped",
        "1b",
    ),
    "boundary init": DeferredCommand(
        "one proposal entry per discovered candidate root",
        "1b",
    ),
    "boundary sync": DeferredCommand(
        "--verify-current-tree emits one row per changed filesystem or synthetic-probe ignore decision",
        "1b",
    ),
}

DEFERRED.update(
    {
        path: DeferredCommand(
            "one output member per annotation, source, decomposition unit, "
            "reconciliation action, path, or diagnostic",
            "1b",
        )
        for path in (
            "annotate apply-proposition-reconciliation",
            "annotate apply-proposition-resynthesis",
            "annotate apply-prose-promotion-plan",
            "annotate archive-superseded-propositions",
            "annotate audit",
            "annotate build-prose-health",
            "annotate check-prose-decomposition",
            "annotate cross-paper-evidence",
            "annotate ground-prose-decomposition",
            "annotate ingest-prose-decomposition",
            "annotate lift-tokens",
            "annotate plan-proposition-reconciliation",
            "annotate plan-prose-promotions",
            "annotate reconcile-propositions",
            "annotate record-proposition-reconciliation-decisions",
            "annotate resynthesis-draft-context",
            "annotate scaffold-proposition-resynthesis",
            "annotate validate-proposition-reconciliation",
            "annotate validate-proposition-resynthesis",
            "annotate validate-prose-decomposition-artifact",
            "annotate verify",
        )
    }
)
DEFERRED.update(
    {
        "belief profile": DeferredCommand("one row per belief-bearing entity", "1b"),
        "markers scan": DeferredCommand("one row per marker hit and token", "1b"),
        "search": DeferredCommand("one row per matching project record", "1b"),
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one row per benchmark, test, gap, candidate, or calibration bucket", "1b")
        for path in (
            "benchmark gaps",
            "benchmark hint-candidates",
            "benchmark opportunities",
            "benchmark test-triage",
            "benchmark tests",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one row per question, cluster, knowledge gap, or validation finding", "1b")
        for path in (
            "big-picture cluster-digests",
            "big-picture knowledge-gaps",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand(
            "one output member per commons entity, resource, finding, promotion action, "
            "or delegated build event",
            "1b",
        )
        for path in (
            "commons dataset status",
            "commons dataset validate",
            "commons find",
            "commons index rebuild",
            "commons inventory",
            "commons list",
            "commons promote dataset",
            "commons promote paper",
            "commons promote theme",
            "commons promote topic",
            "commons validate",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per DAG finding, mutation, changed path, or diff line", "1b")
        for path in (
            "dag apply-workbench",
            "dag workbench",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per dataset, consumer, capability, link, resource, run, or warning", "1b")
        for path in (
            "dataset capability-pairs",
            "dataset consumers",
            "dataset identity resolve",
            "dataset list",
            "dataset stochasticity",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per external dataset, file, resource, schema field, QA result, or adapter", "1b")
        for path in (
            "datasets infer-schema",
            "datasets qa",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per typed entity reference warning, field, or body element", "1b")
        for path in (
            "evidence-lines list",
            "hypotheses list",
            "propositions list",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per entity, archive action, import, consolidation member, or decision", "1b")
        for path in (
            "entities archive",
            "entities audit-identifiers",
            "entities consolidate apply",
            "entities consolidate scaffold",
            "entities generate-decisions",
            "entities mark-superseded",
            "entities unarchive",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per entity, field, relation, warning, migration action, or body element", "1b")
        for path in (
            "entity field-inventory",
            "entity migrate-hypothesis",
            "entity migrate-specs",
            "entity neighbors",
            "entity remove",
            "entity status-inventory",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per idea candidate, lens view, gap, anchor, or apply action", "1b")
        for path in ("explore-ideas backfill-lens-views",)
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per feedback entry, target, neighbor, cluster, or occurrence", "1b")
        for path in (
            "feedback report",
            "feedback show",
            "feedback triage",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per graph entity, edge, finding, summary row, or DOT statement", "1b")
        for path in (
            "graph claims",
            "graph coverage",
            "graph cross-impact",
            "graph evidence",
            "graph export-json",
            "graph neighborhood",
            "graph propagate-freshness",
            "graph scan-prose",
            "graph viz",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per inquiry, node, edge, validation check, or generated script line", "1b")
        for path in ("inquiry export-chirho",)
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per patch membership or validation finding", "1b")
        for path in (
            "patch check",
            "patch explain",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per peer or peer validation issue", "1b")
        for path in ("peers check",)
    }
)
DEFERRED.update(
    {
        path: DeferredCommand(
            "one output member per artifact registry item, diff line, migration step, "
            "delegated process event, project entity, reference, topic, or finding",
            "1b",
        )
        for path in ("project verify",)
    }
)
DEFERRED.update(
    {
        path: DeferredCommand(
            "one output member per skill, source reference, coverage report member, or lint finding", "1b"
        )
        for path in (
            "skills coverage",
            "skills sources check",
            "skills sources list",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per telemetry event, command bucket, error class, or recent failure", "1b")
        for path in (
            "telemetry export",
            "telemetry report",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per parsed verdict token, claim, interpretation, warning, or rollup group", "1b")
        for path in ("verdict rollup",)
    }
)


def lookup(command_path: str) -> CommandBudget | None:
    return BUDGETS.get(command_path)


def shape_for(command_path: str) -> PayloadShape | None:
    budget = BUDGETS.get(command_path)
    return budget.shape if budget is not None else None
