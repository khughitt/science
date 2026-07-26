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
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


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
    "graph add article": "fixed retired-command error",
    "graph add concept": "fixed retired-command error",
    "graph add discussion": "fixed retired-command error",
    "graph add edge": "fixed retired-command error",
    "graph add evidence": "fixed retired-command error",
    "graph add falsification": "fixed retired-command error",
    "graph add finding": "fixed retired-command error",
    "graph add hypothesis": "fixed retired-command error",
    "graph add interpretation": "fixed retired-command error",
    "graph add mechanism": "fixed retired-command error",
    "graph add observation": "fixed retired-command error",
    "graph add proposition": "fixed retired-command error",
    "graph add question": "fixed retired-command error",
    "graph add story": "fixed retired-command error",
    "graph import": "fixed retired-command error",
    "graph init": "at most three fixed initialization guidance lines",
    "graph migrate-addresses": "fixed retired-command error",
    "graph stats": "measured 341 chars on 2026-07-24; fixed-shape summary",
    "graph stamp-revision": "fixed retired-command error",
    "inquiry add-assumption": "fixed retired-command error",
    "inquiry add-edge": "fixed retired-command error",
    "inquiry add-node": "fixed retired-command error",
    "inquiry add-transformation": "fixed retired-command error",
    "inquiry import": "single imported-inquiry path",
    "inquiry init": "single scaffold path",
    "inquiry set-estimand": "fixed retired-command error",
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

DEFERRED: dict[str, DeferredCommand] = {
    # Measured over budget on 2026-07-24; wiring scheduled for slice 1b.
    "curate inventory": DeferredCommand("one record per entity", "1b", 683_657),
    "prose lint": DeferredCommand("one row per prose finding", "1b", 550_226),
    "validate": DeferredCommand("one row per validation finding", "1b", 109_466),
    "curate consolidation-candidates": DeferredCommand("one row per candidate cluster", "1b", 71_553),
    # Growable but small on the audited project -- the case that has no truthful
    # exemption. Populated further by Task 13 Step 3.
    "tasks archive": DeferredCommand("one row per archivable task", "1b"),
    "tasks summary": DeferredCommand(
        "one output member per distinct task type and group value",
        "1b",
    ),
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
}

DEFERRED.update(
    {
        path: DeferredCommand(
            "one output member per annotation, source, decomposition unit, "
            "reconciliation action, path, or diagnostic",
            "1b",
        )
        for path in (
            "annotate ack",
            "annotate apply-proposition-reconciliation",
            "annotate apply-proposition-resynthesis",
            "annotate apply-prose-promotion-plan",
            "annotate archive-superseded-propositions",
            "annotate audit",
            "annotate build-prose-health",
            "annotate check-prose-decomposition",
            "annotate cross-paper-evidence",
            "annotate dismiss",
            "annotate extract",
            "annotate fix",
            "annotate ground-prose-decomposition",
            "annotate ingest-prose-decomposition",
            "annotate lift-tokens",
            "annotate list",
            "annotate plan-proposition-reconciliation",
            "annotate plan-prose-promotions",
            "annotate promote",
            "annotate promote-prose-decomposition",
            "annotate pubtator",
            "annotate reconcile-propositions",
            "annotate record-proposition-reconciliation-decisions",
            "annotate resynthesis-draft-context",
            "annotate scaffold-proposition-resynthesis",
            "annotate stats",
            "annotate synthesize",
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
        "book-split": DeferredCommand("one row per detected chapter", "1b"),
        "doi lookup": DeferredCommand("one row per returned DOI metadata field", "1b"),
        "markers scan": DeferredCommand("one row per marker hit and token", "1b"),
        "paper-fetch": DeferredCommand("variable-length source and acquisition metadata", "1b"),
        "qa-audit": DeferredCommand("one row per audited workflow", "1b"),
        "search": DeferredCommand("one row per matching project record", "1b"),
        "wander": DeferredCommand("one output member per generated walk item", "1b"),
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one row per benchmark, test, gap, candidate, or calibration bucket", "1b")
        for path in (
            "benchmark gap-calibration",
            "benchmark gaps",
            "benchmark hint-candidates",
            "benchmark list",
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
            "big-picture resolve-questions",
            "big-picture validate",
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
            "commons dataset build",
            "commons dataset status",
            "commons dataset validate",
            "commons find",
            "commons index rebuild",
            "commons inventory",
            "commons list",
            "commons member-payload",
            "commons promote dataset",
            "commons promote paper",
            "commons promote theme",
            "commons promote topic",
            "commons reference-graph resolve-member",
            "commons show",
            "commons validate",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per DAG finding, mutation, changed path, or diff line", "1b")
        for path in (
            "dag apply-workbench",
            "dag audit",
            "dag validate",
            "dag workbench",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per dataset, consumer, capability, link, resource, run, or warning", "1b")
        for path in (
            "dataset add",
            "dataset capability-pairs",
            "dataset consumers",
            "dataset identity resolve",
            "dataset list",
            "dataset prioritize",
            "dataset reconcile",
            "dataset reconcile-links",
            "dataset register-run",
            "dataset show",
            "dataset stochasticity",
            "dataset verify-access",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per external dataset, file, resource, schema field, QA result, or adapter", "1b")
        for path in (
            "datasets download",
            "datasets files",
            "datasets hydrate-worktree",
            "datasets infer-schema",
            "datasets qa",
            "datasets search",
            "datasets sources",
            "datasets validate",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per typed entity reference warning, field, or body element", "1b")
        for path in (
            "discussions create",
            "discussions show",
            "evidence-lines create",
            "evidence-lines list",
            "evidence-lines show",
            "hypotheses create",
            "hypotheses list",
            "hypotheses show",
            "interpretations create",
            "interpretations show",
            "propositions create",
            "propositions list",
            "propositions show",
            "questions create",
            "questions show",
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
            "entities import",
            "entities mark-superseded",
            "entities unarchive",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per entity, field, relation, warning, migration action, or body element", "1b")
        for path in (
            "entity create",
            "entity edit",
            "entity field-inventory",
            "entity migrate-hypothesis",
            "entity migrate-specs",
            "entity neighbors",
            "entity note",
            "entity remove",
            "entity rotation",
            "entity sections",
            "entity show",
            "entity status-inventory",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per idea candidate, lens view, gap, anchor, or apply action", "1b")
        for path in (
            "explore-ideas apply",
            "explore-ideas backfill-lens-views",
            "explore-ideas gaps",
            "explore-ideas resolve-anchors",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per feedback entry, target, neighbor, cluster, or occurrence", "1b")
        for path in (
            "feedback add",
            "feedback regression-candidates",
            "feedback report",
            "feedback show",
            "feedback targets",
            "feedback triage",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per graph entity, edge, finding, summary row, or DOT statement", "1b")
        for path in (
            "graph attention-rank",
            "graph attention-sample",
            "graph audit",
            "graph build",
            "graph claims",
            "graph coverage",
            "graph cross-impact",
            "graph dashboard-summary",
            "graph diff",
            "graph evidence",
            "graph export-json",
            "graph gaps",
            "graph inquiry-summary",
            "graph neighborhood",
            "graph neighborhood-summary",
            "graph predicates",
            "graph project-summary",
            "graph propagate-freshness",
            "graph question-summary",
            "graph rehoming-debt",
            "graph scan-prose",
            "graph uncertainty",
            "graph validate",
            "graph viz",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per inquiry, node, edge, validation check, or generated script line", "1b")
        for path in (
            "inquiry export-chirho",
            "inquiry export-pgmpy",
            "inquiry list",
            "inquiry show",
            "inquiry validate",
        )
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
        for path in (
            "peers check",
            "peers list",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand(
            "one output member per artifact registry item, diff line, migration step, "
            "delegated process event, project entity, reference, topic, or finding",
            "1b",
        )
        for path in (
            "project artifacts diff",
            "project artifacts exec",
            "project artifacts list",
            "project artifacts update",
            "project index",
            "project resolve-refs",
            "project topic-coverage",
            "project verify",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per package, package validation finding, or build error", "1b")
        for path in (
            "research-package build",
            "research-package validate",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per reference problem or unresolved marker", "1b")
        for path in ("refs check",)
    }
)
DEFERRED.update(
    {
        path: DeferredCommand(
            "one output member per skill, source reference, coverage report member, or lint finding", "1b"
        )
        for path in (
            "skills coverage",
            "skills lint",
            "skills sources check",
            "skills sources list",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per registered project, drift warning, or rebuild action", "1b")
        for path in (
            "sync projects",
            "sync rebuild",
            "sync run",
            "sync status",
        )
    }
)
DEFERRED.update(
    {
        path: DeferredCommand("one output member per blocker, task preview row, or blocker repair", "1b")
        for path in (
            "tasks block",
            "tasks blockers",
            "tasks fix-blockers",
            "tasks show",
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
        for path in (
            "verdict parse",
            "verdict rollup",
        )
    }
)


def lookup(command_path: str) -> CommandBudget | None:
    return BUDGETS.get(command_path)


def shape_for(command_path: str) -> PayloadShape | None:
    budget = BUDGETS.get(command_path)
    return budget.shape if budget is not None else None
