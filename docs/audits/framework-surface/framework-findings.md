# Framework Findings

## Finding 1: Root CLI File Has Become The Integration Hub

`science/src/science_tool/cli.py` is about 7,987 lines and owns many unrelated
command families: entity authoring, graph operations, inquiry, datasets, tasks,
sync, project packaging, benchmark registration, feedback, telemetry, and legacy
migration surfaces.

This makes routine changes expensive because a developer or agent must load a
large mixed context before touching a narrow command. It also increases the risk
that shared command semantics drift because helper patterns are embedded near
individual command groups.

**Recommendation:** Do not rewrite the root CLI wholesale. Extract one cohesive
family at a time, using existing split modules as the pattern:

- already split: `annotation/cli.py`, `commons/cli.py`, `dag/cli.py`,
  `validate/cli.py`, `big_picture/cli.py`, `curate/cli.py`;
- candidate extractions: `tasks`, `dataset`, `datasets`, `graph add`, `project`,
  `feedback`/`telemetry`.

## Finding 2: Shared CLI Semantics Need A Small Contract

Common behavior is repeated across command families:

- `--format json|table|text`
- `--project-root` / `--root` / current-directory resolution
- report-then-apply / dry-run/apply
- read-only diagnostics vs source writes vs generated-state writes
- stale graph warnings
- migration-only commands
- telemetry for command failures

These are framework concepts, but they are not documented as a framework-level
contract. This makes new commands easy to add but hard to keep consistent.

**Recommendation:** Create a short "CLI behavior contract" section in the user
guide before making broad CLI changes. Then add helpers or tests only where the
contract exposes real drift.

## Finding 3: Data/Dataset Surfaces Encode Too Much History

The current command family set is accurate but hard to learn:

- `science data audit`: tracked-source vs payload boundary.
- `science dataset ...`: local dataset entity lifecycle.
- `science datasets ...`: external dataset discovery/download/datapackage QA.
- `science data-package ...`: legacy migration.
- `science commons dataset ...`: commons-born dataset package workflow.

Each surface has a reason to exist. The issue is that the names do not expose the
reason. A user or agent must already know the model to choose correctly.

**Recommendation:** Treat this as the first command-taxonomy case study. Improve
docs/help first. Consider aliases or regrouping only after the docs make the
desired model explicit.

## Finding 4: Source-Authored vs Generated-State Boundaries Are Strong But Need Better Signposting

The framework's core design is sound: authored Markdown/YAML sources are durable;
`knowledge/graph.trig` and related files are derived views. The docs say this in
multiple places.

However, the CLI still exposes direct graph mutation commands under `graph add`.
Those commands warn that their writes will be wiped by the next graph build. That
warning is correct, but the command group name makes the surface look canonical.

**Recommendation:** The command map should explicitly label `graph add` as
exploratory/manual graph surgery. New durable workflows should prefer `entity`
or typed source-authoring commands.

## Finding 5: Annotation Workflows Are Powerful But Dense

`science annotate` has 25 leaf commands. They cover several phases:

- mechanical audit and sidecar rows;
- token lifting;
- prose decomposition;
- prose grounding and promotion;
- proposition reconciliation;
- PubTator seeding;
- statement extraction/promotion/synthesis;
- status transitions and stats.

This is a real subsystem, not a small command group. The convention doc preserves
important phase knowledge, but the user guide does not yet give a compact
operator view of the annotation lifecycle.

**Recommendation:** After the CLI taxonomy, write or extract an annotation
workflow guide. Keep command semantics in the CLI taxonomy and workflow details
in the annotation guide.

## Finding 6: Migration Surfaces Are Necessary But Too Visible

The framework keeps several migration and transition tools live, including
legacy entity layout migration, legacy data-package promotion, legacy topic
handling, legacy paper dataset migration, legacy annotation token migration, and
legacy task blocker repair.

Keeping these tools is pragmatic. The risk is that agents interpret top-level
visibility as endorsement for new work.

**Recommendation:** Mark migration surfaces explicitly in docs and help text.
Use "migration-only" rather than "legacy" where the command is actively useful
for cleanup.

## Finding 7: Model Tightening Should Follow Observed Drift

The audit found likely tightening opportunities, but they should be handled as
small, evidence-backed slices:

- standardize output format options and names;
- standardize path flags (`--root`, `--project-root`, `--repo-root`);
- standardize `--apply` semantics and dry-run wording;
- define command write classes: read-only, source-write, generated-write,
  external-registry-write;
- clarify canonical entity authoring path vs typed wrappers;
- identify legacy command deprecation criteria.

These are better addressed by contract plus tests than by a broad refactor.
