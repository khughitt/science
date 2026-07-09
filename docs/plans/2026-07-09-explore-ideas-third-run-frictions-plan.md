# explore-ideas third-run frictions — plan

**Date:** 2026-07-09
**Design:** `2026-07-09-explore-ideas-third-run-frictions-design.md`
**Companion design:** `2026-07-09-typed-claim-to-claim-relations-design.md`

Five slices, ordered by independence. Slices 1–4 do not depend on each other and
can land in any order. Slice 5 depends on the typed-relations design landing
first.

Each slice is independently shippable and independently revertible.

---

## Slice 1 — reference resolution safety (design group D)

Highest severity: this is the only item that writes a **wrong** value rather than
losing a right one, and `apply` hard-validates against it.

**Files**

- `science/src/science_tool/resolve_refs.py`
- `science/tests/test_resolve_refs.py`

**Changes**

1. Add `_SHORT_ID_RE = re.compile(r"^([a-z])(\d+)$")` and a kind map
   (`h` → `hypothesis`, `q` → `question`, `t` → `task`, …) sourced from the
   existing entity-kind registry rather than a new literal.
2. In `RefIndex.resolve`, insert **Tier 1.5** after `id-exact`: if the query
   matches `_SHORT_ID_RE`, resolve by zero-padded numeric match within the mapped
   kind. Return `match_kind: "short-id"`.
3. If the query matches `_SHORT_ID_RE` and Tier 1.5 finds nothing, return
   `unresolved` immediately — do **not** fall through to the substring tiers.
4. Render `match_kind` in the text output.

**Tests**

- `h012` → `hypothesis:0012-*` while a decoy entity's title contains
  `h012-class` (regression for the observed failure).
- `h999` → `unresolved`, never `title-slug`.
- Long descriptive query still resolves via `id-slug` / `title-slug`.
- Two decoys still yield `ambiguous`.

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

- `science/src/science_tool/project/topic_coverage.py`
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

## Slice 5 — `already-covered` harvest (design group E)

**Blocked on:** the typed-relations slice. `merge` must write a typed edge, not an
untyped `related` entry, or it will be re-opened to type it later.

**Files**

- `science/src/science_tool/explore_ideas.py` (`decision` enum, `MergePlan`, write-back)
- `commands/explore-ideas.md` (Phase 3 bucket → decision mapping; Phase 4 harvest step)
- `science/tests/test_explore_ideas.py`

**Changes**

1. Accept `decision: merge`; require exactly one `related_existing` target.
2. `apply` routes the block's resolved supporting (non-`predates:`) anchors into
   the target entity's `source_refs`, idempotently. It creates nothing and writes
   no prose.
3. Write back `decision: merged` + `merged_into: <entity-id>` + `merged_at`.
4. Report merges as a distinct category in the created/skipped/manual summary.
5. Phase 4 instructs the orchestrator to fold each merged candidate's rationale
   into the parent's `## Thoughts`, and to record the reciprocal pointer.
6. `gaps` learns `unharvested_merge`: a `merged` block whose target's body has no
   prose citing the merged anchor.

**Tests**

- `decision: merge` adds anchors to the target's `source_refs` and creates no
  entity.
- Re-running `apply` on a `merged` block is a no-op.
- `merge` with zero or multiple `related_existing` targets → validation error.
- `merge` naming an unresolved target → validation error (same path as
  `related_existing` today).

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
