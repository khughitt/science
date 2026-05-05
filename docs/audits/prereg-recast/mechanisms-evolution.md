# Pre-registration recast audit — mechanisms/evolution

**Audit date:** 2026-05-04
**Project root:** `~/d/cancer/mechanisms/evolution` (= `/mnt/ssd/Dropbox/cancer/mechanisms/evolution`)
**Scope:** all 2 pre-regs under `doc/meta/pre-registration-*.md`
**Recast spec:** `docs/plans/2026-05-04-prereg-recast-draft.md` (revision 2)
**Migration branch:** `migration/prereg-recast-mechanisms-evolution`

---

## Summary

mechanisms/evolution has 2 pre-regs, both freshly authored (May 2026) and among the cleanest, most recast-compatible pre-regs in the audit set. Both have:

- Fully canonical frontmatter (`id`, `type`, `committed`, `status: committed` from canonical vocabulary).
- Hypothesis ref (h003) AND multiple question refs (q013, q070, q071, q075) in `related:`.
- Explicit narrow-scope verdict language separating "the t002 reading of h003" from "h003 itself" — the recast philosophy operating cleanly without explicit awareness of the recast.
- Documented bias-audit-driven amendment trail.

Migration added explicit `commits_to:` lists to distinguish formal epistemic commitments from navigation/context refs. This is especially important here because the pre-regs deliberately mention broader h003/q013/q070/q071/q075 context while locking narrower verdict-bearing estimands.

Both pre-regs use a third variant of the amendment-tracking field (`amended:`, distinct from natural-systems' `amendments:` and mm's `amendment_history:`). This was left unchanged because it is project-side amendment metadata, not part of the prereg commitment-target migration.

**Recommendation for mechanisms/evolution:** Merge the project-side migration.

---

## Inventory

| File | `committed:` | Status | Hypothesis | Questions | Other epistemic | Custom fields |
|---|---|---|---|---|---|---|
| `pre-registration-h003-t002-ecdna-selection.md` | 2026-05-03 | committed | h003 | 4 (q013, q070, q071, q075) | — | `amended:` |
| `pre-registration-t007-tcga-ecdna-cox.md` | 2026-05-03 | committed | h003 | 4 (q013, q070, q071, q075) | discussion | `amended:`, plus new ref kinds: `analysis-plan:`, `meta:`, `bias-audit:` |

### Migration decisions

| File | Added `commits_to:` | Rationale |
|---|---|---|
| `pre-registration-h003-t002-ecdna-selection.md` | `hypothesis:h003-ecdna-segregation-variation-source`; `question:071-ecdna-copynumber-distribution-signature` | The body names h003 as the primary target, but only the t002 reading. The Bafna CN-distribution model is the direct question-level surface. q013, q070, and q075 remain broader context or explicitly out of scope. |
| `pre-registration-t007-tcga-ecdna-cox.md` | `hypothesis:h003-ecdna-segregation-variation-source`; `question:070-ecdna-survival-penalty-cn-vs-segregation`; `question:075-ecdna-regime-vs-mode-adjudication` | The body states that Fit A is the q070 estimand and Fit B is the q075 estimand, and explicitly says the Fit A coefficient bears more directly on h003. |

Notes:

- No `id:`, `type:`, `committed:`, or `status:` changes were needed.
- `amended:` remains as-is. Canonicalizing amendment history would require a separate project-side schema migration.
- `bias-audit:`, `analysis-plan:`, and `meta:` are registered as project-local operational kinds in `knowledge/sources/local/manifest.yaml`, so they remain valid navigation/provenance context but are not commitment targets.
- Removed the stale project-local `pre-registration` kind from `knowledge/sources/local/manifest.yaml`; `pre-registration` is now a Science core kind, and extension manifests must not shadow core kinds.

### Classification breakdown

- **Pure-epistemic:** 0
- **Pure-operational:** 0
- **Mixed:** 2 (both)

### Project-local ref kinds in `related:`

mechanisms/evolution uses three project-local operational kinds:

- **`bias-audit:`** — `bias-audit:h003-t002-ecdna-selection`. Used in both pre-regs. Different from cbioportal/protein-landscape's `task:bias-audit-...` shape (which uses `task:` prefix). evolution treats `bias-audit:` as its own kind prefix.
- **`analysis-plan:`** — `analysis-plan:t007-tcga-ecdna-cox-shape-vs-mean`. Used in t007. May relate to `science:plan-analysis` skill output.
- **`meta:`** — `meta:g1-reconnaissance-t007`. Used in t007. Project-specific.

All three are registered in `knowledge/sources/local/manifest.yaml` as operational kinds. They should not become `bears_on` targets, but they are valid context refs. The broader cross-project silent-skip finding still applies to projects that use unregistered kinds without a local manifest entry.

---

## Author-intent vs. recast interpretation

### `pre-registration-h003-t002-ecdna-selection` — exemplary recast-compatible shape

The body opens with explicit narrow-scope language:

> This pre-registration covers a **single, narrow test**: whether the EGFR-amplifying ecDNA copy-number distribution observed in GBM0510 (Lee2026 scWGS) is better explained by the Bafna2022 binomial-segregation+selection model than by neutral binomial-segregation alone.
>
> - **Primary target:** `hypothesis:h003-ecdna-segregation-variation-source` — but only the *t002 reading* of h003. A supportive result here cannot, on its own, move h003 to `partially-supported`; that promotion requires independent non-Lee2026 replication per h003's locally-stated promotion criteria.

This is the recast spirit verbatim — a single test result feeds weighted evidence into h003 without being a verdict on h003 as a whole. The author has the operational/epistemic distinction in their head explicitly.

The 4-tier verdict language is also exemplary:
- **Supports t002 reading of h003** — strong-weight `cito:supports` evidence
- **Selection present, mechanism unidentified** — partial support; intermediate weight
- **Weakens t002 reading** — weak `cito:disputes` evidence
- **Does not support t002 reading** — strong-weight `cito:disputes` evidence

And the explicit non-killswitch language:
> A "does not support" outcome falsifies the t002 selection reading on this cohort. It does not by itself refute h003, because the broader hypothesis rests on a multi-layered evidence base (segregation, chromatin, longitudinal discordance, pan-cancer prevalence) that this analysis does not test.

Identical to the recast's stance. **No conflict; complete alignment.**

The amendment trail is also notable: the pre-reg was amended on the same day it was first committed, in response to a bias audit. The amendment substantively expanded the model space (added M2 Wright-Fisher continuous-trait alternative + M2N null) and added the "selection present, mechanism unidentified" verdict tier. This is a real epistemic refinement happening through the canonical amendment workflow.

### `pre-registration-t007-tcga-ecdna-cox` — same shape, broader test

t007 extends to the TCGA cohort with similar verdict-language discipline. Same recast-compatible shape. No new findings beyond what h003-t002 surfaced.

---

## Plan-level issues surfaced

### Issue 1 (recurrent, growing): project-local kinds in `related:`

mm's audit surfaced `decision:` and `latent:`. mechanisms/evolution adds **`bias-audit:`, `analysis-plan:`, `meta:`**, but unlike the mm cases, these are registered in the project's local manifest as operational kinds.

Cumulative list of non-core or unregistered kinds across cancer cluster (so far):
- `decision:` (mm)
- `latent:` (mm)
- `bias-audit:` (evolution; registered project-local operational kind)
- `analysis-plan:` (evolution; registered project-local operational kind)
- `meta:` (evolution; registered project-local operational kind)
- (`rq:` was seen in mm pre-canonical pre-reg-decomposition — likely "research question" syntax)

**This is a pattern worth flagging in the recast plan.** Each project may introduce project-specific kinds that exist in `related:` refs but are not core kinds. The recast doesn't need to register all of them, but it should:

1. Document that unregistered kinds in `related:` are silently dropped during source loading.
2. Recommend a `science-tool` health-check command that lists unregistered ref kinds across all `related:` fields in a project — useful for projects regularizing their kind taxonomy.
3. Note that operational extension kinds can be registered via a local manifest, as mechanisms/evolution does here.
4. Note that operational kinds should not become `bears_on` targets merely because they are valid refs.

### Issue 2 (recurrent): variant amendment-tracking fields

Three variants seen so far across projects:
- **`amendments:`** (canonical, used in natural-systems h07-beta-arbitration)
- **`amendment_history:`** (mm t468)
- **`amended:`** (evolution h003-t002 and t007)

All three serve the same purpose; the canonical schema (`amendments:`) is plural-list-of-objects. mm's `amendment_history:` is the same shape. evolution's `amended:` looks like a single-date scalar in the frontmatter (`amended: "2026-05-03"`) but the body has structured amendment prose tagged with `[Amended 2026-05-03]` markers — so the frontmatter scalar is a flag, not a list.

This is convention drift across projects. Out of t012 scope but worth flagging for `[t009]` declarative-migrations work.

---

## Recommended actions

### For mechanisms/evolution

1. Explicit `commits_to:` added for both pre-regs.
2. Stale local `pre-registration` manifest registration removed because it shadows the core kind.
3. Graph rebuild and validation passed.
4. Direct commitment edges match `commits_to:`:
   - `pre-registration:h003-t002-ecdna-selection` -> h003 and q071
   - `pre-registration:t007-tcga-ecdna-cox` -> h003, q070, and q075
5. Context-only question refs did not produce direct prereg edges:
   - t002 has no direct q013/q070/q075 edges
   - t007 has no direct q013/q071 edges
6. No content changes recommended. The verdict-language discipline in both pre-regs is exemplary.
7. Remaining convention drift is outside this migration:
   - `amended:` field shape — canonical alternative is `amendments:` list.

### For the recast plan (`docs/plans/2026-05-04-prereg-recast-draft.md`)

1. **Document silent-skip behavior for unregistered kinds in `related:`.** Add a paragraph to the recast plan's § "Code prerequisites" (or its successor section) explaining that unregistered kinds in `related:` are silently dropped during source loading — this is correct semantics, not a bug, and project-side regularization (via local manifest extension kinds or by adopting canonical kinds) is the resolution path.

2. **Confirms the pattern from mm Issue 3.** No structural change.

3. **No new structural issues** from evolution. Both pre-regs validate the recast's intent.

---

## Remaining questions

No blocking project-owner questions remain for this migration. A later schema cleanup can decide whether to convert `amended:` to canonical `amendments:`.

---

## Cross-project pattern (after all audited projects)

Cumulative findings across 9 projects, **60 pre-regs reviewed** (14 + 3 + 5 + 0 + 30 + 2 + 2 + 4 + 0):

- **`related:` conflation:** universal across pre-reg-using projects.
- **Hypothesis-in-body-only pattern:** confirmed in 5 pre-regs across 2 projects (mm 4, cbioportal 1).
- **Inquiry-targeting (no hypothesis):** confirmed in mm only (3 pre-regs; t494, t498, t500). Will be addressed by reclassifying `inquiry` to `EPISTEMIC` per agreed plan.
- **Falsification-clause language:** benign as anti-bias procedural rigor.
- **Non-core / unregistered kinds in `related:`:** `decision:`, `latent:`, `bias-audit:`, `analysis-plan:`, `meta:`, `rq:`. mechanisms/evolution registers its custom kinds locally as operational; unregistered kinds elsewhere need documented silent-skip semantics and a health-check pattern.
- **Variant amendment-tracking fields:** `amendments:` (canonical, ns), `amendment_history:` (mm), `amended:` (evolution). Convention drift across projects.
- **Status-vocabulary drift:** `status: active` (non-canonical) seen in seq-feats (5/5), mm pre-canonical (4/4), cbioportal (2/2). Canonical: `draft` / `committed` / `complete`.
- **Pure-operational pre-regs (from `related:` only):** still 0 truly pure (cbioportal's t077 looks like one but its body is epistemic-arm).
- **Best-of-class recast-compatible pre-regs:** mechanisms/evolution h003-t002 and t007 — explicit narrow-scope verdict language, 4-tier verdict structure, anti-killswitch framing throughout.

The recast plan after this audit needs:
- **Reclassify `inquiry` to EPISTEMIC** (per agreed mm Issue 2 resolution).
- **Document unregistered-kinds silent-skip** (per cumulative pattern).
- **Add prose for hypothesis-in-body-only pre-regs** (per mm Issue 1, strengthened by cbioportal).
- **No further structural changes.**

---

## What's next

After this migration is merged, continue with any remaining project-side migrations or the consolidated recast-plan revision.
