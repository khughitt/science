# explore-ideas third-run frictions — design

**Date:** 2026-07-09
**Target:** third `explore-ideas` run (`cancer/mechanisms/evolution`); reopens `fb-2026-07-04-008`
**Surface:** `command:explore-ideas`, `science explore-ideas`, `science project resolve-refs`, `science project topic-coverage`
**Companion:** `2026-07-09-typed-claim-to-claim-relations-design.md`

The third run of `explore-ideas` (30 candidates across six lenses, 23 promoted to
entities) succeeded on its core promise: structural blindness produced five
candidate areas with zero prior coverage anywhere in `entities/`, and two lenses
independently converged on the same idea, which is the signal the `lens_views` /
`independent: true` machinery exists to capture.

The frictions below are not about whether the approach works. They are about five
places where the command or CLI **loses information silently** or **writes
something wrong without stopping**. Each is grouped by fix surface, not by the
order it was observed.

Two items observed in the same run are deliberately excluded; see
"Handled elsewhere" at the end.

## Prior art, and one prematurely-closed item

`2026-07-07-explore-ideas-first-run-frictions-audit.md` classified **id-slug
truncation** (group C below) as *already addressed*, on the grounds that entity
creation now warns when a title-derived slug is truncated.

That assessment was made against the entity CLI, where `--slug` exists and the
warning is actionable. It does not hold for `explore-ideas apply`, which is where
the ids in question are actually minted:

- `create_entity()` accepts `slug=` and honours it, but
  `explore_ideas.py:792` never passes it, and the candidate-block schema has no
  `slug` field. There is no way for an author to control the id.
- The warning text (`entities.py:882`) ends `pass --slug to choose a different
  one`. `explore-ideas apply` has no `--slug` option, so the suggested remedy is
  unreachable from the only surface that emits the warning at scale.

In the third run this produced 23 truncated ids and 23 warnings, none of which
prevented anything. Ids are permanent; the only recovery was to delete all 23
entities, rewrite every title to be short enough to survive truncation, re-apply,
and then restore the intended titles in frontmatter. A warning is not a fix when
the thing being warned about is immutable and about to be written.

This is a process point as much as a technical one: an item closed as "already
addressed" should be re-checked against every surface that reaches the code path,
not only the one the fix was authored on.

## Group A — Phase-1 brief integrity

Two defects, one contract. The brief handed to the lens agents is the agents'
entire view of the project, and nothing currently guarantees it is either
*blind* or *representative*.

### A1. Topic bodies leak claim content into the "blind" brief

Phase 1 forbids reading `entities/hypotheses/`, `entities/questions/`, and
`entities/papers/`, with an explicit rationale: the project's existing epistemic
framing must not leak into the brief. It then instructs the orchestrator to read
the *bodies of substantive topics*.

In the third run, the project's sole substantive topic body contained:

- every hypothesis referenced by canonical id (`h001`–`h014`);
- a "Combined Implications for Project Hypotheses" table scoring each one
  (*"Strongly strengthens"*, *"Weakens"*);
- the full paper set;
- a section titled **"Open Questions Surfaced."**

Passing that body verbatim would have handed the lens agents the project's entire
epistemic surface — including its open questions — through the one directory the
blindness rule does not cover. The pass would have looked blind and been fully
anchored. Nothing in the command says otherwise; the leak was caught by
orchestrator suspicion, which is not a control.

The excluded directories are a proxy for the real invariant. The invariant is
**the brief carries subject terrain, never claims.**

### A2. `stub_dominated` is structurally blind to the thinnest seed

`topic-coverage` returned `n_topics: 1, n_substantive: 1, stub_ratio: 0.0,
stub_dominated: false` — a clean bill of health for the narrowest possible seed.

`stub_ratio` measures *stubbiness*, not *breadth*, and the two come apart exactly
at low `n`: a one-topic project trivially has a 0.0 stub ratio. The command keys
its "lean harder on blindness-safe breadth sources" instruction off
`stub_dominated`, so that instruction stayed silent in precisely the case that
most needed it, and the report header advertised a representative seed that was
one topic wide.

### Decision — A

1. **State the invariant, then enforce it in guidance.** Phase 1 gains an
   explicit brief-construction rule: extract subject terrain from topic bodies —
   entities, mechanisms, methods, populations, settings — and strip claim content:
   no entity ids, no hypothesis-impact tables, no verdict language, no "Open
   Questions" sections, no paper lists.

2. **Make it deterministic where possible.** `topic-coverage` gains a
   `claim_leakage` signal per topic: does the body contain canonical entity-id
   references (`h\d+`, `q\d+`, `hypothesis:`, `question:`, `paper:`) or a heading
   matching `open question`? Topics flagged this way are reported to the
   orchestrator, which must strip rather than skip them — a leaky topic is often
   the *most* substantive one, and dropping it would trade an anchoring bug for a
   coverage bug.

3. **Add a breadth signal alongside the stub signal.** `topic-coverage` emits
   `thin_seed: true` when `n_substantive < 3` or `n_topics < 5`, independent of
   `stub_ratio`. The command's "lean harder on breadth sources" instruction keys
   off `stub_dominated OR thin_seed`, and the report header caveat fires for
   either.

`stub_dominated` keeps its current meaning. Nothing is renamed; a second,
orthogonal signal is added, because the two failure modes are genuinely different
and a project can hit either alone.

## Group B — origin provenance fidelity (`predates:`)

`predates:` is load-bearing. An anchor whose `note` begins with `predates:` mints
a second origin (`type: literature`, `independent: true`), which is a durable
provenance claim that the literature reached the idea first.

In the third run, five of twelve `predates:` tags were unfaithful **by the
agent's own note text** — the note conceded the paper did not state the claim:

- *"motivates the mechanistic question"*
- *"applied to gene-expression networks rather than clonal frequency trajectories"*
- *"does not address whether non-canonical orderings alter subsequent diversification"*

Each would have written a false literature origin. The `idea-lens-researcher`
prompt says only that the anchor should be prefixed if the literature "already
states the idea," which is not a test an agent can apply consistently, and Phase 3
tells the orchestrator to copy resolver results into `ref` — never to check that
the tag is honest.

### Decision — B

1. **Give the agent a decision procedure, not an adjective.** The
   `idea-lens-researcher` prompt states the test as a counterfactual: *would a
   reader of this paper alone, having never seen this candidate, already hold the
   candidate's claim?* If no, it is a supporting anchor, not `predates:`. Add the
   negative heuristic: a note containing *motivates*, *suggests*, *without*,
   *rather than*, or *does not address* is disqualifying — those words describe a
   gap between the paper and the claim.

2. **Add an explicit orchestrator audit step to Phase 3.** Before finalizing
   `origin_plan`, re-read each `predates:` anchor's own note and demote any whose
   note does not assert the claim. Demotion routes the paper to `source_refs`,
   which is where an anchor that merely supports belongs.

3. **Make apply fail loudly on the cheap case.** `apply` rejects a `predates:`
   anchor whose `note`, after the prefix, is empty — a `predates:` with no
   justification is unreviewable.

The counterfactual is deliberately stated as a question about the *reader*, not
the paper. "Does the paper support this?" is answered yes far too easily.

## Group C — apply write-path control (id slugs)

Root-caused above. Ids minted by `apply` are permanent and uncontrollable, and the
warning points at a flag the command does not have.

The project's own convention — visible across all 121 pre-existing entities — is a
**short id slug paired with a long descriptive title**
(`question:0060-1f-neutral-vaf-test-calibration`, titled *"Can the 1/f neutral VAF
test be calibrated for reliable cross-cancer application, controlling for
cancer-type-specific mutation rates, sequencing depth, and subclonal ascertainment
biases?"*). `apply` structurally cannot produce this shape, because it derives the
slug from the title and nothing else.

### Decision — C

1. **Add an optional `slug:` field to the candidate-block schema**, thread it
   through `CreatePlan` into the existing `create_entity(slug=...)` parameter. Three
   lines of plumbing; the capability already exists one layer down.

2. **Have Phase 4 emit `slug:` for every candidate**, derived from the title but
   authored deliberately, so the human reviewing the report sees the id before it
   is permanent rather than a warning after.

3. **Fix the warning text** to name a remedy reachable from the current surface —
   `--slug` for the entity CLI, the block's `slug:` field for `explore-ideas apply`.

4. **Surface truncation in `apply --check`**, which is the pre-write validator and
   therefore the correct place to see a bad id while it is still cheap. `--check
   --format json` `to_create` rows should carry the planned `entity_id` and a
   `slug_truncated` boolean. (Those rows currently also omit `proposed_kind`,
   printing it as `?`; fix in passing.)

## Group D — reference resolution safety (`resolve-refs`)

`resolve-refs --query h012` returned
`question:0089-mouse-human-applicability-cliff-cycle-hypotheses` with
`match_kind: title-slug`. Not *unresolved* — confidently wrong.

Root cause, `resolve_refs.py:62–68`: Tiers 2 and 3 are **substring** matches
(`qslug in e.id_slug`, `qslug in e.title_slug`), and `_from_hits` resolves
silently whenever exactly one entity matches. Question 0089's title reads *"What
is the human-applicability path for **h012-class** continuous-recording cycle
hypotheses"* — it *mentions* h012. One substring hit, one confident resolution,
wrong entity.

Two properties make this dangerous rather than merely annoying:

- **Cross-referencing projects are the vulnerable ones.** Any entity that names
  another entity's short id in its title becomes a resolution decoy. The better
  the project's internal linking, the more decoys.
- **The failure is anti-correlated with detection.** With *two* decoys the result
  is `ambiguous` and errors out. Exactly one decoy resolves silently. And `apply`
  hard-validates `related_existing`, so it would have accepted the wrong id
  without complaint.

The other short forms (`h003`, `q0105`, …) came back `unresolved`, because no
entity happened to mention them in a title. So the resolver is not just unsafe on
short ids — it does not support them at all, despite `h012`-style short ids being
the project's own prose convention and the form an orchestrator naturally reaches
for.

### Decision — D

1. **Add a short-id tier above the substring tiers.** Recognize `h\d+` / `q\d+` /
   `t\d+` and friends as abbreviations of canonical ids, resolving `h012` →
   `hypothesis:0012-*` by zero-padded numeric match within kind. This is exact, not
   fuzzy. It fixes the wrong answer *and* the unresolved ones, and it is the tier
   the resolver was missing.

   Scope the tier to the kinds `resolve_refs` actually indexes. `_INDEX_KINDS`
   (`resolve_refs.py:10`) is exactly `("hypothesis", "question")`, so the map is
   `h` and `q` only. Widening it to tasks or papers means widening the index, which
   is a separate change.

2. **Never resolve a short-id-shaped query via substring.** If a query matches
   `^[a-z]\d+$` and the short-id tier does not resolve it, return `unresolved`.
   Falling through to substring matching on such a query is what produced the wrong
   answer; there is no case where it produces a right one. This covers unmapped
   prefixes as well: `t077` should be `unresolved`, not silently matched against
   whichever entity mentions it.

The substring tiers stay as they are for long, descriptive queries, where they
work well and their failure mode is `ambiguous` rather than wrong.

`match_kind` **already** renders in text output (`cli.py:4400`) — it is how the
wrong resolution was spotted in the first place. No change needed there.

## Group E — `already-covered` candidates are silently discarded

Classification assigns `already-covered` to candidates an existing entity already
asks. Phase 4 collapses them in the report; `apply` skips them. Their content is
then gone.

But `already-covered` is a judgment about the *question*, not about the
*material*. In the third run, five already-covered candidates carried genuinely
new content into questions that had existed for two months: a power-matched null
as the right calibration target, the PATH heritability formalism, a
foreclosed-trajectory exemplar, and two new mechanistic axes. Every one improved
its parent entity. None would have survived the pass, because nothing in the
command mentions harvesting them and `apply` cannot write into an existing entity.

`sharpens-existing` has a weaker version of the same problem: it becomes a new
child entity whose only tie to its parent is an untyped `related` link, so the
relationship "this sharpens that" is not recoverable from the graph.

### Decision — E

1. **Add `decision: merge`.** A merge block names a `related_existing` target and
   routes its resolved supporting anchors into that entity's `source_refs`, leaving
   the body prose to the human. Apply reports merges separately from creates and
   writes `decision: merged` + `merged_into` back to the block.

2. **Keep prose authorship out of apply.** Consistent with the gap-closure design's
   rejection of "infer and patch missing content": apply moves *refs*, never
   *sentences*. The harvest prose is scientific authorship and stays with the
   curator. `merge` exists so the refs and the audit trail survive; the
   orchestrator writes the paragraph.

3. **Give Phase 4 a harvest step.** After apply, the command instructs the
   orchestrator to fold each merged candidate's rationale into its parent's
   `## Thoughts`, and to record the reciprocal pointer.

### Relationship to the typed-relations report

An earlier draft of this design said `merge` was blocked on typed relations. That
was wrong twice over, and the split below is the correction.

**It is not blocked.** `2026-07-09-typed-claim-to-claim-relations-design.md` is a
substrate-gap *report*, not a design carrying a decision — it states "No code
change proposed here" and closes on three unanswered maintainer questions, chiefly
whether an entity↔entity `qualifies` is a first-class edge or a `proposition`
whose `target` is another entity. There is no edge field, relation kind, validator,
or materialization behavior to build against, so nothing can be sequenced behind
it.

**And most of `merge` never needed it.** Routing a resolved anchor into an
entity's `source_refs` is a *paper → entity* reference, which the substrate
already types. Only the *entity → entity* half needs the typed edge. So:

- **Merge's anchor routing ships now** (plan slice 5a). It is the half that was
  silently losing information, and it introduces no untyped `related` entry — a
  test enforces that.
- **Typed provenance edges defer** (plan slice 5b), with an explicit entry
  condition: the maintainer answers open question 1 of the typed-relations report,
  and a real design + plan pair exists specifying field, values, validator, and
  materialization.

Until then, `sharpens-existing` keeps writing untyped `related`, and folding a
merged candidate's *prose* into its parent stays a manual curator step. That
workflow ran across five entities in the third run and worked. It is slow, not
broken — and slice 5a is careful not to entrench the untyped edge meanwhile.

## Handled elsewhere

Two items from the same run are **not** carried here:

**Phase 3 step 3 ordering bug.** The command instructs `resolve-anchors --from
<report-path-or-id>` in Phase 3, but Phase 4 is what writes the report. The
working order is: draft the report with `ref: null`, resolve, patch refs back in.
This is a prose bug in `commands/explore-ideas.md` with no design surface — a
one-paragraph edit, fixed directly rather than designed.

**`gaps` unactionable `suggested_action`.** All 23 `unresolved_anchors` rows said
`next: Run science explore-ideas resolve-anchors`, which cannot help: the DOIs are
absent from `papers/references.bib`, so re-running resolves nothing. This is not a
papercut — it is a decision baked into
`2026-07-07-explore-ideas-gap-closure-design.md` (Gap Codes, `unresolved_anchors`),
which specifies exactly that suggestion. It should be corrected as a one-line
amendment to that document rather than restated here: the suggested action for an
unresolved anchor is to *add the paper to `papers/references.bib` or
`entities/papers/`, then re-run `resolve-anchors`*.

## Testing

- **A**: `topic-coverage` emits `thin_seed` at `n_topics: 1`; emits `claim_leakage`
  for a topic body containing `h001` and an "Open Questions" heading; command-docs
  test asserts the strip-claims wording and the `stub_dominated OR thin_seed`
  branch.
- **B**: `apply` rejects `note: "predates:"` with empty justification; agent-prompt
  test asserts the counterfactual wording and the disqualifying-verb list.
- **C**: candidate block with `slug:` yields that exact id; block without one
  warns; `apply --check --format json` `to_create` rows carry `entity_id`,
  `proposed_kind`, and `slug_truncated`.
- **D**: `h012` resolves to `hypothesis:0012-*` by short-id tier even when another
  entity's title contains the literal string `h012-class`; a short-id-shaped query
  with no kind match returns `unresolved`, never `title-slug`; long descriptive
  queries still resolve by substring.
- **E**: `decision: merge` routes supporting anchors to the target's `source_refs`,
  writes `merged_into`, creates nothing, and is idempotent on re-run.

Verification: focused `explore-ideas`, `resolve_refs`, and `topic-coverage` tests;
command and Codex-skill docs tests; `ruff check`; `pyright` on touched modules.
