# Pre-registration semantics recast — draft proposal

> **Status:** Draft for circulation (t012). Do **not** merge until downstream projects (natural-systems, protein-landscape, seq-feats, 3d-attention-bias, cats) have surfaced objections. The recast changes how their existing pre-regs are interpreted, even though no schema or file content changes.
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

   Mixed targets are common (e.g., "we will run analysis A and treat H as supported if effect > 0.3"). Treat the procedure portion as operational and the interpretation portion as epistemic. The tool can derive both: the operational `bears_on` from the procedure description, the epistemic `bears_on` from the interpretation rule.

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

   - Locate any pre-reg with the current analysis or its hypothesis/question in its `related` set. Two existing options:

     ```bash
     # List all pre-regs, then filter by inspecting `related:` (matches today's
     # interpret-results pattern, which already references the doc/meta path
     # under § "Suspiciously good results")
     science-tool entity list --type pre-registration

     # Or read directly from the conventional path
     ls doc/meta/pre-registration-*.md doc/pre-registrations/*.md 2>/dev/null
     ```

     *Open question: should we add `entity list --related <ref>` filtering as a small CLI ergonomics fix? Out of scope for t012, worth flagging as `[t012c]` if it materially improves the workflow.*

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
interpretation rule) generate both kinds of `bears_on` automatically.

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

## The pre-registration kind classification gap

**Surfaced during this draft:** `pre-registration` is not in `science_tool/graph/entity_registry.py`'s `_CORE_KIND_CLASSES` mapping. Every other kind referenced in the recast (hypothesis, question, proposition, interpretation, finding, task, workflow-run, dataset, etc.) is registered with an explicit class. Pre-reg is not.

This isn't a t012 blocker, but it should be resolved before the recast actually ships:

- **Recommended classification:** `EntityClass.OPERATIONAL`. A pre-reg is fundamentally a *procedural commitment* — it commits to executing or interpreting in advance. Even epistemic-target pre-regs are themselves operational in nature (they commit to a procedure for interpretation). The pre-reg's role as a `bears_on` source on epistemic targets is independent of its own class.

- **Alternative:** `EntityClass.REFERENCE`. Argued: pre-regs are authored declarations that don't change after committed. Counter-argument: they participate in the dependency graph (their commitment dates are load-bearing), which is more like operational behavior than reference behavior.

- **Suggested follow-up task:** add `"pre-registration": EntityClass.OPERATIONAL` to `_CORE_KIND_CLASSES` (one-line registry change + test). This unblocks both prose recast (skills can branch on `kind_class("pre-registration")`) and the auto-derivation rule below.

### Auto-derivation rule for pre-reg → epistemic target

If we want a pre-reg with an epistemic target to show up as a `bears_on` source automatically (rather than relying on the analysis's interpretation entity to carry the chain), we need a new rule in `freshness.py`'s `derive_bears_on_from_typed_edges`:

> For a `pre-registration` entity P with `related:` member E:
>   - if `EntityClass(E) == EPISTEMIC`: emit `P bears_on E` at depth 1.
>   - if `EntityClass(E) == OPERATIONAL`: do not emit (operational targets aren't `bears_on` sinks).

This is a small implementation follow-up — call it `[t012b]`. It's *optional* for the prose recast (the existing chain `pre-reg → analysis → interpretation → hypothesis` already produces the right edge through closure if the pre-reg participates in the analysis's `related:` graph), but it would make the relationship explicit and let `science:status` surface "this hypothesis has N pre-registered bears_on sources" cleanly.

**Recommendation:** Land t012 (prose) first. Land the registry classification (`pre-registration` → OPERATIONAL) as a tiny standalone fix concurrently with t012's first downstream review. Defer the auto-derivation rule until Phase 2 (`[t011]`) needs it for weighting.

---

## Downstream impact

26 existing pre-regs across 4 of 5 locally-present Science projects (counted 2026-05-04):

| Project | Pre-reg count | Notable instances |
|---|---|---|
| natural-systems | 13 | `pre-registration-h07-beta-arbitration.md` targets `hypothesis:h07-...` + 4 questions (epistemic); `pre-registration-t085-t086.md` targets task IDs (operational) |
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

1. **Now:** circulate this draft (or its summary) to downstream maintainers. Solicit objections specifically on (a) whether the recast changes intent of any existing pre-reg, (b) whether `commitment_weight` is worth adding as an optional field or should be derived from prose, (c) whether any project has tooling that depends on the binary-verdict reading of pre-regs.
2. **After objections resolved:** apply the skill changes from § "Skill changes" and the doc change from § "Doc changes".
3. **Concurrently or shortly after:** land the registry classification fix (`pre-registration` → OPERATIONAL).
4. **Phase 2 prep:** if/when Phase-2 sampling (`[t011]`) needs explicit pre-reg `bears_on` edges, add the auto-derivation rule then.

Total prose-edit work in step 2 is small: ~80 lines added across `commands/pre-register.md`, `commands/interpret-results.md`, and `docs/proposition-and-evidence-model.md`, plus zero edits to `docs/claim-and-evidence-model.md` (already superseded).

---

## Open questions for review

1. **`commitment_weight` field — yes or no?** Adding it (even optional) is a soft schema change and a new authoring decision the user must make at pre-reg time. Alternative: omit it, treat all pre-regs as `strong`, and add weighting later if Phase-2 needs the gradient. **Lean: omit for now.**
2. **Pre-reg classification: OPERATIONAL or REFERENCE?** Lean: OPERATIONAL (a procedural commitment).
3. **Should `bias-audit` skill be reframed in this same recast?** Lean: defer — its current language is mild enough not to mislead.
4. **Should the supersede notice in `claim-and-evidence-model.md` be strengthened?** Lean: out of scope for t012; do separately if at all.

---

## What this draft is **not**

- It is not the final recast text. The skill files and proposition-and-evidence-model.md should be edited only after objections come back.
- It is not a code change. No `science-tool` or `science-model` source files change for t012 itself. The classification fix (pre-reg → OPERATIONAL) and the auto-derivation rule are separate, smaller follow-ups.
- It is not retroactive. Existing pre-regs stay valid as authored; only their interpretation at evaluation time shifts.
