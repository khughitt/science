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
3. Load the `science-scientific-writing` Codex skill. For research methodology, read `../../skills/INDEX.md` and load the leaves relevant to the task (e.g. `literature-evaluation`, `literature-citation-discipline`, `epistemics-proposition-graph-reasoning`).
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
8. **Verify the project-local Science CLI:** Execute the top-level CLI
   Compatibility Gate below before the command's first Science invocation. It
   uses the consumer's frozen lock; do not route through a toolkit checkout or
   another environment.

## CLI Compatibility Gate

```bash
SCIENCE_REQUIRED_VERSION=0.3.0
if output=$(uv run --frozen science --version 2>&1); then
  SCIENCE_INSTALLED_VERSION=${output##* }
elif uv run --frozen science --help >/dev/null 2>&1; then
  # The CLI runs but has no --version option, so it predates the baseline.
  # Decided by behavior, never by matching Click's version-dependent wording.
  SCIENCE_INSTALLED_VERSION=
else
  # The CLI cannot run at all: missing/stale lock, Git fetch failure, import
  # error. Report the real diagnosis; never advise moving the Science pin.
  printf '%s\n' "$output" >&2
  exit 1
fi

if ! SCIENCE_INSTALLED_VERSION="$SCIENCE_INSTALLED_VERSION" \
     SCIENCE_REQUIRED_VERSION="$SCIENCE_REQUIRED_VERSION" \
     uv run --no-project python - <<'PY'
import os
import re
import sys

def release(name: str) -> tuple[int, int, int] | None:
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", name)
    return tuple(map(int, match.groups())) if match else None

installed = release(os.environ["SCIENCE_INSTALLED_VERSION"])
required = release(os.environ["SCIENCE_REQUIRED_VERSION"])
sys.exit(0 if installed is not None and required is not None and installed >= required else 1)
PY
then
  display=${SCIENCE_INSTALLED_VERSION:-unknown-or-pre-0.3.0}
  echo "This Science agent command requires science >=$SCIENCE_REQUIRED_VERSION; found $display." >&2
  echo "upgrade with: uv lock --upgrade-package science && uv sync --frozen" >&2
  exit 1
fi
```

After the gate succeeds, run the command through the consumer's project-local
environment as `uv run science <command>`. Missing dependency, missing or stale
lock, and Git fetch failures are surfaced directly and must be fixed in the
consumer project.

A CLI that answers `--help` but rejects `--version` predates the baseline;
malformed successful output and a version below the floor are likewise
compatibility failures, and all three stop with the upgrade command. A CLI that
cannot run at all is an environment failure: its output is printed verbatim and
must be fixed as reported.

The `--help` probe is what separates those two classes. Do not substitute a match
against Click's error text — its wording changed in Click 8.4, and `science`
allows any `click>=8.1`, so a freshly locked consumer can emit either form. The
root `--version` probe is the permanent bootstrap surface; do not replace it with
a preflight subcommand, which an older CLI could not recognize either.

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

   **`related_existing` targets question and hypothesis ids only.** The project
   index and `resolve-refs` expose exactly those two kinds, and apply validates
   against them. Comparing a candidate against a `topic:` or `theme:` (which the
   brief's `entities/topics/` pass surfaces) is legitimate and **informs your
   novelty judgment**, but a topic/theme is not a citable relation target — do
   not put `topic:`/`theme:`/bare-slug values in `related_existing` (they will
   fail resolution). If a topic comparison matters, record it in the candidate's
   prose, not as a relation.

   **A `sharpens-existing` candidate you want to keep gets `decision: fold`**
   (see the decision vocabulary below), with the entity it sharpens in
   `related_existing`. `fold` records the intent as a worklist item; apply
   writes no new entity, so you fold the framing into the existing entity by
   hand rather than minting a near-duplicate.
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

   **Anchor metadata is model-generated — treat it as unverified.** The lens
   agents emit DOIs/authors/titles from search, and a valid-looking DOI can
   point at a real but unrelated paper. The resolver guards against the worst
   case: when an anchor resolves by DOI or citekey but its stated title/year
   disagree with the resolved record, it reports **`mismatch`** (not `resolved`)
   with the discrepancy. **Never copy a `mismatch` row's ref** — the DOI names a
   different work than the anchor claims. Fix the identifier (or drop it) and
   re-run; a `predates:` mismatch would otherwise misattribute a literature
   origin in the graph.
   Omit unknown identifier fields rather than writing empty placeholders such
   as `doi: ""` or `doi: null`; anchors with no usable `ref`, `doi`, citekey,
   title, or `openalex_id` are ignored by the resolver.
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
`kind:`/entity frontmatter. Keep generated exploration reports under
`doc/explorations/`; prose lint treats that directory as process-output space
and skips it by default.

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

**Titles and the optional `slug:` field.** A block's `title` is what the entity
is called; its **id** is derived from that title and capped at 72 characters on
a word boundary. Apply refuses any `keep` block whose title would lose its
discriminating tail to that cap — refuses the *whole report*, before creating
anything, so a long title in block 11 cannot strand blocks 1–10 half-applied.
Two ways to satisfy it, and prefer the first: keep titles short enough to
survive the cap (a research question that needs 90 characters to state is
usually two questions), or, when the long title is genuinely the right name, add
an optional `slug:` naming a shorter id:

```yaml
title: Collaboration scale at which the single-owner graph model breaks down under concurrent authorship
slug: single-owner-graph-collaboration-scale
```

The full title still lands on the entity; only the id is shortened. Omit `slug:`
whenever the title derives cleanly — it is a recovery path, not routine. Run
`--check` before `--apply` to see every offending block at once.

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

`decision` defaults to `defer`; the human edits it in place before running
`--apply`. The vocabulary is:

- `keep` — apply creates a new entity from the block.
- `drop` / `defer` — apply skips the block.
- `fold` — for a `sharpens-existing` candidate: apply creates **no** entity and
  instead records a fold worklist item (`related_existing` names the entity to
  fold into). Use this instead of `keep` when the candidate sharpens an existing
  entity rather than adding a new one, so apply never mints a near-duplicate.

Never set `decision: applied` yourself — it is written only by Apply mode
(below), as write-back.

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
creates, skipped blocks, and any manual blocks reserved for future
valid-but-not-routable decisions.

- `<report-path-or-id>` is the `--from` value: a path to the report file, or the
  report id — its basename stem, e.g. `explore-2026-07-04` (the `explore-` prefix
  is already part of the id and is not re-prepended).
- `<your-model-id>` is the id of the model running this command.

The CLI parses every fenced `yaml` block that has a `candidate_id`, and for each
`decision: keep` question, hypothesis, topic, or theme it creates a real entity
— routing `origin_plan.origins` to `origins`, supporting (non-`predates:`)
resolved anchors to `source_refs`, and stamping
`--added-by explore-ideas:<model-id>:<candidate_id>` — then writes `decision:
applied` + `applied_as` + `applied_at` back into that block. The created entity
starts **non-hollow**: apply seeds its lead section with the block's
`question_or_claim` and per-lens `rationale`, so the researched framing is not
discarded (a block carrying neither leaves a bare scaffold that `gaps` flags). A
`decision: fold` block creates no entity — it is reported in the summary as a
fold worklist item for you to hand-fold into the entity named in its
`related_existing`. It is idempotent: a re-run skips blocks already `applied`;
`drop`/`defer`/`fold` are skipped. Bad input (duplicate ids, unknown
`decision`/`proposed_kind`, a `keep` block missing `title`/`origin_plan.origins`,
a `fold` block missing `related_existing`, malformed origins, malformed
`lens_views`, unresolved or ambiguous `related_existing`, malformed routed
anchors, or a `title`/`slug:` that cannot form a valid entity id) is rejected
before anything is written.

Relay the CLI's created / skipped / manual / fold / failure summary to the user.
If `--commit` was passed, commit the created entities plus the updated report
with `feat(explore-ideas): apply kept candidates YYYY-MM-DD`.

Add `--format json` if you need the machine-readable result instead of the text
summary.

After apply, inspect the created entities for deterministic follow-up gaps:

```bash
uv run science explore-ideas gaps --from <report-path-or-id>
```

Use `--format json` when another tool needs the structured result. The gaps
command is read-only. It inspects only `decision: applied` blocks and reports
repair work such as `missing_applied_as`, `missing_entity`, `empty_body`,
`unresolved_anchors`, `missing_source_refs`, `missing_related`, and
`missing_lens_views`.
