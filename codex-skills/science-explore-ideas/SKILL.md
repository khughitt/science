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
4. Read project context from layout-v3 entity roots first:
   - `entities/questions/` for active research questions.
   - `entities/hypotheses/` for hypotheses.
   - Read legacy specs/research-question.md only if it exists.
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

1. `science.yaml` (project domain, aspects, scope signals)
2. `specs/research-question.md`
3. `specs/scope-boundaries.md`
4. `entities/topics/`

Do **not** read `entities/hypotheses/`, `entities/questions/`, or
`entities/papers/` in this phase — they are deliberately excluded. The
project's existing epistemic framing and paper set must not leak into the
brief the lens agents receive; that framing is exactly what this pass is
trying to get outside of.

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
   `related_existing` for `sharpens-existing` and `already-covered`.
3. **Anchor resolution.** For each candidate's `literature_anchors[]`
   entry, try to resolve it to a real project reference and record the
   result as `ref`:
   - `paper:<slug>` if the DOI/title matches an entity in
     `entities/papers/`.
   - `cite:<key>` if the DOI/key is present in `papers/references.bib`.
   - otherwise leave `ref` null — the anchor stays a raw citation and
     contributes no literature origin.
   Finalize each candidate's `origin_plan` from the resolution per the
   origin-plan rules in Phase 4 below.

## Generate — Phase 4: Report

Write `entities/meta/explorations/explore-<YYYY-MM-DD>.md` with `type: meta`
frontmatter. If a report for today already exists, suffix with `-<HHMM>`
rather than overwrite it.

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
literature_anchors:
  - doi: 10.1000/example
    openalex_id: W1234567890
    title: Cholinergic control of inflammation
    first_author: Smith
    year: 2021
    note: relevant mechanism review
    ref: null
novelty_bucket: novel
related_existing: []
decision: defer
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-mechanism
  added_by: explore-ideas
```

`decision` defaults to `defer`; the human edits it to `keep` or `drop` in
place before running `--apply`. Never set `decision: applied` yourself — it
is written only by Apply mode (below), as write-back.

**Origin-plan finalization rules** (apply these while assembling each
block in Phase 3→4):

- Purely reasoned candidate → `origins: [{type: assistant, ref: explore-ideas-<lens>}]`.
- A resolvable anchor whose `note` began with `predates:` → ALSO add
  `{type: literature, ref: <paper:slug|cite:key>, independent: true}`
  (convergent: independently reasoned *and* predated in the literature).
- A resolvable anchor that merely supports (no `predates:` prefix) → the
  paper belongs in the entity's `source_refs` at apply time, **not** as an
  origin. Keep the origin `assistant` only.

If `--commit` was passed: commit the report with
`doc(explore-ideas): report YYYY-MM-DD`.

## Apply mode

Require `--from`; if absent, STOP with a clear error (see Flags). Resolve
`--from` to `entities/meta/explorations/explore-<id>.md` when given a bare
date-slug id (e.g. `explore-2026-07-04`), or use the literal path when given
one directly.

Parse **every** fenced `yaml` block in that file containing a `candidate_id`
key — ignore all surrounding markdown (headings, prose, the collapsed
`already-covered` list); it is for humans only. For each parsed block:

- `decision: keep` and `proposed_kind` ∈ {`question`, `hypothesis`} → build
  and run the matching create command below, capture the created entity's
  id, then **write back** into that block in the report file:
  `decision: applied`, `applied_as: <entity-id>`, `applied_at: <YYYY-MM-DD>`.
- `decision: applied` already → skip (idempotent; this is how re-running
  `--apply --from` the same report is safe).
- `decision: keep` but `proposed_kind` ∈ {`topic`, `theme`} → do **not**
  create anything; list it under "apply manually (CLI seam pending)" in the
  report to the user.
- `decision: drop` or `decision: defer` → skip.

Report created vs. skipped counts to the user. If `--commit` was passed:
commit the created entities plus the updated report with
`feat(explore-ideas): apply kept candidates YYYY-MM-DD`.

**Create command templates** (`<model-id>` = the model running this
command). Copy exact — field names, flag spellings, and the `+literature:`
independent-origin spelling all matter. There is no `--slug`: the create
path auto-derives the id from the title, and idempotence comes from the
report write-back above, not slug matching. Forward traceability back to
the report is the `candidate_id` carried in `--added-by`.

```bash
# reasoned-only question
uv run science questions create "<title>" \
  --origin "assistant:explore-ideas-<lens>" \
  --added-by "explore-ideas:<model-id>:<candidate_id>"

# convergent hypothesis (reasoned + predated in literature), plus a supporting (non-predating) paper
uv run science hypotheses create "<title>" \
  --origin "assistant:explore-ideas-<lens>" \
  --origin "+literature:cite:<predating-key>" \
  --source-ref "paper:<supporting-slug>" \
  --added-by "explore-ideas:<model-id>:<candidate_id>"
```

**Literature anchor routing** — the same rule the report's origin-plan
already encodes, restated for apply time: a resolved anchor whose `note`
began with `predates:` becomes an independent
`--origin "+literature:<paper:slug|cite:key>"`; a resolved anchor that
merely **supports** becomes `--source-ref "<paper:slug|cite:key>"`
(provenance kept, but not an origin — origin stays `assistant`); an
**unresolved** raw anchor is dropped from the create call entirely (no
origin, no source-ref) until the paper is imported into the project.
