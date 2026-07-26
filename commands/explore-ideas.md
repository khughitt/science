---
description: Generate the candidate research questions (and testable hypotheses) a project is MISSING — a blind, multi-lens idea-expansion pass de-anchored from the existing hypotheses. Report-first; --apply promotes kept candidates to entities with source-faithful origins. Use when the user asks "what questions/hypotheses are we missing?".
---

# Explore Ideas

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

Parse `$ARGUMENTS`. Two modes, selected by the presence of `--apply`.

**Generate mode (default, read-only):**

- `--center <topic-id>` — narrow generation around one topic.
- `--topic <name>` — narrow around a named topic instead of the whole
  project (equivalent to `--center`, by name rather than id).
- `--lens <name>` — repeatable; restrict to specific lenses. Default: all
  six lenses (see the table in Phase 2).
- `--n <k>` — **ceiling** on candidates per lens (default 5), not a quota. A
  lens returns fewer when it has fewer strong ideas.
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

Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role:
`research-assistant`), same as `next-steps`/`search-literature`.

## Mode detection

If `--apply` is present in `$ARGUMENTS`: **Apply mode** — skip straight to
"Apply mode" below; do not run any of the Generate phases. Otherwise:
**Generate mode** — run Phases 1–4 in order.

## Generate — Phase 1: Frame

Assemble a **blind domain brief**. Run the seed diagnostic **first** — it
resolves the scope boundary for you and tells you where it came from:

```bash
uv run science explore-ideas seed-coverage --format json
```

Then read, in order:

1. `science.yaml` — used **fully**: fold `summary`, `tags`, `aspects`,
   `data_sources`, and `ontologies` into the brief as scope terms (not just the
   project domain). These are self-declared scope, not claims.
2. The `research-question` and `scope-boundaries` documents at the paths
   `brief_sources[]` reports — **do not guess these paths**. Specs are
   canonicalized to `entities/specs/NNNN-slug.md` by
   `science entity migrate-specs`, so in a migrated project the legacy
   `specs/scope-boundaries.md` is gone while the boundary itself is very much
   present. Reading the legacy path directly is how the scope boundary went
   unread fleet-wide (fb-2026-07-25-004).
3. `entities/topics/` — use **all topic titles for breadth** (the subject areas
   the project cares about, even where the body is an uncurated stub) plus the
   bodies of **substantive** topics for depth. Do not let a few fleshed-out
   topics become the whole brief.

Read **only** the two spec documents the diagnostic names — never glob
`specs/*.md` or `entities/specs/*.md`, and do **not** read
`entities/hypotheses/`, `entities/questions/`, or `entities/papers/` in this
phase. They are deliberately excluded: the project's existing epistemic framing
and paper set must not leak into the brief the lens agents receive; that framing
is exactly what this pass is trying to get outside of. (Broadening the brief
means adding *scope/method* signals, never claims.)

`seed-coverage` is a non-blind diagnostic; it is **for the report only and is
never passed to the Phase-2 agents**. When `stub_dominated` is true, the
`topics/` seed is thin/skewed — lean harder on the blindness-safe breadth
sources (all topic titles, `science.yaml` tags/`data_sources`) so the brief
still reflects the project's real scope rather than collapsing onto the handful
of curated topics. Carry the returned
`n_topics`/`n_substantive`/`stub_ratio`/`stub_dominated`/`scope_source` into
Phase 4.

**When `scope_source` is `absent`**, no boundary document exists anywhere. You
may still infer scope from `science.yaml` and `AGENTS.md` — but record
`scope_source: inferred` in the report, not `absent`, and state in one line what
you inferred it from. `out-of-scope` novelty calls made against an inferred
boundary are your reconstruction, not the project's declaration, and the report
must not let a reader mistake one for the other.

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
- `n` (from `--n`, default 5), passed as a **ceiling**: tell the agent to
  return *up to* `n` candidates and to return fewer, with a stated reason, when
  the lens has fewer strong ideas. A per-lens quota manufactures filler — every
  lens returned exactly 5 in the run that prompted this, and both candidates
  later dropped as true-but-inert came from the lens that plainly had the least
  to say (fb-2026-07-25-005). A short return is a signal about the lens, not a
  failure.
- any `--center`/`--topic` focus

| Lens | Frame |
|------|-------|
| `mechanism` | causal/biological mechanism and pathway |
| `methodology` | measurement, assay, study-design, analysis method |
| `population` | population, context, subgroup, setting, boundary conditions |
| `contrarian` | what if the dominant assumption is wrong; null/negative framing |
| `analogy` | cross-disciplinary analogy — how an adjacent field would frame it |
| `temporal` | temporal/longitudinal/dynamics dimension |

Each agent returns a JSON object: `{lens, lens_note, candidates[]}`. Pool the
`candidates` and keep every `lens_note` — it is the lens-productivity signal,
and it goes into the Phase-4 report header beside `seed_coverage`. Do not
deduplicate or judge novelty here — that is Phase 3's job, run with full
visibility this phase deliberately lacks.

A lens returning 2 candidates when `n` was 5 has told you something about the
brief. Record it; do not re-dispatch the lens to fill the gap.

## Generate — Phase 3: Classify (full visibility)

Only now load the existing surface. This is where blindness ends and the
orchestrator (you) compares the pooled candidates from Phase 2 against what the
project already has.

**Two surfaces, and they are not the same set.**

*The judging surface (wide)* — everything the project already holds, which is
what novelty must be measured against:

```bash
uv run science project index --format json     # questions + hypotheses
uv run science entity list --format json       # every other kind, too
uv run science tasks list --format json        # queued work
```

plus `entities/topics/` and `core/decisions.md`. Judging against questions and
hypotheses alone is how a pass calls a candidate `novel` that an existing
command, skill, or queued task already covers — three such calls in the run that
prompted this (fb-2026-07-25-001), each caught only by manual inspection.

*The relation surface (narrow)* — `related_existing` targets **question and
hypothesis ids only**, unchanged (see below). Apply hard-validates against
exactly those two kinds.

A candidate may therefore be judged `already-covered` against a task, a topic,
or a non-epistemic entity **while carrying an empty `related_existing`**. That
is correct, not an omission: name what covers it in the candidate's prose. Do
not widen `related_existing` to make the two surfaces match.

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
   - `out-of-scope` — falls outside the scope boundary Phase 1 resolved. When
     `scope_source` is not `declared`, you are judging against an inferred
     boundary; say so in the candidate's prose rather than presenting the call
     as a check against the project's own declaration.
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

   **Copy each row's `verification` into its anchor, always.** The resolver
   consults `entities/papers/` and `papers/references.bib` and nothing else, so
   an anchor that matches neither has had its identity confirmed by nothing —
   47 of 49 anchors in the run that prompted this (fb-2026-07-25-006). A null
   `ref` alone does not say that; a reader sees a DOI, a title, an author and a
   year and reasonably reads a validated reference. `verification: verified`
   and a non-null `ref` are set together or not at all — apply rejects a block
   carrying one without the other, in either direction.

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
4. **Convergence and cluster detection.** Two relations, at different
   strengths — a single high bar merges nothing when candidates are *related*
   but not *identical*, which is how three candidates describing one mechanism
   on three axes shipped as three near-duplicate blocks (fb-2026-07-25-003).

   - `convergence_group: <id>` — candidates from two or more lenses
     **independently describe the same idea**. Phase 4 emits **one** block
     carrying multiple `lens_views`. Convergent lenses are not collapsed to
     one; the whole idea is one block.
   - `cluster_group: <id>` — candidates describe **different ideas on one
     mechanism, theme, or axis**. This does *not* decide the block count.

   For every `cluster_group`, Phase 4 MUST state explicitly whether it emits one
   block or N, and why. Naming a cluster in the report summary without acting on
   it is the failure this exists to prevent: the reader is told the candidates
   overlap and left to do the merge by hand.

   Both fields are internal Phase-3 classification aids; Phase 4 emits exactly
   one block per apply unit.

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
  scope_source: declared # declared | inferred | absent
  scope_path: entities/specs/0037-scope-boundaries.md   # omit when not declared
lens_yield:
  - lens: mechanism
    n_returned: 5
    note: rich mechanistic literature; ceiling reached
  - lens: population
    n_returned: 2
    note: brief declares a single cohort, so subgroup framings had little to bite on
```

`lens_yield` carries one row per dispatched lens, from each agent's `lens_note`.
A lens that returned fewer than `--n` is reporting on the brief, not failing.

`scope_source` is copied from `seed-coverage` when it reports `declared` or, on
`absent`, set to `inferred` if you reconstructed scope from `science.yaml` /
`AGENTS.md` (say from what, in one line) — or left `absent` if you did not. It
is the provenance of the single most anchoring-relevant input to a blind pass,
and `out-of-scope` calls are only as good as it is.

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
    verification: unverified
novelty_bucket: novel
related_existing: []
decision: defer
decision_note: null
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

**`decision_note` (optional) records *why*.** The decision itself is a bare
token, so a considered rejection and an oversight read identically to anyone
opening the report later — eight candidates were dropped for materially
different reasons in the run that prompted this, and every reason lived only in
the conversation (fb-2026-07-25-007). Write one whenever the reason is not
obvious from the block: inert, badly individuated, absorbed into another block,
out of scope for a stated reason. Apply echoes every note in its summary. A
`keep` rarely needs one — the block is its own justification.

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
