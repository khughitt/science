# Seed Representativeness in the `explore-ideas` Blind Brief

> **Status:** Active design note (Science). Proposes a change to the
> `explore-ideas` Phase-1 (Frame) contract and a small supporting code surface.
> Amends `docs/plans/2026-07-04-explore-ideas-design.md` §Phase 1. Motivated by
> upstream feedback `fb-2026-07-05-002` (`command:explore-ideas`), filed from the
> MM30 (`multiple-myeloma`) project's first substantive `explore-ideas` run on
> 2026-07-05.

## Goal

Make the Phase-1 domain brief a **representative** sample of what the project
actually studies — so the blind lens agents in Phase 2 generate against the
project's real scope rather than against whichever handful of topics happen to
be fleshed out. Do this **without weakening the structural blindness** that is
the command's whole reason to exist.

## Motivating evidence (MM30, 2026-07-05)

Phase 1 seeds the brief from `science.yaml`, `specs/`, and `entities/topics/`.
On MM30 that seed was badly unrepresentative:

- **34 of 37 topic files were uncurated stubs** (bodies containing only the "has
  not yet been curated" template marker).
- The **only 3 substantive topics all clustered in one area** —
  translation / ribosome / PRC2 — which is *exactly* where the project's
  existing questions already concentrate.
- Whole pillars of the actual project — cytogenetics / virtual-FISH, the
  AP-1 / hyperdiploidy program (~20 questions), causal-inference methodology,
  3D-genome — had **zero topic backing**.

Two consequences follow, and the second is the subtle one:

1. **The brief was thin.** Three real topics is not much of a project view.
2. **The brief was skewed toward already-covered ground.** The fleshed-out
   topics bias the generative neighborhood, and here they coincided with the
   best-covered areas — so generation near the seed mostly reproduced
   already-covered / sharpens-existing material, while the genuinely novel hits
   came from the agents ranging *away* from the brief via their own literature
   search.

The run only produced good novelty because the orchestrator **manually enriched
the brief** from `AGENTS.md` (the project's 13-stage pipeline description) —
context Phase 1 does not prescribe reading. A faithful execution of the current
contract would have been thinner and more skewed. The command should not depend
on an out-of-contract rescue.

## The central tension: blindness vs. representativeness

Phase 1 is deliberately blind. It **must not** read
`entities/hypotheses/`, `entities/questions/`, or `entities/papers/`, because
the existing epistemic framing is exactly what the pass is trying to get outside
of (design doc §2). "Make the brief more representative" reads, naively, as
"feed it more of the project" — which is precisely the anchoring the command
forbids.

The resolution is to split one conflated object into two:

- **The blind brief** — the inline text the Phase-2 agents receive. It may be
  *broadened*, but only with **scope and method signals**, never with claims,
  findings, or the existing question/hypothesis set.
- **The (non-blind) seed-coverage diagnostic** — computed by the orchestrator,
  which is *not* blind, and surfaced in the report for the human. It **may** look
  at the full entity index, because it never reaches the lens agents. Its job is
  to answer "how representative was the brief?" and to warn when the answer is
  "not very."

Blindness is a property of *what crosses into the dispatch prompt*, not of what
the orchestrator is allowed to compute. Keeping these two objects distinct is the
core move of this design; everything below follows from it.

## What may broaden the brief (blindness-safe sources)

A source is admissible to the brief iff it describes **what the project studies
or how** (subject area, scope, data, assays, methods), not **what it has
concluded or is asking**. Admissible:

1. **`science.yaml`, used more fully.** Today Phase 1 reads it for "domain,
   aspects, scope signals." Broaden that to explicitly fold in `summary`,
   `tags`, `aspects`, `data_sources`, and `ontologies` as scope terms. These are
   self-declared scope, not claims.
2. **`specs/research-question.md` and `specs/scope-boundaries.md` when present**
   (already in the contract — *these two named files only*, not all of
   `specs/`). Broadening to arbitrary `specs/*.md` is deliberately excluded: a
   project may keep specific questions or claim-shaped notes there, and reading
   them wholesale would reintroduce exactly the framing leak Phase 1 forbids. If
   a future revision wants more of `specs/`, it must define an explicit
   allowlist rule, not glob the directory.
3. **All topic *titles* as a coverage map, plus substantive topic *bodies* for
   depth.** Topic titles enumerate the subject areas the project cares about
   even when the body is an uncurated stub. Titles are subject labels, not
   claims, so using *all 37* titles — not just the 3 with bodies — restores
   breadth without leaking framing. (Topics are already a fully-read Phase-1
   input; this only changes *how much* of them is used.)

Explicitly **not** admissible to the brief (unchanged from §2): any content of
`entities/hypotheses/`, `entities/questions/`, or `entities/papers/`. The
project's pipeline/config (e.g. Snakemake stage names, assay list) is *scope/method*
and would be admissible in principle, but it is project-shaped, not a generic
`science` surface; v1 does not read it. The generic substitute for "the MM30
pipeline description that rescued the run" is the fuller `science.yaml` +
all-topic-titles breadth above.

## The seed-coverage diagnostic

A deterministic metric, computed by the orchestrator and reported — never sent
to agents.

**Substantive vs. stub (deterministic).** This is a pure function of the file and
belongs in code, not agent judgment — but it must be specified precisely, because
there are **two distinct stub shapes** and a naive "empty body" test
misclassifies the common one:

- **Template stub** — a freshly created topic from the packaged
  `background-topic.md` template: headings plus `<!-- … -->` comment prompts, no
  prose. Its body is empty *after normalization*.
- **Promoted / substrate-retirement stub** — the shape that dominates MM30
  (34/37): full heading scaffolding **plus placeholder prose sentences** such as
  "A focused narrative summary has not yet been curated.", "Curated key concepts
  have not yet been added.", "Project-specific relevance has not yet been
  separately curated." Its body is *not* empty, so an empty-body test wrongly
  scores every one of these as substantive.

Detection algorithm (v1):

1. **Normalize the body:** drop YAML frontmatter, then strip ATX headings
   (`^#+ …`), HTML comments (`<!-- … -->`), list-marker prefixes (`- `, `* `),
   and blank lines. What remains is the set of *residual content lines*.
2. **Classify residual lines:** a line is a **placeholder** if it matches the
   packaged sentinel set — case-insensitively, the family
   `(has|have) not yet been (curated|added|separately curated)` (which covers all
   five sentences the MM30 promotion emits). The sentinel set is an explicit,
   versioned constant in code, not an open-ended heuristic.
3. **Verdict:** the topic is a **stub** iff it has no residual content lines *or*
   **every** residual content line is a placeholder. It is **substantive** iff at
   least one residual line is real prose. (Bias: any genuine content →
   substantive; a partially-curated topic with leftover placeholders still counts
   as substantive.)

**Reported quantities (v1):**

- `n_topics`, `n_substantive`, and `stub_ratio = 1 - n_substantive/n_topics`.
- **Zero-topics case is explicit, not a division:** when `n_topics == 0`, emit
  `stub_ratio: null`, `stub_dominated: false`, and a `note: "no topics"`. A
  project with no `entities/topics/` is a legitimate (thin) state, not an error.
- A **warning** (`stub_dominated: true`) when the seed is stub-dominated:
  `stub_ratio > 0.5`. This would have fired on MM30 (34/37 = 0.92).

**Deferred to a later slice (see Non-goals):** the richer "does the seed cover
the project's active thematic clusters?" comparison, which requires clustering
the full question/hypothesis index. That comparison is legitimately non-blind
(orchestrator-only) but is a larger, fuzzier step; v1 ships the cheap
deterministic counts and the stub-ratio warning, which already would have flagged
MM30 (34/37 = 0.92).

## Phase-1 contract changes

Amend `explore-ideas.md` §"Generate — Phase 1: Frame":

1. **Broaden admissible brief sources** per "What may broaden the brief" above —
   use `science.yaml` more fully, and use **all** topic titles for breadth plus
   substantive bodies for depth.
2. **Compute the seed-coverage diagnostic** (below) and **emit it in the Phase-4
   report header** as a small block: `n_topics`, `n_substantive`, `stub_ratio`,
   and the warning line when stub-dominated. This makes "the brief was thin/
   skewed" a visible, first-class caveat on every run rather than a thing the
   reader must infer.
3. **When stub-dominated, say so in the brief-construction step** and lean harder
   on the blindness-safe breadth sources (titles, `science.yaml` tags/
   data_sources) so a stubby `topics/` does not collapse the brief to a few
   bodies.

## Supporting code surface (the "first slice")

The measurement must be deterministic, so it lives in code, not prose
instruction — the same reasoning that makes the Phase-3 slug pre-pass code rather
than agent discretion (`fb-2026-07-05-003`). Propose a read-only helper:

```
uv run science project topic-coverage --format json
# -> {
#   "n_topics": 37,
#   "n_substantive": 3,
#   "stub_ratio": 0.919,
#   "stub_dominated": true,
#   "topics": [
#     {"id": "topic:npm1-ribosome-pi-resistance", "title": "NPM1 ribosome / PI resistance",
#      "path": "entities/topics/npm1-ribosome-pi-resistance.md", "substantive": true},
#     {"id": "topic:perseus-trial", "title": "PERSEUS trial",
#      "path": "entities/topics/perseus-trial.md", "substantive": false},
#     ...
#   ]
# }
# zero-topics: {"n_topics": 0, "n_substantive": 0, "stub_ratio": null,
#               "stub_dominated": false, "note": "no topics", "topics": []}
```

- Pure function over `entities/topics/`; no network, no writes.
- **Per-topic rows, not a flat title list.** Each row is
  `{id, title, path, substantive}`, so a caller can trace any entry back to its
  file (titles alone collide and are not addressable). Rows are sorted
  deterministically **by `id`**. The command derives whatever flat lists it needs
  (all titles for breadth; substantive titles for depth) from these rows — the
  helper does not also emit redundant derived arrays.
- Small enough to be the first shippable slice; the cluster-coverage comparison
  layers on later without changing this surface.

**Namespace: `science project topic-coverage`, not `science explore-ideas …`.**
The *measurement* — how much of `entities/topics/` is curated — is a generic
project-health fact, sibling to `project index`, and is reusable beyond this
command (curation dashboards, a future advisory `validate` note). Only the
*interpretation* ("was the explore-ideas seed representative?") is command-
specific, and that interpretation lives in the command markdown, not the helper.
Keeping the generic fact under `project` avoids burying a reusable inspector
inside one command's namespace.

Everything else stays as prose in the command markdown (reading `science.yaml`
more fully, folding titles into the brief, emitting the header block).

## Validation

- `topic-coverage` is covered by unit tests over a fixture `entities/topics/`
  exercising **both stub shapes** (a packaged-template comment-only stub and a
  promoted placeholder-prose stub), a genuinely substantive topic, and a
  **partially-curated** topic (real prose + leftover placeholder line → must
  score substantive). Assert `n_*`, `stub_ratio`, the `stub_dominated` threshold
  at exactly 0.5, deterministic `by-id` row ordering, and the **zero-topics**
  branch (`stub_ratio: null`, `stub_dominated: false`).
- No new `science validate` check in v1: the diagnostic is advisory, not a
  well-formedness constraint. (A project is not *invalid* for having stubby
  topics.)

## Non-goals (v1, YAGNI)

- **No cluster-coverage comparison** against the question/hypothesis index yet —
  deferred; needs a clustering step and a defensible "cluster" definition.
- **No next-run biasing.** Using coverage (and the multi-lens "which lens is
  under-represented" signal from
  `meta/doc/plans/2026-07-04-multi-lens-first-class-representation-design.md`) to
  steer a subsequent pass toward thin areas/lenses is a natural follow-up, not
  this slice.
- **No auto-generation of topic stubs into substance.** Fixing the *content* of
  `topics/` is project curation work, not an `explore-ideas` responsibility;
  this design only makes the thinness *visible and non-fatal*.
- **No reading of project pipeline/config** into the brief; kept generic in v1.

## Follow-ups this design implies

- Tool tasks against `~/d/science/science`: the `project topic-coverage` helper +
  tests; the Phase-1/Phase-4 command-markdown edits; the report-header block.
- Ties to `fb-2026-07-05-003` (deterministic index-driven resolution) — both push
  discretionary Phase-1/Phase-3 judgments into deterministic code.
- Open question: the placeholder sentences are emitted by the **promotion /
  substrate-retirement path** (not by the `background-topic.md` template, which
  uses HTML-comment prompts). The `topic-coverage` sentinel set therefore
  duplicates a string that path owns. Centralize the sentinel constant so the
  emitter and the detector share one definition and cannot drift. Likely yes;
  scoped out of v1.
- Open question (from `fb-2026-07-05-002`): a cross-project "seed health"
  rollup — how representative are seeds across all `science` projects — deferred
  alongside the multi-lens design's cross-project lens-coverage question.
