# Pre-registration semantics recast — draft proposal

> **Status:** Draft for circulation (t012), revision 2 (2026-05-04 post initial review). Do **not** merge until downstream projects (natural-systems, protein-landscape, seq-feats, 3d-attention-bias, cats) have surfaced objections. The recast changes how their existing pre-regs are interpreted; no entity-file content changes, but two small code prerequisites are required (see § "Code prerequisites").
>
> *t012's task description names "myeloma, natural-systems" as the primary downstream projects to consult. `myeloma` is not a locally-present Science project as of 2026-05-04 — confirm with the project owner before treating its absence as final.*

**Source design:** `docs/plans/2026-05-03-epistemic-dependency-graph-design.md` § Part 4.

**Tracked as:** `[t012]` Pre-registration semantics recast (epistemic vs operational targets).

---

## What changes

The pre-reg entity shape stays exactly as it is (`type: pre-registration`, `committed:`, `spec:`, `related:`, `status:`). What changes is **how the tool and skills interpret the relationship between a pre-reg and the entity it pre-commits to**.

A pre-reg's commitment can target two kinds of thing, and they should not be evaluated the same way:

| Target class | Example | Today's behavior | Recast behavior |
|---|---|---|---|
| **Operational** | "we will run pipeline P with params X before unblinding" | Binary gate. Deviations require an `amendments:` record. | Unchanged — still a gate. |
| **Epistemic** | "if effect size > 0.3, treat hypothesis H as supported" | Implicit binary verdict on H when the result lands. ("Pre-reg said >0.3, we got 0.18 → H rejected.") | Becomes a `bears_on` source on the epistemic target. The result, weighted by the pre-reg's commitment, *updates belief*; it does not return a verdict. |

The shift dissolves the "gate slammed shut on a viable pathway" failure mode without weakening pre-registration's anti-bias function. A null result against a pre-registered epistemic prediction is **evidence**, weighted by the pre-reg's commitment, but it is not a kill switch.

### Why this is safe to change without schema migration

Existing pre-regs already declare their target via `related:`. The classification of that target as operational or epistemic falls out of the entity registry's `EntityClass` mapping (added in `[t010]`):

- `related: [hypothesis:h07-...]` → epistemic target (since `hypothesis` is `EPISTEMIC`)
- `related: [question:q63-...]` → epistemic target (since `question` is `EPISTEMIC`)
- `related: [task:t342]` → operational target (since `task` is `OPERATIONAL`)
- `related: [workflow-run:...]` → operational target (since `workflow-run` is `OPERATIONAL`)

So a pre-reg's "class of target" is computable today from existing data. Skills can branch on it without any frontmatter changes.

---

## Skill changes

### `science:pre-register`

**Adds:** an early prompt to identify the target class, and target-class-aware framing for decision criteria.

Concrete edits to `commands/pre-register.md`:

1. **New section 0 (before "Identify the Analysis"):** "Target class — operational or epistemic?"

   Prompt the user to identify which the pre-reg primarily commits to:
   - **Operational target** — a procedure, pipeline run, dataset processing step, or experimental protocol. The commitment is "we will execute X before observing Y." Deviation requires an amendment.
   - **Epistemic target** — a hypothesis, question, proposition, or interpretation rule. The commitment is "we will *interpret* observed Y in this way to update belief about X." Deviation does not require an amendment, because the pre-reg is not gating a procedure; it is constraining how a future result feeds the epistemic graph.

   Mixed targets are common (e.g., "we will run analysis A and treat H as supported if effect > 0.3"). Treat the procedure portion and the interpretation portion separately:
   - **Operational portion:** stays as an amendment-gate check. `science:interpret-results` confirms the analysis ran as committed (or that any deviation has a corresponding `amendments:` record). No `bears_on` edge — operational targets are not `bears_on` sinks (`science-tool/.../graph/materialize.py` rejects authored `bears_on` edges to non-epistemic targets).
   - **Epistemic portion:** materializes as a `bears_on` edge from the pre-reg into the epistemic target via the new auto-derivation rule (see § "Auto-derivation rule for pre-reg → epistemic target" below). This is the load-bearing graph change of the recast.

2. **Revise § 3 "Define Decision Criteria":** drop the implicit binary framing. Today's wording:

   > What evidence would **refute** it? What would make you abandon this hypothesis?

   Reframe for epistemic targets:

   > What evidence would **shift belief away from** it? Don't frame as "would I abandon" — that's a kill-switch framing. Instead: how strongly would each result class move belief, and in which direction?

   For operational targets, "refute" / "abandon" remains accurate (the procedure either ran as committed or it didn't).

3. **Revise § 4 "Plan for Null Results":** add the epistemic-target qualifier.

   Today:

   > What does a null result mean? Hypothesis is wrong, or test is inadequate?

   Add:

   > **For epistemic targets:** A null result is evidence, weighted by the pre-reg's commitment. It is not a verdict on the hypothesis. Frame the null-result plan as "what update should this trigger?" rather than "would this kill the hypothesis?"

   The existing "Pilot experiments" sub-bullet ("a pilot's null result means 'insufficient signal to justify scaling up', not 'hypothesis is wrong'") already gets this right and can stay.

4. **(Conditional on Open Question #1)** **Update § "Naming and Frontmatter":** if the review concludes a `commitment_weight` field is worth adding, add it as an optional one-of `strong` / `moderate` / `weak`, default `strong` if absent (preserves backward-compatibility — existing pre-regs read as strongly committed). Current lean is **omit** — see Open Questions section. Skip this edit entirely if OQ1 resolves "omit"; in that case, all pre-registered evidence is treated as strongly committed at interpretation time.

### `science:interpret-results`

**Adds:** a step that reads any pre-reg in the `related` set, classifies its target, and frames the interpretation accordingly. Does **not** write `bears_on` edges directly — those are derived by `graph build` from typed-edge writes.

Concrete edits to `commands/interpret-results.md`:

1. **New § 4d "Pre-registration evaluation":** insert after § 4c "Suspiciously good results", before § 5 "Update Proposition Support / Dispute".

   - Locate any pre-reg with the current analysis or its hypothesis/question in its `related` set. Today, the only working approach is a path scan:

     ```bash
     # Read directly from the conventional paths (matches today's
     # interpret-results pattern under § "Suspiciously good results")
     ls doc/meta/pre-registration-*.md doc/pre-registrations/*.md 2>/dev/null
     ```

     *Why not `science-tool entity list --kind pre-registration`?* It does not work today because (a) `pre-registration` is missing from `_CORE_KIND_CLASSES` in `entity_registry.py` and (b) source loading skips unknown kinds (`graph/sources.py`). Both are fixed by the prerequisite registry change (see § "The pre-registration kind classification gap" below). Once that lands, prefer the CLI form. **Until then, the path scan is the only correct lookup and the skill should recommend only that.**

     *Possible future ergonomics fix:* add `entity list --related <ref>` filtering — out of scope for t012, flagged as `[t012c]` if it materially improves the workflow.

   - For each found pre-reg, read its `committed:` clause and its target class (derivable from each `related:` ref's registered `EntityClass`).

   - **Operational pre-regs:** Did the analysis run as committed? If not, flag the deviation and confirm an `amendments:` entry exists. This is the existing behavior and stays gating.

   - **Epistemic pre-regs:** Compare the observed result to the pre-registered prediction. Frame the comparison as a *weighted update*, not a verdict:

     > "Pre-reg `pre-registration:h07-beta-arbitration` predicted effect > 0.3 for support of H07. Observed: 0.18. This is a `disputes` evidence edge into H07, weighted strong (per pre-reg commitment level)."

     Do **not** frame as:

     > "Pre-reg predicted >0.3, observed 0.18 — H07 is rejected per the pre-registered criterion."

2. **Revise § 5 "Update Proposition Support / Dispute":** add a sub-bullet noting that pre-registered evidence edges should be linked back to the pre-reg via the existing `sci:preRegisteredIn` mechanism so downstream weighting (Phase 2 sampling, `[t011]`) can boost them. Concretely:

   - When emitting a `cito:supports` or `cito:disputes` proposition grounded in a pre-registered analysis, pass `--pre-registration pre-registration:<slug>` to `science-tool graph add proposition` (existing CLI flag, `cli.py:1568`). This writes a `sci:preRegisteredIn` triple in the materialized graph (`store.py:707`), readable later via `_load_proposition_pre_registrations` (`store.py:3434`) and surfaced through the causal exporters. No frontmatter change required — the link lives in the graph.

3. **Drop kill-switch framing from § 4 "Suspiciously good results":** today's wording references "Reference the pre-registration document … and compare observed vs. expected range explicitly." That stays. But add a sentence: "For epistemic-target pre-regs, an out-of-range result is `disputes` evidence, weighted by the pre-reg's commitment — it does not invalidate the hypothesis on its own."

### Skills not in t012 scope but adjacent

- `science:next-steps` and `science:status` — already updated by `[t010]` to surface freshness flags. No prereg-recast change needed; the recast plays out through `bears_on` derivation.
- `science:bias-audit` — references pre-registrations as a check ("Do current hypotheses match pre-registration?" — `science-model/.../templates/bias-audit.md:65`). Could optionally be reframed to "do current hypotheses match the *commitments* in their pre-registrations, classifying each as operational or epistemic?" but this is mild and can be deferred.
- `science:plan-analysis` — pre-reg-adjacent (recommends running pre-register after planning). No language change needed.

---

## Doc changes

### `docs/proposition-and-evidence-model.md`

This is the canonical reference. It needs a new subsection introducing pre-reg target classification.

**New subsection** (insert after current `## Epistemic Dependency: bears_on and Freshness`):

```markdown
## Pre-registration: Operational vs Epistemic Targets

Pre-registrations carry commitments about future analyses. Two distinct
commitment shapes coexist under the single `type: pre-registration`:

- **Operational pre-regs** commit to a procedure: "run pipeline P with
  params X before unblinding." These are **gating** — deviations require
  an `amendments:` record. Belief about the operational target is binary
  (the procedure either ran as committed or it didn't).
- **Epistemic pre-regs** commit to an interpretation rule: "if effect > 0.3,
  treat hypothesis H as supported." These are **non-gating** — the result
  feeds H's evidence base via a weighted `bears_on` edge derived at
  graph-build time. A null result against an epistemic pre-reg is
  evidence weighted by the pre-reg's commitment, not a kill switch on H.

The classification falls out of the registered `EntityClass` of each entity
in the pre-reg's `related:` field — no per-entity schema change is needed.
Mixed pre-regs (an analysis that commits to both a procedure and an
interpretation rule) split cleanly: the operational portion remains an
amendment-gate check at interpret-results time, and the epistemic portion
materializes as a `bears_on` edge into the epistemic target. Operational
targets are not `bears_on` sinks, so no operational `bears_on` is emitted.

This dissolves the "gate slammed shut on a viable pathway" failure mode:
under hard-gating semantics, a null result against a pre-registered
prediction terminates a hypothesis even when the underlying physical claim
is still viable. Under the recast, the null result reduces belief weighted
by the pre-reg's commitment level, and the hypothesis remains queryable
and reviewable in the graph (subject to freshness propagation).

See `commands/pre-register.md` for the authoring workflow and
`commands/interpret-results.md` for the evaluation workflow.
```

### `docs/claim-and-evidence-model.md`

This document is already marked `Superseded` (line 4) and points readers to `proposition-and-evidence-model.md`. **No edits needed** — the superseded doc keeps its current `bears_on` section as the historical record. Anyone landing on this page is already redirected.

*Open question: should the supersede notice be strengthened to "deprecated, do not edit"? Out of scope for t012 but worth flagging.*

---

## Code prerequisites (must land before the prose recast)

Two code changes are **required** for the recast to mean anything in the materialized graph. The original draft framed both as optional follow-ups; that was wrong (see § "What changed in this revision" at the bottom).

### Prerequisite 1: register `pre-registration` as a kind

`pre-registration` is missing from `science_tool/graph/entity_registry.py`'s `_CORE_KIND_CLASSES` mapping. Every other kind referenced in the recast (hypothesis, question, proposition, interpretation, finding, task, workflow-run, dataset, etc.) is registered with an explicit class.

Two consequences as long as it's missing:

- `science-tool entity list --kind pre-registration` returns nothing — source loading skips unknown kinds (`graph/sources.py`).
- The auto-derivation rule below has no kind to dispatch on.

**Fix:** add `"pre-registration": EntityClass.OPERATIONAL` to `_CORE_KIND_CLASSES` and the matching `register_core_kind` call in `with_core_types()`. One-line registry change plus a test asserting `kind_class("pre-registration") == OPERATIONAL`.

**Why OPERATIONAL, not REFERENCE:** a pre-reg is fundamentally a *procedural commitment* — it commits to executing or interpreting in advance, and its `committed:` date is load-bearing in the dependency graph. REFERENCE classification would be argued for "authored declaration that doesn't change after committed", but pre-regs do participate as `bears_on` *sources* (after Prerequisite 2), which is operational behavior. The pre-reg's class as a node is independent of the class of its target.

Tracked as `[t012b]`.

### Prerequisite 2: auto-derive `bears_on` from pre-reg `related:` to epistemic targets

A pre-reg's `related:` field materializes as `skos:related` (`graph/materialize.py`). Freshness derivation does not consume `skos:related`. So without an explicit auto-derivation rule, the recast has no graph effect on `bears_on` edges into the epistemic target — the prose changes would be teaching humans to think differently while the materialized graph behaves identically to today.

**Fix:** add a rule in `freshness.py`'s `derive_bears_on_from_typed_edges` (or a sibling deriver):

> For a `pre-registration` entity P with `related:` member E:
>   - if `kind_class(kind_of(E)) == EPISTEMIC`: emit `P bears_on E` at depth 1.
>   - if `kind_class(kind_of(E)) == OPERATIONAL` or `REFERENCE`: do not emit (operational and reference targets are not `bears_on` sinks; materialization rejects authored `bears_on` edges to non-epistemic targets per `graph/materialize.py`).

Tests: pre-reg with `related: [hypothesis:H]` → `P bears_on H` derived; pre-reg with `related: [task:T]` → no `bears_on` derived; mixed `related: [hypothesis:H, task:T]` → exactly one edge to H. Unit-test against the existing freshness derivation harness.

Tracked as `[t012b']` (companion to t012b — same PR is fine, since both are tiny and tightly coupled).

### Why these are prerequisites, not follow-ups

The original draft asserted that the existing closure chain `pre-reg → analysis → interpretation → hypothesis` already produces the right edge. This was wrong: that chain depends on each hop being a typed edge that triggers an auto-derivation rule, and `pre-reg related: analysis` is `skos:related` — untyped from the freshness derivation's perspective. The chain is broken at the first hop. So:

- Without Prerequisite 1: the skill cannot even ask the registry whether a target is epistemic, because pre-reg isn't a registered kind.
- Without Prerequisite 2: the prose recast is purely cosmetic — humans get new framing language, but `science:status`, `science:next-steps`, `bears_on`-derived freshness, and Phase-2 sampling weights see no new edges.

**Sequencing:**

1. Land Prerequisites 1 & 2 (small, mechanical, can ship as one PR — call it `[t012b]`).
2. Apply prose changes from § "Skill changes" and § "Doc changes". Skill prose can now safely reference `science-tool entity list --kind pre-registration` and rely on the auto-derived edges existing in the graph.
3. Circulate to downstream maintainers per § "Downstream impact".

---

## Downstream impact

26 existing pre-regs across 4 of 5 locally-present Science projects (counted 2026-05-04, excluding `.worktrees/` duplicates):

| Project | Pre-reg count | Notable instances |
|---|---|---|
| natural-systems | 14 | `pre-registration-h07-beta-arbitration.md` targets `hypothesis:h07-...` + 4 questions (epistemic); `pre-registration-t085-t086.md` targets task IDs (operational) |
| 3d-attention-bias | 4 | `pre-registration-phase1-ablation.md`; `pre-registration-t045-t046-mechanism-and-env-shift.md` |
| seq-feats | 5 | `pre-registration-t152-bpe-nda.md`; `pre-registration-cycle1-domains.md` |
| protein-landscape | 3 | `pre-registration-q63-heldout-taxa-benchmark.md` (question target — epistemic) |
| cats | 0 | none authored |
| myeloma | n/a | not locally present (see status note above) |

**No file in any project needs editing.** Each existing pre-reg's `related:` field already declares its targets; the recast simply changes how those targets are interpreted at evaluation time.

**What downstream maintainers should review before merge:**

1. **For each existing pre-reg with epistemic targets:** does the recast change the *intended* meaning of that pre-reg? E.g., for `pre-registration-h07-beta-arbitration.md`, the author probably did intend "this constrains how we evaluate H07" rather than "this gates whether H07 lives or dies" — but it's worth confirming with the author rather than assuming.

2. **Operational pre-regs are unaffected.** Anything pre-registering a procedural commitment (run-with-params, datapackage-before-unblinding) keeps its current gating semantics.

3. **No `committed:` re-dating.** Pre-regs already committed stay committed; the recast applies prospectively to interpretation, not retroactively to the commitment record.

**Specific maintainers to flag:** anyone with active pre-regs in natural-systems (highest count and most active project), 3d-attention-bias (uses pre-regs with both operational and epistemic targets in the same file), and seq-feats (cycle-based pre-regs that explicitly stage commitments across phases).

---

## Sequencing for landing

1. **Now:** circulate this draft to downstream maintainers. Solicit objections specifically on (a) whether the recast changes intent of any existing pre-reg, (b) whether `commitment_weight` is worth adding as an optional field or should be derived from prose, (c) whether any project has tooling that depends on the binary-verdict reading of pre-regs.
2. **Land code prerequisites (`[t012b]`):** add `pre-registration` → `EntityClass.OPERATIONAL` to the registry, plus the `pre-reg related: → bears_on epistemic-target` auto-derivation rule. One small PR. See § "Code prerequisites" for details and tests.
3. **Apply prose changes:** the skill edits from § "Skill changes" and the doc edit from § "Doc changes". Now safe because the registry knows about pre-reg and the graph carries the new edges.
4. **(If applicable)** Land any `commitment_weight` field per the resolution of Open Question #1.
5. **Phase 2:** when `[t011]` lands weighted sampling, the pre-reg `bears_on` edges are already in place to feed weighting.

Total prose-edit work in step 3 is small: ~80 lines added across `commands/pre-register.md`, `commands/interpret-results.md`, and `docs/proposition-and-evidence-model.md`, plus zero edits to `docs/claim-and-evidence-model.md` (already superseded).

---

## Open questions for review

1. **`commitment_weight` field — yes or no?** Adding it (even optional) is a soft schema change and a new authoring decision the user must make at pre-reg time. Alternative: omit it, treat all pre-regs as `strong`, and add weighting later if Phase-2 needs the gradient. **Lean: omit for now.**
2. **Pre-reg classification: OPERATIONAL or REFERENCE?** Lean: OPERATIONAL (a procedural commitment).
3. **Should `bias-audit` skill be reframed in this same recast?** Lean: defer — its current language is mild enough not to mislead.
4. **Should the supersede notice in `claim-and-evidence-model.md` be strengthened?** Lean: out of scope for t012; do separately if at all.

---

## What this draft is **not**

- It is not the final recast text. The skill files and `proposition-and-evidence-model.md` should be edited only after objections come back and the code prerequisites land.
- It is not retroactive. Existing pre-regs stay valid as authored; only their interpretation at evaluation time shifts.

The original draft additionally claimed "no code changes for t012 itself." That was withdrawn in revision 2 — see § "What changed in this revision" below.

---

## What changed in this revision

Revision 2 (2026-05-04, post initial review):

- **Auto-derivation rule is required, not optional.** The original draft asserted that the existing chain `pre-reg → analysis → interpretation → hypothesis` produces the right `bears_on` edge through closure. That was wrong: a pre-reg's `related:` materializes as `skos:related`, which freshness derivation does not consume. The recast has no graph effect without the explicit pre-reg → epistemic-target derivation rule. Promoted from "optional follow-up `[t012b]`" to "Prerequisite 2".
- **Registry classification is required for the prose recast to even branch correctly.** Without `pre-registration` in `_CORE_KIND_CLASSES`, `science-tool entity list --kind pre-registration` returns nothing (source loading skips unknown kinds) and the deriver has no kind to dispatch on. Promoted from "concurrent" to "Prerequisite 1".
- **CLI command corrected.** `science-tool entity list --type` → `--kind` (the `--kind` form is the one supported by `cli.py`). Recommended lookup is path-scan only until the registry change lands.
- **Mixed-target language corrected.** Operational targets are not `bears_on` sinks (materialization rejects them), so a "mixed pre-reg" does not generate "both kinds of bears_on" — only the epistemic portion produces a `bears_on` edge. The operational portion stays a procedural amendment-gate check.
- **Count corrected.** natural-systems pre-reg count was 13; correct is 14 (the original `find` command included `.worktrees/` duplicates which inflated other counts; the table number was off by one). Total of 26 was correct.
