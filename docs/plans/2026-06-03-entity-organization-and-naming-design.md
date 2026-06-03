# Unified entity organization & naming — design

**Date:** 2026-06-03
**Status:** Proposed
**Scope:** `science` tool (CLI, validation, migration) + downstream project layout convention

> Paths in this document are relative to the repo root
> (`/mnt/ssd/Dropbox/science`). The tool lives under `science/src/science_tool/`
> and the model under `science/model/src/science_model/`.

## Problem

Project-specific entities are split across two top-level locations with no
principle tying location to meaning:

- `specs/` holds hypotheses, propositions, `claim-registry.yaml`, and
  `research-question.md`.
- `doc/` holds questions, interpretations, discussions, findings, inquiries,
  themes, topics, evidence-lines, observations, mechanisms, reports/synthesis —
  **and** genuine prose documentation (guides, figures, architecture, meta).

Two consequences:

1. **"specs" is misleading.** Its contents are not specifications; they are
   belief-bearing entities like the ones in `doc/`. The deeper issue: `doc/` is a
   junk drawer mixing three *classes* of entity plus a little true documentation.
   Directory location does not track what a thing *is*.

2. **Naming has drifted, because the CLI is bypassable.** When created through
   the CLI, an entity's filename is its id's local-part, so CLI-authored files
   are consistent. Files written directly by agents (or predating the CLI's
   entity support) drift. Observed in audits:

   - `multiple-myeloma`: 164 questions use bare slugs (no prefix); hypotheses mix
     `h1-` and `h-` (numberless), with a gap (no `h5`). The mixed prefixes
     currently **break the CLI** — `generate_entity_id` raises "Mixed ID
     conventions" and refuses to create a new hypothesis without `--id`.
   - `cycles`, `pan-disease`: questions mix `NN-` with `q##-`.
   - `pan-disease`: interpretations have **no YAML frontmatter** (prose headers
     only); hypotheses are multi-file (`.md` + `.yaml` + `.lock.yaml`).
   - `reports/`, `inquiries/`: inconsistent (mixed file types, ad-hoc subdirs).
   - Paper summaries land in **both** `doc/papers/` and `doc/background/papers/`.
   - `claim-registry.yaml` exists only in `multiple-myeloma`.

   `natural-systems` is the well-behaved counterexample: clean `q##-`, `h##-`,
   date-prefixed interpretations/discussions throughout.

### What already exists in the model

`science/model/src/science_model/entities.py:111-125` defines `EntityClass`:

- **EPISTEMIC** — belief-bearing; valid `bears_on` targets (question, hypothesis,
  proposition, interpretation, discussion, finding, inquiry, theme, evidence-line,
  observation, mechanism, synthesis, research-question, …).
- **REFERENCE** — external, stable (concept, topic, article).
- **OPERATIONAL** — artifacts produced by work (plan, search, method,
  pre-registration, paper, dataset, task, workflow, experiment, code-file).

The kind→class map lives in `science/src/science_tool/graph/entity_registry.py:48-91`.
The path policy (`_BUILTIN_MARKDOWN_POLICIES`,
`science/src/science_tool/entities.py:33-41`) is the existing — but incomplete —
source of truth for where source-authored markdown kinds live and how they are
named.

## Two kinds of entity kind (terminology)

- **markdown entity kinds** — authored as single markdown files with YAML
  frontmatter. These get a home under `entities/<kind>/` and are subject to the
  filename/location/frontmatter checks. *Only these are in scope.* The exact set,
  and what CLI support each has, is the **CLI support matrix** below.
- **adapter-backed kinds** — `task`, `dataset`, `workflow`, `workflow-run`,
  `code-file`, `data-package`, etc. Stored/managed by non-markdown adapters (DAG,
  packages, code). They keep their existing root homes (`tasks/`, `datasets/`,
  `workflows/`, …) and are **exempt** from the filename/location checks. They
  remain registered in the model so the future task-unification effort can fold
  them into `entities/` cleanly.

The policy table is the single source of truth **for markdown entity kinds**.

## Decisions

Settled during brainstorming and two rounds of code review:

1. **Single `entities/` home** (Scheme B). All markdown entity kinds live under
   `entities/<kind>/`. `doc/` becomes prose-only. `specs/` is retired.
   `EntityClass` stays as frontmatter metadata + validation, not directory depth.
2. **Global canonical naming** (not per-project policy).
3. **Uniform numeric naming is the default filename strategy.** Drop the letter
   *and* date prefix; the directory signals the kind and the id carries the kind.
   Most kinds converge on `NNNN-slug`. **Papers are the one exception** (#9).
4. **Fixed width 4** (`0001`–`9999`) for numeric kinds.
5. **Build all three:** validation checks, a `science entities migrate` command,
   and a migration guide.
6. **Tasks/datasets/workflows are a designed-for follow-on** (adapter-backed,
   out of scope here).
7. **All markdown entity kinds go under `entities/`** — incl. `synthesis/`,
   `reports/`, `plans/`, `searches/`, `methods/`, `pre-registrations/`,
   `papers/`. `doc/` is strictly prose.
8. **Gaps in numbering are tolerated.** No renumber-to-contiguous; already-
   conformant numbers are preserved.
9. **Papers keep the citekey convention.** `paper:Adams2025`, file
   `Adams2025.md`. No numeric migration. Only the location unifies to
   `entities/papers/` (consolidating `doc/papers/` + `doc/background/papers/`).
10. **Promote `synthesis` to a first-class core markdown kind** (#Synthesis vs
    report). It already appears as `type: synthesis` / `id: synthesis:…` in the
    template and `id_prefixes` rules; promoting (rather than demoting to `report`)
    is the lower-churn resolution.
11. **Hard cutover — no fallback.** Steady-state tooling targets `entities/` only;
    it does not read legacy `doc/`/`specs/` entity locations. The migrate command
    is the one-time bridge. A project is invalid until it is `layout_version: 3`.

## Synthesis vs report (resolving a pre-existing inconsistency)

Today: the template uses `type: "synthesis"` + `id: synthesis:…`
(`science/model/src/science_model/templates/synthesis.md:2`); `id_prefixes`
carries both `report:` and `synthesis:` rules; but the core registry registers
only `report` (`science/src/science_tool/graph/entity_registry.py:136`), and
`discussions.py:77` scans `doc/reports/synthesis` for `type: synthesis`. So
synthesis files are authored as a distinct type that the graph does not formally
recognize.

**Decision:** register `synthesis` as a first-class core markdown kind
(EPISTEMIC), keeping `report` as the separate generic kind. Concrete edits:

- add `synthesis` to `_CORE_KIND_CLASSES` (EPISTEMIC) and the core-kind
  registration loop (`entity_registry.py`);
- add `synthesis` (and `report`) to the policy table, `_DEFAULT_STATUS`,
  `_STATUS_VALUES`;
- move the synthesis frontmatter check off `doc/reports/synthesis` onto
  `entities/synthesis/` (see Legacy semantic checks);
- `report`-kind authored docs get `entities/reports/`.

## Target layout

```
project/
  entities/                       # ALL markdown entity kinds
    research-question.md          # singleton (singleton root)
    claim-registry.yaml           # singleton (singleton root)
    questions/        0001-slug.md
    hypotheses/       0001-slug.md
    propositions/     0001-slug.md
    interpretations/  0001-slug.md
    discussions/      0001-slug.md
    findings/         0001-slug.md
    inquiries/        0001-slug.md
    themes/           0001-slug.md
    topics/           0001-slug.md
    evidence-lines/   0001-slug.md
    observations/     0001-slug.md
    mechanisms/       0001-slug.md
    synthesis/        0001-slug.md
    reports/          0001-slug.md
    plans/  searches/  methods/  pre-registrations/   # NNNN-slug
    papers/           Adams2025.md   # citekey filenames (exception)
  doc/                            # prose ONLY (non-entities)
    guides/  architecture/  figures/  meta/  background/  notes/
  tasks/  datasets/  workflows/  results/    # adapter-backed (unchanged)
```

**Principle:** *location tracks what a thing is.* Every markdown entity kind has
exactly one canonical home.

## Policy schema (explicit)

The policy is `kind → {root, filename_strategy}`. Roots are explicit (not always
`pluralize(kind)` — note `evidence-line`→`evidence-lines`,
`pre-registration`→`pre-registrations`). Two **singleton roots** hold exactly one
file at the `entities/` root rather than a subdirectory.

| kind | root | filename_strategy |
|---|---|---|
| research-question | `entities/research-question.md` | singleton |
| claim-registry | `entities/claim-registry.yaml` | singleton (YAML) |
| question | `entities/questions/` | numeric |
| hypothesis | `entities/hypotheses/` | numeric |
| proposition | `entities/propositions/` | numeric |
| interpretation | `entities/interpretations/` | numeric |
| discussion | `entities/discussions/` | numeric |
| finding | `entities/findings/` | numeric |
| inquiry | `entities/inquiries/` | numeric |
| theme | `entities/themes/` | numeric |
| topic | `entities/topics/` | numeric |
| evidence-line | `entities/evidence-lines/` | numeric |
| observation | `entities/observations/` | numeric |
| mechanism | `entities/mechanisms/` | numeric |
| synthesis | `entities/synthesis/` | numeric |
| report | `entities/reports/` | numeric |
| plan | `entities/plans/` | numeric |
| search | `entities/searches/` | numeric |
| method | `entities/methods/` | numeric |
| pre-registration | `entities/pre-registrations/` | numeric |
| paper | `entities/papers/` | citekey |

`filename_strategy`:

| strategy | filename | id local-part |
|---|---|---|
| `numeric` | `NNNN-slug.md`, width-4 | `NNNN-slug` |
| `citekey` | `Citekey.md` | `Citekey` |
| `singleton` | fixed filename | n/a |

Shared rules: kebab slug ≤72 chars (`derive_slug`); id `<kind>:<local-part>`;
numbering per-kind sequential from `0001`, gaps allowed; `created:`/`updated:` in
frontmatter only; shortforms `q5`/`h3` resolve as **input sugar** →
`question:0005-…`; required frontmatter `id, type, title, status, created,
updated` (+ per-kind fields). The `date-local-part` policy is removed; numbers
assigned in `created:` order preserve the chronological sort date prefixes gave
interpretations/discussions.

## CLI support matrix

The current CLI supports only seven kinds (`_DEFAULT_STATUS`,
`science/src/science_tool/entities.py:55`) and explicitly **rejects `concept`**
(`entities.py:359`, "use graph add concept instead"). The broadened set needs
explicit per-kind support. Three support tiers:

- **CLI-createable** — has policy entry + `_DEFAULT_STATUS` + `_STATUS_VALUES` +
  template/sections; `science entities create <kind>` works. Target set:
  question, hypothesis, proposition, interpretation, discussion, finding,
  inquiry, theme, topic, evidence-line, observation, mechanism, synthesis,
  report, plan, search, method, pre-registration, paper. **Task:** add the
  missing `_DEFAULT_STATUS`/`_STATUS_VALUES`/templates for kinds beyond today's
  seven.
- **Migration-only** — files exist in projects and get an `entities/<kind>/`
  home + validation, but `create` support is deferred if no template exists yet.
  Flagged per-kind in the implementation plan rather than assumed.
- **Graph-managed (excluded)** — `concept` is not source-authored markdown; it
  has **no** `entities/concepts/` home in this effort. Authored concept files
  found during migration are flagged for case-by-case handling, not auto-homed.

The plan must enumerate, per CLI-createable kind: `default_status`, allowed
`statuses`, and template/required-sections.

## Discovery & singletons — pipeline updates (hard cutover)

Moving files to `entities/` is invisible to the graph unless discovery learns the
new root. Under the no-fallback decision the steady-state pipeline targets
`entities/` only:

1. **`MarkdownAdapter` scan roots.** Default is
   `["doc", "specs", "research/packages"]`
   (`science/src/science_tool/graph/storage_adapters/markdown.py:20`). Change to
   `["entities", "research/packages"]`. (Prose `.md` under `doc/` has no entity
   frontmatter and is skipped anyway by `sources.py:272`.)
2. **Staleness scan.** `graph_is_stale`
   (`science/src/science_tool/entities.py:549`) iterates
   `MarkdownAdapter().scan_roots` — fixed automatically once (1) lands; add a
   regression test.
3. **`research-question.md`.** `check_research_scope` hard-requires
   `specs/research-question.md` (ERROR,
   `science/src/science_tool/validate/checks/research_scope.py:28`). Point it at
   `entities/research-question.md` — **no `specs/` fallback**.
4. **`claim-registry.yaml`.** Discovery is hard-coded to `specs/claim-registry.yaml`
   in `science/src/science_tool/verdict/registry.py:113` (`has_registry`) and
   `science/src/science_tool/verdict/cli.py:131` (`_load_registry_for_rollup`).
   Point both at `entities/claim-registry.yaml` — **no `specs/` fallback**.
5. **`_ALLOWED_EXPLICIT_ROOTS`** (`science/src/science_tool/entities.py:92`) — set
   to `entities` (drop `doc`/`specs`).

## Legacy semantic checks to migrate

Beyond discovery and the five new checks, existing semantic validators hardcode
legacy paths and must be repointed at `entities/` (or driven by the policy table
/ `markdown_documents`). Known set:

- **`discussions.py`** — scans `doc/discussions` and `doc/reports/synthesis`
  (`:47`, `:77`). Repoint to `entities/discussions/` and `entities/synthesis/`.
- **`document_structure.py`** — scans `doc/background/topics`,
  `doc/background/papers` (`:35`). Repoint to `entities/topics/`,
  `entities/papers/`.
- **`papers.py`** — messaging points at `doc/background/papers` (`:24`). Repoint
  to `entities/papers/`.
- **`hypotheses.py`** — globs `specs/hypotheses/h*.md`. Both the root *and* the
  `h*` glob break under `entities/hypotheses/NNNN-slug.md`; repoint and drop the
  letter-glob.
- **`id_prefixes.py`** — make `PREFIX_RULES` a derived view of the policy table
  so the lists cannot drift.

The implementation plan should grep for `doc/`, `specs/`, and per-kind globs
across `validate/checks/` to catch any not listed here.

## CLI changes

- **`generate_entity_id`** (`science/src/science_tool/entities.py:171-206`)
  rewritten: remove letter/date inference and the "mixed conventions" error path;
  for `numeric` kinds scan siblings for max number, emit `NNNN` width 4; for
  `citekey` kinds require/validate a citekey. Fixes the `multiple-myeloma`
  create breakage.
- **Atomic reservation** — generalize `questions.reserve`'s `O_CREAT|O_EXCL` to
  all numeric kinds.
- **`create_entity`** — extend support per the CLI support matrix (drop the
  hard-coded seven-kind assumptions).
- **`path_for_entity` / `resolve_path_policy`** read the unified policy and honor
  the per-kind strategy.

## Validation / health checks

New checks, driven by the policy table, scoped to **markdown entity kinds**
(adapter-backed kinds exempt). A project at `layout_version: 2` fails fast with a
"run `science entities migrate`" ERROR; checks below assume `layout_version: 3`.
The location check additionally scans `doc/` and `specs/` to flag any stranded
entity files.

1. **Location coherence** — directory matches `type`/`id` kind; no entity files
   in `doc/`/`specs/`.
2. **Filename conformance** — matches the kind's strategy (`NNNN-slug` width 4,
   or citekey); filename local-part equals `id` local-part.
3. **Frontmatter completeness** — required fields present (catches the
   `pan-disease` prose-header interpretations).
4. **Number hygiene** — no duplicate numbers within a numeric kind; flag mixed
   widths.
5. **Stray-file check** — non-entity files inside `entities/<kind>/`.

## Migration: command + guide + transition

### `science entities migrate [--apply]`

Dry-run by default (mirroring `migrate_identifiers`). The steady-state pipeline
no longer reads legacy locations, so the command does its **own raw filesystem
scan** of legacy paths and operates on raw text — it cannot rely on the graph
loader (which skips frontmatterless files, `sources.py:272`) or on
`ReferenceResolver` (which only resolves authored refs to canonical ids; it does
not rewrite raw markdown/YAML, parse wiki links, or touch frontmatterless files,
`reference_resolution.py:53`).

Steps:

1. **Frontmatter synthesis (first).** For files with missing/partial frontmatter
   (prose-header interpretations, multi-file `.lock.yaml` hypotheses), synthesize
   a valid frontmatter block from prose headers + git history *before* anything
   else, so the file becomes loadable.
2. **Discover** all markdown entity files in legacy locations (`doc/<kind>/`,
   `specs/<kind>/`, `doc/papers/`, `doc/background/papers/`,
   `doc/reports/synthesis/`).
3. **Plan** target path + new id per the policy. Numeric kinds: assign numbers in
   `created:` order (backfill missing `created:` from git first-commit date,
   fallback file mtime); preserve already-conformant numbers. Papers: keep
   citekey, change only directory.
4. **Build the full old→new id map**, using `ReferenceResolver` to canonicalize
   authored refs into that map.
5. **Raw rewrite layer** applies the map in one pass:
   - YAML frontmatter parser/renderer for `id:`, `related:`, and id-bearing
     fields (preserve key order/comments where feasible);
   - prose/body token scanner for inline `<kind>:…` refs and `[[…]]` wiki-links;
   - claim-registry entry rewriting; task-graph ref rewriting;
   - old-id alias handling (a ref already at the new id is a no-op).
6. **Move files** with `git mv` (preserve history).
7. **Re-run graph validation**; **fail loud** on any unresolved reference.
8. **Emit a diff/report**; `--apply` commits and sets `layout_version: 3`.

### Transition

Reuse the **existing** required manifest field `layout_version`
(`science/src/science_tool/validate/checks/manifest.py:13`; documented in
`docs/project-organization-profiles.md:100`). All audited projects are currently
`layout_version: 2`; the reorg is **`layout_version: 3`**. Because of the
no-fallback decision, v2 is not a supported steady state — validation errors with
a directive to run migrate. Existing `SCIENCE_VALIDATE_SKIP_*` escape hatches are
retained for mid-migration work.

### `docs/migration-guide.md`

When to run migrate, how to review the dry-run diff, and how to handle flagged
edge cases — `pan-disease`'s `.lock.yaml` hypotheses, prose-header interpretations
needing frontmatter synthesized, paper-summary consolidation, and any
graph-managed `concept` files found in legacy locations.

## Scope boundaries (YAGNI)

- **In:** reorg of markdown entity kinds to `entities/`; uniform numeric naming
  (citekey papers); promote `synthesis`; policy table as single source of truth;
  CLI support matrix; discovery pipeline updates; legacy semantic-check
  repointing; the five validation checks; the migrate command; the guide.
- **Out (future):** unifying `tasks`/`datasets`/`workflows` storage into
  `entities/` and reworking the task DAG.

## Key risks

- **Reference-rewrite completeness.** A missed inline `question:q01-…` becomes a
  dead link. Mitigation: synthesize frontmatter first; build the full id-map;
  rewrite atomically with the raw-file layer; re-run graph validation; fail loud.
- **Incomplete check migration.** Any legacy check left scanning `doc/`/`specs/`
  silently passes/misses under v3. Mitigation: the grep sweep across
  `validate/checks/`.
- **Hard cutover.** No fallback means a project is broken between ship and
  migrate. Mitigation: migrate is fast, dry-run-first, one project at a time;
  `SCIENCE_VALIDATE_SKIP_*` covers in-progress work.
- **Number-assignment determinism.** Reproducible (sort by `created:` then path).

## Open questions

None blocking. Width 4, gap-tolerance, papers citekey, synthesis promotion, and
the no-fallback `layout_version: 3` cutover are settled; task unification is
deferred.
