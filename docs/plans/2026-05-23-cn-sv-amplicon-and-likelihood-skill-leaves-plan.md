# CN/SV/Amplicon and Likelihood Skill Leaves Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Author three new methodology skill leaves (CN/SV/amplicon QA, general likelihood model-comparison, population-genetics likelihood), wire them into the skill index / SKILL hubs / plan-analysis rubric, and fix the pre-existing linter failure that blocks the verification gate — closing downstream feedback fb-2026-05-03-001 and fb-2026-05-03-002.

**Architecture:** Pure documentation work in the `skills/` and `commands/` trees at the repo root. The "test" for each task is the skills linter (`science skills lint`), which checks frontmatter, required `## Companion Skills` sections, relative-link target existence, and INDEX coverage; `test_command_docs` is the gate for the `plan-analysis.md` edit. Leaves follow the established skeleton of `skills/data/genomics/somatic-mutation-qa.md` and `skills/statistics/survival-and-hierarchical-models.md`.

**Tech Stack:** Markdown skill docs; `uv run --frozen science skills lint --root ../skills` (run from `science/`); `pytest` for `test_command_docs`.

**Branch:** `docs/t10-skill-leaves` (already created; the approved design doc is committed there).

**Linter ordering note:** `check_relative_links` verifies that every relative `.md` link target exists. The genomics leaf (Task 2) and the pop-gen leaf (Task 4) reference each other as companions, so Task 2 and Task 3 will each leave exactly the documented forward `broken-relative-link` to `population-genetics-likelihood.md`. That link resolves when Task 4 creates the file; the linter reaches **zero errors at Task 4**. Each task wires its own INDEX entry, so no `missing-index-entry` ever lingers.

---

## Task 1: Prerequisite — green the linter

**Files:**
- Modify: `skills/statistics/prereg-defensive-instrumentation.md:193`
- Modify: `skills/INDEX.md:49`

- [ ] **Step 1: Run the linter to see the pre-existing failures (RED)**

Run (from `science/`): `uv run --frozen science skills lint --root ../skills`

Expected: exits non-zero with exactly:
```
statistics/prereg-defensive-instrumentation.md: missing-section: Companion Skills
INDEX.md: missing-index-entry: statistics/prereg-defensive-instrumentation.md
```

- [ ] **Step 2: Rename the companion heading to the canonical form**

In `skills/statistics/prereg-defensive-instrumentation.md`, change the line:
```markdown
## Companion Leaves
```
to:
```markdown
## Companion Skills
```
(The section body is already only companion links; this is a pure heading correction.)

- [ ] **Step 3: Add the missing INDEX entry**

In `skills/INDEX.md`, after line 49 (`- `statistics-prereg-amendment-vs-fresh`: ...`) add:
```markdown
- `statistics-prereg-defensive-instrumentation`: `skills/statistics/prereg-defensive-instrumentation.md`
```

- [ ] **Step 4: Run the linter to verify it is green (GREEN)**

Run (from `science/`): `uv run --frozen science skills lint --root ../skills`
Expected: exits 0, no issues printed.

- [ ] **Step 5: Commit**

```bash
git add skills/statistics/prereg-defensive-instrumentation.md skills/INDEX.md
git commit -m "fix(skills): align prereg-defensive-instrumentation with Companion Skills schema + INDEX

Pre-existing linter failure unrelated to the new leaves: the leaf used
## Companion Leaves instead of the required ## Companion Skills and was
missing from INDEX.md. Fixing the doc to match the canonical schema (not
loosening the linter) greens the gate before the new leaves land."
```

---

## Task 2: Genomics leaf — `data-genomics-copy-number-sv-qa`

**Files:**
- Create: `skills/data/genomics/copy-number-sv-qa.md`
- Modify: `skills/INDEX.md:27`
- Modify: `skills/data/genomics/SKILL.md` (layers table + anticipated-growth line)

- [ ] **Step 1: Create the leaf**

Create `skills/data/genomics/copy-number-sv-qa.md` with exactly:

````markdown
---
name: data-genomics-copy-number-sv-qa
description: Use when ingesting or auditing copy-number segments, structural-variant/breakpoint calls, or AmpliconArchitect/AmpliconClassifier focal-amplicon and ecDNA outputs, from bulk WGS/WES or per-cell scWGS (e.g. DLP+).
---

# Copy-Number, Structural-Variant, and Amplicon QA

Use when ingesting or auditing copy-number (CN) segments, structural-variant
(SV) / breakpoint calls, or AmpliconArchitect (AA) / AmpliconClassifier (AC)
focal-amplicon and ecDNA outputs — from bulk WGS/WES or per-cell single-cell
WGS (e.g. DLP+).

CN, SV, and amplicon calls share one root QA problem: every call is conditional
on a ploidy/purity model, a calling-pipeline version, and an assay fragmentation
profile, any of which can turn an artifact into apparent biology. AA/AC outputs
add a second problem: they are *derived* from the same CN+SV calls, so they are
not independent confirmation of them.

## Acquisition Checklist

1. **Lock the coordinate system.** Genome build, chromosome naming, and whether
   segment coordinates are 0- or 1-based. Never join GRCh37 and GRCh38
   breakpoints or segments without liftover plus post-liftover validation.
2. **Name the unit of analysis.** Bulk sample, per-cell, clone, or patient. Cells
   from one tumor are not independent; bulk calls are mixtures over an unknown
   clone composition. State the unit the endpoint is computed over.
3. **Record the ploidy/purity model.** Every absolute-CN value is conditional on
   an estimated tumor purity and ploidy. Store the caller, its version, and the
   purity/ploidy estimate per sample. CN 8 at ploidy 2 and at ploidy 4 are
   different biological claims.
4. **Record per-cell binning / segmentation parameters.** For scWGS, the bin size
   and segmentation method set the floor on detectable focal events and the
   discreteness of per-cell CN. Bins must be identical across cells being
   compared.
5. **Record SV breakpoint support and filters.** Split-read / discordant-pair
   support, mapping-quality filters, and blacklist/centromere masking. A
   breakpoint with single-end support near a repeat is not a confirmed SV.
6. **Pin the AA/AC version and reference.** AmpliconArchitect and
   AmpliconClassifier change amplicon-type logic across versions. Store both
   versions, the reference build, the CN/seed threshold used to define amplified
   intervals, and the AC amplicon-type confidence.

## Minimum QA Tables

| Artifact | Required fields |
|---|---|
| `cn_segments` | sample_or_cell_id, chrom, start, end, copy_number, caller, purity, ploidy |
| `sv_breakpoints` | sample_id, chrom1, pos1, chrom2, pos2, sv_type, support, pass_filter |
| `amplicon_calls` | sample_id, amplicon_id, amplicon_type, intervals, aa_version, ac_version, ac_confidence |
| `ploidy_purity_audit` | sample_id, purity, ploidy, method, low_confidence_flag |
| `percell_binning_audit` | cell_id, bin_size, n_bins, segmentation, qc_status |

## Common Failure Modes

- **AA/AC version + ploidy-correction drift.** Amplicon type (ecDNA, BFB,
  complex, linear) and CN thresholds shift across AA/AC releases and across the
  purity/ploidy estimate used. Re-running with a different version or ploidy can
  reclassify ecDNA as linear and vice versa.
- **FFPE fragmentation.** FFPE damage shortens fragments and inflates artifactual
  breakpoints while suppressing true long-range amplicon reconstruction. FFPE and
  fresh-frozen amplicon calls are not comparable without an explicit
  fragmentation/quality covariate.
- **Per-cell CN-binning choices.** Coarse bins miss focal amplicons; fine bins
  inflate per-cell CN variance. A "convergent amplification" signal can be a
  binning artifact when bins differ across compared cells.
- **Classifier-confidence handling.** AC assigns amplicon types with a
  confidence; ecDNA-vs-HSR-vs-BFB-vs-linear calls near the threshold should carry
  the confidence forward, not be hardened to a categorical label.
- **AA/AC pipeline non-independence.** AC consumes AA output, which consumes the
  CN+SV calls. Agreement among AA, AC, and the CN caller is expected by
  construction and is not independent corroboration of an amplicon.
- **GC / mappability waviness.** Uncorrected GC and mappability bias produces wavy
  CN profiles read as low-amplitude gains/losses.

## Analysis Rules

- Never report an absolute CN without the purity/ploidy it is conditional on.
- Never treat AA and AC (or AA/AC and the CN caller) as independent confirmation
  of an amplicon; they share inputs by construction.
- Never compare amplicon detection across FFPE and fresh-frozen samples without a
  fragmentation/quality adjustment or restriction.
- Keep per-cell bin size and segmentation fixed across all cells in a contrast.
- Carry AC amplicon-type confidence into downstream verdicts; do not harden
  near-threshold ecDNA/HSR/BFB calls.

## Halt-On Conditions

- Tumor purity/ploidy is unavailable or low-confidence for samples whose absolute
  CN drives the endpoint.
- AA/AC versions are unpinned or mismatched across the cohort.
- FFPE and fresh-frozen samples are mixed in an amplicon contrast without
  adjustment.
- Per-cell bins are incomparable across cells being contrasted.

## Output Package

Generate a `datapackage.json` for this directory; see [`../frictionless.md`](../frictionless.md).

```
data/processed/<cohort_id>/cn_sv_amplicon_qa/
|-- cn_segments.parquet
|-- sv_breakpoints.parquet
|-- amplicon_calls.parquet
|-- ploidy_purity_audit.parquet
|-- percell_binning_audit.parquet
`-- cohort_audit.json
```

The audit should state the purity/ploidy model behind every absolute CN, the
AA/AC versions, and which amplicon calls share inputs (and are therefore not
independent).

## Companion Skills

- [`SKILL.md`](./SKILL.md) — genomics data-ingestion hub.
- [`somatic-mutation-qa.md`](./somatic-mutation-qa.md) — callable-territory and missing-vs-zero rules that also govern CN/SV denominators.
- [`../../statistics/population-genetics-likelihood.md`](../../statistics/population-genetics-likelihood.md) — downstream selection/segregation modelling that consumes per-cell CN.
- [`../../statistics/power-floor-acknowledgement.md`](../../statistics/power-floor-acknowledgement.md) — focal-event and per-cell contrasts are typically low-power.
- [`../../statistics/sensitivity-arbitration.md`](../../statistics/sensitivity-arbitration.md) — ploidy-model and AA/AC-version variants are the canonical sensitivity pair.
````

- [ ] **Step 2: Add the INDEX entry**

In `skills/INDEX.md`, after line 27 (`- `data-genomics-mutational-signatures-and-selection`: ...`) add:
```markdown
- `data-genomics-copy-number-sv-qa`: `skills/data/genomics/copy-number-sv-qa.md`
```

- [ ] **Step 3: Update the genomics SKILL hub**

In `skills/data/genomics/SKILL.md`, change the section heading and intro:
```markdown
## Two layers, two QA mindsets
```
to:
```markdown
## Layers and QA mindsets
```
Add this row to that table (after the signatures/selection row):
```markdown
| CN / SV / amplicon calls (input + derived QA) | [`copy-number-sv-qa.md`](./copy-number-sv-qa.md) | ploidy/purity conditioning, AA/AC version drift, FFPE fragmentation, per-cell binning, AA→AC non-independence |
```
And in the "Anticipated growth" paragraph, change:
```markdown
Future leaves likely under this hub: copy-number QA, structural-variant QA,
fusion-transcript QA, methylation/EPIC-array QA.
```
to:
```markdown
Future leaves likely under this hub: fusion-transcript QA,
methylation/EPIC-array QA.
```

- [ ] **Step 4: Run the linter (interim — one expected pending link)**

Run (from `science/`): `uv run --frozen science skills lint --root ../skills`
Expected: exits non-zero with exactly one issue:
```
data/genomics/copy-number-sv-qa.md: broken-relative-link: ../../statistics/population-genetics-likelihood.md
```
This is the forward reference to the pop-gen leaf created in Task 4. No other issues should appear (frontmatter, `## Companion Skills`, `## Halt-On Conditions`, INDEX entry, and all other links are satisfied within this task).

- [ ] **Step 5: Commit**

```bash
git add skills/data/genomics/copy-number-sv-qa.md skills/INDEX.md skills/data/genomics/SKILL.md
git commit -m "feat(skills): add data-genomics-copy-number-sv-qa leaf (fb-2026-05-03-001)

CN segments (bulk + per-cell scWGS), SV/breakpoint calls, and AA/AC
focal-amplicon/ecDNA QA in one leaf. Wires INDEX + genomics SKILL hub."
```

---

## Task 3: General statistics leaf — `statistics-likelihood-model-comparison`

**Files:**
- Create: `skills/statistics/likelihood-model-comparison.md`
- Modify: `skills/INDEX.md:49` (statistics block)
- Modify: `skills/statistics/SKILL.md` (Leaves table + Principles)

- [ ] **Step 1: Create the leaf**

Create `skills/statistics/likelihood-model-comparison.md` with exactly:

````markdown
---
name: statistics-likelihood-model-comparison
description: Use when comparing parametric models by likelihood — AIC, BIC, likelihood-ratio tests, nested vs non-nested comparison, identifiability and rare-event numerical-precision audits, and bootstrap confidence intervals on the selected model.
---

# Likelihood Model Comparison

Use when comparing parametric models by likelihood: AIC, BIC, likelihood-ratio
tests (LRT), nested vs non-nested comparison, bootstrap CIs, and the
identifiability / numerical-precision checks that decide whether a comparison is
even well-posed.

Model comparison is where a fitting bug or an incomparable likelihood quietly
becomes a verdict. The discipline is to confirm the comparison is well-posed —
same data, comparable likelihoods, identified parameters, converged optimizer —
before reading off AIC/BIC/LRT.

## Pre-Flight Checklist

1. **Enumerate the candidate set and name the null.** State every model being
   compared and which one is the null / reference.
2. **Classify nested vs non-nested.** Models are nested when one is a parameter
   restriction of another (e.g. a selection coefficient fixed at zero). Nesting
   decides whether LRT is available.
3. **Confirm identical data and response.** AIC/BIC are comparable only across
   models fit to the *same observations on the same response scale*. A model on
   log-CN and one on natural-scale CN are not AIC-comparable without a
   change-of-variable correction (below).
4. **Check identifiability.** Confirm each parameter is identified by the data
   (not at a boundary, not redundant). Unidentified parameters make the parameter
   count — and therefore AIC/BIC — meaningless.
5. **State which metric is verdict-bearing.** Pre-commit whether AIC, BIC, or LRT
   decides the verdict and which others are reported alongside.

## AIC vs BIC vs LRT

| Tool | Requires | Use for |
|---|---|---|
| LRT | strictly nested models + regularity (parameter not on a boundary) | a formal test of whether the extra parameter(s) improve fit |
| AIC | identical data + comparable likelihood normalization | predictive-accuracy ranking, including non-nested models |
| BIC | identical data + comparable normalization; meaningful n | consistency-oriented selection; penalizes parameters harder as n grows |

- LRT on a parameter at its boundary (e.g. a variance or selection coefficient
  fixed at zero) does **not** have the usual χ² null; use the appropriate mixture
  distribution or a parametric-bootstrap null.
- A small ΔAIC/ΔBIC is not a decision. Report the difference and its bootstrap
  stability, not just the argmin.

## Re-Expression for Comparability

Non-nested likelihoods are often expressed on different variable scales or time
axes. To compare them:

- Re-express all models onto a **common response scale / common time axis** before
  fitting, OR
- Apply the **change-of-variable Jacobian** to the log-likelihood when a model is
  fit on a transformed variable. Comparing AIC across an untransformed and a
  log-transformed response without the Jacobian term is a category error — the
  densities are not on the same measure.

State explicitly which models were re-expressed and what the Jacobian correction
was.

## Numerical-Precision Audit

Likelihoods that sum over rare events or large state spaces underflow silently.

- Evaluate and accumulate log-likelihoods in **log space** (logsumexp); never log a
  summed probability.
- Check for underflow / `-inf` contributions and for terms dominated by a single
  state.
- Confirm optimizer convergence (gradient norm / relative tolerance), not just a
  returned value. Re-fit from multiple starts for multimodal likelihoods.
- Record the minimum representable likelihood contribution and whether any
  verdict-bearing term is near it.

## Bootstrap Confidence and Selection Stability

- Report bootstrap CIs for the parameters and for the ΔAIC/ΔBIC between the top
  models (parametric bootstrap for generative models; nonparametric for
  exchangeable data).
- Report **selection stability**: across bootstrap resamples, how often does the
  selected model win? A model that wins by ΔAIC but only 55% of the time is not a
  confident selection.

## Common Failure Modes

- **Incomparable likelihoods.** Different data, different response scale, or a
  transform without its Jacobian.
- **LRT on non-nested or boundary models.** Wrong reference distribution.
- **Argmin worship.** Treating the lowest AIC as decisive regardless of ΔAIC size
  or selection stability.
- **Unconverged or single-start optimization.** A local optimum reported as the
  MLE.
- **Counting unidentified parameters.** Inflated or deflated penalties.

## Reporting

Report the candidate set, nesting structure, the data/response scale shared by
all models, any re-expression + Jacobian, the verdict-bearing metric and its
value, ΔAIC/ΔBIC with bootstrap CIs and selection stability, and the convergence
diagnostics. State any verdict downgrade caused by incomparability,
non-identifiability, or selection instability.

## Companion Skills

- [`sensitivity-arbitration.md`](./sensitivity-arbitration.md) — pre-commit which comparison metric is verdict-bearing and which are reported alongside.
- [`power-floor-acknowledgement.md`](./power-floor-acknowledgement.md) — the minimum effect a likelihood comparison can resolve at the available n.
- [`population-genetics-likelihood.md`](./population-genetics-likelihood.md) — a domain consumer: constructing the pop-gen likelihoods this leaf then compares.
````

- [ ] **Step 2: Add the INDEX entry**

In `skills/INDEX.md`, in the Statistics block (after the `statistics-prereg-defensive-instrumentation` line added in Task 1) add:
```markdown
- `statistics-likelihood-model-comparison`: `skills/statistics/likelihood-model-comparison.md`
```

- [ ] **Step 3: Register the leaf in the statistics SKILL hub**

In `skills/statistics/SKILL.md`, add this row to the `## Leaves` table (after the `compositional-data.md` row):
```markdown
| [`likelihood-model-comparison.md`](./likelihood-model-comparison.md) | Comparing parametric models by likelihood — AIC/BIC/LRT, nested vs non-nested, numerical precision, bootstrap selection stability |
```
And add this principle to the `## Principles` list (as item 9):
```markdown
9. **Make likelihood comparisons well-posed before reading them.** Same data,
   same response scale, identified parameters, and a converged optimizer come
   before AIC/BIC/LRT; non-nested models need a common scale or a Jacobian
   correction. See
   [`likelihood-model-comparison`](./likelihood-model-comparison.md).
```

- [ ] **Step 4: Run the linter (interim — same one expected pending link)**

Run (from `science/`): `uv run --frozen science skills lint --root ../skills`
Expected: exits non-zero with exactly two issues, both the forward reference to the pop-gen leaf created in Task 4:
```
data/genomics/copy-number-sv-qa.md: broken-relative-link: ../../statistics/population-genetics-likelihood.md
statistics/likelihood-model-comparison.md: broken-relative-link: population-genetics-likelihood.md
```
No other issues.

- [ ] **Step 5: Commit**

```bash
git add skills/statistics/likelihood-model-comparison.md skills/INDEX.md skills/statistics/SKILL.md
git commit -m "feat(skills): add statistics-likelihood-model-comparison leaf (fb-2026-05-03-002)

Domain-agnostic AIC/BIC/LRT machinery: nested vs non-nested, re-expression +
Jacobian for comparability, rare-event numerical precision, bootstrap selection
stability. Wires INDEX + statistics SKILL hub."
```

---

## Task 4: Pop-gen leaf — `statistics-population-genetics-likelihood` (linter goes green)

**Files:**
- Create: `skills/statistics/population-genetics-likelihood.md`
- Modify: `skills/INDEX.md` (statistics block)
- Modify: `skills/statistics/SKILL.md` (Leaves table + Principles)

- [ ] **Step 1: Create the leaf**

Create `skills/statistics/population-genetics-likelihood.md` with exactly:

````markdown
---
name: statistics-population-genetics-likelihood
description: Use when constructing or fitting population-genetics likelihoods — Wright-Fisher, Moran, or binomial-segregation+selection models (e.g. ecDNA copy number) — and comparing selection against a neutral null.
---

# Population-Genetics Likelihood

Use when constructing or fitting population-genetics likelihoods — Wright-Fisher
(WF), Moran, or binomial-segregation+selection models (e.g. ecDNA copy-number
evolution) — and comparing a selection model against a neutral null.

This leaf owns *what likelihood to write and what it assumes*. The machinery for
comparing the resulting models (AIC/BIC/LRT, numerical precision, bootstrap) is
in [`likelihood-model-comparison.md`](./likelihood-model-comparison.md); load it
as a companion.

## Likelihood Construction

State the generative process explicitly before fitting:

- **Wright-Fisher.** Non-overlapping generations, multinomial/binomial sampling of
  the next generation; selection enters as a fitness reweighting. The diffusion
  approximation gives a tractable continuous likelihood with drift ∝ selection
  and variance ∝ the per-generation sampling scale.
- **Moran.** Overlapping generations, one birth-death per step; appropriate when
  the population turns over continuously rather than in discrete generations.
- **Binomial-segregation+selection (ecDNA).** Per division, copies segregate
  binomially to daughters; selection reweights cells by copy number. The
  continuous (Gaussian-diffusion) approximation parameterizes a drift term
  (selection) and a per-generation variance scale (segregation noise).

For each, write down: the state variable and its scale (keep it identical across
the models you will compare, for likelihood comparability), the transition
kernel, the selection parameter, and the variance/noise parameter.

## Neutral Null vs Selection Alternative

- The **neutral null** fixes the selection parameter at zero while still estimating
  the variance/noise scale. Drift alone must be given a fair chance to explain the
  data.
- The **selection alternative** frees the selection parameter.
- A **Wright-Fisher continuous-trait alternative** can serve as a non-nested rival
  to a discrete segregation model; compare it via AIC on a common response scale
  (see the companion leaf), not LRT.

## Independent Unit and Time Axis

- State the time axis — generations, cell-cycles, or sampling time — and how it
  maps to the data. The axis must be common across compared models.
- State the independent unit: per-cell, per-clone, or per-lineage. Cells sharing
  ancestry are not independent draws.
- State the effective population size assumption wherever the likelihood depends
  on it.

## Identifiability and Confounding

- **Drift vs selection are confounded** at small effective population size or few
  generations: strong drift mimics selection in a single trajectory. Confirm the
  data can separate them before reading a selection verdict.
- **Segregation variance vs selection.** A high per-generation variance scale can
  absorb apparent directional change; estimate the variance scale rather than
  fixing it by convention.

## Halt-On Conditions

- The transition variance scale / time axis is **neither identified from data nor
  pre-registered** as an estimated / profiled / sensitivity parameter. A model
  that *estimates* its per-generation variance scale on a stated
  per-cell-generation axis is ready — a known effective population size is not
  required.
- Drift and selection are not separable on the available data and the analysis is
  nonetheless being read as a selection verdict.

## Verdict Scope

A selection signal fit on a single cohort is scoped to that cohort: because drift
and selection are confounded at low effective size, a single-cohort fit cannot
rule out cohort-specific drift. Report the within-cohort verdict, and require
independent replication in another cohort before promoting a cross-cohort
selection claim.

## Companion Skills

- [`likelihood-model-comparison.md`](./likelihood-model-comparison.md) — the AIC/BIC/LRT, numerical-precision, and bootstrap machinery for comparing these models.
- [`../data/genomics/copy-number-sv-qa.md`](../data/genomics/copy-number-sv-qa.md) — QA for the per-cell CN calls these likelihoods are fit to.
- [`power-floor-acknowledgement.md`](./power-floor-acknowledgement.md) — the minimum selection coefficient resolvable at the available cell/generation count.
- [`sensitivity-arbitration.md`](./sensitivity-arbitration.md) — pre-committing how drift-vs-selection sensitivity passes resolve the verdict.
````

- [ ] **Step 2: Add the INDEX entry**

In `skills/INDEX.md`, in the Statistics block (after the `statistics-likelihood-model-comparison` line) add:
```markdown
- `statistics-population-genetics-likelihood`: `skills/statistics/population-genetics-likelihood.md`
```

- [ ] **Step 3: Register the leaf in the statistics SKILL hub**

In `skills/statistics/SKILL.md`, add this row to the `## Leaves` table (after the `likelihood-model-comparison.md` row):
```markdown
| [`population-genetics-likelihood.md`](./population-genetics-likelihood.md) | Wright-Fisher / Moran / binomial-segregation likelihoods; selection vs neutral null |
```
And add this principle to the `## Principles` list (as item 10):
```markdown
10. **Give drift a fair chance before crediting selection.** Population-genetics
    likelihoods (Wright-Fisher, Moran, binomial-segregation) must estimate their
    variance/noise scale and confirm drift and selection are separable on the
    data; a single-cohort selection signal is cohort-scoped. See
    [`population-genetics-likelihood`](./population-genetics-likelihood.md).
```

- [ ] **Step 4: Run the linter to verify it is fully green (GREEN)**

Run (from `science/`): `uv run --frozen science skills lint --root ../skills`
Expected: exits 0, no issues. The pop-gen leaf now exists, so the forward links from Task 2 and Task 3 resolve, and this leaf's own links (to `likelihood-model-comparison.md` and `../data/genomics/copy-number-sv-qa.md`, both created earlier) resolve.

- [ ] **Step 5: Commit**

```bash
git add skills/statistics/population-genetics-likelihood.md skills/INDEX.md skills/statistics/SKILL.md
git commit -m "feat(skills): add statistics-population-genetics-likelihood leaf (fb-2026-05-03-002)

WF/Moran/binomial-segregation likelihood construction, neutral-vs-selection
comparison, t002-aware halt-on (estimated variance scale is ready, not blocked)
and single-cohort verdict scope. Loads likelihood-model-comparison + the CN/SV
QA leaf as companions; linter now reports zero errors."
```

---

## Task 5: Wire the leaves into `plan-analysis`

**Files:**
- Modify: `commands/plan-analysis.md` (Leaf Selection Rubric table + Validation Pressure Scenarios)
- Test: `science/tests/test_command_docs.py`

- [ ] **Step 1: Add the two rubric rows**

In `commands/plan-analysis.md`, in the "Leaf Selection Rubric" table, after the row beginning `| SBS signatures, TMB, dN/dS, dNdScv, driver ranking |`, add:
```markdown
| CN segments, scWGS/DLP+ per-cell CN, SV/breakpoints, AmpliconArchitect/AmpliconClassifier, ecDNA | `data-genomics-copy-number-sv-qa`, `statistics-power-floor-acknowledgement`, `statistics-sensitivity-arbitration` |
| Likelihood model fit, AIC/BIC/LRT, Wright-Fisher/Moran/binomial-segregation, selection-vs-neutral | `statistics-likelihood-model-comparison`, `statistics-population-genetics-likelihood`, `statistics-sensitivity-arbitration` |
```

- [ ] **Step 2: Add a validation-pressure scenario**

In `commands/plan-analysis.md`, in the "Validation Pressure Scenarios" numbered list, add item 5:
```markdown
5. **ecDNA selection-vs-neutral on per-cell scWGS (e.g. Bafna-style binomial segregation on DLP+)** - include `data-genomics-copy-number-sv-qa` for the per-cell CN calls, `statistics-population-genetics-likelihood` for the WF/Moran/segregation likelihoods, `statistics-likelihood-model-comparison` for the AIC/BIC/LRT comparison, plus `statistics-power-floor-acknowledgement` and `statistics-sensitivity-arbitration`. A single-cohort selection signal is cohort-scoped pending independent replication.
```

- [ ] **Step 3: Run the command-docs test (RED→GREEN check)**

Run (from `science/`): `uv run pytest tests/test_command_docs.py -q`
Expected: PASS. The relevant tests (`test_plan_analysis_command_covers_pressure_scenarios`, `test_plan_analysis_command_defines_methodology_readiness_workflow`) assert presence of the existing required strings and impose no count, so the added rows and 5th scenario do not break them. These tests do **not** themselves validate the new rubric leaf IDs — the skills linter's INDEX-coverage check (Tasks 2–4) is what guarantees every referenced leaf file exists.

- [ ] **Step 4: Run the skills linter again to confirm still green**

Run (from `science/`): `uv run --frozen science skills lint --root ../skills`
Expected: exits 0.

- [ ] **Step 5: Commit**

```bash
git add commands/plan-analysis.md
git commit -m "feat(plan-analysis): route CN/SV/amplicon + likelihood model-comparison tasks to new leaves

Two leaf-selection rubric rows (CN/SV/amplicon; likelihood model comparison /
pop-gen) and an ecDNA selection-vs-neutral validation-pressure scenario."
```

---

## Task 6: Verify, close feedback, land

**Files:**
- Read-only: t002/t007 plans + pre-registration in `~/d/cancer/mechanisms/evolution`
- Feedback: `~/.config/science/feedback/fb-2026-05-03-001.yaml`, `fb-2026-05-03-002.yaml`
- Memory: `~/.claude/projects/-mnt-ssd-Dropbox-science/memory/`

- [ ] **Step 1: Full verification gate**

Run (from `science/`):
```bash
uv run --frozen science skills lint --root ../skills
uv run pytest tests/test_command_docs.py -q
```
Expected: linter exits 0; `test_command_docs` passes.

- [ ] **Step 2: Content-fidelity check against the real tasks**

Read `~/d/cancer/mechanisms/evolution/doc/plans/2026-05-03-t002-bafna-binomial-segregation-on-lee2026-gbm0510-analysis-plan.md`, the t007 plan, and `doc/meta/pre-registration-h003-t002-ecdna-selection.md`. Confirm:
- the genomics leaf's checklist/failure-modes cover what t007 (bulk AA/AC) and t002 (per-cell scWGS CN) needed;
- the pop-gen leaf's halt-on does **not** block t002 (which estimates σ₀² on a per-cell-generation axis), and its verdict-scope rule matches the pre-reg's Lee2026-local promotion limitation.
Record the check as a sentence in the final commit/PR message. If a gap is found, amend the relevant leaf and re-run Step 1 before continuing.

- [ ] **Step 3: Close the two feedback items**

Run (from `science/`):
```bash
uv run science feedback update fb-2026-05-03-001 --status addressed --resolution "Added skills/data/genomics/copy-number-sv-qa.md: CN segments (bulk + per-cell scWGS), SV/breakpoint, and AmpliconArchitect/AmpliconClassifier focal-amplicon/ecDNA QA in one leaf (ploidy/purity conditioning, AA/AC version drift, FFPE fragmentation, per-cell binning, classifier confidence, AA->AC non-independence). Wired into INDEX, the genomics SKILL hub, and the plan-analysis rubric + an ecDNA pressure scenario. Verified the checklist covers t002 (per-cell scWGS CN) and t007 (bulk AA/AC)."
uv run science feedback update fb-2026-05-03-002 --status addressed --resolution "Added two statistics leaves: likelihood-model-comparison (domain-agnostic AIC/BIC/LRT, nested vs non-nested, Jacobian re-expression for comparability, rare-event numerical precision, bootstrap selection stability) and population-genetics-likelihood (WF/Moran/binomial-segregation construction, neutral-vs-selection, t002-aware halt-on, single-cohort verdict scope) that loads the first as a companion. Wired into INDEX, the statistics SKILL hub, and the plan-analysis rubric + pressure scenario. Verified halt-on does not block t002's estimated-sigma_0^2 model."
```

- [ ] **Step 4: Update the triage memory**

In `~/.claude/projects/-mnt-ssd-Dropbox-science/memory/project_feedback_triage_themes.md`, mark T10 done and update the count to 27/27 (0 open). In `MEMORY.md`, update the triage line to "27/27 closed ... 0 open".

- [ ] **Step 5: Land**

```bash
git checkout main
git merge --ff-only docs/t10-skill-leaves
git push origin main
git branch -d docs/t10-skill-leaves
```

---

## Notes for the implementer

- Run all `science` / `pytest` commands from the `science/` directory (the package root). The skills/commands being edited live at the **repo root**, one level up (`../skills`, `../commands`).
- The leaf content above is final — copy it verbatim. Do not paraphrase or "improve" it during implementation; any wording change should go back through the design.
- Tasks 2 and 3 intentionally leave a documented forward `broken-relative-link` to the pop-gen leaf; do not try to "fix" it before Task 4 (e.g. by removing the companion link). It resolves when Task 4 creates the file.
