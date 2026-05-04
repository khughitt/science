# Pre-registration recast audit — protein-landscape

**Audit date:** 2026-05-04
**Project root:** `/mnt/ssd/Dropbox/protein-landscape`
**Scope:** all 3 pre-regs under `doc/meta/pre-registration-*.md` (worktree duplicates excluded)
**Recast spec:** `docs/plans/2026-05-04-prereg-recast-draft.md` (revision 2)

---

## Summary

protein-landscape has the smallest pre-reg count of any pre-reg-using project (3 of 26), but two of its pre-regs (`q63`, `q81`) are **deliberately structured as discriminating tests between competing hypotheses**. One (`q63`) contains a "No post-hoc revision of the thresholds in this section is permitted" clause that initially looked like a deliberately authored kill switch.

On closer reading **it is not a kill switch in the recast's sense** — it is an **anti-bias procedural lock** ("don't let me nudge thresholds after seeing data"). The author committed to procedural rigor against post-hoc threshold-shifting, not to a metaphysical claim that the hypothesis "can never be true." Under the recast, this lock is preserved verbatim as the operational portion of the pre-reg (locked thresholds, no post-hoc revision). What happens *after* the threshold fires is normal evidence flow: the result becomes a `disputes bears_on` edge weighted by what the actual analysis shows (effect sizes, CIs, magnitudes of disagreement), not by a binary "threshold crossed → hypothesis terminated."

This is the recast's core philosophical stance: all scientific analyses are imperfect; upstream changes (better data, better processing, better baselines) can shift epistemic status even for things we currently put very low confidence in. The pre-reg's role is to prevent the author from p-hacking their own confidence higher; it is not to declare the hypothesis dead on threshold-crossing.

**Recommendation for protein-landscape:** no file edits required. The pre-regs' falsification clauses are operational rigor commitments that the recast preserves; the resulting evidence flow is normal weighted-update flow.

The audit *did* surface one substantive plan-level issue — but it's the same `related:` conflation already noted in the natural-systems audit (Issue 2 below). No new plan-level issue from protein-landscape.

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

### `q63-heldout-taxa-benchmark` — anti-bias procedural lock, not a kill switch

This pre-reg's "joint-failure clause" initially looks like a deliberately authored kill switch:

> `gap(low-LAD) ≤ 0` (95% CI includes 0 or is negative) on both tasks, **AND** raw-PCA50 also fails to beat Pfam on low-LAD on at least one task, **jointly refutes** H02 P3 and H03 P-predict-1 as currently stated. This is the falsification condition. **No post-hoc revision of the thresholds in this section is permitted.**

On the right reading, **this is an anti-bias procedural lock, not a verdict gate.** The "no post-hoc revision permitted" line is anti-p-hacking — the author committed in advance to *not letting themselves shift the thresholds after seeing data*. That commitment is to procedural rigor, not to a metaphysical claim that H02 P3 is removable from the graph if the threshold crosses.

What actually happens under the recast when this clause fires:

1. **Operational portion (preserved verbatim):** the locked thresholds, the no-post-hoc-revision rule, and the cohort/CI specifications stay exactly as written. `science:interpret-results` confirms these were honored. If they weren't, that's an `amendments:` violation — same as today.
2. **Epistemic portion (normal evidence flow):** the gap-on-low-LAD result feeds H02 P3 and H03 P-predict-1 as a `disputes bears_on` edge. The edge's effective weight is driven by *what the data actually shows* — effect sizes, CIs, magnitudes of disagreement — not by the binary fact that the threshold was crossed. If the gap is large and confidently negative, the edge has high weight and belief drops a lot. If the gap is barely negative with a wide CI, the edge has low weight and belief drops a little.

The `is currently stated` qualifier in the falsification clause is doing real work here. The author isn't saying "H02 P3 can never be true"; they're saying "if we observe X, the version of H02 P3 we currently hold is mistaken" — which is exactly weighted-update semantics. Future evidence can re-elevate H02 P3 (perhaps in a re-formulated version), and the recast's graph structure preserves that pathway.

**Graded null-result handling** (smaller than joint-failure):
> Update H02 P3 to specify "at some scale k" rather than a blanket claim, and re-run at the winning k as a confirmatory follow-up.

This is the recast's spirit operating without explicit awareness of the recast — null → refine the proposition, not abandon the hypothesis.

**Explicit "ambiguous" handling** (won't retroactively reclassify):
> The decision rule explicitly includes an "ambiguous" label. In that case the project writes the interpretation as "evidence insufficient to discriminate Reading A from Reading B" and does **not** retroactively re-classify the outcome into a more favourable bucket.

Also recast-spirit. No conflict.

**No plan change required.** The recast's "null is not a kill switch" framing is correct as-stated; q63's "kill switch" reads correctly as an anti-bias procedural lock once parsed carefully.

**Skill-prose implication only:** `commands/pre-register.md` and `commands/interpret-results.md` should help authors and interpreters parse falsification clauses this way. A pre-reg author who writes "this jointly refutes H02 P3" should be guided to read their own commitment as "this commits us to taking that result as strong disputes evidence, weighted by what we actually observe." This is a phrasing-and-prompts refinement, not a structural plan change.

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

### Issue 1 (substantive, recurrent): `related:` conflates commitment target with navigation context

**Same issue as natural-systems' Issue 1.** `t098-phylogenetic-2m`'s body is methodologically operational; the epistemic entities in `related:` (q11, q14, F43, propositions) are context, not commitment targets. Confirms the cross-project pattern: pre-reg authors use `related:` for discovery/navigation, not exclusively for declaring commitment targets.

The natural-systems audit's recommended resolution (a sub-prompt at pre-reg authoring time to confirm which `related:` entries are commitment targets) applies here too. Two of three protein-landscape pre-regs (`q81`, `t098`) would benefit from the prompt; only `q63` is unambiguously a commitment-to-the-target pre-reg.

### Issue 2 (minor): `task:bias-audit-...` reference shape

Pre-existing convention drift (a non-task entity referenced as a task). Not a recast issue but worth flagging in a separate cleanup pass — possibly aligns with `[t008]` (validator: warn on inline-dict synthesized_from items) or `[t009]` (entity-rename / declarative-migrations primitive).

---

## Recommended actions

### For protein-landscape

1. **No file edits required.** All three pre-regs' intent is preserved by the recast: q63's falsification language is correctly read as an anti-bias procedural lock (operational, preserved verbatim), and the resulting evidence flow is normal weighted-update flow.
2. **Author confirmation requested:** for `t098-phylogenetic-2m`, confirm whether the epistemic entries in `related:` (q11, q14, F43, propositions) are commitment targets (the pre-reg promises a result-pattern interpretation for them) or navigation context (the pre-reg is procedurally locked, the questions are what's being tested).
3. **Pre-existing convention drift** (`task:bias-audit-...`): consider regularizing in a separate pass; not blocking.

### For the recast plan (`docs/plans/2026-05-04-prereg-recast-draft.md`)

1. **Confirms Issue 1 from natural-systems audit (`related:` conflation).** Cross-project pattern confirmed; the natural-systems audit's resolution applies. No new structural plan change from protein-landscape.

2. **Skill-prose refinement (no plan-structure change):** `commands/pre-register.md` and `commands/interpret-results.md` should help authors and interpreters parse "this jointly refutes hypothesis H" pre-reg language as **anti-bias procedural commitment** ("if we observe X, we commit to taking that as strong disputes evidence"), rather than verdict-gate language. This is a phrasing-and-prompts refinement, not a structural change to the recast's claims.

---

## Open questions for project owner

1. For `t098-phylogenetic-2m`: are the epistemic entries in `related:` (q11, q14, F43, propositions) commitment targets or context?
2. For `q63-heldout-taxa-benchmark`: confirming the audit's reading — the "No post-hoc revision permitted" clause is anti-bias procedural rigor (preserved verbatim under the recast), not a metaphysical "this hypothesis can never be true" claim. Result feeds in as normal weighted-update evidence whose weight reflects the actual gap-on-low-LAD magnitude/CI rather than a binary threshold-crossing flag. Acceptable framing?
3. Does the project have any tooling that depends on a binary-verdict reading of `q63`'s falsification clause? (None found in audit; please confirm.)

---

## Cross-project pattern (after natural-systems + protein-landscape)

One substantive plan-level issue is recurrent across both projects:

- **Operational pre-regs with epistemic context in `related:`** (h07, t098). The recast's classification rule is too coarse to distinguish a pre-reg's commitment targets from its navigation/discoverability context. → natural-systems' Issue 1.

A second pattern surfaced but resolved without a plan change:

- **Pre-registered falsification clauses** (q63). On first read these look like recast-incompatible kill switches; on closer reading they are **anti-bias procedural locks** — anti-p-hacking commitments that "we will not nudge thresholds after seeing data." The recast preserves these verbatim as the operational portion of the pre-reg, and the resulting evidence flow is normal weighted-update flow whose weight reflects the actual analysis result, not the binary threshold-crossing event. No plan change required; skill prose should help authors and interpreters parse falsification language this way.

Pre-reg shapes seen so far across the two projects:
- Operational with epistemic context (most common): h07, t098, t214, most natural-systems pre-regs with operational tasks in `related:`.
- Discriminating epistemic test (less common but present): q63, q81. These are the cleanest fit for the recast's epistemic-arm semantics.
- Purely operational with no epistemic context (rare): none seen yet.

The recast's draft target — "epistemic-arm pre-reg whose commitment is an interpretation rule" — applies cleanly to the discriminating-test shape (q63, q81) once falsification clauses are read as anti-bias procedural locks. The operational-with-epistemic-context shape is what surfaces the substantive plan-level issue.

---

## What's next

After protein-landscape sign-off, proceed to:
- seq-feats (5 pre-regs, cycle-staged commitments)
- 3d-attention-bias (4 pre-regs, mixed targets)
- cats (0 pre-regs, brief completeness note)
