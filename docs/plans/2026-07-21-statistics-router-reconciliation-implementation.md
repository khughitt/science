# Statistics Router Reconciliation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert `skills/statistics/SKILL.md` from a route-and-teach hub into a pure router in the same shape as `skills/study-design/SKILL.md`, reconciling the discovery surface and doctrine invariant that phase 3 left inconsistent.

**Architecture:** Rewrite the statistics SKILL.md (fold its 6 own-leaf principles into a routing table; delete its 8 principles that teach `study-design/` leaves, whose theses already live in those leaves), migrate its discovery keywords to the routers that own them, update the doctrine invariant count, and regenerate the codex mirror. No leaf file is created, renamed, or moved.

**Tech Stack:** Markdown skills corpus; `science skills lint`; the codex-skills generator (`scripts/generate_codex_skills.py`) and its committed-mirror pytest.

**Design doc:** [`2026-07-21-statistics-router-reconciliation-design.md`](2026-07-21-statistics-router-reconciliation-design.md) — the principle→leaf mapping table, the keyword→destination map, and the accepted routing rows are authoritative there and reproduced below.

## Global Constraints

- **No AI-attribution trailers/footers** on any commit (no `Co-Authored-By`, no "Generated with" line).
- **No "legacy"/"compatibility" layers; no `Unified` prefix.** Composition over inheritance; explicit over defensive; fail early.
- **Router doctrine (the target state):** the final `statistics/SKILL.md` carries navigation only — **no numbered `## Principles` list and no `## When to invoke` prose block**. It mirrors `study-design/SKILL.md`'s section skeleton *and* its style: backticked relative paths, **not** `[](…)` markdown links, throughout the body.
- **Composable axes:** `statistics` owns the model's structure/fit/comparison; `study-design` owns the rigor wrapper (pre-registration, replicate/power justification, estimator certification, sensitivity arbitration, causal identification, bias/variance). A task may load **both**; the scope boundary states ownership of *methodology*, never that a task touches only one router.
- **Keyword map is authoritative — no discovery term is silently dropped.** `MCMC` → statistics; `bootstrap` → **both** descriptions; `permutation` / `Monte Carlo` / `downsampling` → study-design; `power` / `bias-vs-variance` / `sensitivity arbitration` / `defensive instrumentation` / `pre-registering` → study-design. Verbatim `description` drafts are in the design doc's *Description reconciliation* section.
- **Certify mapping vs data:** for each of the 8 deleted principles, confirm the target `study-design/` leaf carries the thesis **before** deleting the digest (honesty discipline — reorganize, don't drop).
- **Edit `skills/INDEX.md`** (the hand-maintained source index). **Do NOT** edit `codex-skills/INDEX.md` or any `codex-skills/science-*/` file by hand — those are generated (Task 4).
- **Regenerate the codex mirror after all `skills/` edits.** The committed-mirror test is the green gate; intermediate task commits may be RED on `test_committed_codex_skills_match_fresh_generation` and that is expected (green gate is Task 4).
- **Run all `uv run` from `science/`.** Skills lint: `uv run --frozen science skills lint --root ../skills`.
- **Only four source files change** (plus the regenerated `codex-skills/` tree): `skills/statistics/SKILL.md` (full rewrite), `skills/study-design/SKILL.md` (`description` frontmatter only — body untouched), `skills/meta/skill-authoring.md` (invariant line only), `skills/INDEX.md` (statistics descriptive line only).

---

### Task 1: Rewrite `statistics/SKILL.md` as a router

**Files:**
- Modify: `skills/statistics/SKILL.md` (full rewrite)
- Read-only reference: `skills/study-design/SKILL.md` (the shape to mirror), the eight `skills/study-design/*.md` leaves (thesis-survival check)

**Interfaces:**
- Produces: a committed `statistics/SKILL.md` whose `description` frontmatter is the statistics-side of the keyword map (Task 2 reads this committed description to verify no term was dropped).

- [ ] **Step 1: Certify the 8 deleted principles' theses survive in their leaves.**

Run this and confirm every line prints a non-empty match (each foreign principle's thesis is present in its target leaf). If any is empty, STOP and report — do not delete that principle.

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/skills-phase4/skills/study-design
echo "1 replicate-count:";        rg -c -i 'precision|monte carlo|pilot|replicate'        replicate-count-justification.md
echo "2 bias-vs-variance:";       rg -c -i 'bias|variance'                                 bias-vs-variance-decomposition.md
echo "3 sensitivity:";            rg -c -i 'sensitivity|veto|caveat|override'              sensitivity-arbitration.md
echo "4 power-floor:";            rg -c -i 'power|detectable|floor'                         power-floor-acknowledgement.md
echo "5 prereg-amendment:";       rg -c -i 'amendment|inherit'                             prereg-amendment-vs-fresh.md
echo "6 defensive-instr:";        rg -c -i 'universe lock|tripwire|candidate|familywise'   prereg-defensive-instrumentation.md
echo "7 estimator-cert:";         rg -c -i 'converged|well-posed|forward-map|calibrat'     estimator-certification.md
echo "8 causal-id:";              rg -c -i 'dag|identification|m-bias|collider'             causal-identification.md
```

Expected: every count ≥ 1.

- [ ] **Step 2: Confirm no anchor deep-links into the sections being removed.**

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/skills-phase4
rg -n --no-heading -g '!**/codex-skills/**' 'statistics/SKILL\.md#' . ; echo "rc=$? (rc=1 = no matches = good)"
```

Expected: no output, `rc=1`.

- [ ] **Step 3: Overwrite `skills/statistics/SKILL.md` with the router below.**

Replace the entire file contents with exactly this (mirrors `study-design/SKILL.md`'s skeleton and backticked-path style):

```markdown
---
name: statistics
description: Use when designing, building, fitting, comparing, or reviewing a finite-sample statistical model — survival / hierarchical / mixed-effects, compositional, time-series / longitudinal, likelihood model comparison (AIC/BIC/LRT, bootstrap CIs), population-genetics likelihood, or Bayesian workflow (priors, MCMC, convergence, calibration).
provenance: internal
---

# Statistics — Model-Fitting Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when a finite-sample statistical model is being designed,
built, constructed, fit, compared, analyzed, or reviewed — distinct from the
rigor commitments and verdict certifications that route to
`../study-design/SKILL.md`.

## Scope boundary

Covers the model's structure, fit, and comparison across the six modeling
families below. Excludes the rigor wrapper — pre-registration, replicate/power
justification, estimator certification, sensitivity arbitration, causal
identification, and bias/variance reasoning (see `../study-design/SKILL.md`).
The two routers are composable axes: a task may load both — pre-registering a
Cox model loads this router for the model family and `study-design` for the
commitment.

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| `survival-and-hierarchical-models.md` | designing or reviewing Cox / Weibull / AFT / frailty / mixed-effects / Bayesian-hierarchical / multi-dataset models, or when repeated cells / genes / samples inside a donor or study are not independent observations | no grouping, censoring, or repeated-measure structure — a single-level i.i.d. model suffices |
| `compositional-data.md` | analyzing proportions, fractions, cell-type composition, microbiome relative abundance, clone fractions, topic mixtures, or deconvolution outputs — anything constrained to sum to one | features are unconstrained counts or continuous measurements |
| `time-series-and-longitudinal-models.md` | designing or reviewing repeated-measure, wearable, sensor, EMA, actigraphy, symptom-diary, cross-lag, or longitudinal analyses needing explicit time origin, cadence, lag, and within-unit dependence | measurements are cross-sectional (one row per unit, no time axis) |
| `likelihood-model-comparison.md` | comparing parametric models by likelihood — AIC / BIC / LRT, nested vs non-nested, identifiability and rare-event precision audits, bootstrap CIs, or Bayesian out-of-sample comparison (PSIS-LOO / ELPD / stacking) | fitting a single model with no competing model to rank |
| `population-genetics-likelihood.md` | constructing or fitting Wright-Fisher / Moran / binomial-segregation+selection likelihoods and testing selection against a neutral null | no allele-frequency, segregation, or selection-vs-drift question |
| `bayesian-workflow.md` | building, fitting, or reviewing a Bayesian / probabilistic model — priors, MCMC, convergence, posterior-predictive / calibration, prior sensitivity, Bayesian model comparison | a frequentist point estimate or test suffices and no posterior is needed |

## Decision / compose order

Leaves are independent; several may apply to one analysis. Choose by model
family and data structure, not by discipline.

## Parent & neighbors

- Parent index: `../INDEX.md`
- Neighboring router: `../study-design/SKILL.md`

## Success test

A modeling task routes to the correct leaf with no methodology read from this
router.

## Companion Skills

- `../study-design/SKILL.md` — the rigor-commitment and verdict-certification axis; compose with this router.
- `../literature/SKILL.md`, `../epistemics/SKILL.md` — high-level research methodology; this router is the quantitative-modeling layer beneath them.
- `../writing/SKILL.md` — reporting statistical decisions in pre-regs and interpretations.
- `../data-management/SKILL.md` — input-data conventions; some modeling decisions depend on data shape (count vs continuous, zero-inflation).
```

- [ ] **Step 4: Structural assertions — no methodology remains, links resolve.**

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/skills-phase4
# no numbered Principles list and no When-to-invoke block:
rg -n '^## Principles|^## When to invoke|^[0-9]+\. ' skills/statistics/SKILL.md ; echo "rc=$? (rc=1 = clean = good)"
# lint passes:
cd science && uv run --frozen science skills lint --root ../skills ; echo "lint rc=$?"
```

Expected: first grep prints nothing (`rc=1`); lint `rc=0`.

- [ ] **Step 5: Commit.**

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/skills-phase4
git add skills/statistics/SKILL.md
git commit -m "refactor(skills): statistics SKILL.md is now a pure router

Fold the six own-leaf principles into a Load-when/Do-not-load-when routing
table; drop the eight principles that taught study-design/ leaves (theses
verified present in those leaves). Mirrors study-design/SKILL.md's skeleton.
Codex mirror regenerated in a later task."
```

Note: `test_committed_codex_skills_match_fresh_generation` is now RED (mirror not yet regenerated) — expected; the green gate is Task 4.

---

### Task 2: Migrate discovery keywords to the owning routers

**Files:**
- Modify: `skills/study-design/SKILL.md` (`description` frontmatter line only — body untouched)
- Modify: `skills/INDEX.md` (the statistics descriptive line, currently line 107)

**Interfaces:**
- Consumes: Task 1's committed `statistics/SKILL.md` `description` (to confirm `MCMC` and `bootstrap` are retained there and the study-design-only terms are absent).

- [ ] **Step 1: Update `study-design/SKILL.md` `description` to gain the migrated terms.**

Replace the `description:` line in the frontmatter with exactly:

```
description: Use when analysis rigor must be pre-committed or a numeric verdict certified / arbitrated — pre-registration, replicate / permutation / bootstrap / Monte-Carlo / downsampling count justification, power-floor acknowledgement, bias-vs-variance decomposition, sensitivity arbitration, defensive instrumentation, estimator certification, or causal identification. Routes to the discipline leaves.
```

Leave every other line of `study-design/SKILL.md` unchanged.

- [ ] **Step 2: Narrow the `skills/INDEX.md` statistics descriptive line.**

Change the line that currently reads:

```
- [`statistics/SKILL.md`](statistics/SKILL.md) - load when finite-sample quantitative interpretation is in scope.
```

to:

```
- [`statistics/SKILL.md`](statistics/SKILL.md) - load when designing, fitting, or comparing a finite-sample statistical model.
```

Leave the study-design descriptive line (currently line 108) and every machine `name: path` entry unchanged.

- [ ] **Step 3: Verify the keyword map holds (no term dropped, shared terms in both).**

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/skills-phase4
echo "--- statistics keeps MCMC + bootstrap, drops study-design-only terms ---"
rg -i 'mcmc|bootstrap' skills/statistics/SKILL.md | head -1
rg -i 'permutation|downsampling|sensitivity arbitration|defensive instrumentation|pre-regist' skills/statistics/SKILL.md ; echo "rc=$? (rc=1 = correctly absent)"
echo "--- study-design gains the migrated terms ---"
rg -i 'permutation|monte-carlo|downsampling|power-floor|bias-vs-variance|sensitivity arbitration|defensive instrumentation|estimator certification|causal identification' skills/study-design/SKILL.md | head -1
cd science && uv run --frozen science skills lint --root ../skills ; echo "lint rc=$?"
```

Expected: statistics matches `mcmc|bootstrap`; the study-design-only grep on statistics is empty (`rc=1`); study-design matches the migrated terms; lint `rc=0`.

- [ ] **Step 4: Commit.**

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/skills-phase4
git add skills/study-design/SKILL.md skills/INDEX.md
git commit -m "refactor(skills): move statistics discovery keywords to the owning routers

Migrate pre-reg/power/sensitivity/bias-variance/estimator/causal keywords to
study-design's description; keep MCMC and bootstrap discoverable via statistics.
Narrow the skills/INDEX.md statistics line to the modeling scope."
```

---

### Task 3: Update the router invariant in doctrine

**Files:**
- Modify: `skills/meta/skill-authoring.md` (the "Router invariant" paragraph, currently line 44)

**Interfaces:** none.

- [ ] **Step 1: Update the count and hub list.**

In the "### Router invariant and the hub anti-pattern" paragraph, change `4 of 14 current `SKILL.md` files are still **hubs** (route + teach) — `data-management/SKILL.md`, `bio/transcriptomics/SKILL.md`, `pipelines/SKILL.md`, and `statistics/SKILL.md`.` to:

```
3 of 14 current `SKILL.md` files are still **hubs** (route + teach) — `data-management/SKILL.md`, `bio/transcriptomics/SKILL.md`, and `pipelines/SKILL.md`.
```

Then, immediately after the existing sentence noting `writing/SKILL.md` was extracted on 2026-07-20, add:

```
`statistics/SKILL.md` was reconciled to a router on 2026-07-21 (its own-leaf principles folded into its routing table; the principles that taught `study-design/` leaves were dropped, their theses already living in those leaves).
```

Leave the rest of the paragraph (and the file) unchanged.

- [ ] **Step 2: Sanity-check the count and lint.**

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/skills-phase4
rg -n '3 of 14|statistics/SKILL.md. was reconciled' skills/meta/skill-authoring.md
# the hub-list sentence (the one containing "still **hubs**") must no longer name statistics:
rg -n 'still \*\*hubs\*\*.*statistics/SKILL\.md' skills/meta/skill-authoring.md ; echo "stale-list rc=$? (rc=1 = statistics no longer in the hub list = good)"
cd science && uv run --frozen science skills lint --root ../skills ; echo "lint rc=$?"
```

Expected: the two new strings are found; statistics is no longer in the hub list; lint `rc=0`.

- [ ] **Step 3: Commit.**

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/skills-phase4
git add skills/meta/skill-authoring.md
git commit -m "docs(skills): router invariant now 3 of 14 hubs (statistics reconciled)"
```

---

### Task 4: Regenerate the codex mirror + full validation (green gate)

**Files:**
- Modify (generated): `codex-skills/` tree — via the generator only, never by hand.

**Interfaces:**
- Consumes: all edits from Tasks 1–3.

- [ ] **Step 1: Regenerate the mirror.**

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/skills-phase4/science
uv run --frozen python ../scripts/generate_codex_skills.py
```

Expected: prints `Generated Codex skills in …/codex-skills`.

- [ ] **Step 2: Confirm the committed mirror matches fresh generation (the green gate).**

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/skills-phase4/science
uv run --frozen pytest tests/test_codex_skills.py -q
echo "codex tests rc=$?"
```

Expected: all pass, `rc=0` (in particular `test_committed_codex_skills_match_fresh_generation`).

- [ ] **Step 3: Full validation.**

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/skills-phase4/science
uv run --frozen science skills lint --root ../skills ; echo "lint rc=$?"
uv run --frozen pytest -q ; echo "pytest rc=$?"
```

Expected: lint `rc=0`; full suite `rc=0`.

- [ ] **Step 4: Commit the regenerated mirror.**

```bash
cd /mnt/ssd/Dropbox/science/.worktrees/skills-phase4
git add codex-skills/
git commit -m "chore(codex): regenerate mirror after statistics router reconciliation"
```

If `git add codex-skills/` stages nothing (the statistics SKILL.md body already produced an identical mirror because it carried no rewritable markdown links), that is acceptable — the green gate is Step 2 passing, not a non-empty diff. Record in the ledger whether the mirror changed.

---

## Self-Review

- **Spec coverage:** design doc's four elements are all covered — router rewrite + fold/delete (Task 1), keyword migration incl. INDEX (Task 2), invariant count (Task 3), mirror regen (Task 4). The honesty gate (thesis-survival) and the no-anchor-deeplink check are Task 1 Steps 1–2.
- **Placeholder scan:** every step carries the exact file content or exact command; no "TBD"/"handle appropriately".
- **Consistency:** the routing table, the two `description` drafts, and the invariant text are identical to the accepted design doc. Only four source files change; leaf files are untouched.
- **RED-by-construction note:** Tasks 1–3 leave `test_committed_codex_skills_match_fresh_generation` RED until Task 4 regenerates the mirror. The green gate is Task 4 Step 2/3. This is the same pattern as phases 2–3.
