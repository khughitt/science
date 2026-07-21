# Statistics Router Reconciliation — Design

**Date:** 2026-07-21
**Status:** Accepted
**Phase:** 4, slice 1 (of the phase-4 hub-conformance umbrella)
**Worktree/branch:** `.worktrees/skills-phase4` / `skills-phase4`

## Problem

`skills/statistics/SKILL.md` is the last remaining *route-and-teach hub* whose
teaching bulk is a 14-item **Principles** section. Two things are wrong with it
after the phase-3 reorg:

1. **It violates the router doctrine the corpus already adopted.**
   `skills/meta/skill-authoring.md` states the target invariant (lines 42–44,
   58): *"A document that routes and teaches is a hub; its teaching content is
   extracted into typed leaves before it is a true router. Routers contain
   navigation only; substantive methodology lives in typed leaves."* The
   sibling `skills/study-design/SKILL.md`, built in phase 3, already embodies
   this: a routing table with **no** principle prose.

2. **8 of its 14 principles teach leaves it no longer owns.** Phase 3 split the
   overloaded `statistics/` into `statistics/` (6 modeling `method-guide`
   leaves) and `study-design/` (8 `analysis-discipline` leaves). The Principles
   section was not updated: principles 1–6, 12, 14 still teach the eight
   `study-design/` leaves, which `study-design/SKILL.md` now routes to. So the
   statistics hub teaches methodology for another hub's leaves.

The current `statistics/SKILL.md` (153 lines) also carries a `When to invoke`
prose block (lines 123–143) that mixes statistics-modeling triggers with
study-design triggers (pre-registration, reviewing a pre-reg, resolving
sensitivity passes, deciding a bias correction), compounding the same overlap.

## Principle → leaf mapping (the reconciliation table)

| # | Principle (statistics/SKILL.md) | Target leaf | Owning hub | Disposition |
|---|---|---|---|---|
| 1 | Lock parameters by measurement | `study-design/replicate-count-justification.md` | study-design | **delete** (fold routing into study-design, already present) |
| 2 | Bias vs variance | `study-design/bias-vs-variance-decomposition.md` | study-design | **delete** |
| 3 | Pre-commit sensitivity arbitration | `study-design/sensitivity-arbitration.md` | study-design | **delete** |
| 4 | Power floor | `study-design/power-floor-acknowledgement.md` | study-design | **delete** |
| 5 | Pre-reg amendment vs fresh | `study-design/prereg-amendment-vs-fresh.md` | study-design | **delete** |
| 6 | Defensive instrumentation | `study-design/prereg-defensive-instrumentation.md` | study-design | **delete** |
| 7 | Model the independent unit | `statistics/survival-and-hierarchical-models.md` | statistics | **fold** into Leaves table |
| 8 | Compositional constraints | `statistics/compositional-data.md` | statistics | **fold** |
| 9 | Well-posed likelihood comparison | `statistics/likelihood-model-comparison.md` | statistics | **fold** |
| 10 | Drift before selection | `statistics/population-genetics-likelihood.md` | statistics | **fold** |
| 11 | Repeated time rows dependent | `statistics/time-series-and-longitudinal-models.md` | statistics | **fold** |
| 12 | Estimator self-report ≠ evidence | `study-design/estimator-certification.md` | study-design | **delete** |
| 13 | Bayesian gated sequence | `statistics/bayesian-workflow.md` | statistics | **fold** |
| 14 | Identification is a DAG question | `study-design/causal-identification.md` | study-design | **delete** |

Result: **6 fold** (own leaves) + **8 delete** (foreign leaves already routed
by study-design).

## Chosen approach: delete-to-conformance (Approach A)

Rewrite `statistics/SKILL.md` as a **pure router in the same section skeleton as
`study-design/SKILL.md`**. The two become sibling routers with one shared form.

Approaches considered and rejected:

- **B — move the 8 principles into `study-design/SKILL.md` as a Principles
  section.** Rejected: re-introduces methodology-in-router, the exact
  anti-pattern `study-design/SKILL.md` was built to avoid. The thesis of each
  moved principle already lives in its leaf.
- **C — trim in place to a 14-line one-liner digest.** Rejected: still
  routes-and-teaches and still teaches foreign leaves; only half-fixes the
  incoherence and leaves `statistics` off-doctrine.

### Target `statistics/SKILL.md` skeleton

Mirror `study-design/SKILL.md`:

1. **Frontmatter** — `name: statistics`, `provenance: internal`, and a
   `description` trimmed to the six modeling leaves (see *Description
   reconciliation* below).
2. Title + a one-sentence router doctrine line
   (*"A router carries no methodology; teaching content belongs in a typed
   leaf."*), consistent with `study-design/SKILL.md:9`.
3. **Routing trigger** — load when a finite-sample statistical model is being
   *designed, built, constructed, fit, compared, analyzed, or reviewed*. The
   verb set is taken from the six leaf descriptions (which say "designing",
   "building", "constructing or fitting", "analyzing", "comparing",
   "reviewing") — it must not be narrower than what the leaves promise.
4. **Scope boundary — composable axes, not mutually exclusive.** `statistics`
   owns the *model's structure, fit, and comparison*; `study-design` owns the
   *rigor wrapper* (pre-registration, replicate/power justification, estimator
   certification, sensitivity arbitration, causal identification,
   bias/variance reasoning). The two routers are composable axes: many tasks
   load **both** — e.g. pre-registering a Cox model loads `statistics`
   (`survival-and-hierarchical-models`) for the model family *and*
   `study-design` (`prereg-*`, `power-floor-acknowledgement`) for the
   commitment. The boundary states which router carries the *methodology* for
   each concern, not that a task may touch only one. This is the exact mirror
   of `study-design/SKILL.md:16–20` ("Excludes model fitting (see
   `../statistics/SKILL.md`)"), read as an ownership boundary, not an exclusion
   of composition.
5. **Leaves** — a table with `Leaf | Load when | Do not load when` for the six
   modeling leaves, matching `study-design/SKILL.md`'s three-column form. The
   `Load when` cells are drawn from the leaf **descriptions** (the public
   trigger), enriched by the folded principle; the `Do not load when` cells are
   authored as genuine negative applicability criteria (a principle carries
   methodology, not a negative criterion, so these are written, not copied).
   The accepted rows are:

   | Leaf | Load when | Do not load when |
   |---|---|---|
   | `survival-and-hierarchical-models.md` | designing or reviewing Cox / Weibull / AFT / frailty / mixed-effects / Bayesian-hierarchical / multi-dataset models, or when repeated cells / genes / samples inside a donor or study are not independent observations | no grouping, censoring, or repeated-measure structure — a single-level i.i.d. model suffices |
   | `compositional-data.md` | analyzing proportions, fractions, cell-type composition, microbiome relative abundance, clone fractions, topic mixtures, or deconvolution outputs — anything constrained to sum to one | features are unconstrained counts or continuous measurements |
   | `time-series-and-longitudinal-models.md` | designing or reviewing repeated-measure, wearable, sensor, EMA, actigraphy, symptom-diary, cross-lag, or longitudinal analyses needing explicit time origin, cadence, lag, and within-unit dependence | measurements are cross-sectional (one row per unit, no time axis) |
   | `likelihood-model-comparison.md` | comparing parametric models by likelihood — AIC / BIC / LRT, nested vs non-nested, identifiability and rare-event precision audits, bootstrap CIs, or Bayesian out-of-sample comparison (PSIS-LOO / ELPD / stacking) | fitting a single model with no competing model to rank |
   | `population-genetics-likelihood.md` | constructing or fitting Wright-Fisher / Moran / binomial-segregation+selection likelihoods and testing selection against a neutral null | no allele-frequency, segregation, or selection-vs-drift question |
   | `bayesian-workflow.md` | building, fitting, or reviewing a Bayesian / probabilistic model — priors, MCMC, convergence, posterior-predictive / calibration, prior sensitivity, Bayesian model comparison | a frequentist point estimate or test suffices and no posterior is needed |
6. **Decision / compose order** — leaves are independent; several may apply.
7. **Parent & neighbors** — parent `../INDEX.md`; neighboring router
   `../study-design/SKILL.md` (currently statistics does **not** list
   study-design as a neighbor — this closes the asymmetry, since
   `study-design/SKILL.md:43` already lists statistics).
8. **Success test** — a modeling task routes to the correct leaf with no
   methodology read from the router.
9. **Companion Skills** — retain the genuinely cross-hub companions
   (`literature`, `epistemics`, `writing`, `data-management`); these are
   navigation, not methodology.

The `When to invoke` prose block is removed; its statistics-modeling content is
absorbed by the Routing trigger + Leaves table, and its study-design content is
already covered by `study-design/SKILL.md`.

### Description reconciliation

The current `statistics` `description` is a keyword list dominated by
study-design terms. For a router those keywords misroute discovery **to**
statistics. Every keyword gets an explicit destination — no term is silently
dropped, and terms genuinely shared by both axes stay in **both** descriptions:

| Old keyword | Destination | Rationale |
|---|---|---|
| `bootstrap` | **both** | statistics (`likelihood-model-comparison`: bootstrap CIs) *and* study-design (`replicate-count-justification`: bootstrap replicate counts) |
| `MCMC` | **statistics** | belongs to `bayesian-workflow` (MCMC sampling / convergence) |
| `permutation` | **study-design** | `replicate-count-justification` (permutation-count justification) |
| `Monte Carlo` | **study-design** | `replicate-count-justification` (Monte Carlo SE / minimum-attainable-p) |
| `downsampling` | **study-design** | `replicate-count-justification` (resampling-count choice) |
| `power` | **study-design** | `power-floor-acknowledgement` |
| `bias-vs-variance` | **study-design** | `bias-vs-variance-decomposition` |
| `sensitivity arbitration` | **study-design** | `sensitivity-arbitration` |
| `defensive instrumentation` | **study-design** | `prereg-defensive-instrumentation` |
| `pre-registering` / `pre-registered` / `round-number default` | **study-design** | `prereg-*`, `replicate-count-justification` |

Resulting frontmatter edits (both are single-field `description` edits; neither
router **body** is touched beyond statistics' own rewrite):

- **`statistics` `description`** → the six modeling leaves plus the two retained
  shared terms (`MCMC`, `bootstrap`). Draft: *"Use when designing, building,
  fitting, comparing, or reviewing a finite-sample statistical model —
  survival / hierarchical / mixed-effects, compositional, time-series /
  longitudinal, likelihood model comparison (AIC/BIC/LRT, bootstrap CIs),
  population-genetics likelihood, or Bayesian workflow (priors, MCMC,
  convergence, calibration)."*
- **`study-design` `description`** → gains the migrated terms. Draft: *"Use when
  analysis rigor must be pre-committed or a numeric verdict certified /
  arbitrated — pre-registration, replicate / permutation / bootstrap /
  Monte-Carlo / downsampling count justification, power-floor acknowledgement,
  bias-vs-variance decomposition, sensitivity arbitration, defensive
  instrumentation, estimator certification, or causal identification. Routes to
  the discipline leaves."*

## Safety / honesty checks (built into the plan)

- **No anchor deep-links.** A repo grep confirms nothing links to
  `statistics/SKILL.md#principles` or `#when-to-invoke`; all inbound refs are
  file-level. Deleting the Principles / When-to-invoke sections breaks no link.
- **Thesis-survives check (certify mapping vs data).** For each of the 8
  deleted foreign principles, confirm the target `study-design/` leaf carries
  the principle's thesis *before* deleting the digest. All 8 leaves exist
  (91–425 lines). This is the classification-honesty discipline: reorganize,
  do not silently drop content.
- **Inbound file refs unchanged.** The eleven file-level inbound references to
  `statistics/SKILL.md` (from `INDEX.md`, `bio/`, `ml/`, `writing/`,
  `pipelines/`, `data-management/`, `study-design/`) all point at the file, not
  a section, and remain valid.

## Required companion edits

1. **`skills/meta/skill-authoring.md:44`** — the router invariant names the four
   remaining hubs and states "4 of 14". After this slice, statistics is a true
   router: update the count to **3 of 14** and drop `statistics/SKILL.md` from
   the hub list (leaving `data-management/SKILL.md`, `bio/transcriptomics/SKILL.md`,
   `pipelines/SKILL.md`). Note: `pipelines/SKILL.md` remains listed there and is
   a separate phase-4 slice — this design does not touch it.
2. **`skills/INDEX.md:107`** — the statistics descriptive line still reads
   "load when finite-sample quantitative interpretation is in scope", which
   keeps routing power / estimator-certification / sensitivity work to
   statistics. Narrow it to the modeling scope (e.g. "load when designing,
   fitting, or comparing a finite-sample statistical model"). Line 108
   (study-design: "load when rigor must be pre-committed or a numeric verdict
   certified/arbitrated") already matches the boundary and is left as-is. The
   machine name→path entries (INDEX.md:46, :56, and the per-leaf lines) are
   unaffected — no leaf is renamed or moved.
3. **Regenerate the codex mirror.** Any `skills/` edit (including `skills/meta/`)
   requires regenerating `codex-skills/` or
   `test_committed_codex_skills_match_fresh_generation` fails.

## Out of scope

- The other phase-4 slices (data-management extraction, transcriptomics
  extraction, mutational-signatures split, and the pipelines question) — each
  is its own spec → plan → execution cycle.
- No new leaf files are created or renamed in this slice; the six statistics
  modeling leaves and eight study-design leaves are untouched on disk.

## Validation

From `science/`:

- `uv run --frozen science skills lint --root ../skills` — PASS.
- `uv run --frozen pytest -k codex` (committed-mirror test) — PASS after regen.
- `uv run --frozen pytest` — full suite green.
- Manual: `statistics/SKILL.md` and `study-design/SKILL.md` render as two
  routers of identical section skeleton; no numbered Principles list remains in
  `statistics/SKILL.md`.
