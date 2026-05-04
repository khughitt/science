# Pre-registration recast audit — data-sources/cbioportal

**Audit date:** 2026-05-04
**Project root:** `~/d/cancer/data-sources/cbioportal` (= `/mnt/ssd/Dropbox/cancer/data-sources/cbioportal`)
**Scope:** all 2 pre-regs under `doc/meta/pre-registration-*.md`
**Recast spec:** `docs/plans/2026-05-04-prereg-recast-draft.md` (revision 2)

---

## Summary

cbioportal has 2 pre-regs, both from mid-late April 2026. Both have **mostly-canonical frontmatter** but use `status: active` (non-canonical vocabulary) and a doubled-prefix `id:` field (`pre-registration:pre-registration-<slug>`). Beyond the convention drift, the two pre-regs are very different in shape:

1. **`t077-glmm-logit-pooling`** is the cbioportal version of the **hypothesis-in-body-only pattern** surfaced by multiple-myeloma's audit. Its `related:` field has zero epistemic targets — only tasks (operational), topic (reference), search (operational), and 7 papers (operational). The body, however, opens with a clear "H1 (primary, confirmatory)" claim that's defined in `specs/research-question.md` (a `spec:` entity, OPERATIONAL) — **not** as a formal `hypothesis:hN-...` entity, even though cbioportal does have h01-h06 formal hypothesis entities elsewhere. So under the recast, t077 produces **zero `bears_on` edges** despite testing a real epistemic claim.

2. **`t126-sbs1-lrr-bias-test`** is a more typical mixed pre-reg, with `question:q009-...`, a discussion, and 3 interpretations in `related:` providing epistemic linkage. The bias test is methodological (testing whether SBS1 LRR is a contamination flag) but with clear epistemic targets in `related:`.

**Recommendation for cbioportal:** No file edits required for the recast itself. The audit reinforces multiple-myeloma's Issue 1 (hypothesis-in-body-only). Convention-drift items (`status: active`, doubled `id:` prefix, `task:bias-audit-...` shape) are pre-existing data-quality issues out of t012 scope.

---

## Inventory

| File | `committed:` | Status (raw) | Hypothesis refs in `related:`? | Body has inline hypothesis? | Class |
|---|---|---|---|---|---|
| `pre-registration-t077-glmm-logit-pooling.md` | 2026-04-14 | active | **No** | Yes — H1 from `specs/research-question.md` (a `spec:` entity, not a `hypothesis:` entity) | mixed (operational tasks + papers; no epistemic in `related:`) |
| `pre-registration-t126-sbs1-lrr-bias-test.md` | 2026-04-24 | active | No (cbioportal's h01-h06 entities aren't referenced) | Body discusses SBS1/SBS5 mechanisms in question:q009 frame | mixed (epistemic via question + discussion + interpretations) |

### Frontmatter anomalies

Both pre-regs have:
- `id:` with **doubled prefix** — `pre-registration:pre-registration-t077-glmm-logit-pooling` instead of `pre-registration:t077-glmm-logit-pooling`. This is a frontmatter authoring drift; the canonical shape per `2026-04-25-pre-registration-canonical-type.md` is `pre-registration:<slug>`. Pre-existing data-quality issue.
- `status: active` — non-canonical (canonical: `draft` / `committed` / `complete`).

Both have full `committed:` dates and `type:` fields, so the recast's auto-derivation rule will reach them — the doubled prefix in `id:` is cosmetic for the recast (it's still a valid pre-registration identifier; just an unusual slug).

`t077` also references `task:bias-audit-cross-study-aggregation-pipeline` — same `task:bias-audit-...` non-canonical shape seen in protein-landscape's t098. Cross-project convention drift.

### Classification breakdown

- **Pure-epistemic:** 0
- **Pure-operational (from `related:` only):** 1 (`t077`) — but body language is epistemic-arm (real H1 hypothesis claim)
- **Mixed:** 1 (`t126`)

---

## Author-intent vs. recast interpretation

### `t077-glmm-logit-pooling` — extreme hypothesis-in-body-only case

This is the cleanest example I've seen of the pattern multiple-myeloma's audit surfaced as Issue 1. The body opens:

> ## Hypotheses Under Test
>
> - **H1** (primary, confirmatory — from `specs/research-question.md`):
>   *Aggregating somatic mutation evidence across heterogeneous cBioPortal studies reveals gene-cancer associations that are more robust and more generalizable than any single study, and exposes clusters of cancer types with shared mutational structure.*
> - **G1** (methodological gate, confirmatory): GLMM-logit random-intercept meta-analysis converges on the majority of (gene, cancer) cells in our cohort, yielding stable between-study variance estimates that credibly expose panel- and cohort-effect heterogeneity. G1 is a prerequisite gate — if G1 fails, H1's evidence is not evaluable and the method has to be revised before re-registering.

H1 is a real epistemic claim about cross-study meta-analysis recovering robust gene-cancer associations. **G1 is an operational gate** — methodological convergence is the gating condition; if G1 fails, the H1 evidence is not evaluable.

Under the recast as currently drafted:
- `related:` has 0 epistemic targets. The auto-derivation rule fires no `bears_on` edges.
- The body's H1 references `specs/research-question.md` — a `spec:` entity, OPERATIONAL. Even if we somehow extracted that ref, it wouldn't trigger `bears_on`.
- **The pre-reg's epistemic commitment is invisible to the materialized graph.**

This compounds with multiple-myeloma's Issue 1 (pre-canonical pre-regs reference hypotheses inline-only): cbioportal also has formal hypothesis entities (`specs/hypotheses/h01-...md` through `h06-...md`), but **none of them are the H1 t077 references**. The cbioportal team uses "H1" in the research-question doc to mean the project's central hypothesis at a different level than h01-h06. There's no formal hypothesis entity for t077 to point at, even if it wanted to.

**Resolution:** same as mm Issue 1 — project-side cleanup (promote `specs/research-question.md`'s H1 to a formal hypothesis entity, or accept the gap for this style of pre-reg). The recast adds prose to `interpret-results` § 4d for the transition period.

The G1 / H1 split is also worth noting structurally: the pre-reg explicitly distinguishes operational (G1, methodological convergence) from epistemic (H1, the meta-analysis claim) commitments **in body language**, while collapsing them in `related:`. This is exactly what the natural-systems audit's Issue 1 (`related:` conflation) describes — the pre-reg's author has the operational/epistemic distinction in mind but the schema doesn't capture it. A sub-prompt at authoring time would help.

### `t126-sbs1-lrr-bias-test` — typical mixed shape

Body opens with the SBS1/SBS5 mechanistic question and references q009 directly:

> question:q009-sbs1-lrr-bias-as-normal-contamination-flag

Tests whether SBS1 log-rate-ratio bias can serve as a flag for normal-tissue contamination in cancer mutation data. This is a methodological test with clear epistemic linkage:
- The question (q009) is the epistemic target.
- The interpretations referenced are prior evidence (t110, t122, t123 SBS1/SBS5 work).
- The discussion ref records the t124/q009 fork decision.
- Tasks (t126, t124, t109, t110, t121) are operational.

Under the recast: `bears_on` edge from the pre-reg to `question:q009`, with depth-1 weight; question's freshness propagates downstream when the pre-reg's analysis lands. Clean fit.

---

## Plan-level issues surfaced

### Issue 1 (recurrent, strengthened): hypothesis-in-body-only

Multiple-myeloma surfaced this issue with 4 pre-canonical pre-regs. cbioportal extends it to a different shape: **a fully-canonical-frontmatter pre-reg whose body references a hypothesis that exists only in a `spec:` entity, not as a formal `hypothesis:` entity.**

This isn't a frontmatter migration issue (cbioportal already has canonical-ish frontmatter); it's a **deeper data-modeling gap** — the project's central research-question hypothesis isn't promoted to a formal `hypothesis:` entity, so there's nothing for `related:` to point at even if the author wanted to.

**Resolution:** project-side promotion of research-question H1 to a formal hypothesis entity (out of t012 scope). The recast plan's prose note covers the transition.

This finding **does not change the recast plan's structure**; it strengthens the existing Issue 1 from mm and reinforces that the project-side cleanup work is real and meaningful for the recast's full benefit.

### Issue 2 (recurrent): `related:` conflation

`t126` has tasks + question + discussion + interpretations in `related:`. Same pattern. Resolved by the recast plan's sub-prompt addition.

### Issue 3 (recurrent, minor): convention drift

- `status: active` — non-canonical vocabulary, also seen in seq-feats and mm pre-canonical pre-regs.
- Doubled `id:` prefix (`pre-registration:pre-registration-<slug>`) — cbioportal-specific.
- `task:bias-audit-...` shape — also seen in protein-landscape's t098.

All pre-existing; out of t012 scope.

---

## Recommended actions

### For cbioportal

1. **No file edits required for the recast itself.**
2. **Pre-existing convention drift** (out of t012 scope):
   - Doubled `id:` prefix on both pre-regs — fix to canonical `pre-registration:<slug>` shape.
   - `status: active` — migrate to canonical vocabulary.
   - `task:bias-audit-...` ref shape on t077 — regularize.
3. **Consider:** promote `specs/research-question.md`'s H1 to a formal `hypothesis:` entity so future pre-regs (and t077 itself, if revised) can point at it via `related:`. This is a deeper data-modeling decision not blocking the recast.

### For the recast plan (`docs/plans/2026-05-04-prereg-recast-draft.md`)

1. **Strengthens mm Issue 1.** No new structural issue from cbioportal; the hypothesis-in-body-only pattern extends to fully-canonical-frontmatter pre-regs whose body references `spec:`-level hypotheses.
2. **Confirms recurrent issues** (Issue 2: `related:` conflation; Issue 3: status-vocabulary drift; cross-project `task:bias-audit-...` drift).

---

## Open questions for project owner

1. For `t077-glmm-logit-pooling`: is the H1 in body prose intended to refer to the project's research-question-level hypothesis, or to one of the formal `hypothesis:h01-h06` entities? (If the latter, would adding the appropriate ref to `related:` be acceptable as part of a regularization pass?)
2. The doubled `id:` prefix (`pre-registration:pre-registration-<slug>`) on both pre-regs — is this an intentional namespacing choice or convention drift to be regularized?
3. Does the project have any tooling that loads `topic:` or `search:` refs from pre-reg `related:`? (Both are non-bearing under the recast; silent-skip is fine if no tooling depends on them.)

---

## Cross-project pattern (after natural-systems + protein-landscape + seq-feats + cancer-meta + multiple-myeloma + cbioportal)

Cumulative findings across 6 projects, **54 pre-regs reviewed** (14 + 3 + 5 + 0 + 30 + 2):

- **`related:` conflation:** universal (5/5 pre-reg-using projects).
- **Hypothesis-in-body-only pattern:** confirmed in 5 pre-regs across 2 projects (4 mm pre-canonical + cbioportal t077).
- **Falsification-clause language:** benign as anti-bias procedural rigor.
- **Frontmatter regularity:** wildly variable. Status-vocabulary drift (`status: active`) is the most common form across multiple projects.
- **Pure-operational pre-regs (from `related:` only):** 1 (cbioportal t077) — but body is epistemic-arm. Still no truly pure-operational pre-reg in the corpus.
- **`task:bias-audit-...` ref shape:** confirmed in 2 projects (protein-landscape, cbioportal); a small cross-project convention drift.

The recast's plan structure (after this audit) requires **one structural decision** beyond what's already in revision 2: reclassify `inquiry` as `EPISTEMIC` per multiple-myeloma's Issue 2. Everything else surfaced is prose-level skill refinements or out-of-scope project cleanup.

---

## What's next

After cbioportal sign-off, proceed to:
- mechanisms/evolution (2 pre-regs)
- 3d-attention-bias (4 pre-regs, Science cluster)
- cats (0 pre-regs, brief completeness note)
