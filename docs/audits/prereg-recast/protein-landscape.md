# Pre-registration recast audit — protein-landscape

**Audit date:** 2026-05-04
**Project root:** `/mnt/ssd/Dropbox/protein-landscape`
**Scope:** all 3 pre-regs under `doc/meta/pre-registration-*.md` (worktree duplicates excluded)
**Recast spec:** `docs/plans/2026-05-04-prereg-recast-draft.md` (revision 2)

---

## Summary

protein-landscape has the smallest pre-reg count of any pre-reg-using project (3 of 26), but two of its pre-regs (`q63`, `q81`) are **deliberately structured as discriminating tests between competing hypotheses**, and one (`q63`) contains an **explicit, pre-registered falsification clause** with strict thresholds. This is a different shape than natural-systems' single-hypothesis tests and it surfaces a substantive plan-level issue:

> **The recast says "null is not a kill switch," but q63 contains a deliberately authored kill switch.** The author has thought carefully about which result patterns falsify which propositions, with explicit "No post-hoc revision of the thresholds in this section is permitted" language.

This isn't a contradiction with the recast's underlying intent — the recast's concern is that hypotheses get *removed* from the graph or stop being queryable when null results land. q63's falsification clause doesn't remove the hypothesis; it commits to an interpretation pattern strongly. But the recast's framing language ("no kill switches") needs to distinguish between "no graph removal on null" (correct) and "no strong-weight commitments allowed" (incorrect — q63 should still be honored). See § "Plan-level issues surfaced — Issue 1".

**Recommendation for protein-landscape:** no file edits required. The pre-regs' explicit falsification commitments should map cleanly to strong-weight `bears_on` edges under the recast.

---

## Inventory and classification

| # | File | Status | Outcome | Epistemic targets | Operational targets | Class | Notes |
|---|---|---|---|---|---|---|---|
| 1 | `pre-registration-q63-heldout-taxa-benchmark.md` | committed (2026-04-24) | — | q63, h02, h03, discussion | t143, t144, t145, t147, t156 | mixed | **Discriminating test** — pre-registered falsification clause on H02 P3 + H03 P-predict-1 |
| 2 | `pre-registration-q81-curator-derived-non-structural.md` | committed (2026-04-26) | — | q81, q63, h02, h03, interpretation, discussion | t169 | mixed | **Discriminating test** — Generalist vs Specialist refutation reading |
| 3 | `pre-registration-t098-phylogenetic-2m.md` | committed (2026-04-13) | — | q11, q14, finding:F43, 2 interpretations | t098, t074, "task:bias-audit-t098-pre-registration" | mixed | Methodology lock-in (raw vs dedup); revised after bias-audit |

### Classification breakdown

- **Pure-epistemic:** 0
- **Pure-operational:** 0
- **Mixed:** 3 (all)

All three pre-regs have canonical frontmatter (`id`, `type`, `committed`). **None of natural-systems' minimal-frontmatter issues apply here.**

### Frontmatter anomaly worth noting

`pre-registration-t098-phylogenetic-2m.md` has `"task:bias-audit-t098-pre-registration"` in `related:`. The reference is to a sibling document `doc/meta/bias-audit-t098-pre-registration.md`; treating it as a `task:` entity is unusual (bias audits aren't tasks in the canonical kind list). This is a pre-existing convention drift, not a recast issue, but it means the recast's auto-derivation rule will look up `kind_class("task")` for that ref and resolve to `OPERATIONAL` — which is the right answer mechanically, but the conceptual mismatch is worth flagging.

---

## Author-intent vs. recast interpretation

### `q63-heldout-taxa-benchmark` — explicit pre-registered falsification

This is the canonical example of a sophisticated discriminating-test pre-reg. Notable features:

**Pre-registered "joint-failure clause":**
> `gap(low-LAD) ≤ 0` (95% CI includes 0 or is negative) on both tasks, **AND** raw-PCA50 also fails to beat Pfam on low-LAD on at least one task, **jointly refutes** H02 P3 and H03 P-predict-1 as currently stated. This is the falsification condition. **No post-hoc revision of the thresholds in this section is permitted.**

**Graded null-result handling** (separate from joint failure):
> Update H02 P3 to specify "at some scale k" rather than a blanket claim, and re-run at the winning k as a confirmatory follow-up.

**Explicit "ambiguous" handling** (won't retroactively reclassify):
> The decision rule explicitly includes an "ambiguous" label. In that case the project writes the interpretation as "evidence insufficient to discriminate Reading A from Reading B" and does **not** retroactively re-classify the outcome into a more favourable bucket.

The author has built a **graded kill-switch**: small null → refine the proposition; joint-failure threshold met → falsification of the propositions as currently stated. This is much more careful than blanket "null = kill" semantics.

**How the recast should handle this.** Three readings of the recast's "no kill switches" language:

- **Reading A** (the recast as currently drafted, taken literally): "even pre-registered kill switches become weighted updates" — would *override* q63's deliberate falsification commitment. **Wrong reading.**
- **Reading B** (the recast's actual intent, charitably): "no graph-level removal of hypotheses on null; belief can drop very low, but the hypothesis remains queryable" — q63's falsification still fires, producing a strong-weight `disputes bears_on` edge that drives belief very low. **Right reading.**
- **Reading C** (the recast's actual intent, sharper): "default semantics: null = weighted update; pre-registered explicit falsification: null = strong-weight `disputes` evidence with the commitment level the author specified." **Best reading.**

The recast's draft text ("a null result against a pre-registered prediction is **evidence**, weighted by the pre-reg's commitment, but it is not a kill switch") points toward Reading C if "weighted by the pre-reg's commitment" is interpreted to mean "strong-weight if the author explicitly registered a falsification clause, lighter weight otherwise." But that interpretation is not made explicit in the draft, and Reading A is plausibly what a casual reader would extract.

**Plan-level finding:** the recast should make Reading C explicit. See § "Plan-level issues surfaced — Issue 1".

### `q81-curator-derived-non-structural` — discriminating test, follow-up shape

Frames the inquiry as choosing between two readings:
> **Generalist refutation.** The CATH-architecture loss generalizes to curator-derived targets.
> **Specialist refutation.** The CATH-architecture loss is specific to structural classifiers whose curation pipeline directly conditions on structure.

The word "refutation" appears in the body but applied to *which mechanism operates*, not to the hypothesis as a whole. The recast handles this naturally — the `bears_on` edge is from q81 into both H02 and H03, weighted by which reading the result supports. No conceptual conflict.

### `t098-phylogenetic-2m` — operational methodology lock-in

The pre-reg's body opens with:
> **Methodology Lock-in (the actual pre-registration call):** Report BOTH raw and dedup metrics. Dedup is the PRIMARY/canonical metric. Raw is reported as a methodological diagnostic.

This is overwhelmingly **operational** — it commits to a methodological choice (which metric is canonical) before observing results. The hypothesis-portion (q11, q14, finding:F43, propositions) is mostly context / what's being tested, not what's being committed.

This is the same shape as natural-systems' `h07-beta-arbitration`: an operational pre-reg whose `related:` field includes epistemic entities for context, not as commitment targets. **Same plan-level Issue 1 as in natural-systems** (`related:` conflates commitment target with navigation context).

The pre-reg also has a **bias-audit revision history** documented in the body opening. This is a useful pattern — the bias audit found three blind spots and the pre-reg was revised in response. Under the recast, this revision history should remain valid (it predates committed status; the original methodology is still locked).

---

## Plan-level issues surfaced

### Issue 1 (substantive, new): pre-registered falsification clauses

**Not surfaced in natural-systems' audit.** q63 contains an explicit "no post-hoc revision permitted" falsification threshold. The recast's "null is not a kill switch" framing, taken literally, would override this commitment.

**Resolution proposed:** make Reading C explicit in the recast draft. Specifically, edit `commands/pre-register.md` § "Section 0" target-class prompt to add:

> If the pre-reg includes an **explicit falsification clause** (a pattern that, if observed, the author commits to interpreting as "this hypothesis is refuted as currently stated"), record this as a strong-weight `disputes` commitment. Belief about the hypothesis can drop very low under this clause; the hypothesis remains a graph entity (queryable, citable, reviewable) but is unlikely to be re-elevated without significant new evidence. The recast's "no kill switches" framing prevents *graph removal* on null, not strong-weight belief loss.

This refinement also helps the q63 case interpret cleanly under the recast: the pre-registered falsification produces a high-weight `disputes` edge; belief about H02 P3 drops sharply; the hypothesis remains a node in the graph; future work that wishes to re-elevate H02 P3 must produce new evidence at a similarly high weight.

### Issue 2 (substantive, recurrent): `related:` conflates commitment target with navigation context

**Same issue as natural-systems' Issue 1.** `t098-phylogenetic-2m`'s body is methodologically operational; the epistemic entities in `related:` (q11, q14, F43, propositions) are context, not commitment targets. Confirms the cross-project pattern: pre-reg authors use `related:` for discovery/navigation, not exclusively for declaring commitment targets.

The natural-systems audit's recommended resolution (a sub-prompt at pre-reg authoring time to confirm which `related:` entries are commitment targets) applies here too. Two of three protein-landscape pre-regs (`q81`, `t098`) would benefit from the prompt; only `q63` is unambiguously a commitment-to-the-target pre-reg.

### Issue 3 (minor): `task:bias-audit-...` reference shape

Pre-existing convention drift (a non-task entity referenced as a task). Not a recast issue but worth flagging in a separate cleanup pass — possibly aligns with `[t008]` (validator: warn on inline-dict synthesized_from items) or `[t009]` (entity-rename / declarative-migrations primitive).

---

## Recommended actions

### For protein-landscape

1. **No file edits required.** All three pre-regs' intent is preserved by the recast under Reading C (see Issue 1 resolution).
2. **Author confirmation requested:** for `t098-phylogenetic-2m`, confirm whether the epistemic entities in `related:` (q11, q14, F43, propositions) are commitment targets (the pre-reg promises a result-pattern interpretation for them) or navigation context (the pre-reg is procedurally locked, the questions are what's being tested).
3. **Pre-existing convention drift** (`task:bias-audit-...`): consider regularizing in a separate pass; not blocking.

### For the recast plan (`docs/plans/2026-05-04-prereg-recast-draft.md`)

1. **NEW: add Issue 1 (pre-registered falsification clauses) resolution.** Revise the recast's "no kill switches" framing to make Reading C explicit: "no graph removal on null + default-light-weighted; explicit pre-registered falsification clauses produce strong-weight `disputes` edges that can drive belief very low while keeping the hypothesis as a graph entity." This is a substantive refinement to the recast's central claim.

2. **Confirms Issue 1 from natural-systems audit (`related:` conflation).** Cross-project pattern confirmed; the natural-systems audit's resolution applies.

3. **Remember:** Issue 1 here is *additive* to natural-systems' Issue 1. The two are different concerns:
   - natural-systems' Issue 1: classification rule too coarse — operational pre-regs with epistemic context get misclassified.
   - protein-landscape's Issue 1: blanket "no kill switches" too aggressive — pre-registered falsification clauses get overridden.

   Both need addressing in the recast.

---

## Open questions for project owner

1. For `t098-phylogenetic-2m`: are the epistemic entries in `related:` (q11, q14, F43, propositions) commitment targets or context?
2. For `q63-heldout-taxa-benchmark`: under the recast, would a strong-weight `disputes` edge that drops H02 P3's belief very low (without removing it from the graph) preserve the falsification's intended effect? (Confirming Reading C is acceptable.)
3. Does the project have any tooling that depends on a binary-verdict reading of `q63`'s falsification clause? (None found in audit; please confirm.)

---

## Cross-project pattern (after natural-systems + protein-landscape)

Two distinct shapes are emerging:
1. **Operational pre-regs with epistemic context in `related:`** (h07, t098). The recast's classification rule is too coarse to handle these correctly. → natural-systems' Issue 1.
2. **Epistemic pre-regs with explicit falsification thresholds** (q63). The recast's "no kill switches" language is too aggressive. → protein-landscape's Issue 1 (new).

A third potential shape — **purely-epistemic, no falsification clause, weighted-update by default** — would be the "vanilla" recast case. None of the audited natural-systems or protein-landscape pre-regs are this shape unambiguously; the closest is q81 (discriminating, no explicit falsification clause).

This suggests the recast's draft target ("vanilla weighted update") is the *least common* pre-reg shape in the surveyed projects so far. The recast's prose needs to handle the two more-common shapes well, not just the vanilla case.

---

## What's next

After protein-landscape sign-off, proceed to:
- seq-feats (5 pre-regs, cycle-staged commitments)
- 3d-attention-bias (4 pre-regs, mixed targets)
- cats (0 pre-regs, brief completeness note)
