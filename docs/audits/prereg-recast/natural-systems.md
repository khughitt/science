# Pre-registration recast audit — natural-systems

**Audit date:** 2026-05-04
**Project root:** `/mnt/ssd/Dropbox/natural-systems`
**Scope:** all 14 pre-regs under `doc/meta/pre-registration-*.md` (worktree duplicates excluded)
**Recast spec:** `docs/plans/2026-05-04-prereg-recast-draft.md` (revision 2)

---

## Summary

natural-systems is the most pre-reg-heavy locally-present project (14 of 26 across all projects). The audit found that **author practice already aligns with the recast's spirit** — null-result language is consistently informative-rather-than-terminal, and one of the most prominent pre-regs (`h07-beta-arbitration`) explicitly states "It does not update the H07 verdict by itself." The recast codifies what good authors here already do.

The audit also surfaced **one substantive plan-level issue** (the `related:` field conflates *commitment target* with *navigation context* — a pre-reg can have a hypothesis in `related:` purely for context while its actual commitment is procedural) and several smaller items.

**Recommendation for natural-systems:** no file edits required. The recast's interpretation rules apply cleanly to all 14 existing pre-regs without ambiguity. Plan-level issue noted in § "Plan-level issues surfaced" below — worth addressing in the recast spec before merge.

---

## Inventory and classification

Under the recast, target classification falls out of `EntityClass` of each entity in `related:`:
- `hypothesis`, `question`, `interpretation`, `discussion`, `proposition`, `finding` → **EPISTEMIC**
- `task`, `workflow-run`, `dataset`, `paper`, `spec`, `experiment` → **OPERATIONAL**
- `pre-registration` → unregistered today (Prerequisite 1 of recast assigns `OPERATIONAL`)

A pre-reg is "mixed" if `related:` contains at least one entity of each class. "Pure-epistemic" / "pure-operational" otherwise.

| # | File | Status | Outcome | Epistemic targets | Operational targets | Class | Notes |
|---|---|---|---|---|---|---|---|
| 1 | `pre-registration-h07-beta-arbitration.md` | draft | — | h07, q65, q67, q69, discussion | t376, t392, t437 | mixed | Amendment; load-bearing example |
| 2 | `pre-registration-q54-temporal-profile.md` | (no field) | — | q54, q56 | — | pure-epistemic | Minimal frontmatter (no `id`/`type`/`status`/`committed`) |
| 3 | `pre-registration-t085-t086.md` | (no field) | — | h01, h02, interpretation | — | pure-epistemic | Minimal frontmatter |
| 4 | `pre-registration-t092.md` | (no field) | — | q52, q56, interpretation | t092 | mixed | Minimal frontmatter |
| 5 | `pre-registration-t214.md` | (committed) | — | h01, q83, q86, 2 interpretations | t214 | mixed | |
| 6 | `pre-registration-t333.md` | draft | — | h05, q92, q23, 5 interpretations, 2 discussions, 3 chained pre-regs | t333 | mixed | Chains `pre-reg:t342`, `pre-reg:t349`, `pre-reg:t353` |
| 7 | `pre-registration-t342.md` | committed | — | h01, h02, q95, discussion | t342, t339 | mixed | |
| 8 | `pre-registration-t344.md` | **complete** | **null** | h01, h02, q95, q98, q99, discussion, 2 interpretations, chained pre-reg | t344, t342, t339 | mixed | **Critical case:** completed null result; hypothesis not killed |
| 9 | `pre-registration-t349.md` | active | — | h01, h02, q100, q95, q99, discussion, 5 interpretations, 2 chained pre-regs | t349, t347, t348 | mixed | |
| 10 | `pre-registration-t353.md` | complete | — | h01, h02, q75, q100, q101, discussion, 5 interpretations, chained pre-reg | t350, t353 | mixed | |
| 11 | `pre-registration-t371.md` | complete | — | h04, q72, interpretation | t371 | mixed | |
| 12 | `pre-registration-t372.md` | complete | — | h02, q49, 4 interpretations | t372 | mixed | |
| 13 | `pre-registration-t403.md` | draft | — | h05, q92, 3 interpretations, chained pre-reg | t393, t403 | mixed | Amendment |
| 14 | `pre-registration-t409.md` | complete | — | h03, q15, q70, 2 interpretations | t370, t408, t409 | mixed | |

### Classification breakdown

- **Pure-epistemic:** 2 (q54, t085-t086)
- **Pure-operational:** 0
- **Mixed:** 12

**All 14 pre-regs have at least one epistemic target.** Zero are pure-operational. This is unsurprising for a project working actively on hypothesis testing, but it means the recast's epistemic-arm semantics will apply to every existing pre-reg here; no pre-reg is unaffected.

---

## Author-intent vs. recast interpretation

**Spot-checked the three highest-signal cases:** h07-beta-arbitration (load-bearing example in t012's task description), t344 (the only completed pre-reg with null outcome), and q54 (minimal frontmatter, oldest). Author intent matches the recast in all three.

### `h07-beta-arbitration` — explicit alignment with the recast

The pre-reg's body opens:

> This amendment locks the formulation-breadth (`beta`) source used by `task:t392` and `task:t376` before the H07 beta-fidelity test is run. It is a methodological registration for paper selection, source/equation yield, and robustness arbitration. **It does not update the H07 verdict by itself.**

And the "Null Result Plan" section says:

> A null result with inadequate power remains inconclusive; **a null result with adequate detectable-effect calibration weakens H07 C1.**

The author already wrote this in the recast's spirit — null *weakens*, not *kills*. The recast formalizes what's already practiced.

**Caveat:** despite naming `hypothesis:h07-...` and questions in `related:`, the body's tone is overwhelmingly **operational** — the commitment is to procedures (paper selection, yield audit, robustness arbitration). The hypothesis is in `related:` for context and discoverability, not because the pre-reg commits to an interpretation rule for h07. The hypothesis-portion of the recast (treating this as an `bears_on` source) will produce a real edge in the graph — and that edge will reflect both the procedural rigor *and* the small-but-real epistemic commitment in the decision criteria. **This is correct.** But see § "Plan-level issues surfaced" — the rough categorization "epistemic target → epistemic-class pre-reg" misses the subtler operational-with-context shape that h07 actually has.

### `t344` — completed null outcome, no kill

Pre-reg's body opens with:

> **A null verdict here is informative**: it would mean the size-weighted criterion is saturated even on the most-coherent-looking slice of the catalog, and the per-fiber framing is decoratively but not empirically privileged at any scale we have probed.

Outcome was `null`. Hypothesis h01 was not abandoned — instead, follow-up pre-regs (`t349`, `t353`) probed the same hypothesis from different angles. This is the recast's spirit operating in pre-existing practice without explicit awareness of the recast.

Under hard-gating semantics, this null result on h01 / h02 should have terminated those hypotheses. It did not. The recast simply documents the actual norm.

### `q54-temporal-profile` — minimal-frontmatter case

This pre-reg lacks the canonical `id:` / `type:` / `status:` / `committed:` fields. Body framing of decision criteria (sampled): commits Level-2 validation thresholds. Targets are pure-epistemic (q54, q56). Under the recast: classification works (`related:` is the only field needed), but the absent `committed:` date prevents the freshness-engine and any `commitment_weight` from anchoring temporally. **This is a pre-existing data-quality issue independent of the recast** — flagged for awareness.

**Sample of pre-existing data-quality issue:** `pre-registration-q54-temporal-profile.md` (no `committed:`, no `status:`, no `id:`/`type:`), same shape for `pre-registration-t085-t086.md` and `pre-registration-t092.md`. Three of fourteen.

---

## Plan-level issues surfaced

### Issue 1 (substantive): `related:` conflates *commitment target* with *navigation context*

**The recast's classification rule** (any epistemic entity in `related:` → epistemic-arm of the pre-reg) is too coarse to capture what natural-systems actually does. The h07 case shows a pre-reg whose body is overwhelmingly operational (procedure locks, file hashes, robustness gates) but whose `related:` field includes a hypothesis and three questions — those entries are there for **discoverability/navigation**, not because the pre-reg commits to an interpretation rule for them.

Under the recast as currently drafted, h07 becomes an epistemic `bears_on` source on `hypothesis:h07-...` purely because the hypothesis is in `related:`. That edge is technically correct (the pre-reg does indirectly bear on h07 through procedural rigor) but the *strength* of that bearing is weaker than the recast's framing implies. The pre-reg isn't saying "if X then h07 is supported"; it's saying "the procedure that will test h07 is locked to these settings."

**Two plausible resolutions:**

(a) **Sub-field within `related:`.** Distinguish "commits-to" targets from "context" targets, e.g.:

```yaml
commits_to:
  - hypothesis:h07-empirical-fidelity-alignment   # epistemic commitment
  - task:t376                                      # operational commitment
related:
  - question:q65-...                               # context only
  - discussion:...                                 # context only
```

But this is a schema change — exactly what t012 says we should not introduce.

(b) **Derive commitment-target from body language, not `related:`.** The pre-reg's body explicitly states what it commits to (decision criteria, locked settings). A skill-time prompt could ask the user to confirm which `related:` entries are commitment targets vs. context. This is close to t012's existing § 1 prompt ("identify whether the target is operational or epistemic") but adds a "which `related:` entries are commitment targets?" sub-prompt.

(c) **Accept the over-broad classification.** Treat any epistemic entry in `related:` as a commitment target, knowing the resulting `bears_on` edges may overstate the strength of commitment. This is acceptable if Phase-2 weighting can downgrade weak bearings; it's not acceptable if `bears_on` edges are treated as binary "this is a commitment" claims by `science:status` / `science:next-steps`.

**Recommendation:** add resolution (b) to the recast's `science:pre-register` skill changes. Cost: one extra prompt at pre-reg authoring time. Benefit: the `bears_on` edges actually mean what the recast claims they mean.

### Issue 2 (medium): chained pre-regs (pre-reg → pre-reg in `related:`)

natural-systems chains pre-regs: t333 references t342/t349/t353; t344 references t342; t349 references t342/t344; t353 references t349; t403 references t333.

Under the recast (with Prerequisite 1: `pre-registration` → `OPERATIONAL`), the auto-derivation rule from Prerequisite 2 is "for `pre-reg P` with `related: E`, if `E` is EPISTEMIC, emit `P bears_on E`." A pre-reg in `related:` is `OPERATIONAL`, so no `bears_on` edge fires from pre-reg-to-pre-reg.

That's the right call (a pre-reg amending or referencing another pre-reg is methodological context, not an epistemic commitment), but it means the `related:` chain pre-reg→pre-reg is silent in the materialized graph. If projects expect "this pre-reg is a follow-up to that one" to surface in graph queries, that expectation is unmet. **Worth confirming with natural-systems' maintainer** that this is acceptable.

### Issue 3 (minor): "amendment" pre-regs

Two pre-regs (h07-beta-arbitration, t403) are titled as amendments and have an `amendments:` field listing additional locked specifications (h07's amendment date is 2026-05-04). Under operational-pre-reg semantics, amendments are a first-class concept (you amend the procedural lock, with audit trail). Under epistemic-pre-reg semantics, what does it mean to amend an interpretation rule?

The recast's draft does not address this. **Recommendation:** add a note in `commands/pre-register.md` § "Plan for Null Results" that for epistemic-arm commitments, "amendments" function as a *new* `bears_on` source (a refinement of the original commitment) rather than a replacement; the original commitment's `bears_on` edge remains in the graph.

### Issue 4 (data-quality, pre-existing): minimal-frontmatter pre-regs

3 of 14 (q54, t085-t086, t092) lack canonical fields. The `2026-04-25-pre-registration-canonical-type.md` design specifies the canonical shape; these pre-existed that spec. Migrating them is **out of t012 scope** (separate task), but the recast should not pretend they're absent — `commands/interpret-results.md`'s pre-reg lookup needs to handle missing `committed:` gracefully (skip rather than crash).

---

## Recommended actions

### For natural-systems

1. **No file edits required.** The recast's interpretation applies cleanly; no existing pre-reg's *intent* is contradicted by the recast.
2. **Author confirmation requested:** for `h07-beta-arbitration` and any other mixed pre-reg with epistemic entries in `related:`, confirm whether those entries are commitment targets or navigation context. If the project preference is consistently "context only", that informs Issue 1's resolution.
3. **Pre-existing data-quality migration** (out of t012 scope): consider regularizing the minimal-frontmatter pre-regs (q54, t085-t086, t092) to canonical shape during a separate pass.

### For the recast plan (`docs/plans/2026-05-04-prereg-recast-draft.md`)

1. **Add Issue 1 resolution to the plan.** Recommend resolution (b): add a sub-prompt at pre-reg authoring time asking the user to confirm which `related:` entries are commitment targets vs. context. Update `commands/pre-register.md` § "Section 0" accordingly.
2. **Address chained-pre-regs (Issue 2)** explicitly in the plan: state that pre-reg → pre-reg `related:` does not produce a `bears_on` edge (because `pre-registration` is OPERATIONAL), and that this is intentional.
3. **Address amendments (Issue 3)** in the plan: note that for epistemic-arm commitments, amendments add new `bears_on` sources rather than replacing existing ones.
4. **Specify graceful handling of minimal-frontmatter pre-regs (Issue 4)** in the `interpret-results` § 4d skill changes: missing `committed:` → skip the temporal-anchoring step but still emit the `bears_on` edge.

---

## Open questions for project owner

1. Do any natural-systems tools or skills depend on a binary-verdict reading of pre-regs? (None found in audit; please confirm.)
2. Is the chained-pre-reg pattern (e.g., `t333` → `t342`/`t349`/`t353` in `related:`) expected to produce graph edges, or is it pure metadata?
3. For the three minimal-frontmatter pre-regs (q54, t085-t086, t092), is regularization on the project's roadmap independent of this recast?

---

## What's next

After natural-systems sign-off (or rejection of any audit conclusion), proceed to:
- protein-landscape (3 pre-regs, includes `q63-heldout-taxa-benchmark.md` question target)
- seq-feats (5 pre-regs, cycle-staged commitments)
- 3d-attention-bias (4 pre-regs, mixed targets)
- cats (0 pre-regs, brief completeness note)
