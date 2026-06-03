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
   belief-bearing entities like the ones in `doc/`. But the deeper issue is that
   `doc/` is a junk drawer mixing three *classes* of entity plus a little true
   documentation. Directory location does not track what a thing *is*.

2. **Naming has drifted, because the CLI is bypassable.** When created through
   the CLI, an entity's filename is its id's local-part, so CLI-authored files
   are consistent. Files written directly by agents (or predating the CLI's
   entity support) drift. Observed in audits:

   - `multiple-myeloma`: 164 questions use bare slugs (no prefix); hypotheses mix
     `h1-` and `h-` (numberless), with a gap (no `h5`). The mixed hypothesis
     prefixes currently **break the CLI** — `generate_entity_id` raises "Mixed ID
     conventions" and refuses to create a new hypothesis without `--id`.
   - `cycles`, `pan-disease`: questions mix `NN-` (numeric-only) with `q##-`.
   - `pan-disease`: interpretations have **no YAML frontmatter** at all (prose
     headers only); hypotheses are multi-file (`.md` + `.yaml` + `.lock.yaml`).
   - `reports/`, `inquiries/`: inconsistent everywhere (mixed file types, ad-hoc
     subdirectories, some dated, some not).
   - Paper summaries land in **both** `doc/papers/` and `doc/background/papers/`.
   - `claim-registry.yaml` exists only in `multiple-myeloma`.

   `natural-systems` is the well-behaved counterexample: clean `q##-`, `h##-`,
   and date-prefixed interpretations/discussions throughout.

### What already exists in the model

The model already encodes the taxonomy this design leans on.
`science/model/src/science_model/entities.py:111-125` defines `EntityClass`:

- **EPISTEMIC** — belief-bearing; valid `bears_on` targets in the evidence graph
  (question, hypothesis, proposition, interpretation, discussion, finding,
  inquiry, theme, evidence-line, observation, mechanism, report/synthesis,
  research-question, …).
- **REFERENCE** — external, stable (concept, topic, article).
- **OPERATIONAL** — artifacts produced by work (plan, search, method,
  pre-registration, paper, dataset, task, workflow, experiment, code-file).

The kind→class map lives in `science/src/science_tool/graph/entity_registry.py:48-91`.
The path policy (`_BUILTIN_MARKDOWN_POLICIES`,
`science/src/science_tool/entities.py:33-41`) is the existing — but incomplete —
source of truth for where source-authored markdown kinds live and how they are
named.

## Two kinds of entity kind (terminology)

The review surfaced an ambiguity in "all recognized entity kinds." This design
splits the term explicitly:

- **markdown entity kinds** — authored as single markdown files with YAML
  frontmatter (question, hypothesis, proposition, interpretation, discussion,
  finding, inquiry, theme, topic, concept, evidence-line, observation,
  mechanism, synthesis/report, plan, search, method, pre-registration, paper).
  These get a home under `entities/<kind>/` and are subject to the
  filename/location/frontmatter checks below. *Only these are in scope.*
- **adapter-backed kinds** — `task`, `dataset`, `workflow`, `workflow-run`,
  `code-file`, `data-package`, etc. Stored and managed by non-markdown adapters
  (DAG, packages, code). They keep their existing root homes (`tasks/`,
  `datasets/`, `workflows/`, …) and are **exempt** from the filename/location
  checks. They remain registered in the policy table so the future
  task-unification effort can fold them into `entities/` cleanly.

The policy table is the single source of truth **for markdown entity kinds**.

## Decisions

Settled during brainstorming and the subsequent code review:

1. **Single `entities/` home** (Scheme B). All markdown entity kinds live under
   `entities/<kind>/`. `doc/` becomes prose-only. `specs/` is retired.
   `EntityClass` stays as frontmatter metadata + validation, not directory depth.
2. **Global canonical naming** (not per-project policy). Trade one-time migration
   for a single, uniform model.
3. **Uniform numeric naming is the default filename strategy.** Drop the letter
   prefix *and* the date prefix; the directory signals the kind and the id
   carries the kind. Most kinds converge on `NNNN-slug`. **Papers are the one
   deliberate exception** (decision 9).
4. **Fixed width 4** (`0001`–`9999`) for numeric kinds. Sorts correctly under
   plain `ls`; effectively uncapped in practice. Crossing 9999 is a rare,
   explicit, CLI-managed re-pad event.
5. **Build all three:** validation/health checks, a `science entities migrate`
   command, and a migration guide.
6. **Tasks/datasets/workflows are a designed-for follow-on** (see terminology
   section). Their storage/tooling migration is out of scope here.
7. **All markdown entity kinds go under `entities/`** — including `synthesis/`,
   `plans/`, `searches/`, `methods/`, `pre-registrations/`, `papers/`. `doc/` is
   strictly prose.
8. **Gaps in numbering are tolerated.** The migrate command does not renumber to
   make sequences contiguous; a gap can be meaningful (a retired `h5`), and
   renumbering would cause needless id churn. Already-conformant numbers are
   preserved.
9. **Papers keep the citekey convention.** `paper:Adams2025`, filename
   `Adams2025.md`. We do **not** migrate papers to `NNNN-slug` — citekeys are
   more natural and stable. What *does* change: papers move to a single home,
   `entities/papers/`, consolidating today's `doc/papers/` and
   `doc/background/papers/`.

## Target layout

```
project/
  entities/                       # ALL markdown entity kinds
    research-question.md          # singletons at the entities/ root
    claim-registry.yaml
    questions/        0001-slug.md
    hypotheses/       0001-slug.md
    propositions/     0001-slug.md
    interpretations/  0001-slug.md
    discussions/      0001-slug.md
    findings/         0001-slug.md
    inquiries/        0001-slug.md
    themes/           0001-slug.md
    topics/           0001-slug.md
    concepts/         0001-slug.md
    evidence-lines/   0001-slug.md
    observations/     0001-slug.md
    mechanisms/       0001-slug.md
    synthesis/        0001-slug.md   # report-kind big-picture summaries
    plans/  searches/  methods/  pre-registrations/   # operational markdown, NNNN-slug
    papers/           Adams2025.md   # citekey filenames (exception)
  doc/                            # prose ONLY (non-entities)
    guides/  architecture/  figures/  meta/  background/  notes/
  tasks/  datasets/  workflows/  results/    # adapter-backed kinds (unchanged)
```

**Principle:** *location tracks what a thing is.* Every markdown entity kind has
exactly one canonical home.

## Canonical naming — per-kind filename strategy

`_BUILTIN_MARKDOWN_POLICIES` is promoted to the single source of truth for every
**markdown** kind. The `filename` field, today `local-part` | `date-local-part`,
is replaced by a **strategy** enum:

| Strategy | Kinds | Filename | Id local-part |
|---|---|---|---|
| `numeric` (default) | everything except papers | `NNNN-slug.md`, width-4 | `NNNN-slug` |
| `citekey` | paper | `Citekey.md` (e.g. `Adams2025.md`) | `Citekey` |

Shared rules:

| Element | Rule |
|---|---|
| Slug | kebab, ≤72 chars, via existing `derive_slug` |
| Id | `<kind>:<local-part>` (kind from directory; numeric kinds carry no letter/date) |
| Numbering | per-kind sequential from `0001`; gaps allowed |
| Date | `created:` / `updated:` in frontmatter only |
| Shortforms | `q5`, `h3` still resolve as **input sugar** → `question:0005-…` (letter→kind map retained) |
| Required frontmatter | `id, type, title, status, created, updated` (+ per-kind fields) |

`evidence-line`'s existing `##-slug` (letterless) is the precedent the `numeric`
strategy generalizes. The `date-local-part` policy is removed; numeric prefixes
assigned in `created:` order preserve the chronological sort that date prefixes
gave interpretations and discussions.

## Discovery & singletons — pipeline updates (was under-specified)

Moving files to `entities/` is invisible to the graph unless discovery learns
the new root. The migration is incomplete without these concrete edits:

1. **`MarkdownAdapter` scan roots.** Default `scan_roots` is
   `["doc", "specs", "research/packages"]`
   (`science/src/science_tool/graph/storage_adapters/markdown.py:20`). Add
   `"entities"`. Retain `"specs"`/`"doc"` so un-migrated (`layout_version: 2`)
   projects still load.
2. **Staleness scan.** `graph_is_stale`
   (`science/src/science_tool/entities.py:549`) iterates
   `MarkdownAdapter().scan_roots` — fixed automatically once (1) lands; add an
   explicit regression test.
3. **`research-question.md`.** `check_research_scope` hard-requires
   `specs/research-question.md` as an ERROR
   (`science/src/science_tool/validate/checks/research_scope.py:28`). Update it
   to look in `entities/research-question.md` first, falling back to `specs/` for
   `layout_version: 2` projects.
4. **`claim-registry.yaml`.** Discovery is hard-coded to
   `specs/claim-registry.yaml` in both
   `science/src/science_tool/verdict/registry.py:113` (`has_registry`) and
   `science/src/science_tool/verdict/cli.py:131` (`_load_registry_for_rollup`).
   Update both to prefer `entities/claim-registry.yaml`, falling back to `specs/`.
   Without this, v3 projects silently lose all claim-registry behavior.
5. **`_ALLOWED_EXPLICIT_ROOTS`** (`science/src/science_tool/entities.py:92`) — add
   `entities`.

## CLI changes

- **`generate_entity_id`** (`science/src/science_tool/entities.py:171-206`)
  rewritten: remove letter/date inference and the "mixed conventions" error path;
  for `numeric` kinds scan siblings for the max number and emit `NNNN` at width 4;
  for `citekey` kinds (papers) require/validate an explicit citekey. This also
  fixes the current breakage where `multiple-myeloma` cannot create a new
  hypothesis.
- **Atomic reservation** — generalize the `questions.reserve`
  `O_CREAT|O_EXCL` mechanism to all numeric kinds, so parallel agents do not
  collide on a number.
- **`path_for_entity` / `resolve_path_policy`** read the unified policy and
  honor the per-kind strategy.

## Validation / health checks

New checks, driven by the policy table, scoped to **markdown entity kinds**
(adapter-backed kinds are exempt). WARN during transition; promotable to ERROR
once a project declares `layout_version: 3`.

1. **Location coherence** — a file's directory matches its `type`/`id` kind; no
   entity files stranded in `doc/` or `specs/`.
2. **Filename conformance** — matches the kind's strategy (`NNNN-slug` width 4, or
   citekey); the filename local-part equals the `id` local-part.
3. **Frontmatter completeness** — required fields present. Directly catches
   `pan-disease` interpretations that have no frontmatter, only prose headers.
4. **Number hygiene** — no duplicate numbers within a numeric kind; flag mixed
   widths.
5. **Stray-file check** — non-entity files sitting in `entities/<kind>/`.

`id_prefixes.py`'s `PREFIX_RULES` becomes a derived view of the policy table so
the two lists cannot drift apart.

## Migration: command + guide + transition

### `science entities migrate [--apply]`

Dry-run by default (mirroring the existing `migrate_identifiers` contract).

The review correctly flagged that `ReferenceResolver`
(`science/src/science_tool/graph/reference_resolution.py:53`) only resolves
authored refs to canonical ids — it does **not** rewrite raw markdown/YAML, parse
wiki links, or operate on frontmatterless files. And `load_project_sources`
**skips markdown with no `kind`/frontmatter**
(`science/src/science_tool/graph/sources.py:272`), so prose-header files like
`pan-disease`'s interpretations never even enter the graph. The migrate command
therefore needs a dedicated **raw-file rewrite layer**, not just the resolver.

Steps:

1. **Frontmatter synthesis (first).** For files with missing/partial frontmatter
   (prose-header interpretations, multi-file `.lock.yaml` hypotheses), synthesize
   a valid frontmatter block from prose headers + git history *before* anything
   else, so the file becomes loadable and analyzable.
2. **Discover** all markdown entity files in legacy locations (`doc/<kind>/`,
   `specs/<kind>/`, `doc/papers/`, `doc/background/papers/`).
3. **Plan** target path + new id per the policy. For numeric kinds, assign
   numbers in `created:` order (backfill missing `created:` from git first-commit
   date, fallback file mtime); preserve already-conformant numbers. For papers,
   keep the citekey, change only the directory.
4. **Build the full old→new id map**, using `ReferenceResolver` to canonicalize
   authored refs into that map.
5. **Raw rewrite layer** applies the map in one pass:
   - a YAML frontmatter parser/renderer for `id:` and `related:` (and any
     id-bearing fields), preserving key order and comments where feasible;
   - a prose/body token scanner for inline `<kind>:…` references and `[[…]]`
     wiki-links;
   - claim-registry entry rewriting; task-graph ref rewriting;
   - old-id alias handling so a ref already pointing at the new id is a no-op.
6. **Move files** with `git mv` (preserve history).
7. **Re-run graph validation** and **fail loud** on any unresolved reference.
8. **Emit a diff/report**; `--apply` commits the changes.

### Transition coexistence

Reuse the **existing** manifest field `layout_version` (a required field per
`science/src/science_tool/validate/checks/manifest.py:13`; documented in
`docs/project-organization-profiles.md:100`). All audited projects are currently
`layout_version: 2`; the `entities/` reorg is **`layout_version: 3`**.
Validation treats v2 as the legacy layout (entity-conformance checks WARN, old
roots accepted) and v3 as migrated (checks ERROR, `entities/` required).
Existing `SCIENCE_VALIDATE_SKIP_*` escape hatches are retained. (The earlier
draft's `layout: v2` field was wrong and is dropped.)

### `docs/migration-guide.md`

For agents and humans: when to run migrate, how to review the dry-run diff, and
how to handle edge cases the command flags — `pan-disease`'s multi-file
`.lock.yaml` hypotheses, prose-header interpretations needing frontmatter
synthesized, and paper-summary consolidation.

## Scope boundaries (YAGNI)

- **In:** reorg of markdown entity kinds to `entities/`; uniform numeric naming
  (citekey for papers); the policy table as single source of truth; the discovery
  pipeline updates; the five validation checks; the migrate command; the guide.
- **Out (future):** unifying `tasks` / `datasets` / `workflows` storage into
  `entities/` and reworking the task DAG. Conventions are chosen to make this
  clean later, but it is a separate project.

## Key risks

- **Reference-rewrite completeness.** A missed inline `question:q01-…` becomes a
  dead link. Mitigation: synthesize frontmatter first so every file is loadable;
  build the full id-map; rewrite atomically with the raw-file layer; re-run graph
  validation; fail loud on any unresolved ref.
- **Discovery regressions.** If `MarkdownAdapter`, `research_scope`, or the
  verdict registry are not updated in lockstep, migrated files load-but-disappear
  or v3 projects fail validation. Covered by the §Discovery edits + regression
  tests.
- **Number-assignment determinism.** Must be reproducible (sort by `created:`
  then path) so re-runs and parallel migrations agree.
- **Scale.** A near-total id rewrite across projects with 150–170 entities per
  kind. The dry-run diff is the safety valve; migrate one project at a time
  behind the `layout_version` bump.

## Open questions

None blocking. Width 4, gap-tolerance, the papers citekey exception, and the
`layout_version: 3` marker are settled; the task-unification follow-on is
explicitly deferred.
