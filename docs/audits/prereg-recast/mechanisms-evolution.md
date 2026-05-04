# Pre-registration recast audit — mechanisms/evolution

**Audit date:** 2026-05-04
**Project root:** `~/d/cancer/mechanisms/evolution` (= `/mnt/ssd/Dropbox/cancer/mechanisms/evolution`)
**Scope:** all 2 pre-regs under `doc/meta/pre-registration-*.md`
**Recast spec:** `docs/plans/2026-05-04-prereg-recast-draft.md` (revision 2)

---

## Summary

mechanisms/evolution has 2 pre-regs, both freshly authored (May 2026) and **the cleanest, most recast-compatible pre-regs I've seen across all six projects**. Both have:

- Fully canonical frontmatter (`id`, `type`, `committed`, `status: committed` from canonical vocabulary).
- Hypothesis ref (h003) AND multiple question refs (q013, q070, q071, q075) in `related:`.
- Explicit narrow-scope verdict language separating "the t002 reading of h003" from "h003 itself" — the recast philosophy operating cleanly without explicit awareness of the recast.
- Documented bias-audit-driven amendment trail.

Both pre-regs surface a small set of **new unregistered kinds** in `related:` (`bias-audit:`, `analysis-plan:`, `meta:`). And both use a **third variant of the amendment-tracking field** (`amended:`, distinct from natural-systems' `amendments:` and mm's `amendment_history:`).

**Recommendation for mechanisms/evolution:** No file edits required. The pre-regs are well-formed and recast-ready. The new unregistered kinds are out of t012 scope but worth flagging.

---

## Inventory

| File | `committed:` | Status | Hypothesis | Questions | Other epistemic | Custom fields |
|---|---|---|---|---|---|---|
| `pre-registration-h003-t002-ecdna-selection.md` | 2026-05-03 | committed | h003 | 4 (q013, q070, q071, q075) | — | `amended:` |
| `pre-registration-t007-tcga-ecdna-cox.md` | 2026-05-03 | committed | h003 | 4 (q013, q070, q071, q075) | discussion | `amended:`, plus new ref kinds: `analysis-plan:`, `meta:`, `bias-audit:` |

### Classification breakdown

- **Pure-epistemic:** 0
- **Pure-operational:** 0
- **Mixed:** 2 (both)

### Unregistered ref kinds in `related:`

mechanisms/evolution introduces three new unregistered kinds to track:

- **`bias-audit:`** — `bias-audit:h003-t002-ecdna-selection`. Used in both pre-regs. Different from cbioportal/protein-landscape's `task:bias-audit-...` shape (which uses `task:` prefix). evolution treats `bias-audit:` as its own kind prefix.
- **`analysis-plan:`** — `analysis-plan:t007-tcga-ecdna-cox-shape-vs-mean`. Used in t007. May relate to `science:plan-analysis` skill output, but not a registered kind.
- **`meta:`** — `meta:g1-reconnaissance-t007`. Used in t007. Project-specific.

All three will be silently skipped during source loading under the recast (same as mm's `decision:` and `latent:`). **Same resolution as mm's Issue 3 — document in recast plan, recommend project-side regularization.**

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

### Issue 1 (recurrent, growing): unregistered kinds in `related:`

mm's audit surfaced `decision:` and `latent:`. mechanisms/evolution adds **`bias-audit:`, `analysis-plan:`, `meta:`**. All silently skipped during source loading.

Cumulative list of unregistered kinds across cancer cluster (so far):
- `decision:` (mm)
- `latent:` (mm)
- `bias-audit:` (evolution)
- `analysis-plan:` (evolution)
- `meta:` (evolution)
- (`rq:` was seen in mm pre-canonical pre-reg-decomposition — likely "research question" syntax)

**This is a pattern worth flagging in the recast plan.** Each project introduces project-specific kinds that exist in `related:` refs but aren't registered in `_CORE_KIND_CLASSES`. The recast doesn't need to register all of them, but it should:

1. Document that unregistered kinds in `related:` are silently dropped during source loading.
2. Recommend a `science-tool` health-check command that lists unregistered ref kinds across all `related:` fields in a project — useful for projects regularizing their kind taxonomy.
3. Note that the recast's auto-derivation rule's "unknown kinds → no `bears_on`" behavior is correct (silent-skip is the right semantics for unrecognized refs), but project-side regularization is needed for full graph coverage.

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

1. **No file edits required for the recast itself.** Both pre-regs are well-formed and recast-ready.
2. **Pre-existing convention drift** (out of t012 scope):
   - `amended:` field shape — canonical alternative is `amendments:` list.
   - `bias-audit:`, `analysis-plan:`, `meta:` ref shapes — consider whether these are meant to be project-specific kind extensions (in which case they could be registered via the `register_extension_kind` API) or convention drift to be regularized to canonical kinds.
3. **No content changes recommended.** The verdict-language discipline in both pre-regs is exemplary; would not encourage edits.

### For the recast plan (`docs/plans/2026-05-04-prereg-recast-draft.md`)

1. **Document silent-skip behavior for unregistered kinds in `related:`.** Add a paragraph to the recast plan's § "Code prerequisites" (or its successor section) explaining that unregistered kinds in `related:` are silently dropped during source loading — this is correct semantics, not a bug, and project-side regularization (via `register_extension_kind` or by adopting canonical kinds) is the resolution path.

2. **Confirms the pattern from mm Issue 3.** No structural change.

3. **No new structural issues** from evolution. Both pre-regs validate the recast's intent.

---

## Open questions for project owner

1. The `amended:` field (vs canonical `amendments:`) — intentional simplification or convention drift to regularize?
2. The `bias-audit:`, `analysis-plan:`, `meta:` ref kinds — meant to be registered as project-specific extensions, or aliases for canonical kinds (e.g., `bias-audit:<slug>` could be a `task:bias-audit-<slug>` shape)?
3. Are there project-specific tools that consume these ref kinds today, or are they purely human-readable annotations?

---

## Cross-project pattern (after natural-systems + protein-landscape + seq-feats + cancer-meta + multiple-myeloma + cbioportal + mechanisms/evolution)

Cumulative findings across 7 projects, **56 pre-regs reviewed** (14 + 3 + 5 + 0 + 30 + 2 + 2):

- **`related:` conflation:** universal (6/6 pre-reg-using projects).
- **Hypothesis-in-body-only pattern:** confirmed in 5 pre-regs across 2 projects (mm 4, cbioportal 1).
- **Inquiry-targeting (no hypothesis):** confirmed in mm only (3 pre-regs; t494, t498, t500). Will be addressed by reclassifying `inquiry` to `EPISTEMIC` per agreed plan.
- **Falsification-clause language:** benign as anti-bias procedural rigor.
- **Unregistered kinds in `related:`:** growing list — `decision:`, `latent:`, `bias-audit:`, `analysis-plan:`, `meta:`, `rq:`. All silently skipped. Need a documented health-check pattern.
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

After mechanisms/evolution sign-off, proceed to:
- 3d-attention-bias (4 pre-regs, Science cluster — last pre-reg-using project)
- cats (0 pre-regs, brief completeness note)
