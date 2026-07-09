# explore-ideas third-run frictions — plan

**Date:** 2026-07-09
**Design:** `2026-07-09-explore-ideas-third-run-frictions-design.md`
**Companion design:** `2026-07-09-typed-claim-to-claim-relations-design.md`

Slices 1–4 and 5a do not depend on each other and can land in any order. Slice 5b
is **deferred**, not scheduled: it has no entry condition yet (see below).

Each slice is independently shippable and independently revertible.

---

## Slice 1 — reference resolution safety (design group D)

Highest severity: this is the only item that writes a **wrong** value rather than
losing a right one, and `apply` hard-validates against it.

**Files**

- `science/src/science_tool/resolve_refs.py`
- `science/tests/test_resolve_refs.py`

**Changes**

1. Add `_SHORT_ID_RE = re.compile(r"^([a-z])(\d+)$")` and a kind map derived from
   `_INDEX_KINDS` — **`h` → `hypothesis`, `q` → `question`, and nothing else.**

   `resolve_refs.py:10` indexes exactly `("hypothesis", "question")`, so those are
   the only kinds a short id can resolve to. Do not promise `t` → `task`:
   expanding `_INDEX_KINDS` is a separate change with its own index-shape and
   cross-kind-collision questions (`science project index` exposes the same two
   kinds, and both would have to move together).

2. In `RefIndex.resolve`, insert **Tier 1.5** after `id-exact`: if the query
   matches `_SHORT_ID_RE` *and* its prefix is in the kind map, resolve by
   zero-padded numeric match within that kind. Return `match_kind: "short-id"`.

3. If the query matches `_SHORT_ID_RE`, return `unresolved` immediately when Tier
   1.5 finds nothing — do **not** fall through to the substring tiers. This
   deliberately covers unmapped prefixes too: `t077` returns `unresolved` rather
   than substring-matching some entity whose title happens to mention it. That is
   the correct answer for an un-indexed kind, and it is the safe one.

**Tests**

- `h012` → `hypothesis:0012-*` while a decoy entity's title contains
  `h012-class` (regression for the observed failure).
- `q0060` and `q60` both → `question:0060-*` (zero-padding is normalized).
- `h999` (mapped prefix, no match) → `unresolved`, never `title-slug`.
- `t077` (unmapped prefix) → `unresolved` even when an entity title contains the
  literal `t077`.
- Long descriptive query still resolves via `id-slug` / `title-slug`.
- Two decoys still yield `ambiguous`.

**Not in this slice:** `match_kind` already renders in text output
(`cli.py:4400`, `f"{r.query} -> {r.resolved} ({r.match_kind})"`) — it is how the
original wrong resolution was spotted. No change needed.

---

## Slice 2 — apply write-path control (design group C)

**Files**

- `science/src/science_tool/explore_ideas.py` (`CreatePlan`, `plan_report`, `apply_report`)
- `science/src/science_tool/entities.py` (warning text only)
- `commands/explore-ideas.md` (candidate-block schema + Phase 4)
- `science/tests/test_explore_ideas.py`, `science/tests/test_entities.py`

**Changes**

1. Parse an optional `slug:` from the candidate block; carry it on `CreatePlan`.
2. Pass `slug=create_plan.slug` at `explore_ideas.py:792`. The parameter already
   exists and is honoured — no change to `create_entity` semantics.
3. Add `entity_id` and `slug_truncated` to `--check --format json` `to_create`
   rows; populate `proposed_kind`, which currently renders as `?`.
4. Reword the truncation warning in `entities.py:882` so the remedy names the
   surface: `--slug` (entity CLI) or the block's `slug:` field (explore-ideas
   apply).
5. Document `slug:` in the command's block schema; instruct Phase 4 to emit it
   for every candidate.

**Tests**

- Block with `slug: foo` → `question:NNNN-foo`.
- Block without `slug:` and a long title → id truncated *and* `slug_truncated:
  true` in `--check` JSON.
- Warning text no longer names `--slug` when raised from the apply path.
- Amend `test_entities.py::test_create_entity_warns_when_title_slug_is_truncated`,
  which currently asserts `"--slug" in warning`.

---

## Slice 3 — origin provenance fidelity (design group B)

**Files**

- `agents/idea-lens-researcher.md`
- `commands/explore-ideas.md` (Phase 3 audit step)
- `science/src/science_tool/explore_ideas.py` (anchor validation)
- `science/tests/test_explore_ideas.py`

**Changes**

1. Rewrite the `predates:` instruction in the agent prompt as the reader
   counterfactual, plus the disqualifying-verb list (*motivates*, *suggests*,
   *without*, *rather than*, *does not address*).
2. Add a Phase 3 step: re-read each `predates:` anchor's note; demote any whose
   note does not assert the claim. Demotion routes the anchor to `source_refs`.
3. Reject at parse time a `predates:` anchor whose note is empty after the prefix.

**Tests**

- `note: "predates:"` (empty justification) → `ApplyValidationError`.
- `note: "predates: motivates the question"` → parses, but the docs test asserts
  the agent prompt disqualifies it. (Deliberately not enforced in code: the verb
  list is a heuristic for an agent, and hard-failing on it in the CLI would reject
  legitimate notes that happen to contain the word.)
- Agent-prompt docs test asserts the counterfactual wording is present.

---

## Slice 4 — Phase-1 brief integrity (design group A)

**Files**

- `science/src/science_tool/topic_coverage.py`
- `commands/explore-ideas.md` (Phase 1 + report header)
- Codex skill mirror
- `science/tests/test_topic_coverage.py`

**Changes**

1. `topic-coverage` emits `thin_seed: bool` — true when `n_substantive < 3` or
   `n_topics < 5`, independent of `stub_ratio`.
2. `topic-coverage` emits `claim_leakage: list[str]` — topic ids whose body
   contains canonical entity-id references (`h\d+`, `q\d+`, `hypothesis:`,
   `question:`, `paper:`) or an `open question` heading.
3. Phase 1 gains the brief-construction rule: extract subject terrain, strip claim
   content. Leaky topics are **stripped, not skipped**.
4. Phase 1's "lean harder on breadth sources" instruction keys off
   `stub_dominated OR thin_seed`.
5. Report header `seed_coverage` block carries `thin_seed` and `claim_leakage`;
   the caveat line fires on either flag.

**Tests**

- `n_topics: 1, stub_ratio: 0.0` → `thin_seed: true`, `stub_dominated: false`
  (regression for the observed case).
- Topic body containing `h001` and an `## Open Questions Surfaced` heading →
  reported in `claim_leakage`.
- Command-docs test asserts the strip-claims wording and the `OR thin_seed` branch.

---

## Slice 5a — `already-covered` harvest, anchor routing (design group E)

**Not blocked.** Routing a paper into an entity's `source_refs` is a paper→entity
reference, which the substrate already types. No entity↔entity edge is created, so
nothing here waits on the typed-relations question.

**Files**

- `science/src/science_tool/explore_ideas.py` (`decision` enum, `MergePlan`, write-back)
- `commands/explore-ideas.md` (Phase 3 bucket → decision mapping; Phase 4 harvest step)
- `science/tests/test_explore_ideas.py`

**Changes**

1. Accept `decision: merge`; require exactly one `related_existing` target.
2. `apply` routes the block's resolved supporting (non-`predates:`) anchors into
   the target entity's `source_refs`, idempotently. It creates nothing, writes no
   prose, and adds no `related` entry.
3. Write back `decision: merged` + `merged_into: <entity-id>` + `merged_at`.
4. Report merges as a distinct category in the created/skipped/manual summary.
5. Phase 4 instructs the orchestrator to fold each merged candidate's rationale
   into the parent's `## Thoughts`. The *prose* pointer is the curator's job, per
   the gap-closure design's rule that apply moves refs, never sentences.
6. `gaps` learns `unharvested_merge`: a `merged` block whose target's body has no
   prose citing the merged anchor.

**Tests**

- `decision: merge` adds anchors to the target's `source_refs` and creates no
  entity.
- Re-running `apply` on a `merged` block is a no-op.
- `merge` with zero or multiple `related_existing` targets → validation error.
- `merge` naming an unresolved target → validation error (same path as
  `related_existing` today).
- `merge` writes no `related` entry on the target (guards against re-introducing
  the untyped edge this design set out to avoid).

---

## Slice 5b — typed provenance edges — DEFERRED, no entry condition yet

**Status:** deferred. Do not schedule.

`2026-07-09-typed-claim-to-claim-relations-design.md` is a substrate-gap *report*,
not a design with a decision: its "Not doing yet" section states *"No code change
proposed here,"* and it closes on three unanswered maintainer questions — most
critically whether an entity↔entity `qualifies` is a first-class edge or a
`proposition` whose `target` is another entity. Until that is answered there is no
edge field, relation kind, validation rule, or materialization behavior to
implement against, and therefore nothing for this slice to be blocked *on*.

**Entry condition:** maintainer answers open question 1 of the typed-relations
report, and a typed-relations design + plan pair exists specifying the field name,
the permitted relation values, the validator, and the graph materialization.

**Scope when unblocked**

- A typed edge from a `sharpens-existing` child to its parent, replacing the
  untyped `related` link `apply` writes today.
- A typed provenance edge from a `merge`d candidate to its target, so the harvest
  is recoverable from the graph rather than only from the report.

**Until then**, `sharpens-existing` continues to write untyped `related`, and the
harvest of merged candidates' prose stays a manual curator step. That manual
workflow was exercised across five entities in the third run and worked; it is
slow, not broken. Slice 5a makes its *reference* half durable and machine-checked,
which is the part that was silently lost.

---

## Out of band

Neither of these needs a slice; both are corrections to shipped text.

1. **`commands/explore-ideas.md` Phase 3 step 3** instructs `resolve-anchors
   --from <report>` before Phase 4 writes the report. Reword to the working order:
   draft the report with `ref: null` → run `resolve-anchors` → patch `ref` values
   back in. Alternatively, teach `resolve-anchors` to accept a candidates JSON
   blob; the reword is sufficient and cheaper.

2. **`2026-07-07-explore-ideas-gap-closure-design.md`**, Gap Codes,
   `unresolved_anchors`: the specified `suggested_action` is `run
   resolve-anchors`, which cannot resolve an anchor whose DOI is absent from the
   bib. Amend to: *add the paper to `papers/references.bib` or `entities/papers/`,
   then re-run `resolve-anchors`*. Update the string in
   `science_tool/explore_ideas.py` and the doc's JSON/text contract examples
   together.

---

## Verification

Per slice: focused module tests, command and Codex-skill docs tests, `ruff check`,
`pyright` on touched modules.

End to end, after slices 1–4: re-run generate mode against
`cancer/mechanisms/evolution` and confirm the report header reports `thin_seed:
true`, that `slug:` appears on every candidate block, and that
`resolve-refs --query h012` resolves to `hypothesis:0012-*`.
