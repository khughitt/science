# Pre-registration recast audit — 3d-attention-bias

**Audit date:** 2026-05-04
**Project root:** `/mnt/ssd/Dropbox/3d-attention-bias`
**Scope:** all 4 pre-regs under `doc/meta/pre-registration-*.md`
**Recast spec:** `docs/plans/2026-05-04-prereg-recast-draft.md` (revision 2)
**Migration branch:** `migration/prereg-recast-3d-attention-bias`

---

## Summary

3d-attention-bias has 4 pre-regs, all from March-April 2026. All target the H01 epistemic surface, and three of four also reference multiple `proposition:` entities (`h01-structure-sensitive-improvement`, `h01-bias-function-varies`, `h01-shortcutting-risk`, and later `h01-distance-semantics-secondary`). Propositions are EPISTEMIC, so this is the richest epistemic linkage of any project audited.

Migration regularized the non-canonical frontmatter (`id:`, `type:`, `committed:`, canonical `status: committed`) and added explicit `commits_to:` lists. This avoids treating every navigation/context reference as a formal epistemic commitment while keeping the pre-regs responsive to upstream epistemic changes through direct commitment targets.

**Recommendation for 3d-attention-bias:** Merge the project-side migration.

---

## Inventory

| File | Committed | Status | Hypothesis | Propositions | Other epistemic | Class |
|---|---|---|---|---|---|---|
| `pre-registration-experimental-distance-pilot.md` | 2026-03-18 | committed | h01 | — | — | mixed (only h01 epistemic) |
| `pre-registration-phase1-ablation.md` | 2026-03-19 (updated 2026-04-13) | committed | h01 | 3 (structure-sensitive, bias-function-varies, shortcutting-risk) | question (q16) | mixed |
| `pre-registration-t041-specificity-extension.md` | 2026-04-14 | committed | h01 context | 2 (shortcutting-risk, structure-sensitive) | 2 questions (q15, q19) | mixed |
| `pre-registration-t045-t046-mechanism-and-env-shift.md` | 2026-04-14 | committed | h01 context | 2 (structure-sensitive, distance-semantics-secondary) | 2 questions (q20, q21), interpretation | mixed |

### Migration decisions

| File | Added `commits_to:` |
|---|---|
| `pre-registration-experimental-distance-pilot.md` | `hypothesis:h01-3d-attention-improves-performance` |
| `pre-registration-phase1-ablation.md` | `hypothesis:h01-3d-attention-improves-performance`; `proposition:h01-structure-sensitive-improvement`; `proposition:h01-bias-function-varies`; `proposition:h01-shortcutting-risk` |
| `pre-registration-t041-specificity-extension.md` | `proposition:h01-shortcutting-risk`; `proposition:h01-structure-sensitive-improvement`; `question:q15-does-3d-attention-bias-improve-representations-or-act-as-a-structural-shortcut`; `question:q19-seeds-test-set-to-distinguish-3d-from-shortcut` |
| `pre-registration-t045-t046-mechanism-and-env-shift.md` | `question:q20-why-does-random-distance-match-real-3d`; `question:q21-t037-vs-t041-environment-shift`; `proposition:h01-structure-sensitive-improvement`; `proposition:h01-distance-semantics-secondary` |

Notes:

- `date:` was migrated to canonical `committed:`.
- Missing `id:` and `type:` fields were added.
- `status: registered` and `status: revised` were migrated to canonical `status: committed`.
- The `supersedes:` field on `experimental-distance-pilot` remains as a string annotation. It is project-specific history, not a commitment target.
- `question:q16-is-r90-ratio-overshoot-a-sequence-length-confound` remains in `related:` for `phase1-ablation`; it is calibration context, not one of the pre-reg's stated decision targets.
- `hypothesis:h01-3d-attention-improves-performance` remains in `related:` for the two extension pre-regs, but is not duplicated in `commits_to:` because those pre-regs explicitly narrow their commitments to constituent claims and discriminating questions.
- H01 still appears as a transitive `bears_on` target for the two extension pre-regs through their committed propositions. That is intended: the pre-regs are directly committed to narrower upstream entities while still remaining responsive to changes in the parent hypothesis surface.
- `proposition:h01-distance-semantics-secondary` was added to `related:` for `t045-t046` because its decision matrix names that proposition directly.

### Classification breakdown

- **Pure-epistemic:** 0
- **Pure-operational:** 0
- **Mixed:** 4 (all)

3 of 4 pre-regs reference 1-3 `proposition:` entities — distinct from any other project audited. Explicit `commits_to:` now records which of those references are formal commitment targets versus navigation/context.

---

## Author-intent vs. recast interpretation

### `phase1-ablation` — clean proposition-decomposed hypothesis

The body explicitly decomposes H01 into three propositions and asks one question per proposition:

> **H01 claim: `h01-structure-sensitive-improvement`** — Does the t033 result replicate with 5 seeds? Do other bias functions perform better?
> **H01 claim: `h01-bias-function-varies`** — Does the optimal bias function differ from power law? MoG dominance in attention profiles (t001) suggests learned bins may be more natural.
> **H01 claim: `h01-shortcutting-risk`** — Does the A-seq control (sequence distance) produce the same effect? If so, the improvement is from any pairwise signal, not 3D structure specifically.

Under the migration: 4 commitment edges from the pre-reg (one to h01, three to the propositions). This is the richest edge structure in the audit. The propositions match canonical proposition-and-evidence-model usage — h01 as the bundling hypothesis, propositions as the truth-apt sub-claims, evidence edges (after analysis) attaching to specific propositions rather than to the hypothesis as a whole.

**Excellent recast fit.** The author has internalized the proposition-vs-hypothesis decomposition the proposition-and-evidence-model.md doc prescribes, and explicit `commits_to:` preserves the right edge structure.

### `t045-t046-mechanism-and-env-shift` — discriminating mechanism question

Body opens with question-driven framing for q20 ("why does random distance match real 3d") and q21 ("environment-shift verification") — exactly the recast spirit of using questions to organize discriminating tests. The pre-reg is checking whether t037's effect is environment-shift-driven vs. mechanism-driven.

The `interpretation:phase1-ablation-n29-extension` ref provides upstream-evidence context, but the formal commitments are the Q20/Q21 questions plus the two propositions named by the decision surface. This is a good example of why `commits_to:` should be explicit: interpretations can be upstream dependency context without becoming the thing this pre-reg commits to answer.

**Clean fit.**

### `experimental-distance-pilot` — minimal pre-reg, ok shape

Only h01 in `related:` (no propositions or questions). Body is short ("Experimental-Distance Pilot Training (RNA SS)"). It now commits directly to h01.

**Adequate fit, simpler shape than the others.**

---

## Plan-level issues surfaced

### Issue 1 (recurrent): `related:` conflation

All 4 pre-regs have `task:` refs alongside epistemic refs in `related:`. Same pattern as every other project. Resolved by the recast plan's sub-prompt addition.

### Issue 2 (project-side): non-canonical frontmatter

- 4th distinct date-field variant: `date:` (vs canonical `committed:`).
- New `status:` variants: `registered`, `revised`.
- Missing `id:`, `type:` fields.

Same broad pattern as seq-feats — pre-canonical pre-regs. Migration regularized these fields in the project branch.

### No new structural plan-level issues from 3d-attention-bias.

This is the third project in a row (after cbioportal and evolution) that surfaces no new structural issues. The substantive plan-level findings have all been surfaced.

---

## Migration status

### For 3d-attention-bias

1. Frontmatter regularized for all 4 pre-regs.
2. Explicit `commits_to:` added for all 4 pre-regs.
3. Graph rebuild and validation passed.
4. Direct commitment edges match `commits_to:`; parent H01 edges on the extension pre-regs are depth-2 transitive edges through the committed propositions.
5. `question:q16-is-r90-ratio-overshoot-a-sequence-length-confound` has no direct edge from `pre-registration:phase1-ablation`, confirming it remains context-only.

### For the recast plan (`docs/plans/2026-05-04-prereg-recast-draft.md`)

1. **Confirms recurrent issues** (Issue 1: `related:` conflation; Issue 2: status-vocabulary drift).
2. **No new structural changes.**
3. **Possible plan-prose addition**: 3d-attention-bias's proposition-decomposed pattern (h01 + 3 propositions, with each proposition being the truth-apt sub-claim) is a useful exemplar of "what a well-shaped epistemic-arm pre-reg looks like." Could be cited in `commands/pre-register.md` § "Section 0" prompt as an example.

---

## Remaining questions

No blocking project-owner questions remain for this migration. The only retained non-canonical field is the project-specific `supersedes:` string on `experimental-distance-pilot`.

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
