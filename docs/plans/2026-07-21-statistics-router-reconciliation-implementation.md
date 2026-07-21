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
- **Regenerate the codex mirror after the `skills/meta/` edit.** Verified against the generator: only Task 3's `skills/meta/skill-authoring.md` edit reaches the mirror (copied verbatim to `codex-skills/science-skill-development/skill-authoring.md`). The statistics/study-design **routers** and `skills/INDEX.md` are **not** generator inputs — their content is not bundled into any `codex-skills/` file — so Tasks 1–2 leave `test_committed_codex_skills_match_fresh_generation` GREEN. The test goes RED only after Task 3 and returns GREEN after Task 4 regenerates. Green gate = Task 4.
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
fail=0
gate() {  # $1 regex, $2 leaf, $3 label — fail-closed: any 0 count sets fail
  local n; n=$(rg -c -i "$1" "$2" 2>/dev/null || true)
  printf '  %-52s %s\n' "$3" "${n:-0}"
  [ "${n:-0}" -ge 1 ] || { echo "    ^ DEFECT: thesis absent from $2 — do not delete this principle"; fail=1; }
}
gate 'monte carlo se|minimum.attainable|precision you need|pre-committed decision rule' replicate-count-justification.md '1 replicate-count (precision, not convention)'
gate 'more replicates reduce variance|which error term the compute|do not remove estimator bias' bias-vs-variance-decomposition.md '2 bias-vs-variance (replicates shrink variance, not bias)'
gate 'caveat the verdict|which flags|override' sensitivity-arbitration.md '3 sensitivity (which flags caveat vs override)'
gate 'minimum (effect|detectable)|detectable effect|evidence of absence' power-floor-acknowledgement.md '4 power-floor (minimum detectable effect)'
gate 'amendment.*inherit|inherit.*(parent|amendment)|not a new pre-reg' prereg-amendment-vs-fresh.md '5 amendment (inherits, not a fresh pre-reg)'
gate 'universe lock|candidate-snapshot|tripwire|decision table' prereg-defensive-instrumentation.md '6 defensive (universe/candidate/tripwire/table)'
gate 'claim the optim|about itself|well-posed|forward-map' estimator-certification.md '7 estimator-cert (converged is a claim, not evidence)'
gate 'missing edge|m-bias|collider|not identified' causal-identification.md '8 causal-id (missing edges / M-bias / collider)'
[ "$fail" -eq 0 ] && echo "thesis gate PASS" || { echo "thesis gate FAIL"; exit 1; }
```

Expected: baseline counts 4, 2, 2, 3, 3, 12, 5, 7 and `thesis gate PASS`. Any `DEFECT` line aborts with `exit 1`.

- [ ] **Step 2: Confirm no anchor deep-links into the sections being removed.**

The design doc intentionally names `statistics/SKILL.md#principles` in prose, so
exclude `docs/plans/` (and the generated mirror); a real inbound deep-link would
be a `skills/` file.

```bash
cd ~/d/science/.worktrees/skills-phase4
out=$(rg -n --no-heading -g '!docs/plans/**' -g '!**/codex-skills/**' 'statistics/SKILL\.md#' . || true)
if [ -n "$out" ]; then echo "DEFECT: anchor deep-link(s) into removed sections:"; echo "$out"; exit 1; fi
echo "anchor check PASS (no deep-links outside docs/plans and the mirror)"
```

Expected: `anchor check PASS`.

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
bad=$(rg -n '^## Principles|^## When to invoke|^[0-9]+\. ' skills/statistics/SKILL.md || true)
if [ -n "$bad" ]; then echo "DEFECT: methodology remains in the router:"; echo "$bad"; exit 1; fi
echo "structure PASS (no Principles list / When-to-invoke block / numbered items)"
cd science && uv run --frozen science skills lint --root ../skills || { echo "DEFECT: skills lint failed"; exit 1; }
echo "lint PASS"
```

Expected: `structure PASS` then `lint PASS`.

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

Note: the committed-mirror test stays GREEN after this task — `statistics/SKILL.md` is not a generator input, so rewriting it does not change the mirror. It goes RED only at Task 3.

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

The two `description:` captures pass `--max-columns=0` explicitly: a global
`RIPGREP_CONFIG_PATH` (e.g. `--max-columns=150 --max-columns-preview`) otherwise
truncates these long single-line descriptions at capture time and appends
`[... omitted end of long line]`, making every downstream keep/drop/gain check
run against partial text and report false negatives. `--max-columns=0` disables
the limit for these two lines regardless of the ambient config.

```bash
cd ~/d/science/.worktrees/skills-phase4
fail=0
stats_desc=$(rg --max-columns=0 -m1 '^description:' skills/statistics/SKILL.md)
sd_desc=$(rg --max-columns=0 -m1 '^description:' skills/study-design/SKILL.md)
keep() { printf '  keep %-26s ' "$1:"; printf '%s' "$stats_desc" | rg -qi -- "$1" && echo PRESENT || { echo "MISSING (defect)"; fail=1; }; }
drop() { printf '  drop %-26s ' "$1:"; printf '%s' "$stats_desc" | rg -qi -- "$1" && { echo "LEAKED (defect)"; fail=1; } || echo absent; }
gain() { printf '  gain %-28s ' "$1:"; printf '%s' "$sd_desc"   | rg -qi -- "$1" && echo PRESENT || { echo "MISSING (defect)"; fail=1; }; }
echo "--- statistics description KEEPS the shared terms ---"
for t in 'MCMC' 'bootstrap'; do keep "$t"; done
echo "--- statistics description DROPS the study-design-only terms ---"
for t in 'permutation' 'downsampling' 'monte' 'power' 'sensitivity' 'defensive' 'pre-regist' 'estimator' 'causal' 'bias'; do drop "$t"; done
echo "--- study-design description GAINS every migrated term ---"
for t in 'pre-regist' 'permutation' 'bootstrap' 'monte-carlo' 'downsampling' 'power-floor' 'bias-vs-variance' 'sensitivity arbitration' 'defensive instrumentation' 'estimator certification' 'causal identification' 'round-number default'; do gain "$t"; done
[ "$fail" -eq 0 ] || { echo "keyword map FAIL"; exit 1; }
echo "keyword map PASS"
cd science && uv run --frozen science skills lint --root ../skills || { echo "DEFECT: skills lint failed"; exit 1; }
echo "lint PASS"
```

Expected: every KEEP `PRESENT`, every DROP `absent`, every GAIN `PRESENT`, then `keyword map PASS` and `lint PASS`. Any `(defect)` aborts with `exit 1`.

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

The historical note also names `statistics/SKILL.md` on the same physical line, so
a substring regex like `still **hubs**.*statistics/SKILL.md` would false-match.
Assert the **exact** hub-list sentence (fixed-string), which passes only when the
list is exactly the three remaining hubs:

```bash
cd ~/d/science/.worktrees/skills-phase4
rg -F 'still **hubs** (route + teach) — `data-management/SKILL.md`, `bio/transcriptomics/SKILL.md`, and `pipelines/SKILL.md`.' skills/meta/skill-authoring.md >/dev/null \
  || { echo "DEFECT: hub-list sentence is not exactly the three remaining hubs"; exit 1; }
rg -F '3 of 14 current' skills/meta/skill-authoring.md >/dev/null || { echo "DEFECT: count not updated to 3 of 14"; exit 1; }
rg -F '`statistics/SKILL.md` was reconciled to a router' skills/meta/skill-authoring.md >/dev/null || { echo "DEFECT: historical note missing"; exit 1; }
echo "invariant PASS (3 of 14; hub list correct; statistics reconciled)"
cd science && uv run --frozen science skills lint --root ../skills || { echo "DEFECT: skills lint failed"; exit 1; }
echo "lint PASS"
```

Expected: `invariant PASS` then `lint PASS`. The em-dash (—) in the fixed string must match the file byte-for-byte.

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
uv run --frozen pytest tests/test_codex_skills.py -q || { echo "DEFECT: codex mirror tests failed"; exit 1; }
echo "codex mirror tests PASS"
```

Expected: `codex mirror tests PASS` (in particular `test_committed_codex_skills_match_fresh_generation`).

- [ ] **Step 3: Full validation.**

```bash
cd ~/d/science/.worktrees/skills-phase4/science
uv run --frozen science skills lint --root ../skills || { echo "DEFECT: skills lint failed"; exit 1; }
uv run --frozen pytest -q || { echo "DEFECT: full suite failed"; exit 1; }
echo "full validation PASS"
```

Expected: `full validation PASS`.

- [ ] **Step 4: Commit the regenerated mirror.**

The mirror **must** have changed: Task 3 edited `skills/meta/skill-authoring.md`,
which the generator copies verbatim to
`codex-skills/science-skill-development/skill-authoring.md`. An empty
`codex-skills/` diff means the generator did not run or an edit was missed — a
defect, not an acceptable outcome.

```bash
cd ~/d/science/.worktrees/skills-phase4
git status --porcelain codex-skills/science-skill-development/skill-authoring.md | rg . >/dev/null \
  || { echo "DEFECT: skill-authoring.md not regenerated — stop and investigate"; exit 1; }
echo "OK: mirror changed (skill-authoring.md regenerated)"
git status --porcelain codex-skills/   # informational: the full set of regenerated files
git add codex-skills/
git commit -m "chore(codex): regenerate mirror after statistics router reconciliation"
```

Record in the ledger which mirror files changed.

---

## Self-Review

- **Spec coverage:** design doc's four elements are all covered — router rewrite + fold/delete (Task 1), keyword migration incl. INDEX (Task 2), invariant count (Task 3), mirror regen (Task 4). The honesty gate (thesis-survival) and the no-anchor-deeplink check are Task 1 Steps 1–2.
- **Placeholder scan:** every step carries the exact file content or exact command; no "TBD"/"handle appropriately".
- **Consistency:** the routing table, the two `description` drafts, and the invariant text are identical to the accepted design doc. Only four source files change; leaf files are untouched.
- **RED-by-construction note:** verified against the generator — only Task 3's `skills/meta/skill-authoring.md` edit reaches the mirror, so Tasks 1–2 stay GREEN on `test_committed_codex_skills_match_fresh_generation`; Task 3 turns it RED and Task 4 restores GREEN (the green gate). The statistics/study-design routers and `skills/INDEX.md` are not generator inputs.
