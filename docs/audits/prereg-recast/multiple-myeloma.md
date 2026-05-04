# Pre-registration recast audit — multiple-myeloma

**Audit date:** 2026-05-04
**Project root:** `~/d/cancer/cancer-types/multiple-myeloma` (= `/mnt/ssd/Dropbox/cancer/cancer-types/multiple-myeloma`)
**Scope:** all 30 pre-regs across two placements
**Recast spec:** `docs/plans/2026-05-04-prereg-recast-draft.md` (revision 3; code prerequisites merged 2026-05-04)

---

## Summary

multiple-myeloma is the largest pre-reg-using project across the entire surveyed set: **30 pre-regs**, more than the 4 Science cluster projects combined (26). The audit found:

1. **Two-generation split.** 4 older pre-regs at `doc/meta/pre-registration-*.md` (March / early-April 2026) use **non-canonical frontmatter and inline-body hypothesis labels** (H1/H2/H3/H4/H5 in prose, no `hypothesis:hN-...` refs in `related:`). 26 newer pre-regs at `doc/pre-registrations/<date>-<slug>.md` (mid-April onward) use **fully canonical frontmatter** with proper entity-form `hypothesis:` refs. The migration appears to coincide with the project adopting `2026-04-25-pre-registration-canonical-type.md`.

2. **The 4 older pre-regs surface a substantive migration issue:** they target hypotheses *in their bodies* but not in `related:`. The recast's auto-derivation rule only sees `related:` / `commits_to:`, so these older files need canonical frontmatter and explicit `commits_to:` scoping. The safest migration is to connect only targets that already exist as formal epistemic entities, and leave body-only H labels as prose until the project promotes or maps them deliberately.

3. **Two new unregistered kinds surfaced:** `decision:` (D1–D11, used in 7+ pre-regs' `related:`) and `latent:` (latent:state_commitment_entropy, latent:disease_severity_index, latent:hopfield_basin_energy, used in 6+ pre-regs). Both are absent from `_CORE_KIND_CLASSES`; both will be silently skipped during source loading. mm has a documented internal cleanup task for `decision:` registration (`doc/meta/2026-04-25-graph-data-cleanup.md`). The recast's Prerequisite-1 register-the-kind pattern applies cleanly to both, but only if the project decides which `EntityClass` they belong to.

4. **Custom frontmatter fields** in several newer pre-regs: `parent_pre_registration:` (t419), `amendment_history:` (t468), `drafted:` (t280), `draft:` (t412, t419), `plan:` and `plan_review:` (t204). These are project-specific extensions to the canonical pre-reg shape. The recast doesn't interact with them, but they're useful signal for downstream tooling design.

5. **Heavy chained-pre-reg pattern** confirmed at scale. At least 8 of the 30 pre-regs reference other pre-regs in `related:`. One (t419) makes the parent-child relationship explicit via `parent_pre_registration:` field.

**Recommendation for multiple-myeloma:** Apply a small project migration after the recast lands:

- canonicalize the 4 pre-canonical `doc/meta/pre-registration-*.md` files;
- add `commits_to:` to the 3 inquiry-targeting Gen-2 pre-regs so `related:` context does not over-derive `bears_on` edges;
- use `commits_to: []` for operational quality gates such as t28 where epistemic refs are context, not commitments;
- remove the stale project-local `pre-registration` extension-kind registration now that Science provides the core kind;
- defer `decision:` / `latent:` kind registration to a separate project-kind cleanup.

---

## Inventory by generation

### Generation 1: pre-canonical (4 pre-regs, `doc/meta/pre-registration-*.md`)

| File | `committed:` | Status (raw) | Hypothesis refs in `related:`? | Body has H1/H2/...? | Class |
|---|---|---|---|---|---|
| `pre-registration-decomposition.md` | (none) | active | **No** (only questions, discussions, `rq:` ref) | Yes (H1–H5 inline) | mixed (epistemic via questions only in `related:`) |
| `pre-registration-h-mgus-enrichment.md` | (none) | active | **No** (only question, discussion, interpretation) | (need to verify) | epistemic-leaning |
| `pre-registration-integration.md` | (none) | active | **No** (only question, method, discussion, pre-reg) | (need to verify) | mixed |
| `pre-registration-t28-fraction-qc.md` | (none) | active | **No** (only question, pre-reg, discussion) | (need to verify) | epistemic-leaning |

**Pre-canonical anomalies:**
- No `id:` field
- No `type:` field
- No `committed:` field
- `status: active` — non-canonical vocabulary
- Hypothesis-level structure expressed inline in the body (e.g., decomposition's H1/H2/H3/H4/H5), not as entity-form refs

### Generation 2: canonical (26 pre-regs, `doc/pre-registrations/<date>-<slug>.md`)

| File (date prefix omitted) | `committed:` | Hypothesis targets | Inquiries | Other epistemic | Custom fields |
|---|---|---|---|---|---|
| t172-scrna-per-cell-validation | 2026-04-12 | h1, h2 | — | — | — |
| t174-pc-continuum-validation | 2026-04-13 | h1, h2 | — | — | — |
| t190-depmap-crispr-sweep | 2026-04-14 | h1, h2 | inquiry:h1-prognosis | discussion | — |
| t197-gse155135-ezh2i-replication | 2026-04-14 | h1 | inquiry:h1-prognosis | 2 discussions, 2 interpretations | — |
| t202-multi-signature-null-audit | 2026-04-14 | h1 | — | question, pre-reg, interpretation, plan, discussion | `spec: null` (not `""`) |
| t203-ledergor-replication | 2026-04-16 | h1, h2 | — | question, report | — |
| t204-bulk-composition-beyond-pc-maturity | 2026-04-18 | h1, h2 | — | 2 questions, 2 propositions, 2 pre-regs, 2 interpretations, report | `plan:`, `plan_review:` |
| t214-healthy-pc-maturation-signature | 2026-04-18 | h1 | — | question, pre-reg, 2 interpretations | `plan:` |
| t199-lincs-l1000-screen | 2026-04-19 | h1 | inquiry:h1-prognosis | discussion, 3 interpretations, pre-reg, paper | — |
| t205-gse214668-ms177-replication | 2026-04-19 | h1 | inquiry:h1-prognosis | discussion, 3 interpretations, pre-reg, paper | — |
| t217-mmrf-dnds-stratified | 2026-04-19 | h6 | — | 2 questions, 4 papers | — |
| t219-mm30-hopfield-basins | 2026-04-19 | h4 | — | method, topic, 2 papers, 2 questions | — |
| t263-pcdp-proxy-correlation | 2026-04-23 | h4 | inquiry:h4-attractor-convergence | latent (unregistered kind) | — |
| t277-within-basin-variance | 2026-04-24 | h4 | inquiry:h4-attractor-convergence | 3 latents (unregistered) | — |
| t278-dwell-time-cox | 2026-04-24 | h4 | inquiry:h4-attractor-convergence | 2 latents (unregistered) | — |
| t280-bulk-vs-sc-pr-unimodality | 2026-04-24 | h4 | inquiry:h4-attractor-convergence | latent (unregistered), 4 papers | `drafted:` |
| t412-laisne-potency-metrics | 2026-04-26 | h4 | inquiry:h4-attractor-convergence | latent (unregistered), paper | `draft:` |
| t413-te-dsrna-ifn-arm | 2026-04-26 | h1 | inquiry:h1-prognosis | 2 interpretations, 2 pre-regs, 2 papers | — |
| t419-downsampled-entropy | 2026-04-26 | h4 | inquiry:h4-attractor-convergence | latent (unregistered), paper | **`parent_pre_registration:`**, `draft:` |
| t494-myc-r-direct-program-phase1 | 2026-05-02 | — (none!) | 2 inquiries | 3 interpretations, 2 decisions (unregistered) | — |
| t468-hd-ap1-construction-qa | 2026-05-03 | h2 | inquiry:h-jun-hyperdiploidy-ap1 | plan, discussion, 3 decisions (unregistered) | **`amendment_history:`** |
| t469-hd-ap1-pc-maturity | 2026-05-03 | h2 | inquiry:h-jun-hyperdiploidy-ap1 | 7 papers, plan, interpretation, 3 pre-regs | — |
| t493-treatment-confounded-convergence | 2026-05-03 | h4, h6 | — | plan, question, 4 papers, decision (unregistered) | — |
| t498-myc-r-warburg-reallocation | 2026-05-03 | — (none!) | 2 inquiries | 6 papers, interpretation, discussion, pre-reg, decision | — |
| t500-eif4a-inhibitor-sensitivity | 2026-05-04 | — (none!) | inquiry:h-myc-r-translation-vulnerability | 2 interpretations, 2 decisions | — |

**Note three Generation-2 pre-regs (t494, t498, t500) have no `hypothesis:` ref in `related:` either — they target inquiries instead.** The h-myc-r-* work is structured around inquiries that may not have promoted to formal hypotheses yet. After the recast, `inquiry` is `EPISTEMIC`, so these pre-regs can produce `bears_on` edges. They still need `commits_to:` because their `related:` lists also include interpretations and other navigation context.

### Classification breakdown

- **Pure-epistemic:** 0 (all 30 are mixed)
- **Pure-operational:** 0
- **Mixed:** 30

But of the 30, **9 have no hypothesis target visible to the recast** (4 pre-canonical + 3 inquiry-only Gen-2 + 2 question-only-with-no-hypothesis Gen-1 cases). Under revision 3 this is no longer a total invisibility problem: `question:` and `inquiry:` are epistemic targets. The remaining migration concern is precision — using `commits_to:` to distinguish true epistemic commitments from navigational `related:` context.

---

## Author-intent vs. recast interpretation

### `t419-downsampled-entropy` — clean amendment-style rerun

This is the cleanest example I've seen of the recast spirit operating in practice. Body opens:

> This pre-registration is an **amendment-style rerun** of t412.

And explicitly inherits sections from t412 by reference (a structured amendment that doesn't repeat the unchanged portions). The "decisive question" framing acknowledges that t412's `null` patient-level result might be **metric-form-driven** (depth confound) rather than biological — exactly the recast's stance: a null is evidence about a *formulation*, not a verdict on the underlying claim.

The pre-reg uses a custom `parent_pre_registration:` field to make the chain structural. This is exactly the kind of project-level extension t012's task description anticipated ("a pre-reg that's a follow-up to another pre-reg").

**No conflict with the recast.** If anything, mm's `parent_pre_registration:` field is a useful pattern that could be lifted into the canonical pre-reg shape (out of t012 scope, but worth noting for `[t009]` declarative-migrations work).

### `pre-registration-decomposition` (older, pre-canonical) — H1–H5 in body only

The body opens with five hypotheses (H1, H2, H3, H4, H5) labeled as "primary", "secondary", "exploratory" — clearly the pre-reg's actual epistemic targets. But none appear in `related:`; only `question:proliferation-dominance`, `question:effect-size-vs-pvalue-aggregation`, and a discussion ref do.

Under the recast:
- The auto-derivation rule fires `bears_on` to the questions (epistemic) — partial epistemic linkage.
- The H1–H5 hypotheses are body-only and invisible to the deriver. **No `bears_on` edge is emitted to whatever entity those represent** (which may be `hypothesis:h1`, `hypothesis:h2`, etc. — promoted later when the project adopted hypothesis entities, but not back-referenced in this pre-reg's frontmatter).

This is a real plan-level issue: **the recast's classification rule is blind to inline-body hypothesis structure**. Pre-canonical pre-regs are silently under-derived.

**Resolution options:**
- (a) **Project-side:** mm migrates the 4 older pre-regs to canonical shape, adding hypothesis refs to `related:`. Out of t012 scope.
- (b) **Recast-side, prose only:** `interpret-results` § 4d notes that for older pre-regs lacking hypothesis refs in `related:`, the interpreter should manually identify body-level hypothesis labels and emit `bears_on` edges by hand (or by `science-tool graph add proposition --pre-registration <ref>`).
- (c) **Recast-side, code:** add a body parser that extracts `H<N>` patterns and resolves them to hypothesis refs. **Bad idea** — too brittle and project-specific.

**Recommendation: (a) + (b).** Project does the cleanup migration on its own timeline; recast adds the prose to handle the transition period.

### `t494-myc-r-direct-program-phase1` (Gen-2, no hypothesis ref) — inquiry-targeting

Body opens with explicit references to `inquiry:h-myc-r-direct-program` and `inquiry:h-myc-r-translation-vulnerability` as the targets. No hypothesis ref in `related:` because the work is at inquiry stage — it's testing whether to promote the inquiry to a formal hypothesis.

Under revision 3 of the recast:
- `inquiry` is `EPISTEMIC`, so the auto-derivation rule can fire `bears_on` to inquiry refs.
- The pre-reg is also operationally locked (Phase 1 spec) and references decisions (D5, D11) for context.
- Without `commits_to:`, the fallback would treat all epistemic `related:` refs as commitment targets, including interpretation context. The project migration should therefore add `commits_to:` to t494/t498/t500.

**This is a different shape than the Gen-1 inline-body issue.** Gen-1's gap is "hypothesis exists in prose but isn't referenced." Gen-2-inquiry's issue is "the project hasn't promoted to formal hypothesis yet, but still needs an epistemic commitment edge." Revision 3 resolves the classification part by making `inquiry` epistemic; the project migration resolves the scoping part with `commits_to:`.

The inquiry stage matters because mm uses inquiries as **pre-hypothesis structure** — a way to organize work toward a future hypothesis without committing to one yet. Treating inquiries as REFERENCE under the recast loses the epistemic-commitment signal.

**Resolution applied:** `inquiry` was reclassified as `EPISTEMIC` in the recast implementation. For mm, t494 should commit to both `inquiry:h-myc-r-direct-program` and `inquiry:h-myc-r-translation-vulnerability`; t498 and t500 should commit only to `inquiry:h-myc-r-translation-vulnerability`.

### `t468-hd-ap1-construction-qa` — `amendment_history:` custom field

Has a dedicated `amendment_history:` field listing amendments with dates and rationale ("amendments A1/A2/B1/B2 per `doc/meta/bias-audit-t468-pre-reg.md`; committed before any chr-LOO score computation"). This is a project-specific structured-amendment field that's similar but not identical to natural-systems' `amendments:` field (h07-beta-arbitration uses `amendments:`).

**No recast issue** — both fields are body/frontmatter conventions independent of the recast's auto-derivation. But the divergent shapes (`amendments:` vs `amendment_history:`) are convention drift worth flagging. → out of t012 scope; possibly aligns with `[t009]`.

---

## Plan-level issues surfaced

### Issue 1 (substantive, new): pre-canonical pre-regs target hypotheses inline-only

The 4 older mm pre-regs at `doc/meta/pre-registration-*.md` have hypotheses in body prose (H1, H2, ...) but not in `related:`. The recast's deriver only sees `related:`, so these hypothesis-level commitments are invisible.

**Resolution:** project-side migration to canonical shape (out of t012 scope), plus a recast prose note in `interpret-results` § 4d for the transition period. **No structural change to the recast plan.**

### Issue 2 (resolved by recast revision 3): inquiry-targeting pre-regs

3 of 30 mm pre-regs (t494, t498, t500) target `inquiry:` entities but no `hypothesis:` entity. `inquiry` is now `EPISTEMIC`, so auto-derivation can fire `bears_on` to inquiry refs.

This is a real epistemic structure: mm uses inquiries as pre-hypothesis exploration. The remaining project action is explicit scoping: add `commits_to:` to t494/t498/t500 so interpretations and decisions in `related:` stay as context.

### Issue 3 (substantive, new): unregistered kinds in `related:` — `decision:`, `latent:`

mm uses these heavily (decision: in 7+ pre-regs, latent: in 6+). Both are absent from `_CORE_KIND_CLASSES`. Under the recast's Prerequisite 1, both will be silently skipped during source loading.

This is **fine for the recast** in the narrow sense (the auto-derivation rule doesn't need decision or latent classifications because they're not bears_on targets in mm's pattern). But it means:

- mm's pre-regs lose discoverability through `decision:` and `latent:` refs in any tooling that loads kinds-driven indexes.
- mm has a documented internal cleanup task for `decision:` registration (`doc/meta/2026-04-25-graph-data-cleanup.md`). The recast should not block on it but should be aware that mm is mid-migration.

**Resolution:** document in the recast plan that unregistered kinds in `related:` are silently dropped, and recommend mm regularize at its own pace. **No structural change to the recast plan.**

### Issue 4 (recurrent): `related:` conflation

Universal pattern. mm's 30 pre-regs all have task: refs in `related:` alongside hypothesis/inquiry/question refs. Same resolution as natural-systems' Issue 1.

### Issue 5 (recurrent): non-canonical frontmatter in pre-canonical pre-regs

Same as natural-systems' Issue 4 and seq-feats' Issue 2. The recast must handle missing `committed:` gracefully.

### Issue 6 (minor): custom frontmatter fields

`parent_pre_registration:`, `amendment_history:`, `drafted:`, `draft:`, `plan:`, `plan_review:` — project-specific extensions. Don't interact with the recast. Worth flagging for `[t009]` declarative-migrations work.

---

## Recommended actions

### For multiple-myeloma

1. **Pre-canonical pre-reg migration:** canonicalize the 4 older pre-regs at `doc/meta/pre-registration-*.md` and add explicit `commits_to:`. Do not invent mappings from body-only H labels to modern hypotheses unless the project owner confirms the mapping.
2. **Inquiry-targeting pre-reg migration:** add `commits_to:` to t494/t498/t500. Recommended targets: t494 → both h-myc-r inquiries; t498/t500 → `inquiry:h-myc-r-translation-vulnerability`.
3. **Operational gate scoping:** add `commits_to: []` to t28 so the `question:simpsons-paradox-purity` ref remains navigation context rather than a derived epistemic commitment.
4. **Stale local prereg kind cleanup:** remove `pre-registration` from `knowledge/sources/local/manifest.yaml` and remove stale aggregate placeholders for preregs now loaded from markdown frontmatter.
5. **`decision:` and `latent:` kind registration** (project-side, mm has a documented cleanup task): when the project decides which `EntityClass` they belong to, register them. Lean: `decision` → `REFERENCE`; `latent` → `EPISTEMIC` (latent variables are uncertain assertions about underlying constructs).

### For the recast plan (`docs/plans/2026-05-04-prereg-recast-draft.md`)

1. **Inquiry classification resolved.** Revision 3 reclassifies `inquiry` as `EPISTEMIC`.
2. **Unregistered kinds in `related:`.** Document the silent-skip behavior and recommend project-side regularization.
3. **Confirms Issue 1, 4, 5** from prior audits.
4. **Update the missing-myeloma footnote.** mm is at `~/d/cancer/cancer-types/multiple-myeloma/` with 30 pre-regs. Definitely the highest-impact downstream project.

---

## Open questions for project owner

1. For the 4 older pre-canonical pre-regs (decomposition, h-mgus-enrichment, integration, t28-fraction-qc): should any body-only H labels be promoted to formal entities or mapped onto existing hypotheses/questions?
2. Custom frontmatter fields (`parent_pre_registration:`, `amendment_history:`, `drafted:`, `plan:`, etc.) — are these intentional project-level extensions, or convention drift the project would like to regularize?
3. Does the project have any tooling that loads `decision:` or `latent:` refs from pre-reg `related:`? (If so, the silent-skip behavior under the recast may surprise.)

---

## Cross-project pattern (after natural-systems + protein-landscape + seq-feats + cancer-meta + multiple-myeloma)

Cumulative findings across 5 projects, **52 pre-regs reviewed** (14 + 3 + 5 + 0 + 30):

- **`related:` conflation:** universal in all 4 pre-reg-using projects. The recast plan needs the sub-prompt resolution.
- **Falsification-clause language:** benign when read as anti-bias procedural rigor.
- **Frontmatter regularity:** wildly variable. protein-landscape canonical (3/3); seq-feats uniformly minimal (5/5); natural-systems mixed (11 canonical, 3 minimal); mm split by generation (4 minimal, 26 canonical). Recast must handle missing `committed:` and missing canonical fields gracefully.
- **Pre-reg shapes seen:**
  - Operational with epistemic context (most common): natural-systems h07/t214/t342/etc., protein-landscape t098, seq-feats cycle1-domains/t138/t143
  - Discriminating epistemic test: protein-landscape q63/q81, seq-feats t152-bpe-nda
  - Vanilla weighted-update epistemic: rare (mm t419 closest, with parent-pre-reg amendment shape)
  - Inquiry-targeting (no hypothesis ref): mm t494/t498/t500 — **new shape, surfaced in mm only**
  - Hypothesis-in-body-only (pre-canonical): mm decomposition + 3 others — **new shape, surfaced in mm only**
- **Unregistered kinds in `related:`:** none in Science cluster; significant in mm (`decision:`, `latent:`).
- **Custom frontmatter fields:** not seen in Science cluster; 6 distinct in mm.
- **Federation-aware:** cancer/meta has 0 local pre-regs but federates 32 pre-reg identifiers from children.

mm dominates the surveyed pre-reg corpus and surfaces most of the new substantive plan-level issues. The recast plan's "vanilla weighted-update" target shape is a small minority of real-world pre-regs across all projects.

---

## What's next

After multiple-myeloma sign-off, proceed to:
- data-sources/cbioportal (2 pre-regs)
- mechanisms/evolution (2 pre-regs)
- 3d-attention-bias (4 pre-regs, Science cluster)
- cats (0 pre-regs, brief completeness note)
