# Pre-registration semantics recast — draft proposal

> **Status:** Draft for circulation (t012), revision 3 (2026-05-04 post 9-project audit). Do **not** merge until downstream projects (Science cluster: natural-systems, protein-landscape, seq-feats, 3d-attention-bias; cancer cluster: multiple-myeloma, cbioportal, mechanisms/evolution, cancer/meta) have surfaced objections. The recast changes how their existing pre-regs are interpreted; no entity-file content changes, but small code prerequisites are required (see § "Code prerequisites"). Per-project audit reports under `docs/audits/prereg-recast/` cover all 60 surveyed pre-regs across 7 pre-reg-using projects.

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

Existing pre-regs already declare their target via `related:`. The classification of that target as operational or epistemic falls out of the entity registry's `EntityClass` mapping (added in `[t010]`, refined in this recast — see § "Code prerequisites"):

- `related: [hypothesis:h07-...]` → epistemic target (since `hypothesis` is `EPISTEMIC`)
- `related: [question:q63-...]` → epistemic target (since `question` is `EPISTEMIC`)
- `related: [proposition:p09-...]` → epistemic target (since `proposition` is `EPISTEMIC`)
- `related: [inquiry:h-myc-r-direct-program]` → epistemic target (since `inquiry` is **reclassified to `EPISTEMIC` in this recast**, per Prerequisite 3)
- `related: [task:t342]` → operational target (since `task` is `OPERATIONAL`)
- `related: [workflow-run:...]` → operational target (since `workflow-run` is `OPERATIONAL`)

So a pre-reg's "class of target" is computable today from existing data, plus the inquiry reclassification this recast introduces. Skills can branch on it without any frontmatter changes.

---

## Skill changes

### `science:pre-register`

**Adds:** an early prompt to identify the target class, and target-class-aware framing for decision criteria.

Concrete edits to `commands/pre-register.md`:

1. **New section 0 (before "Identify the Analysis"):** "Target class — operational or epistemic?"

   Prompt the user to identify which the pre-reg primarily commits to:
   - **Operational target** — a procedure, pipeline run, dataset processing step, or experimental protocol. The commitment is "we will execute X before observing Y." Deviation requires an amendment.
   - **Epistemic target** — a hypothesis, question, proposition, inquiry, or interpretation rule. The commitment is "we will *interpret* observed Y in this way to update belief about X." Deviation does not require an amendment, because the pre-reg is not gating a procedure; it is constraining how a future result feeds the epistemic graph.

   Mixed targets are common (e.g., "we will run analysis A and treat H as supported if effect > 0.3"). Treat the procedure portion and the interpretation portion separately:
   - **Operational portion:** stays as an amendment-gate check. `science:interpret-results` confirms the analysis ran as committed (or that any deviation has a corresponding `amendments:` record). No `bears_on` edge — operational targets are not `bears_on` sinks (`science-tool/.../graph/materialize.py` rejects authored `bears_on` edges to non-epistemic targets).
   - **Epistemic portion:** materializes as a `bears_on` edge from the pre-reg into the epistemic target via the new auto-derivation rule (see § "Auto-derivation rule for pre-reg → epistemic target" below). This is the load-bearing graph change of the recast.

   **Sub-prompt: which `related:` entries are commitment targets vs. navigation context?** This is the load-bearing question for whether `bears_on` edges produced from this pre-reg accurately reflect the author's commitment.

   Cross-project audit (60 pre-regs across 7 projects, 2026-05-04) found that every pre-reg-using project mixes two distinct uses of `related:` in the same field:
   - **Commitment targets** — entities the pre-reg actually commits to constraining ("if effect > 0.3, treat hypothesis H as supported")
   - **Navigation context** — entities cited for discoverability ("this pre-reg sits within the work on hypothesis H")

   The recast's auto-derivation rule treats every epistemic entity in `related:` as a commitment target, which over-derives `bears_on` edges. To prevent this, after the user lists `related:` entries, prompt:

   > "Of the epistemic entries in `related:`, which are commitment targets — i.e., entities this pre-reg actually constrains the interpretation of? Anything *not* called out here will still appear in `related:` for discoverability, but won't produce a `bears_on` edge."

   Record the commitment-target subset as `commits_to:` in the pre-reg frontmatter (new optional field; if absent, the recast falls back to "all epistemic `related:` entries are commitment targets" — the over-deriving default). The auto-derivation rule (Prerequisite 2 below) then prefers `commits_to:` when present.

   This handles the recurrent pattern surfaced by the audit:
   - `pre-registration-h07-beta-arbitration` lists `hypothesis:h07-...` for context but its body is operationally locked. Author would set `commits_to:` to operational tasks only.
   - `pre-registration-cycle1-domains` lists `hypothesis:h01-raw-feature-embedding-informativeness` but commits to experiment-design/analysis-tier specifications. Same.
   - `pre-registration-q63-heldout-taxa-benchmark` is the rarer case where the hypothesis ref *is* a commitment target. `commits_to:` would include both H02 and H03.

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

   - **Pre-canonical pre-regs (hypothesis-in-body-only):** Some older pre-regs reference hypotheses inline in their body prose (e.g., "H1 (primary, confirmatory)" labels) but do not carry corresponding `hypothesis:` refs in `related:`. Audit found this pattern in 5 pre-regs across 2 projects (multiple-myeloma's 4 pre-canonical, cbioportal's t077-glmm-logit-pooling).

     For these pre-regs the auto-derivation rule produces no `bears_on` edge to the body-level hypothesis (it only sees `related:`). When interpreting the analysis:

     1. Read the pre-reg's body for inline hypothesis labels (H1, H2, ...) and identify the corresponding `hypothesis:` entity, if one exists.
     2. If the entity exists, emit the evidence edge by hand using `science-tool graph add proposition --pre-registration <pre-reg-ref>` plus `cito:supports` / `cito:disputes` to the hypothesis. The `sci:preRegisteredIn` triple still threads through correctly.
     3. If no formal `hypothesis:` entity exists yet (cbioportal t077 case — hypothesis lives only in `specs/research-question.md`), flag this in the interpretation document and recommend the project promote it to a formal entity. The recast cannot fully derive `bears_on` for body-only hypotheses; project-side cleanup is the resolution path.

     This is a transitional accommodation — once projects regularize their pre-canonical pre-regs (out of t012 scope), the auto-derivation rule will catch them naturally and this manual step disappears.

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
Epistemic kinds for `bears_on` participation are: `hypothesis`, `question`,
`proposition`, `inquiry`, `interpretation`, `finding`, `report`, `story`,
`assumption`, `discussion`, `validation-report`, `mechanism`, and
`observation`. (Note: `inquiry` was reclassified from REFERENCE to
EPISTEMIC as part of the recast — see Prerequisite 3 below.)
Mixed pre-regs (an analysis that commits to both a procedure and an
interpretation rule) split cleanly: the operational portion remains an
amendment-gate check at interpret-results time, and the epistemic portion
materializes as a `bears_on` edge into the epistemic target. Operational
targets are not `bears_on` sinks, so no operational `bears_on` is emitted.

When the pre-reg's frontmatter includes the optional `commits_to:` field
(introduced by this recast — see `commands/pre-register.md` § Section 0),
that field overrides `related:` for commitment-target derivation:
`bears_on` edges are emitted from the pre-reg only to entities listed in
`commits_to:`, treating other `related:` entries as navigation context
only. This handles the common case where `related:` is used both for
genuine commitment targets and for discoverability.

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

Three code changes are **required** for the recast to mean anything in the materialized graph. The original draft framed two as optional follow-ups; that was corrected in revision 2. Revision 3 adds the inquiry reclassification (Prerequisite 3) per multiple-myeloma audit findings.

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

Tests: pre-reg with `related: [hypothesis:H]` → `P bears_on H` derived; pre-reg with `related: [task:T]` → no `bears_on` derived; mixed `related: [hypothesis:H, task:T]` → exactly one edge to H. **If `commits_to:` is present in the pre-reg frontmatter, prefer it over `related:` for commitment-target derivation** (per § "Skill changes" Section 0 sub-prompt) — `related:` then becomes navigation context only and does not produce `bears_on`. Unit-test against the existing freshness derivation harness.

Tracked as `[t012b']` (companion to t012b — same PR is fine, since both are tiny and tightly coupled).

### Prerequisite 3: reclassify `inquiry` from `REFERENCE` to `EPISTEMIC`

`inquiry` is currently `REFERENCE` in `_CORE_KIND_CLASSES` (`science-tool/src/science_tool/graph/entity_registry.py:58`). Audit of multiple-myeloma surfaced 3 pre-regs (t494, t498, t500) that target inquiries (e.g., `inquiry:h-myc-r-direct-program`) but no formal `hypothesis:` entity. multiple-myeloma uses inquiries as **pre-hypothesis structure** — a way to organize work toward a future hypothesis without committing to one yet.

Under the current REFERENCE classification, the auto-derivation rule (Prerequisite 2) does not fire `bears_on` to inquiry refs. This loses the epistemic-commitment signal for any pre-reg whose work is at the inquiry stage rather than the formal-hypothesis stage.

**Why EPISTEMIC, conceptually:** inquiry is an organizing structure over questions and propositions, both of which are EPISTEMIC. An inquiry collects uncertain assertions and the work done to constrain them. That's epistemic behavior — same as questions or propositions, just at a coarser organizational level. The Science cluster's current REFERENCE classification was a default rather than a deliberate decision.

**Fix:** change `_CORE_KIND_CLASSES["inquiry"]` from `EntityClass.REFERENCE` to `EntityClass.EPISTEMIC` in `science_tool/graph/entity_registry.py`. One-line change plus tests:

- Test 1: `kind_class("inquiry") == EPISTEMIC`.
- Test 2: pre-reg with `related: [inquiry:I]` → `P bears_on I` derived (the auto-derivation rule from Prerequisite 2 now fires on inquiry refs).
- Test 3: existing tests for inquiry-as-REFERENCE behavior must be updated. Audit `science-tool` tests for any that assert inquiry's REFERENCE class explicitly.

**Cross-cluster impact:** this change affects all 9 audited projects, not just multiple-myeloma. Audit found inquiry refs in pre-regs across natural-systems (multiple), 3d-attention-bias (none), seq-feats (none), protein-landscape (none), multiple-myeloma (heavy use), cbioportal (none), mechanisms/evolution (none). Reclassifying inquiry as EPISTEMIC adds new `bears_on` edges in natural-systems and multiple-myeloma; the other projects are unaffected.

This change is also the right resolution for the broader proposition-and-evidence-model.md doc — see § "Doc changes" updates.

Tracked as `[t012b'']` (third companion fix; can ship in the same PR as `[t012b]` and `[t012b']`).

### Unregistered ref kinds in `related:` — silent-skip behavior

Audit surfaced 6+ unregistered kind prefixes used in `related:` across projects: `decision:` (mm), `latent:` (mm), `bias-audit:` (evolution), `analysis-plan:` (evolution), `meta:` (evolution), `rq:` (mm pre-canonical).

Under the recast (and today), these are silently skipped during source loading per `science_tool/graph/sources.py`. **This is correct semantics, not a bug.** The auto-derivation rule has no class to dispatch on, so it cannot fire `bears_on`. Skipping is the safe behavior.

Project-side resolution paths (out of t012 scope but worth flagging in the recast plan):

1. **Register the kind as a project-specific extension** via `register_extension_kind` (existing `science-tool` API), assigning the appropriate `EntityClass`. Suitable for kinds the project intends to keep (e.g., mm's `decision:` — likely `REFERENCE`; mm's `latent:` — possibly `EPISTEMIC` if latent variables are uncertain assertions about underlying constructs).
2. **Migrate to a canonical kind.** E.g., `bias-audit:<slug>` → `task:bias-audit-<slug>` (matches an alternate convention also seen in cbioportal and protein-landscape).
3. **Drop the ref entirely** if the entity isn't authored anywhere.

**Recommended health-check pattern:** add a `science-tool health` (or sibling) check that lists unregistered ref kinds in `related:` across all entities in the project, so projects can audit their own kind taxonomies. Out of t012 scope; could be tracked as `[t012d]`.

### Federation behavior

Federation umbrella projects (e.g., `cancer/meta`) build a federated graph from children. The recast's auto-derivation rules are implemented in `science-tool` and run during `graph build`. Federated builds run `science-tool graph build` at the federation root, which means **the auto-derivation rules inherit automatically** — no federation-specific configuration required.

Two prerequisites for federation-level edges to materialize correctly:

1. The federated graph must include children's epistemic entities (hypotheses, questions, propositions, inquiries) so pre-reg → epistemic-target edges have valid targets at the federation level. Audit confirmed this is the case for `cancer/meta/knowledge/graph.trig` (32 pre-reg identifiers from children appear in the federated graph).
2. The federation builder must invoke the deriver. By default it does (federated build = `science-tool graph build` at federation root); confirm this hasn't been customized in a federation-specific way.

No federation-specific code changes required. Audit recommendation: confirm with whoever maintains `cancer/meta`'s graph-build pipeline.

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

**60 existing pre-regs across 7 pre-reg-using projects** (counted 2026-05-04, excluding `.worktrees/` duplicates). Per-project audit reports under `docs/audits/prereg-recast/`.

### Science cluster

| Project | Pre-reg count | Notable patterns |
|---|---|---|
| natural-systems | 14 | Author practice already aligns with recast (h07-beta-arbitration: "It does not update the H07 verdict by itself"; t344 null outcome did not kill h01/h02). 3 minimal-frontmatter pre-canonical pre-regs. |
| seq-feats | 5 | All `status: active` (non-canonical), no `id:`/`type:`/`committed:` fields. All target `hypothesis:h01` for navigation. t152-bpe-nda is cleanest epistemic-arm shape. |
| 3d-attention-bias | 4 | Richest epistemic linkage of any project — 3 of 4 reference multiple `proposition:` entities alongside h01. Pre-canonical frontmatter (`date:` instead of `committed:`, `status: registered`/`revised`). |
| protein-landscape | 3 | Fully canonical frontmatter. q63 has the "no post-hoc revision permitted" anti-bias procedural lock (preserved verbatim under the recast). q81 is a clean discriminating epistemic test. |
| cats | 0 | `profile: software`; no impact. |

### Cancer cluster

| Project | Pre-reg count | Notable patterns |
|---|---|---|
| multiple-myeloma | **30** | Largest project by count. Two-generation split: 4 pre-canonical (`doc/meta/`), 26 canonical (`doc/pre-registrations/`). Surfaced inquiry-targeting (3 pre-regs), unregistered kinds (`decision:`, `latent:`), hypothesis-in-body-only pattern (4 pre-regs). |
| cbioportal | 2 | `t077-glmm-logit-pooling`: extreme hypothesis-in-body-only — H1 is in `specs/research-question.md` (a `spec:` entity), not a formal `hypothesis:` entity. Doubled `id:` prefix. |
| mechanisms/evolution | 2 | Cleanest, most recast-compatible pre-regs across all 9 projects. Explicit narrow-scope verdict language with 4-tier outcome buckets. Three new unregistered kinds (`bias-audit:`, `analysis-plan:`, `meta:`). |
| cancer/meta | 0 | Federation umbrella; federates 32 pre-reg identifiers from children. Inherits standard validation; the recast's deriver inherits automatically through `science-tool` (see § Code prerequisites — Federation behavior). |

**No file in any project needs editing.** Each existing pre-reg's `related:` field already declares its targets; the recast changes how those targets are interpreted at evaluation time, plus the inquiry reclassification adds new `bears_on` edges from inquiry-targeting pre-regs (multiple-myeloma is the primary affected project).

### What downstream maintainers should review before merge

1. **For each existing pre-reg with epistemic targets:** does the recast change the *intended* meaning of that pre-reg? Audit found that author practice already aligns with the recast's spirit across all surveyed projects, but project-owner confirmation is the right gate.

2. **For pre-regs whose `related:` mixes commitment targets with navigation context** (the universal pattern surfaced by audit): consider authoring a `commits_to:` field on existing pre-regs to disambiguate. This is optional — the recast's default falls back to "all epistemic `related:` entries are commitment targets" if `commits_to:` is absent, which over-derives but doesn't fail. Setting `commits_to:` is the precise way to control which `bears_on` edges fire.

3. **Operational pre-regs are unaffected.** Anything pre-registering a procedural commitment (run-with-params, datapackage-before-unblinding) keeps its current gating semantics.

4. **No `committed:` re-dating.** Pre-regs already committed stay committed; the recast applies prospectively to interpretation, not retroactively to the commitment record.

5. **Anti-bias procedural locks** (e.g., q63's "No post-hoc revision permitted") are preserved verbatim under the recast. They read as anti-p-hacking commitments to threshold rigor, not as metaphysical "this hypothesis can never be true" verdicts. Project-owner confirmation of this reading is recommended.

**Specific maintainers to flag (highest impact first):**

- **multiple-myeloma** — 30 pre-regs, including the inquiry-targeting cases (t494, t498, t500) that gain new `bears_on` edges from the inquiry reclassification, and the 4 pre-canonical pre-regs whose hypothesis-in-body-only pattern requires manual evidence-edge emission per § "Skill changes" interpret-results subsection.
- **natural-systems** — 14 pre-regs, mostly mixed; cross-project pattern poster child for the `commits_to:` resolution.
- **seq-feats** — 5 pre-regs, all minimal-frontmatter; H01 in every `related:` for navigation.
- **3d-attention-bias** — 4 pre-regs with the richest proposition-decomposed epistemic linkage; ideal exemplars of "what good epistemic-arm pre-regs look like" once normalized.
- **protein-landscape** — 3 pre-regs, all canonical; q63's anti-bias lock interpretation requires confirmation.
- **mechanisms/evolution** — 2 pre-regs, exemplary recast-compatible shape; only `amended:` field shape needs flagging.
- **cbioportal** — 2 pre-regs, both with frontmatter convention drift; t077's body-only H1 needs project-side promotion to a formal `hypothesis:` entity for full recast benefit.
- **cancer/meta** — federation builder; confirm `bears_on` deriver inherits correctly.

---

## Sequencing for landing

1. **Now:** circulate this draft (and the per-project audit reports under `docs/audits/prereg-recast/`) to downstream maintainers. Solicit objections specifically on:
   - Whether the recast changes intent of any existing pre-reg (cross-project audit found author practice already aligns).
   - Whether the inquiry reclassification (`REFERENCE` → `EPISTEMIC`) is acceptable cluster-wide.
   - Whether the `commits_to:` optional frontmatter field is the right resolution for the `related:` conflation issue, or if a different shape is preferred.
   - Whether any project has tooling that depends on the binary-verdict reading of pre-regs.

2. **Land code prerequisites (`[t012b]` / `[t012b']` / `[t012b'']`):** all three changes can ship in one small PR:
   - Register `pre-registration` → `EntityClass.OPERATIONAL` in `_CORE_KIND_CLASSES` (Prerequisite 1).
   - Add the `pre-reg related: → bears_on epistemic-target` auto-derivation rule, with `commits_to:` precedence over `related:` (Prerequisite 2).
   - Reclassify `inquiry` from `REFERENCE` to `EPISTEMIC` (Prerequisite 3).

   See § "Code prerequisites" for details and tests.

3. **Apply prose changes:** the skill edits from § "Skill changes" and the doc edit from § "Doc changes". Safe because the registry now knows about pre-reg, inquiry is properly classified, and the graph carries the new edges.

4. **Phase 2:** when `[t011]` lands weighted sampling, the pre-reg `bears_on` edges are already in place to feed weighting. The inquiry reclassification gives Phase 2 access to inquiry-level signal as well.

5. **Out-of-scope follow-ups** (tracked separately, not blocking t012):
   - `[t012c]`: add `entity list --related <ref>` filtering for ergonomic pre-reg lookup.
   - `[t012d]`: `science-tool health` check listing unregistered ref kinds in `related:` across project entities (recommended by audit cumulative finding).
   - Project-side regularization passes (multiple projects): canonical frontmatter migration, amendment-field shape unification, custom-kind registration via `register_extension_kind`. Tracked per-project in audit reports.

Total prose-edit work in step 3 is small: ~120 lines added across `commands/pre-register.md`, `commands/interpret-results.md`, and `docs/proposition-and-evidence-model.md`, plus zero edits to `docs/claim-and-evidence-model.md` (already superseded).

---

## Open questions for review

1. **`commitment_weight` field — yes or no?** Adding it (even optional) is a soft schema change and a new authoring decision the user must make at pre-reg time. Alternative: omit it, treat all pre-regs as `strong`, and add weighting later if Phase-2 needs the gradient. **Lean: omit for now.**
2. ~~**Pre-reg classification: OPERATIONAL or REFERENCE?**~~ **Resolved (revision 3): OPERATIONAL** per Prerequisite 1.
3. **`commits_to:` field — accepted shape?** The audit-driven resolution to the `related:` conflation issue introduces `commits_to:` as an optional frontmatter field that overrides `related:` for commitment-target derivation. Alternative shapes considered and rejected: (a) repurposing existing `committed:` (already used for the date), (b) splitting `related:` into `commits_to:` + `context:` (more invasive — every pre-reg would need migration). **Lean: optional `commits_to:` with `related:` fallback. Confirmation requested.**
4. **Inquiry reclassification — cross-cluster acceptable?** Reclassifying `inquiry` from `REFERENCE` to `EPISTEMIC` affects all 9 audited projects, not just multiple-myeloma. Audit found inquiry refs in pre-regs only in multiple-myeloma and natural-systems; other projects unaffected. **Lean: reclassify (per agreement); confirm cluster-wide.**
5. **Should `bias-audit` skill be reframed in this same recast?** Lean: defer — its current language is mild enough not to mislead.
6. **Should the supersede notice in `claim-and-evidence-model.md` be strengthened?** Lean: out of scope for t012; do separately if at all.
7. **Pre-canonical pre-reg migration — project-led or cluster-wide initiative?** 12 of 60 surveyed pre-regs are pre-canonical (mm 4, seq-feats 5, 3d-attention-bias 3 with date-field drift, plus 3 minimal-frontmatter cases in natural-systems). Each project's roadmap is independent. **Lean: project-led; not blocking the recast.**

---

## What this draft is **not**

- It is not the final recast text. The skill files and `proposition-and-evidence-model.md` should be edited only after objections come back and the code prerequisites land.
- It is not retroactive. Existing pre-regs stay valid as authored; only their interpretation at evaluation time shifts.

The original draft additionally claimed "no code changes for t012 itself." That was withdrawn in revision 2 — see § "What changed in this revision" below.

---

## What changed in this revision

Revision 3 (2026-05-04, post 9-project audit):

- **Inquiry reclassified to EPISTEMIC** (Prerequisite 3, new). Per multiple-myeloma audit Issue 2 and agreed cluster-wide. mm uses inquiries as pre-hypothesis structure; without this reclassification, 3 of mm's 30 pre-regs (t494, t498, t500) produce no `bears_on` edges. natural-systems also uses inquiry refs in some pre-regs; reclassification is conceptually right (inquiries organize uncertain assertions, same as questions and propositions). One-line change in `_CORE_KIND_CLASSES` plus tests.
- **Sub-prompt for `commits_to:` vs navigation context** added to `commands/pre-register.md` § Section 0. Audit found that every pre-reg-using project (7 of 7) mixes commitment targets with navigation context in `related:`. The recast's auto-derivation rule would over-derive `bears_on` edges without this. The `commits_to:` field is optional; absent → fall back to "all epistemic `related:` entries are commitment targets" (over-deriving but not failing).
- **Prose for hypothesis-in-body-only pre-regs** added to `commands/interpret-results.md` § 4d. Audit found 5 such pre-regs across 2 projects (mm 4 pre-canonical, cbioportal t077). Manual evidence-edge emission is the transitional accommodation; project-side cleanup is the resolution path.
- **Silent-skip behavior for unregistered kinds** documented in § "Code prerequisites". Audit surfaced 6+ unregistered kinds (`decision:`, `latent:`, `bias-audit:`, `analysis-plan:`, `meta:`, `rq:`). Silent-skip is correct semantics; project-side resolution paths documented. Recommended `[t012d]` health-check follow-up.
- **Federation behavior** documented in § "Code prerequisites". Federated graph builders inherit the deriver automatically (no federation-specific config). cancer/meta confirms this.
- **Downstream impact table expanded** to cover the full 60-pre-reg / 7-project corpus surveyed by audit. Cancer cluster (mm, cbioportal, evolution, cancer/meta) added. Stale "myeloma not locally present" footnote removed — multiple-myeloma is at `~/d/cancer/cancer-types/multiple-myeloma/` with 30 pre-regs.
- **`proposition-and-evidence-model.md` subsection** updated to enumerate the EPISTEMIC kinds participating in `bears_on` (now including `inquiry`) and to document the `commits_to:` field.
- **Open questions updated**: OQ2 (pre-reg classification) marked resolved; new OQ3 (`commits_to:` shape acceptance), OQ4 (inquiry reclassification cluster-wide), and OQ7 (pre-canonical migration scope) added.
- **Sequencing updated** to bundle three Prerequisites in a single PR.

**Audit reports** (commits `c2e4e12` … `3ed68da` on `draft/prereg-recast`):
- `docs/audits/prereg-recast/natural-systems.md`
- `docs/audits/prereg-recast/protein-landscape.md` (revised post-feedback to correct kill-switch framing)
- `docs/audits/prereg-recast/seq-feats.md`
- `docs/audits/prereg-recast/cancer-meta.md`
- `docs/audits/prereg-recast/multiple-myeloma.md`
- `docs/audits/prereg-recast/cbioportal.md`
- `docs/audits/prereg-recast/mechanisms-evolution.md`
- `docs/audits/prereg-recast/3d-attention-bias.md`
- `docs/audits/prereg-recast/cats.md`

Revision 2 (2026-05-04, post initial review):

- **Auto-derivation rule is required, not optional.** The original draft asserted that the existing chain `pre-reg → analysis → interpretation → hypothesis` produces the right `bears_on` edge through closure. That was wrong: a pre-reg's `related:` materializes as `skos:related`, which freshness derivation does not consume. The recast has no graph effect without the explicit pre-reg → epistemic-target derivation rule. Promoted from "optional follow-up `[t012b]`" to "Prerequisite 2".
- **Registry classification is required for the prose recast to even branch correctly.** Without `pre-registration` in `_CORE_KIND_CLASSES`, `science-tool entity list --kind pre-registration` returns nothing (source loading skips unknown kinds) and the deriver has no kind to dispatch on. Promoted from "concurrent" to "Prerequisite 1".
- **CLI command corrected.** `science-tool entity list --type` → `--kind` (the `--kind` form is the one supported by `cli.py`). Recommended lookup is path-scan only until the registry change lands.
- **Mixed-target language corrected.** Operational targets are not `bears_on` sinks (materialization rejects them), so a "mixed pre-reg" does not generate "both kinds of bears_on" — only the epistemic portion produces a `bears_on` edge. The operational portion stays a procedural amendment-gate check.
- **Count corrected.** natural-systems pre-reg count was 13; correct is 14 (the original `find` command included `.worktrees/` duplicates which inflated other counts; the table number was off by one). Total of 26 was correct.
