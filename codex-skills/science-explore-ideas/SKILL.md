---
name: science-explore-ideas
description: "Generate the candidate research questions (and testable hypotheses) a project is MISSING — a blind, multi-lens idea-expansion pass de-anchored from the existing hypotheses. Report-first; --apply promotes kept candidates to entities with source-faithful origins. Use when the user asks \"what questions/hypotheses are we missing?\"."
---

# Explore Ideas

Converted from Claude command `/science:explore-ideas`.

## Science Codex Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load role prompt: `.ai/prompts/<role>.md` if present, else `references/role-prompts/<role>.md`.
3. Load the `science-research-methodology` and `science-scientific-writing` Codex skills. If native skill loading is unavailable, use `codex-skills/INDEX.md` to map canonical Science skill names to generated skill files and source paths.
4. Read project context from current entity roots:
   - `entities/questions/` for active research questions.
   - `entities/hypotheses/` for hypotheses.
5. **Load project aspects:** Read `aspects` from `science.yaml` (default: empty list).
   For each declared aspect, resolve the aspect file in this order:
   1. `aspects/<name>/<name>.md` — canonical Science aspects
   2. `.ai/aspects/<name>.md` — project-local aspect override or addition

   If neither path exists (the project declares an aspect that isn't shipped with
   Science and has no project-local definition), do not block: log a single line
   like `aspect "<name>" declared in science.yaml but no definition found —
   proceeding without it` and continue. Suggest the user either (a) drop the
   aspect from `science.yaml`, (b) author it under `.ai/aspects/<name>.md`, or
   (c) align the name with one shipped under `aspects/`.

   When executing command steps, incorporate the additional sections, guidance,
   and signal categories from loaded aspects. Aspect-contributed sections are
   whole sections inserted at the placement indicated in each aspect file.
6. **Check for missing aspects:** Scan for structural signals that suggest aspects
   the project could benefit from but hasn't declared:

   | Signal | Suggests |
   |---|---|
   | Files in `entities/hypotheses/` | `hypothesis-testing` |
   | Files in `models/` (`.dot`, `.json` DAG files) | `causal-modeling` |
   | Workflow files, notebooks, or benchmark scripts in `code/` | `computational-analysis` |
   | Package manifests (`pyproject.toml`, `package.json`, `Cargo.toml`) at project root with project source code (not just tool dependencies) | `software-development` |

   If a signal is detected and the corresponding aspect is not in the `aspects` list,
   briefly note it to the user before proceeding:
   > "This project has [signal] but the `[aspect]` aspect isn't enabled.
   > This would add [brief description of what the aspect contributes].
   > Want me to add it to `science.yaml`?"

   If the user agrees, add the aspect to `science.yaml` and load the aspect file
   before continuing. If they decline, proceed without it.

   Only check once per command invocation — do not re-prompt for the same aspect
   if the user has previously declined it in this session.
7. **Resolve templates:** When a command says "Read `.ai/templates/<name>.md`",
   check the project's `.ai/templates/` directory first. If not found, read from
   `templates/<name>.md`. If neither exists, warn the
   user and proceed without a template — the command's Writing section provides
   sufficient structure.
8. **Resolve science CLI invocation:** When a command says to run `science`,
   prefer the project-local install path: `uv run science <command>`.
   This assumes the root `pyproject.toml` includes `science` as a dev
   dependency installed via `uv add --dev --editable "$SCIENCE_TOOL_PATH"`
   (the distribution is `science`; the entry point it installs is `science`).
   If you are operating from a git worktree and `uv run --frozen science ...`
   fails because a relative editable `tool.uv.sources` path resolves to a
   nonexistent checkout, use the main checkout's synced environment while
   keeping the worktree as the current directory:
   `$MAIN/.venv/bin/science <command>`. For wrappers or rules that shell out to
   nested `uv run --frozen ...`, export `UV_PROJECT=$MAIN` so dependencies
   resolve from the main checkout while cwd-relative project files still come
   from the worktree.
   If that fails (no root `pyproject.toml` or science not in dependencies),
   fall back to:
   `uv run --with <science-plugin-root>/science science <command>`

Generate the research questions (and testable hypotheses) this project may be
**missing** — not a review of what already exists (that's `wander` /
`next-steps` / `bias-audit`), but a deliberately blind, multi-lens generation
pass, judged for novelty only *after* generation completes. Report-first:
this command never mutates the project's epistemic entities on its own.
`--apply` is a separate, explicit second pass that promotes only the
candidates a human marked `keep`.

The anti-anchoring is structural, not a prompt instruction: the lens
sub-agents dispatched in Phase 2 carry only `WebSearch`/`WebFetch` tools — no
`Read`, no `Bash` — so they *cannot* open this repository even if told to.
Their entire view of the project is the domain brief passed inline in their
dispatch prompt.

## Flags

Parse the user input. Two modes, selected by the presence of `--apply`.

**Generate mode (default, read-only):**

- `--center <topic-id>` — narrow generation around one topic.
- `--topic <name>` — narrow around a named topic instead of the whole
  project (equivalent to `--center`, by name rather than id).
- `--lens <name>` — repeatable; restrict to specific lenses. Default: all
  six lenses (see the table in Phase 2).
- `--n <k>` — target candidates per lens (default 5).
- `--commit` — auto-commit the written report.

`--center`/`--topic` accept **topics only** in v1. If the value resolves to a
hypothesis or question id instead of a topic, refuse and tell the user
hypothesis/question-centering is deferred — deriving focus terms from a
claim would require reading that claim, which risks anchoring the very
generation pass this command exists to keep blind.

**Apply mode (side-effecting):**

- `--apply` — promote candidates marked `decision: keep` in a report to real
  entities.
- `--check` — with `--apply`, validate and summarize the apply plan without
  creating entities or writing back `decision: applied`.
- `--from <report-path-or-id>` — **required** with `--apply`. If `--apply`
  is present without `--from`, STOP immediately with a clear error: this
  command never guesses "the latest report."
- `--commit` — auto-commit the created entities and the updated report.

## Setup

Follow `references/command-preamble.md` (role:
`research-assistant`), same as `next-steps`/`search-literature`.

## Mode detection

If `--apply` is present in the user input: **Apply mode** — skip straight to
"Apply mode" below; do not run any of the Generate phases. Otherwise:
**Generate mode** — run Phases 1–4 in order.

## Generate — Phase 1: Frame

Assemble a **blind domain brief**. Read **only** the following, in order,
skipping any that are absent:

1. `science.yaml` — used **fully**: fold `summary`, `tags`, `aspects`,
   `data_sources`, and `ontologies` into the brief as scope terms (not just the
   project domain). These are self-declared scope, not claims.
2. `specs/research-question.md`
3. `specs/scope-boundaries.md`
4. `entities/topics/` — use **all topic titles for breadth** (the subject areas
   the project cares about, even where the body is an uncurated stub) plus the
   bodies of **substantive** topics for depth. Do not let a few fleshed-out
   topics become the whole brief.

Read **only** the two named `specs/` files above — never glob `specs/*.md`, and
do **not** read `entities/hypotheses/`, `entities/questions/`, or
`entities/papers/` in this phase. They are deliberately excluded: the project's
existing epistemic framing and paper set must not leak into the brief the lens
agents receive; that framing is exactly what this pass is trying to get outside
of. (Broadening the brief means adding *scope/method* signals, never claims.)

**Measure seed representativeness.** Run:

```bash
uv run science project topic-coverage --format json
```

This is a non-blind diagnostic computed by you (the orchestrator); it is **for
the report only and is never passed to the Phase-2 agents**. When
`stub_dominated` is true, the `topics/` seed is thin/skewed — lean harder on the
blindness-safe breadth sources (all topic titles, `science.yaml`
tags/`data_sources`) so the brief still reflects the project's real scope rather
than collapsing onto the handful of curated topics. Carry the returned
`n_topics`/`n_substantive`/`stub_ratio`/`stub_dominated` into Phase 4.

If `--center <topic-id>` or `--topic <name>` was given, resolve it against
`entities/topics/` and fold that topic's subject terms into the brief so
generation narrows around it. Refuse per the Flags section above if it
resolves to anything other than a topic.

Produce a compact prose **domain brief**: what the project studies, its
scope boundaries, and its background topics. This is the entire project view
the lens agents in Phase 2 will receive — nothing more.

## Generate — Phase 2: Generate (parallel, blind)

For each selected lens (all six by default, or the `--lens` subset),
dispatch one `idea-lens-researcher` subagent, **in parallel** — send all the
`Agent` calls in a single message, the same pattern `commands/research-papers.md`
uses for `subagent_type: paper-researcher`. Dispatch by the agent's bare
frontmatter `name` — `idea-lens-researcher`, never namespaced as
`science:idea-lens-researcher`.

Pass **inline** in each dispatch prompt (the agent has no filesystem tools,
so this inline text is its whole world):

- the domain brief from Phase 1
- the lens name and its frame, from this table
- `n` (from `--n`, default 5)
- any `--center`/`--topic` focus

| Lens | Frame |
|------|-------|
| `mechanism` | causal/biological mechanism and pathway |
| `methodology` | measurement, assay, study-design, analysis method |
| `population` | population, context, subgroup, setting, boundary conditions |
| `contrarian` | what if the dominant assumption is wrong; null/negative framing |
| `analogy` | cross-disciplinary analogy — how an adjacent field would frame it |
| `temporal` | temporal/longitudinal/dynamics dimension |

Collect each agent's JSON array of candidates. Do not deduplicate or judge
novelty here — that is Phase 3's job, run with full visibility this phase
deliberately lacks.

## Generate — Phase 3: Classify (full visibility)

Only now load the existing epistemic surface:

```bash
uv run science project index --format json
```

plus `entities/topics/`. This is where blindness ends and the orchestrator
(you) compares the pooled candidates from Phase 2 against what the project
already has.

1. **Slug pre-pass (deterministic, cheap).** Slugify each candidate's
   title and compare against slugified existing entity ids/titles. An
   exact or near-exact collision is marked `already-covered` (or
   `sharpens-existing` if it's clearly a variant) immediately — no agent
   judgment spent on the obvious cases.
2. **Agent-judged buckets.** For every remaining candidate, compare against
   the index and assign exactly one `novelty_bucket`:
   - `novel` — no existing entity covers it.
   - `sharpens-existing` — a sharper/edge variant of an existing entity.
   - `already-covered` — an existing entity already asks this.
   - `out-of-scope` — falls outside `specs/scope-boundaries.md`.
   When title-level information from the index is insufficient to tell,
   **read the referenced source files** before deciding. Set
   `related_existing` for `sharpens-existing` and `already-covered`, then
   canonicalize every ref to its exact entity id with
   `uv run science project resolve-refs --query <ref> [--query <ref> ...]`
   — it matches both id-slugs and titles, so a keyword that lives only in an
   id-slug (e.g. `m6a` in `question:0037-m6a-proliferation-axis`) still
   resolves. Apply hard-validates these ids and fails on any that are
   ambiguous or unresolved, so fix them here. (The slug pre-pass above is a
   separate step — it stays as the title-level duplicate detector.)
3. **Anchor resolution.** Before finalizing `origin_plan`, run the resolver
   from the project root:

   ```bash
   uv run science explore-ideas resolve-anchors --from <report-path-or-id>
   ```

   Use `--format json` when you need machine-readable rows. For each
   candidate's `literature_anchors[]` entry, copy unambiguous resolver results
   into the anchor's `ref` field:
   - `paper:<slug>` if the DOI/title matches an entity in
     `entities/papers/`.
   - `cite:<key>` if the DOI/key is present in `papers/references.bib`.
   - otherwise leave `ref` null — ambiguous and unresolved anchors stay raw
     citations and contribute no literature origin.
   Preserve the anchor's `date` (full `YYYY-MM-DD`) if it carries one; a
   `predates:` anchor's date flows into its independent literature origin.
   Finalize each candidate's `origin_plan` from the resolution per the
   origin-plan rules in Phase 4 below.
4. **Convergence detection.** If candidates from two or more lenses
   independently describe the same idea, tag them internally with a shared
   `convergence_group: <id>` so Phase 4 knows to merge them into one block.
   Convergent lenses are **not** collapsed to one: keep the whole idea as a
   single block carrying multiple `lens_views`. `convergence_group` (if used)
   is an internal Phase-3 classification aid only; Phase 4 emits exactly one
   block per apply unit.

## Generate — Phase 4: Report

Write `doc/explorations/explore-<YYYY-MM-DD>.md`. If a report for today
already exists, suffix with `-<HHMM>` rather than overwrite it. The report is
a process artifact, not a graph entity — give it a plain human header, no
`kind:`/entity frontmatter.

**Report header — seed coverage.** Near the top of the report (after the intro,
before the candidates), emit the seed-representativeness diagnostic from Phase 1
so every reader sees how representative the brief was. When `stub_dominated` is
true, add a one-line caveat that novelty judgments were made against a thin seed.

```yaml
seed_coverage:
  n_topics: 37
  n_substantive: 3
  stub_ratio: 0.92
  stub_dominated: true   # brief was stub-dominated; treat novelty calls as made against a thin seed
```

Present candidates **neutrally** — never rank or group in a way that
privileges one source or lens over another:

- `novel` and `sharpens-existing` candidates are shown prominently.
- `already-covered` candidates are collapsed (evidence the pass isn't
  blind-spotting, not something to dwell on).
- `out-of-scope` candidates are listed separately.

Each candidate is one fenced ` ```yaml ` block carrying every schema field.
Copy this shape exactly (field names and structure — values are the
example):

```yaml
candidate_id: cand-mechanism-vagal-cytokine-feedback
proposed_kind: question
title: Vagal tone as a cytokine feedback regulator
question_or_claim: Does reduced vagal tone sustain systemic inflammation in post-acute infection syndromes?
lens: mechanism
rationale: >
  The cholinergic anti-inflammatory pathway is established in acute sepsis but
  under-explored as a chronic feedback failure in post-acute syndromes.
lens_views:
  - lens: mechanism
    rationale: >
      Same framing as the top-level rationale; one entry per lens that frames
      this idea. A single-lens candidate has one entry.
    origin_ref: explore-ideas-mechanism
literature_anchors:
  - doi: 10.1000/example
    openalex_id: W1234567890
    title: Cholinergic control of inflammation
    first_author: Smith
    year: 2021
    date: 2021-06-15
    note: relevant mechanism review
    ref: null
novelty_bucket: novel
related_existing: []
decision: defer
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-mechanism
```

When two lenses independently converge on the **same idea**, emit **one block**
for the whole idea (not one per lens): carry every converged lens as a
`lens_views` entry and one `origin_plan.origins` entry per lens, each marked
`independent: true`. Every `lens_views[].origin_ref` MUST equal one of the
planned `origin_plan.origins[].ref`. A convergent block carries its per-lens
framing in `lens_views` and omits the top-level `lens`/`rationale` fields,
which are only for single-lens blocks.

```yaml
candidate_id: cand-hspc-trained-immunity
proposed_kind: question
title: Progenitor imprinting sustains PAIS inflammation
question_or_claim: Does IL-6/STAT3 imprinting of HSPCs sustain PAIS inflammation independent of antigen?
lens_views:
  - lens: mechanism
    rationale: IL-6/STAT3 imprinting of progenitors as an antigen-independent driver.
    origin_ref: explore-ideas-mechanism
  - lens: analogy
    rationale: Read as a maladaptive trained-immunity set-point in progenitor epigenetic memory.
    origin_ref: explore-ideas-analogy
novelty_bucket: novel
related_existing: []
decision: defer
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-mechanism
      independent: true
    - type: assistant
      ref: explore-ideas-analogy
      independent: true
```

`decision` defaults to `defer`; the human edits it to `keep` or `drop` in
place before running `--apply`. Never set `decision: applied` yourself — it
is written only by Apply mode (below), as write-back.

**Origin-plan finalization rules** (apply these while assembling each
block in Phase 3→4):

- Purely reasoned candidate → `origins: [{type: assistant, ref: explore-ideas-<lens>}]`.
- A resolvable anchor whose `note` began with `predates:` → ALSO add
  `{type: literature, ref: <paper:slug|cite:key>, independent: true}`
  (convergent: independently reasoned *and* predated in the literature). If
  that anchor carries a full `date` (`YYYY-MM-DD`), add it to the origin
  (`date: <YYYY-MM-DD>`); a year-only anchor carries no date (the
  `OriginRecord` validator rejects year-only dates).
- A resolvable anchor that merely supports (no `predates:` prefix) → the
  paper belongs in the entity's `source_refs` at apply time, **not** as an
  origin. Keep the origin `assistant` only.
- Every `lens_views[]` entry links to the origin that produced it via
  `origin_ref`, which MUST match one of this block's `origin_plan.origins[].ref`.
  Apply creates `origins` and `lens_views` together atomically; a legacy block
  with only a top-level `lens`+`rationale` (no `lens_views`) synthesizes a single
  view at apply time.
- In a convergent (multi-lens) block, mark **every** per-lens `origin_plan.origins`
  entry `independent: true` — each lens reached the idea independently, and that
  is precisely what makes the entity convergent (≥2 lens-views whose origins are
  independent).

`origin_plan` holds `origins` only — `added_by` is not stored in the block;
apply stamps it fresh (below) as `explore-ideas:<model-id>:<candidate_id>`.

If `--commit` was passed: commit the report with
`doc(explore-ideas): report YYYY-MM-DD`.

## Apply mode

Apply is a single deterministic CLI call — this command does **not** re-derive
create logic in prose. Require `--from`; if absent, STOP with a clear error (see
Flags).

Run, from the project root:

```bash
uv run science explore-ideas apply --from <report-path-or-id> --model-id <your-model-id>
```

To validate through the same parser and apply validator before writing anything,
run:

```bash
uv run science explore-ideas apply --from <report-path-or-id> --model-id <your-model-id> --check
```

Use `--format json` with `--check` when you need machine-readable planned
creates, skipped blocks, and manual `topic`/`theme` blocks.

- `<report-path-or-id>` is the `--from` value: a path to the report file, or the
  report id — its basename stem, e.g. `explore-2026-07-04` (the `explore-` prefix
  is already part of the id and is not re-prepended).
- `<your-model-id>` is the id of the model running this command.

The CLI parses every fenced `yaml` block that has a `candidate_id`, and for each
`decision: keep` question/hypothesis it creates a real entity — routing
`origin_plan.origins` to `origins`, supporting (non-`predates:`) resolved anchors
to `source_refs`, and stamping `--added-by explore-ideas:<model-id>:<candidate_id>`
— then writes `decision: applied` + `applied_as` + `applied_at` back into that
block. It is idempotent: a re-run skips blocks already `applied`. `topic`/`theme`
keeps are reported as "apply manually"; `drop`/`defer` are skipped. Bad input
(duplicate ids, unknown `decision`/`proposed_kind`, a `keep` block missing
`title`/`origin_plan.origins`, or an invalid origin) is rejected before anything
is written.

Relay the CLI's created / skipped / manual / failure summary to the user. If
`--commit` was passed, commit the created entities plus the updated report with
`feat(explore-ideas): apply kept candidates YYYY-MM-DD`.

Add `--format json` if you need the machine-readable result instead of the text
summary.
