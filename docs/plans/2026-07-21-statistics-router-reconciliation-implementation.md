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

Each grep targets the principle's **thesis** (its relationship or decision
rule), not a generic topic word — a leaf that merely mentioned "bias" must not
pass the bias-vs-variance check. Phrases below were confirmed ≥1 against the
current leaves.

```bash
cd ~/d/science/.worktrees/skills-phase4/skills/study-design
echo "1 replicate-count (justify count by precision, not convention):"; rg -c -i 'monte carlo se|minimum.attainable|precision you need|pre-committed decision rule' replicate-count-justification.md
echo "2 bias-vs-variance (replicates shrink variance, not bias):";      rg -c -i 'more replicates reduce variance|which error term the compute|do not remove estimator bias' bias-vs-variance-decomposition.md
echo "3 sensitivity (which flags caveat vs override the verdict):";     rg -c -i 'caveat the verdict|which flags|override' sensitivity-arbitration.md
echo "4 power-floor (state the minimum detectable effect):";            rg -c -i 'minimum (effect|detectable)|detectable effect|evidence of absence' power-floor-acknowledgement.md
echo "5 amendment (an amendment inherits, is not a fresh pre-reg):";    rg -c -i 'amendment.*inherit|inherit.*(parent|amendment)|not a new pre-reg' prereg-amendment-vs-fresh.md
echo "6 defensive (universe/candidate/tripwire/decision-table locks):"; rg -c -i 'universe lock|candidate-snapshot|tripwire|decision table' prereg-defensive-instrumentation.md
echo "7 estimator-cert (a converged fit is a claim, not evidence):";    rg -c -i 'claim the optim|about itself|well-posed|forward-map' estimator-certification.md
echo "8 causal-id (missing edges / M-bias / collider / not identified):"; rg -c -i 'missing edge|m-bias|collider|not identified' causal-identification.md
```

Expected: every count ≥ 1 (baseline: 4, 2, 2, 3, 3, 12, 5, 7). If any is 0, STOP and report — the thesis is not in the leaf and the principle must not be deleted.

- [ ] **Step 2: Confirm no anchor deep-links into the sections being removed.**

The design doc intentionally names `statistics/SKILL.md#principles` in prose, so
exclude `docs/plans/` (and the generated mirror); a real inbound deep-link would
be a `skills/` file.

```bash
cd ~/d/science/.worktrees/skills-phase4
rg -n --no-heading -g '!docs/plans/**' -g '!**/codex-skills/**' 'statistics/SKILL\.md#' . ; echo "rc=$? (rc=1 = no matches = good)"
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
| `survival-and-hierarchical-models.md` | designing or reviewing Cox / Weibull / AFT / frailty / mixed-effects / Bayesian-hierarchical / multi-dataset models, or when repeated cells / genes / samples inside a donor or study are not independent observations | the outcome is not time-to-event and there is no grouping, censoring, hierarchical, or repeated-measure structure — a single-level i.i.d. model suffices |
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
cd ~/d/science/.worktrees/skills-phase4
# no numbered Principles list and no When-to-invoke block:
rg -n '^## Principles|^## When to invoke|^[0-9]+\. ' skills/statistics/SKILL.md ; echo "rc=$? (rc=1 = clean = good)"
# lint passes:
cd science && uv run --frozen science skills lint --root ../skills ; echo "lint rc=$?"
```

Expected: first grep prints nothing (`rc=1`); lint `rc=0`.

- [ ] **Step 5: Commit.**

```bash
cd ~/d/science/.worktrees/skills-phase4
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
description: Use when analysis rigor must be pre-committed or a numeric verdict certified / arbitrated — pre-registration, replicate / permutation / bootstrap / Monte-Carlo / downsampling count justification (over a round-number default), power-floor acknowledgement, bias-vs-variance decomposition, sensitivity arbitration, defensive instrumentation, estimator certification, or causal identification. Routes to the discipline leaves.
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

The presence/absence assertions target the **`description` frontmatter line
only** (the router *body* legitimately names "pre-registration" and "sensitivity
arbitration" in its scope boundary — a whole-file grep would false-positive), and
each term is checked **separately** (alternation + `head -1` would prove only one
term exists).

```bash
cd ~/d/science/.worktrees/skills-phase4
stats_desc=$(rg -m1 '^description:' skills/statistics/SKILL.md)
sd_desc=$(rg -m1 '^description:' skills/study-design/SKILL.md)

echo "--- statistics description KEEPS the shared terms ---"
for t in 'MCMC' 'bootstrap'; do
  printf '  %-24s ' "$t:"; printf '%s' "$stats_desc" | rg -qi -- "$t" && echo PRESENT || echo "MISSING (defect)"
done
echo "--- statistics description DROPS the study-design-only terms ---"
for t in 'permutation' 'downsampling' 'monte' 'power' 'sensitivity' 'defensive' 'pre-regist' 'estimator' 'causal' 'bias'; do
  printf '  %-24s ' "$t:"; printf '%s' "$stats_desc" | rg -qi -- "$t" && echo "LEAKED (defect)" || echo absent
done
echo "--- study-design description GAINS every migrated term ---"
for t in 'permutation' 'bootstrap' 'monte-carlo' 'downsampling' 'power-floor' 'bias-vs-variance' 'sensitivity arbitration' 'defensive instrumentation' 'estimator certification' 'causal identification' 'round-number default'; do
  printf '  %-28s ' "$t:"; printf '%s' "$sd_desc" | rg -qi -- "$t" && echo PRESENT || echo "MISSING (defect)"
done
cd science && uv run --frozen science skills lint --root ../skills ; echo "lint rc=$?"
```

Expected: every statistics-KEEP term `PRESENT`; every statistics-DROP term `absent`; every study-design term `PRESENT`; no `(defect)` line; lint `rc=0`.

- [ ] **Step 4: Commit.**

```bash
cd ~/d/science/.worktrees/skills-phase4
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
cd ~/d/science/.worktrees/skills-phase4
rg -n '3 of 14|statistics/SKILL.md. was reconciled' skills/meta/skill-authoring.md
# the hub-list sentence (the one containing "still **hubs**") must no longer name statistics:
rg -n 'still \*\*hubs\*\*.*statistics/SKILL\.md' skills/meta/skill-authoring.md ; echo "stale-list rc=$? (rc=1 = statistics no longer in the hub list = good)"
cd science && uv run --frozen science skills lint --root ../skills ; echo "lint rc=$?"
```

Expected: the two new strings are found; statistics is no longer in the hub list; lint `rc=0`.

- [ ] **Step 3: Commit.**

```bash
cd ~/d/science/.worktrees/skills-phase4
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
cd ~/d/science/.worktrees/skills-phase4/science
uv run --frozen python ../scripts/generate_codex_skills.py
```

Expected: prints `Generated Codex skills in …/codex-skills`.

- [ ] **Step 2: Confirm the committed mirror matches fresh generation (the green gate).**

```bash
cd ~/d/science/.worktrees/skills-phase4/science
uv run --frozen pytest tests/test_codex_skills.py -q
echo "codex tests rc=$?"
```

Expected: all pass, `rc=0` (in particular `test_committed_codex_skills_match_fresh_generation`).

- [ ] **Step 3: Full validation.**

```bash
cd ~/d/science/.worktrees/skills-phase4/science
uv run --frozen science skills lint --root ../skills ; echo "lint rc=$?"
uv run --frozen pytest -q ; echo "pytest rc=$?"
```

Expected: lint `rc=0`; full suite `rc=0`.

- [ ] **Step 4: Commit the regenerated mirror.**

The mirror **must** have changed: Task 3 edited `skills/meta/skill-authoring.md`,
which the generator copies verbatim to
`codex-skills/science-skill-development/skill-authoring.md`. An empty
`codex-skills/` diff means the generator did not run or an edit was missed — a
defect, not an acceptable outcome.

```bash
cd ~/d/science/.worktrees/skills-phase4
echo "--- skill-authoring.md copy MUST show as modified ---"
git status --porcelain codex-skills/science-skill-development/skill-authoring.md \
  | rg . && echo "OK: mirror changed" \
  || { echo "DEFECT: skill-authoring.md not regenerated — stop and investigate"; }
git status --porcelain codex-skills/   # a non-empty list is REQUIRED here
git add codex-skills/
git commit -m "chore(codex): regenerate mirror after statistics router reconciliation"
```

Record in the ledger which mirror files changed.

---

## Self-Review

- **Spec coverage:** design doc's four elements are all covered — router rewrite + fold/delete (Task 1), keyword migration incl. INDEX (Task 2), invariant count (Task 3), mirror regen (Task 4). The honesty gate (thesis-survival) and the no-anchor-deeplink check are Task 1 Steps 1–2.
- **Placeholder scan:** every step carries the exact file content or exact command; no "TBD"/"handle appropriately".
- **Consistency:** the routing table, the two `description` drafts, and the invariant text are identical to the accepted design doc. Only four source files change; leaf files are untouched.
- **RED-by-construction note:** Tasks 1–3 leave `test_committed_codex_skills_match_fresh_generation` RED until Task 4 regenerates the mirror. The green gate is Task 4 Step 2/3. This is the same pattern as phases 2–3.
