# Pre-registration recast audit — 3d-attention-bias

**Audit date:** 2026-05-04
**Project root:** `/mnt/ssd/Dropbox/3d-attention-bias`
**Scope:** all 4 pre-regs under `doc/meta/pre-registration-*.md`
**Recast spec:** `docs/plans/2026-05-04-prereg-recast-draft.md` (revision 2)

---

## Summary

3d-attention-bias has 4 pre-regs, all from March-April 2026. All target `hypothesis:h01-3d-attention-improves-performance` (the project's primary hypothesis), and three of four also reference multiple `proposition:` entities (h01-structure-sensitive-improvement, h01-bias-function-varies, h01-shortcutting-risk). Propositions are EPISTEMIC, so the recast's auto-derivation rule will fire `bears_on` edges to all proposition refs as well as the hypothesis ref — the **richest epistemic linkage of any project audited.**

The frontmatter is non-canonical (no `id:`, no `type:`, uses `date:` instead of `committed:`, uses `status:` values "registered" / "revised" rather than canonical `draft` / `committed` / `complete`). Same shape as seq-feats — minimal frontmatter from before the canonical schema stabilized.

**Recommendation for 3d-attention-bias:** No file edits required for the recast itself. Frontmatter regularization is independent of t012.

---

## Inventory

| File | `date:` | Status (raw) | Hypothesis | Propositions | Other epistemic | Class |
|---|---|---|---|---|---|---|
| `pre-registration-experimental-distance-pilot.md` | 2026-03-18 | registered | h01 | — | — | mixed (only h01 epistemic) |
| `pre-registration-phase1-ablation.md` | 2026-03-19 (updated 2026-04-13) | revised | h01 | 3 (structure-sensitive, bias-function-varies, shortcutting-risk) | question (q16) | mixed |
| `pre-registration-t041-specificity-extension.md` | 2026-04-14 | revised | h01 | 2 (shortcutting-risk, structure-sensitive) | 2 questions (q15, q19) | mixed |
| `pre-registration-t045-t046-mechanism-and-env-shift.md` | 2026-04-14 | revised | h01 | 1 (structure-sensitive) | 2 questions (q20, q21), interpretation | mixed |

### Frontmatter anomalies (pre-existing, not recast-specific)

- **`date:` instead of `committed:`** — 4th variant of the date-tracking field across projects (after `committed:`, `created:`, `created:` + `committed:`). Canonical is `committed:`.
- **No `id:` or `type:` fields** — same minimal-frontmatter pattern as seq-feats.
- **`status:` values** — `registered` (1) and `revised` (3). Neither is in canonical vocabulary (`draft` / `committed` / `complete`).
- **`supersedes:` field on experimental-distance-pilot** — string annotation rather than entity ref ("2026-03-16 version (updated with actual t032 results and controlled design)"). Project-specific extension; not a recast issue.

### Classification breakdown

- **Pure-epistemic:** 0
- **Pure-operational:** 0
- **Mixed:** 4 (all)

3 of 4 pre-regs reference 1-3 `proposition:` entities — distinct from any other project audited. Propositions are EPISTEMIC, so the auto-derivation rule will fire **multiple `bears_on` edges per pre-reg**: one to the hypothesis and one per proposition. This is the richest epistemic linkage in the surveyed corpus.

---

## Author-intent vs. recast interpretation

### `phase1-ablation` — clean proposition-decomposed hypothesis

The body explicitly decomposes H01 into three propositions and asks one question per proposition:

> **H01 claim: `h01-structure-sensitive-improvement`** — Does the t033 result replicate with 5 seeds? Do other bias functions perform better?
> **H01 claim: `h01-bias-function-varies`** — Does the optimal bias function differ from power law? MoG dominance in attention profiles (t001) suggests learned bins may be more natural.
> **H01 claim: `h01-shortcutting-risk`** — Does the A-seq control (sequence distance) produce the same effect? If so, the improvement is from any pairwise signal, not 3D structure specifically.

Under the recast: 4 `bears_on` edges from the pre-reg (one to h01, three to the propositions). This is the richest auto-derived edge structure in the audit. The propositions match canonical proposition-and-evidence-model usage — h01 as the bundling hypothesis, propositions as the truth-apt sub-claims, evidence edges (after analysis) attaching to specific propositions rather than to the hypothesis as a whole.

**Excellent recast fit.** The author has internalized the proposition-vs-hypothesis decomposition the proposition-and-evidence-model.md doc prescribes, and the recast's auto-derivation rule produces the right edge structure.

### `t045-t046-mechanism-and-env-shift` — discriminating mechanism question

Body opens with question-driven framing for q20 ("why does random distance match real 3d") and q21 ("environment-shift verification") — exactly the recast spirit of using questions to organize discriminating tests. The pre-reg is checking whether t037's effect is environment-shift-driven vs. mechanism-driven.

The `interpretation:phase1-ablation-n29-extension` ref provides upstream-evidence linkage. Under the recast, this produces a `bears_on` edge from the pre-reg to the interpretation (epistemic), capturing the dependency.

**Clean fit.**

### `experimental-distance-pilot` — minimal pre-reg, ok shape

Only h01 in `related:` (no propositions or questions). Body is short ("Experimental-Distance Pilot Training (RNA SS)"). Will produce a single `bears_on` edge to h01.

**Adequate fit, simpler shape than the others.**

---

## Plan-level issues surfaced

### Issue 1 (recurrent): `related:` conflation

All 4 pre-regs have `task:` refs alongside epistemic refs in `related:`. Same pattern as every other project. Resolved by the recast plan's sub-prompt addition.

### Issue 2 (pre-existing, not recast-specific): non-canonical frontmatter

- 4th distinct date-field variant: `date:` (vs canonical `committed:`).
- New `status:` variants: `registered`, `revised`.
- Missing `id:`, `type:` fields.

Same broad pattern as seq-feats — pre-canonical pre-regs, regularization out of t012 scope.

### No new structural plan-level issues from 3d-attention-bias.

This is the third project in a row (after cbioportal and evolution) that surfaces no new structural issues. The substantive plan-level findings have all been surfaced.

---

## Recommended actions

### For 3d-attention-bias

1. **No file edits required for the recast itself.**
2. **Pre-existing convention drift** (out of t012 scope):
   - `date:` field shape — migrate to canonical `committed:`.
   - `status:` vocabulary — migrate `registered` and `revised` to canonical `draft` / `committed` / `complete`.
   - Add `id:` and `type:` fields to bring frontmatter to canonical shape.

### For the recast plan (`docs/plans/2026-05-04-prereg-recast-draft.md`)

1. **Confirms recurrent issues** (Issue 1: `related:` conflation; Issue 2: status-vocabulary drift).
2. **No new structural changes.**
3. **Possible plan-prose addition**: 3d-attention-bias's proposition-decomposed pattern (h01 + 3 propositions, with each proposition being the truth-apt sub-claim) is a useful exemplar of "what a well-shaped epistemic-arm pre-reg looks like." Could be cited in `commands/pre-register.md` § "Section 0" prompt as an example.

---

## Open questions for project owner

1. The `date:` field — intentional difference from canonical `committed:`, or convention drift to be regularized?
2. The `status: registered` and `status: revised` values — what semantics distinguish them from each other and from canonical `committed:` / `draft:`?
3. The `supersedes:` field on experimental-distance-pilot — is the project tracking pre-reg supersession in any structured way (e.g., link to the prior version's ID), or is the string annotation sufficient?

---

## Cross-project pattern (after all 8 projects)

Cumulative findings across **8 projects, 60 pre-regs reviewed** (14 + 3 + 5 + 0 + 30 + 2 + 2 + 4):

- **`related:` conflation:** universal (7/7 pre-reg-using projects). Single most-confirmed plan-level finding.
- **Pre-reg shapes:** mostly mixed; zero truly-pure-anything.
- **Hypothesis-in-body-only:** 5 pre-regs across 2 projects (mm 4 + cbioportal 1). Project-side migration is the resolution.
- **Inquiry-targeting (no hypothesis):** 3 pre-regs (mm only). Resolved by reclassifying `inquiry` → `EPISTEMIC` per agreed plan.
- **Falsification-clause language:** benign as anti-bias procedural rigor.
- **Unregistered ref-kinds in `related:`:** 6+ varieties (`decision:`, `latent:`, `bias-audit:`, `analysis-plan:`, `meta:`, `rq:`). Silent-skip is correct semantics; document in plan.
- **Variant amendment-tracking fields:** 3 shapes (`amendments:`, `amendment_history:`, `amended:`).
- **Variant date fields:** 2+ shapes (`committed:`, `date:`).
- **Status-vocabulary drift:** 4 non-canonical values seen (`active`, `registered`, `revised`, plus the canonical-but-rare `complete`).
- **Best-of-class recast-compatible pre-regs:** mechanisms/evolution h003-t002 and t007 (explicit narrow-scope verdict language) and 3d-attention-bias phase1-ablation (proposition-decomposed shape).

The recast plan after this audit needs:
- **Reclassify `inquiry` to EPISTEMIC** (per agreed mm Issue 2).
- **Document unregistered-kinds silent-skip** behavior.
- **Add prose for hypothesis-in-body-only pre-regs** (per mm Issue 1, strengthened by cbioportal).
- **Add the sub-prompt at pre-reg authoring time** to distinguish commitment targets from navigation context (per universal `related:` conflation finding).
- **Add federation note** (per cancer-meta audit) — federated graph builders inherit the `bears_on` deriver automatically.
- **Update missing-myeloma footnote** — myeloma is at `~/d/cancer/cancer-types/multiple-myeloma/` with 30 pre-regs.
- **No further structural changes.**

The cumulative audit work has surfaced exactly what the audit was meant to surface: a small set of substantive plan refinements (each backed by real-world pre-reg patterns), and a much larger set of pre-existing project-side data-quality issues that the recast can accommodate but doesn't need to fix.

---

## What's next

After 3d-attention-bias sign-off, proceed to:
- cats (0 pre-regs, brief completeness note — final project)

After cats: consolidated revision of the recast plan incorporating all surfaced findings.
