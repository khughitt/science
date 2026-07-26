# Feedback Batch R — the `explore-ideas` cluster

Seven open filings, all `command:explore-ideas`, all from one dogfooding run
against `meta` on 2026-07-25: `fb-2026-07-25-001` … `-007`.

Successor to Batch P (`docs/plans/2026-07-26-feedback-batch-p-design.md`).
Branch `feedback-batch-r`, based on `474bd68f` (which already carries the
concurrent session's Batch Q).

## Why this cluster

One command, one run, seven independently-fixable defects. The same shape as
Batch P's correspondence-drift cluster, and treated the same way: each filing
is grounded against the tree *before* it is designed, and every fix is measured
against a recorded baseline rather than asserted.

Grounding overturned two of the seven before a line was written.

## D1 — `-002` is already fixed. Close it; do not rebuild.

The filing asks for two things: an optional per-block `slug:` field, and
up-front validation so a long title in block 11 cannot strand blocks 1–10
half-applied.

Both shipped on 2026-07-25 in `7e2e317b`, *"fix(explore-ideas): decide entity
slugs at plan time, add block slug field"* — the same day the filing was made:

- `CreatePlan.slug` (`explore_ideas.py:63-65`), parsed and type-checked at
  `:693-696`.
- `resolve_entity_slug(title, slug)` is called inside `build_create_plan`
  (`:701-704`), and `plan_report` (`:824-885`) accumulates errors across
  **every** block before raising `invalid keep block(s): …`. `apply_report`
  calls `plan_report` first, so the whole report is rejected before the first
  write.

Verified, not assumed. Closing `-002` as `addressed` with the commit named.

## D2 — `-004` is not "degrades silently". The input is unreachable fleet-wide.

The filing says missing `specs/` scope files degrade the brief silently, and in
`meta` they are indeed absent. Grounding found something worse.

`science entity migrate-specs` canonicalizes loose spec docs to
`entities/specs/NNNN-slug.md`. In `natural-systems` that migration has run, and
the scope boundary exists — as `entities/specs/0037-scope-boundaries.md`.
Phase 1 reads `specs/scope-boundaries.md`, the **pre-migration** path, finds
nothing, and takes the "skipping any that are absent" branch in silence.

So the scope boundary is *present and structurally unreachable*, and
`out-of-scope` — one of the four `novelty_bucket` values, defined at
`commands/explore-ideas.md:160` as "falls outside `specs/scope-boundaries.md`"
— is judged against a file that no longer exists there. This is the Batch P
`-013` pattern exactly: a reader pointed at a path the shipped writer no longer
produces, so a whole classification was unreachable.

**Ruling.** Phase 1 resolves the scope boundary through the canonical
`entities/specs/` layout, falling back to the legacy `specs/` path, and records
which one it used. `seed_coverage` gains a structured `scope_source`
(`declared` | `inferred` | `absent`) so the single most anchoring-relevant
input to a blind pass stops living in orchestrator prose.

**Scope.** Five other commands read the same stale path — `search-literature`,
`next-steps`, `review-pipeline`, `catalog-datasets` — and
`create-project.md:353` still *scaffolds* `specs/scope-boundaries.md`, so new
projects are created into the layout the migrator moves away from. That is the
root, and it is out of scope for a single-surface batch. Batch R fixes
`explore-ideas` and files the fleet-wide repair as its own entry.

## D3 — `-001`: widen the judging surface, keep relation targets narrow.

`science project index` is hardcoded to `("hypothesis", "question")`
(`project_cli.py:321`). Novelty is therefore judged blind to every other kind,
the task backlog, and `core/decisions.md`. The run produced three overstated
`novel` calls, each caught only by manual inspection.

The obvious fix — widen the index — is wrong. `related_existing` resolution and
apply validation are *deliberately* ruled to questions and hypotheses
(`commands/explore-ideas.md:171-179`), and `_resolve_related` hard-fails on
anything else. Widening the index would silently widen what apply accepts as a
relation target.

**Ruling.** Two surfaces, on purpose:

- **Judging surface (wide).** Phase 3 additionally loads
  `science entity list --format json` across all kinds plus `tasks/active.md`
  titles. Used for novelty comparison only.
- **Relation surface (narrow).** `related_existing` stays questions and
  hypotheses. Unchanged.

The command doc must state that a candidate can be judged `already-covered`
against a task or a non-epistemic entity while carrying an empty
`related_existing` — the two surfaces are not the same set, and that is the
point.

## D4 — `-006`: mark the unverifiable; no network.

The resolver checks anchors against `entities/papers/` and
`papers/references.bib` only. In the reported run that resolved 2 of 49
anchors. The other 47 are model-generated DOIs, titles, authors and years that
nothing checked — and they read, in the block, exactly like validated
references.

A live DOI check was rejected: it puts a network call in a deterministic CLI,
makes a generation pass non-reproducible, and needs failure semantics when the
network is down.

**Ruling.** Batch P's `unknown is not absent` applies. An anchor the resolver
could not confirm is a fact about the instrument and must be visible in the
artifact, not implied by a null `ref`. The resolver reports a `verification`
verdict per anchor; the block carries it; `gaps` flags applied blocks whose
identifier-bearing anchors are unmarked.

Note the distinction the filing blurs: unresolved anchors *were* checked —
against the project corpus. What is unverified is their **identity**. The
vocabulary says so.

## D5 — `-003`: a weaker relation beside convergence.

Phase 3 merges only when candidates "independently describe the same idea".
Three candidates describing one mechanism on three axes did not merge, and the
report's own summary named the cluster without acting on it.

**Ruling.** Add `cluster_group` alongside `convergence_group`. Convergence
means one idea reached independently by several lenses and still emits one
block. A cluster means several related ideas on one mechanism, and Phase 4 must
state, per cluster, whether it emits one block or N — an explicit decision
rather than a silent default.

## D6 — `-005`: `--n` is a ceiling.

Every lens returned exactly 5 because 5 was requested; the two candidates
dropped as true-but-inert both came from the lens that plainly had fewer strong
ideas. A per-lens target manufactures filler.

**Ruling.** `--n` is a ceiling. A lens returns fewer when it has fewer, and
states why. Lens productivity becomes a visible signal instead of being
flattened to the requested constant.

## D7 — `-007`: `decision: drop` records no reason.

Eight candidates were dropped for materially different reasons — inert, badly
individuated, absorbed into another block — and all of it lived only in the
conversation. A later reader cannot tell a considered rejection from an
oversight.

**Ruling.** Optional `decision_note` on any block, surfaced in the apply
summary. Optional because the reason for `keep` is the block itself; it is
`drop`/`defer`/`fold` whose rationale is otherwise lost.

## Certification

Baseline and post-fix measurements are recorded in
`docs/plans/2026-07-26-feedback-batch-r-results.md`. A prediction in this
document is a claim, and is certified there or corrected.
