# Unified entity organization & naming — design

**Date:** 2026-06-03
**Status:** Proposed
**Scope:** `science` tool (CLI, validation, migration) + downstream project layout convention

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
   - `claim-registry.yaml` exists only in `multiple-myeloma`.

   `natural-systems` is the well-behaved counterexample: clean `q##-`, `h##-`,
   and date-prefixed interpretations/discussions throughout.

### What already exists in the model

The model already encodes the taxonomy this design leans on.
`science_model/entities.py:111-125` defines `EntityClass`:

- **EPISTEMIC** — belief-bearing; valid `bears_on` targets in the evidence graph
  (question, hypothesis, proposition, interpretation, discussion, finding,
  inquiry, theme, evidence-line, observation, mechanism, report/synthesis,
  research-question, …).
- **REFERENCE** — external, stable (concept, topic, article).
- **OPERATIONAL** — artifacts produced by work (plan, search, method,
  pre-registration, paper, dataset, task, workflow, experiment, code-file).

The kind→class map lives in `graph/entity_registry.py:48-91`. The path policy
(`_BUILTIN_MARKDOWN_POLICIES`, `src/science_tool/entities.py:33-41`) is the
existing — but incomplete — source of truth for where source-authored markdown
kinds live and how they are named.

## Decisions

These were settled during brainstorming:

1. **Single `entities/` home** (Scheme B). All source-authored markdown entities
   live under `entities/<kind>/`. `doc/` becomes prose-only. `specs/` is
   retired. `EntityClass` stays as frontmatter metadata + validation, not as
   directory depth.
2. **Global canonical naming** (not per-project policy). Trade one-time migration
   for a single, uniform model.
3. **Fully uniform numeric naming.** Drop the letter prefix *and* the date
   prefix. The directory signals the kind; the id carries the kind. Every kind
   converges on `NNNN-slug`.
4. **Fixed width 4** (`0001`–`9999`). Sorts correctly under plain `ls`;
   effectively uncapped in practice (~60× the largest current kind). Crossing
   9999 is a rare, explicit, CLI-managed re-pad event.
5. **Build all three:** validation/health checks, a `science entities migrate`
   command, and a migration guide.
6. **Tasks are a designed-for follow-on.** Conventions are chosen so
   `tasks/`/`datasets/`/`workflows/` can fold into `entities/` later, but their
   storage/tooling migration is out of scope here.
7. **All recognized entity kinds go under `entities/`** — including `synthesis/`,
   `plans/`, `searches/`, `methods/`, `pre-registrations/`, `papers/`. `doc/` is
   strictly prose.
8. **Gaps in numbering are tolerated.** The migrate command does not renumber to
   make sequences contiguous; a gap can be meaningful (a retired `h5`), and
   renumbering would cause needless id churn.

## Target layout

```
project/
  entities/                       # ALL source-authored markdown entities
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
    plans/  searches/  methods/  pre-registrations/  papers/   # operational, markdown
  doc/                            # prose ONLY (non-entities)
    guides/  architecture/  figures/  meta/  background/  notes/
  tasks/  datasets/  workflows/  results/    # unchanged root homes (separate tooling)
```

**Principle:** *location tracks what a thing is.* Every recognized entity kind
has exactly one canonical home. Kinds with dedicated non-markdown tooling
(`tasks`, `datasets`, `workflows`) keep their root homes for now but remain
registered in the policy table so they can fold into `entities/` in the future
unification effort.

## Canonical naming — one shape for everything

`_BUILTIN_MARKDOWN_POLICIES` is promoted to the single source of truth for
**every** kind, and the `filename` field collapses from two policies
(`local-part`, `date-local-part`) to one.

| Element | Rule |
|---|---|
| Filename | `NNNN-slug.md`; width-4 zero-padded number; kebab slug (≤72 chars via existing `derive_slug`) |
| Id | `<kind>:NNNN-slug` (kind from directory; no letter; no date) |
| Numbering | Per-kind sequential from `0001`; gaps allowed (not forced contiguous) |
| Date | `created:` / `updated:` in frontmatter only |
| Shortforms | `q5`, `h3` still resolve as **input sugar** → `question:0005-…` (letter→kind map retained) |
| Required frontmatter | `id, type, title, status, created, updated` (+ per-kind fields) |

`evidence-line`'s existing `##-slug` (letterless) is the precedent this
generalizes. The `date-local-part` policy is removed entirely; numeric prefixes
assigned in `created:` order preserve the chronological sort that date prefixes
previously gave interpretations and discussions.

## CLI changes

- **`generate_entity_id`** (`src/science_tool/entities.py:171-206`) rewritten:
  remove letter/date inference and the "mixed conventions" error path; scan
  siblings for the max number and emit `NNNN` at width 4. This also fixes the
  current breakage where `multiple-myeloma` cannot create a new hypothesis.
- **Atomic reservation** — generalize the `questions.reserve`
  `O_CREAT|O_EXCL` mechanism to all kinds, so parallel agents do not collide on
  a number.
- **`path_for_entity` / `resolve_path_policy`** read the unified policy;
  `_ALLOWED_EXPLICIT_ROOTS` updated to `entities`, `doc`.
- **New `science entities migrate`** command (§Migration).

## Validation / health checks

New checks, driven by the policy table. They emit WARN during transition and are
promotable to ERROR once a project declares it is migrated (see Transition).

1. **Location coherence** — a file's directory matches its `type`/`id` kind; no
   entity files stranded in `doc/` or `specs/`.
2. **Filename conformance** — matches `NNNN-slug` at width 4; the filename
   local-part equals the `id` local-part.
3. **Frontmatter completeness** — required fields present. Directly catches
   `pan-disease` interpretations that have no frontmatter, only prose headers.
4. **Number hygiene** — no duplicate numbers within a kind; flag mixed widths.
5. **Stray-file check** — non-entity files sitting in `entities/<kind>/`.

`id_prefixes.py`'s `PREFIX_RULES` becomes a derived view of the policy table so
the two lists cannot drift apart.

## Migration: command + guide + transition

### `science entities migrate [--apply]`

Dry-run by default (mirroring the existing `migrate_identifiers` contract). Steps:

1. **Discover** all entity files in legacy locations (`doc/<kind>/`,
   `specs/<kind>/`).
2. **Plan** target path + new id per the policy. Assign numbers in `created:`
   order so chronology is preserved; backfill a missing `created:` from the git
   first-commit date (fallback: file mtime). Preserve already-conformant numbers
   where possible.
3. **Build the full old→new id map first**, then **rewrite all references** in a
   single pass using the graph `ReferenceResolver`/entity registry — `id:`,
   `related:`, claim-registry entries, task-graph refs, and inline `<kind>:…` /
   `[[…]]` mentions in prose. Re-run graph validation and **fail loud** on any
   unresolved reference.
4. **Move files** with `git mv` (preserve history); backfill missing frontmatter
   (synthesize from prose headers where needed).
5. **Emit a diff/report**; `--apply` commits the changes.

### Transition coexistence

A per-project layout marker in `science.yaml` (e.g. `layout: v2`) tells
validation whether to treat conformance as WARN (un-migrated / in progress) or
ERROR (migrated). Existing `SCIENCE_VALIDATE_SKIP_*` escape hatches are retained.

### `docs/migration-guide.md`

For agents and humans: when to run migrate, how to review the dry-run diff, and
how to handle edge cases the command flags — e.g. `pan-disease`'s multi-file
`.lock.yaml` hypotheses and prose-header interpretations needing frontmatter
synthesized.

## Scope boundaries (YAGNI)

- **In:** reorg to `entities/`; uniform numeric naming; the policy table as
  single source of truth; the five validation checks; the migrate command; the
  guide. Covers epistemic + reference + markdown-operational kinds.
- **Out (future):** unifying `tasks` / `datasets` / `workflows` storage into
  `entities/` and reworking the task DAG. Conventions are chosen to make this
  clean later, but it is a separate project.

## Key risks

- **Reference-rewrite completeness.** A missed inline `question:q01-…` becomes a
  dead link. Mitigation: build the full id-map first, rewrite atomically, re-run
  graph validation, fail loud on any unresolved ref.
- **Number-assignment determinism.** Must be reproducible (sort by `created:`
  then path) so re-runs and parallel migrations agree.
- **Scale.** A near-total id rewrite across projects with 150–170 entities per
  kind. The dry-run diff is the safety valve; migrate one project at a time
  behind the `layout: v2` marker.

## Open questions

None blocking. Width 4 and gap-tolerance are settled; the task-unification
follow-on is explicitly deferred.
