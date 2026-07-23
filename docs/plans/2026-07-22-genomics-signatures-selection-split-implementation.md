# Genomics Signatures/Selection Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `skills/bio/genomics/mutational-signatures-and-selection.md` into two single-concern leaves — `mutational-signatures-qa.md` (measurement-qa, owns TMB) and `driver-selection.md` (analysis-discipline) — and reconcile the genomics router and all cross-references.

**Architecture:** Create both new leaves while the old leaf still exists (no dangling references), then one atomic "flip" task retargets every reference, `git rm`s the old leaf, and regenerates the codex mirror. Sibling companion links are backticked only in Task 1 and converted to markdown links in Task 2, so every task is green and no reference stays permanently link-exempt. The controller runs the full-suite green gate.

**Tech Stack:** Markdown skill leaves; `science skills lint`; pytest content-guard tests; `scripts/generate_codex_skills.py`.

## Global Constraints

- Both new leaves use the **exact section headings from their archetype templates** (`skills/meta/templates/measurement-qa.md`, `skills/meta/templates/analysis-discipline.md`). The linter only mechanically enforces `## Halt-On Conditions` for measurement-qa; template fidelity elsewhere is a hard requirement of this plan, not a lint outcome.
- New leaf `name:` values carry the `genomics-` subject prefix; filenames are bare. `measurement-qa` → `## Halt-On Conditions` required; `analysis-discipline` → `## Halt / escalation`, no Halt-On section.
- A leaf declares EITHER `sources:` OR `provenance:`, never both. Both new leaves use `sources:` only: signatures → `[cosmic-signatures, focr-tmb-harmonization]`, selection → `[dndscv]`. `cosmic-signatures`/`dndscv` are already registered; `focr-tmb-harmonization` is ADDED to `skills/sources.yaml` in Task 1 (the leaf teaches substantial TMB methodology and must carry its provenance).
- Output packages land under the canonical `results/<workflow>/<slug>/<qa_step>/` (`<slug>` = `aNNN-description`, project-root-relative). NOT `results/<analysis>/…`. Per `data-management/conventions.md`, the lightweight manifest/config/report records are tracked in-repo; the bulk Parquet resources are payload governed by the data-boundary policy (not committed here). Each step directory carries a `datapackage` descriptor.
- Every leaf file has exactly one `skills/INDEX.md` machine entry and vice-versa.
- No AI-attribution trailers/footers on commits. No "legacy"/"compatibility" layers. Use `~/d/` (not absolute) in any doc path text.
- Commit after each task. Do not push. The controller (not a subagent) runs the full pytest suite for the green gate. Regenerate `codex-skills/` after editing any codex input (`commands/*.md`); never hand-edit `codex-skills/`.

## Pre-Flight Plan Review

- **Non-goal:** do NOT rewrite `bio/genomics/SKILL.md` onto the full router template. Only its layers table, ordering rule, and stale count-prose change.
- **Sibling-heading divergence (accepted, flagged):** the two existing genomics measurement-qa leaves use an older heading convention — as do most measurement-qa leaves corpus-wide, so reshaping only these two would be arbitrary. The new leaves are template-exact; bringing the existing corpus into line is a separate **corpus-wide measurement-qa conformance pass**, out of scope here.
- **All-green ordering:** the old leaf stays on disk and in INDEX through Tasks 1–2; sibling links are backticked in Task 1 and converted to markdown links in Task 2; Task 3 atomically retargets every reference, deletes the old leaf, and regenerates codex. No RED window.
- **Guard risk low** (verified): no test asserts on the split leaf's content or filename; the "signature" test hits are statistical model-signatures in `commands/review-pipeline.md`.

---

### Task 1: Create the mutational-signatures-qa leaf

**Files:**
- Create: `skills/bio/genomics/mutational-signatures-qa.md`
- Modify: `skills/INDEX.md` (insert one machine entry)

**Interfaces:**
- Produces: leaf `genomics-mutational-signatures-qa`; owns TMB. Sibling ref to `driver-selection.md` is backticked here (converted to a markdown link in Task 2).

- [ ] **Step 1: Create the leaf file** with exactly this content:

````markdown
---
name: genomics-mutational-signatures-qa
description: Use when analyzing SBS/DBS/ID mutational signatures, tumor mutational burden, or signature assignment from somatic mutation data.
archetype: measurement-qa
sources: [cosmic-signatures, focr-tmb-harmonization]
---

# Mutational Signature QA

Answers: is a fitted mutational-signature spectrum, assignment, or burden summary
trustworthy for inference?

Mutation counts are not exchangeable across genome, gene, cancer type, assay, or
mutational process, and the two analyses here realize the opportunity model
differently: signature spectra need trinucleotide-context opportunity for the
matching genome build, while tumor mutational burden needs eligible mutations per
callable (interrogated) megabase. Counts without the appropriate opportunity
model are descriptive only.

## Sources & ingestion/construction

Reference signatures come from COSMIC (`cosmic-signatures`). SBS96 (or DBS/ID)
spectra are constructed from eligible variants carrying reference context from
the matching genome build. Tumor mutational burden (TMB) is constructed as
eligible mutations per callable (interrogated) megabase, following a documented
harmonization procedure (`focr-tmb-harmonization`) for numerator definition and
cross-assay comparability. Record the COSMIC release and the exact signature
database file or checksum used for assignment.

## Pre-flight checklist

- [ ] **Mutation opportunity** recorded by sample, panel, trinucleotide context,
  and genome build; exome/panel data carry exome/panel-appropriate opportunity
  normalization.
- [ ] **Signature input eligibility**: SBS96 spectra built from eligible SNVs
  with reference context from the matching genome build.
- [ ] **TMB numerator and denominator**: eligible-variant definition
  (coding/noncoding, synonymous handling) and callable/interrogated-megabase
  denominator recorded per assay; numerator, denominator, and calibration rules
  identical across any samples being compared. Panel and exome TMB are not
  comparable without harmonization (`focr-tmb-harmonization`).
- [ ] **Reference signature version**: COSMIC version, genome build, exome-vs-
  genome setting, and whether split signatures (e.g. SBS40a/b/c) are collapsed
  or retained.
- [ ] **Cancer-type restrictions** applied only when pre-committed
  (over-restriction hides novel processes; no restriction overfits low-count
  spectra).
- [ ] **Cohort-stage and treatment**: primary-only vs treated/relapse cohorts not
  silently pooled (therapy-induced signatures shift burden).

## QA metrics

| Metric | Passing range | Meaning of failure |
|---|---|---|
| Total mutations per spectrum | ≥ precommitted assay-specific threshold recorded in config | Low-count spectra produce unstable assignments |
| Reconstruction error | ≤ precommitted method-specific reconstruction-error limit | Signatures do not explain the sample |
| TMB per callable Mb | Finite and non-negative; denominator > 0; identical numerator / denominator / calibration rules across compared samples | Uncomparable or inflated burden from a wrong denominator, eligibility, or calibration rule |
| Known positive controls | Present where expected (UV in melanoma, tobacco in lung, SBS1 age trend) | Missing expected control signal flags a construction or mapping error |
| Forbidden signatures | Absent (e.g. strong UV in hematologic cancer, SBS4 in brain) | Presence flags a mapping or reference error |
| SBS1/SBS5 exposures | Interpreted only with tissue-aware controls and pre-specified rules | Clock-like signals over-interpreted as biology |
| Hypermutator processes | Flagged (MSI, POLE, APOBEC, UV) | Unflagged hypermutators dominate downstream rankings |

For sample-level assignment, label low-count spectra as underpowered instead of
forcing precise proportions.

## Common failure modes

- **Panel spectra treated as exomes** → sparse, panel-biased SBS96 → invalid
  unrestricted assignment.
- **COSMIC version drift** → signature names and splits change across releases →
  incomparable assignments unless the exact database file or checksum is stored.
- **Study pooling before normalization** → large studies dominate spectrum and
  burden estimates unless per-study effects are modeled.

## Halt-On Conditions

- Opportunity model is unknown for panel-derived data.
- COSMIC signature database version is not pinned.
- TMB is reported without a recorded callable-megabase denominator.

## Minimum output package

Place this QA step under the workflow-result package `results/<workflow>/<slug>/`
(see [`../../data-management/conventions.md`](../../data-management/conventions.md)
for placement) and generate a `datapackage.json` descriptor for the directory
(see [`../../data-management/frictionless.md`](../../data-management/frictionless.md)
for descriptor format):

```
results/<workflow>/<slug>/signature_qa/
  datapackage.json
  input_manifest.json
  spectra_sbs96.parquet
  opportunity_model.parquet
  tmb.parquet
  signature_database_manifest.json
  signature_assignments.parquet
  reconstruction_error.parquet
  low_count_flags.parquet
  hypermutator_flags.parquet
  qa_summary.md
```

The summary should state whether input calls and denominators were already
audited. If not, load `somatic-mutation-qa.md` first and complete that audit
before treating signatures or burden as verdict-bearing.

## Success test

The produced QA package contains the named files (including `tmb.parquet` and its
recorded callable-megabase denominator), and the summary states which Halt-On
Conditions were evaluated and whether inputs were audited upstream.

## Companion Skills

- [`somatic-mutation-qa.md`](somatic-mutation-qa.md) - input-call and denominator QA required before signature or burden verdicts.
- `driver-selection.md` - gene-level selection and dN/dS inference on the same cohort.
- [`../../study-design/power-floor-acknowledgement.md`](../../study-design/power-floor-acknowledgement.md) - low-count signature and burden tests.
- [`../../study-design/sensitivity-arbitration.md`](../../study-design/sensitivity-arbitration.md) - pre-committed arbitration for hypermutator, panel, and low-count sensitivities.
````

- [ ] **Step 2: Register the TMB harmonization source.** In `skills/sources.yaml`, insert this entry immediately AFTER the `dndscv:` block (before `frictionless-spec:`):

```
focr-tmb-harmonization:
  title: "Establishing guidelines to harmonize tumor mutational burden (TMB): in silico assessment of variation in TMB quantification across diagnostic platforms"
  authors: ["Friends of Cancer Research TMB Harmonization Project"]
  url: "https://jitc.bmj.com/content/8/1/e000147"
  kind: paper
  last_checked: "2026-07-22"
```

(Required before lint: the leaf declares `sources: [cosmic-signatures, focr-tmb-harmonization]`, so an unregistered id would fail `unknown-source-ref`.)

- [ ] **Step 3: Add the INDEX entry.** In `skills/INDEX.md`, immediately AFTER the line
  `` - `genomics-mutational-signatures-and-selection`: `skills/bio/genomics/mutational-signatures-and-selection.md` `` insert:

```
- `genomics-mutational-signatures-qa`: `skills/bio/genomics/mutational-signatures-qa.md`
```

(The old `genomics-mutational-signatures-and-selection` entry STAYS; it is removed in Task 3.)

- [ ] **Step 4: Verify skills lint is green.**

Run: `cd science && uv run --frozen science skills lint --root ../skills`
Expected: exit 0, NO issues. The new leaf's markdown links all target existing files (`somatic-mutation-qa.md`, the two `study-design/` leaves, `conventions.md`, `frictionless.md`); `focr-tmb-harmonization` now resolves in `sources.yaml`; the not-yet-created sibling `driver-selection.md` is backticked, so it does not dangle.

- [ ] **Step 5: Commit.**

```bash
git add skills/bio/genomics/mutational-signatures-qa.md skills/sources.yaml skills/INDEX.md
git commit -m "feat(skills): add genomics-mutational-signatures-qa leaf"
```

---

### Task 2: Create the driver-selection leaf and link the siblings

**Files:**
- Create: `skills/bio/genomics/driver-selection.md`
- Modify: `skills/INDEX.md` (insert one machine entry); `skills/bio/genomics/mutational-signatures-qa.md` (convert the sibling ref to a markdown link)

**Interfaces:**
- Consumes: `mutational-signatures-qa.md` (Task 1).
- Produces: leaf `genomics-driver-selection`. After this task both new leaves exist and every sibling reference is a markdown link, so skills lint is fully green with full drift detection.

- [ ] **Step 1: Create the leaf file** with exactly this content:

````markdown
---
name: genomics-driver-selection
description: Use when analyzing driver-gene enrichment, dN/dS, dNdScv, replication-timing bias, or positive/negative selection signals from somatic mutation data, before interpreting a gene rank as selection.
archetype: analysis-discipline
sources: [dndscv]
---

# Driver and Selection Inference

Answers: regardless of the method, what must hold before a gene rank may be
interpreted as selection? Mutation counts are not exchangeable across gene,
cancer type, assay, or mutational process; raw mutation frequency is not a
selection test.

## Triggering condition

Gene-level selection, driver-gene enrichment, dN/dS, dNdScv, replication-timing
bias, or positive/negative selection analysis on somatic mutation data.

## Required reasoning / check / precommitment

- **Opportunity model.** Coding length, trinucleotide context, and local
  mutation-rate covariates per gene, recorded before ranking.
- **Context-aware method.** dNdScv or another context-aware method; raw mutation
  frequency is not a selection test.
- **Pathway membership.** For pathway-level tests, membership defined before
  looking at results, with overlapping pathways handled explicitly.
- **Hypermutator handling.** Recorded treatment of MSI/POLE/APOBEC hypermutators,
  which can dominate rankings.
- **Known-driver lists as priors only.** Used as validation or priors, never as
  circular evidence for discovering the same drivers.

## Decision rule or reasoning criteria

Run these bias audits before interpreting ranks:

1. Correlate gene score with coding length.
2. Correlate gene score with replication timing (or a proxy if available).
3. Stratify by cancer type and assay class.
4. Repeat with hypermutators excluded.
5. Check whether genes absent from targeted panels were treated as zero.
6. Compare known-driver enrichment against a matched negative-control gene set.

Separate positive selection, negative selection, and passenger burden. An audit
whose covariate is unavailable (e.g. no replication-timing proxy) must be
declared unrun: a rank may not be reported as unconfounded along an axis that was
not tested. If any available technical covariate (coding length, replication
timing, expression, panel enrichment, cancer-type specificity) explains the
ranking as well as the biological hypothesis, the result is confounded unless the
model adjusts for it.

## Outcomes (pass / fail / indeterminate, or branch/threshold)

- **Pass.** The signal survives covariate adjustment and every applicable bias
  audit; a context-aware model separates selection from technical covariates.
- **Fail (confounded).** An available technical covariate explains the ranking as
  well as selection and the model does not adjust for it.
- **Indeterminate.** Counts are too low (rare genes, small cohorts) to
  distinguish selection from noise, OR a bias axis could not be tested — the rank
  is indeterminate along that untested axis and may not be reported as
  unconfounded there.

## Halt / escalation

- The opportunity model is missing or cannot be verified for the mutation set
  (per-gene callable territory, coding length, and context are prerequisites; a
  rank may not be interpreted without them).
- Driver ranks correlate with coding length and no length-aware model is run.
- Validation is circular: a method tuned on CGC/Bailey drivers cannot use those
  same drivers as independent evidence of success.

## Required evidence & artifacts

Record the method, the covariates in the selection model, the negative-control
comparison, and the sensitivity results that change verdict interpretation. Place
this step under the workflow-result package `results/<workflow>/<slug>/` (see
[`../../data-management/conventions.md`](../../data-management/conventions.md) for
placement) and generate a `datapackage.json` descriptor for the directory (see
[`../../data-management/frictionless.md`](../../data-management/frictionless.md)
for descriptor format):

```
results/<workflow>/<slug>/driver_selection/
  datapackage.json
  input_manifest.json
  opportunity_model.parquet
  selection_covariates.parquet
  selection_results.parquet
  bias_audit.parquet
  selection_summary.md
```

The summary should state whether input calls and denominators were already
audited. If not, load `somatic-mutation-qa.md` first and complete that audit
before treating selection tests as verdict-bearing.

## Permitted reporting language

- Report "under positive selection" / "under negative selection" only after
  covariate adjustment and passing every applicable bias audit.
- Otherwise report the result as "confounded", "cannot distinguish selection from
  coding-length / expression / replication-timing bias", or "underpowered".
- Never present raw mutation frequency or a length-adjusted rank alone as
  evidence of selection.

## Success test

The opportunity model and every applicable bias audit were run before any gene
was called a driver, and every selection claim in the report uses only the
reporting language permitted by its audit outcome.

## Companion Skills

- [`somatic-mutation-qa.md`](somatic-mutation-qa.md) - input-call and denominator QA required before selection verdicts.
- [`mutational-signatures-qa.md`](mutational-signatures-qa.md) - signature decomposition and burden on the same cohort.
- [`../../study-design/power-floor-acknowledgement.md`](../../study-design/power-floor-acknowledgement.md) - low-power driver tests for rare genes.
- [`../../study-design/sensitivity-arbitration.md`](../../study-design/sensitivity-arbitration.md) - pre-committed arbitration for hypermutator, panel, and low-count sensitivities.
````

- [ ] **Step 2: Convert the signatures leaf's sibling reference to a markdown link.** In `skills/bio/genomics/mutational-signatures-qa.md`, REPLACE the Companion line:

```
- `driver-selection.md` - gene-level selection and dN/dS inference on the same cohort.
```

with:

```
- [`driver-selection.md`](driver-selection.md) - gene-level selection and dN/dS inference on the same cohort.
```

- [ ] **Step 3: Add the INDEX entry.** In `skills/INDEX.md`, immediately AFTER the `genomics-mutational-signatures-qa` line inserted in Task 1, insert:

```
- `genomics-driver-selection`: `skills/bio/genomics/driver-selection.md`
```

- [ ] **Step 4: Verify skills lint is fully green.**

Run: `cd science && uv run --frozen science skills lint --root ../skills`
Expected: exit 0, NO issues. Both new leaves now resolve every markdown link (including both sibling references); the old leaf is still present and listed.

- [ ] **Step 5: Commit.**

```bash
git add skills/bio/genomics/driver-selection.md skills/bio/genomics/mutational-signatures-qa.md skills/INDEX.md
git commit -m "feat(skills): add genomics-driver-selection leaf and link siblings"
```

---

### Task 3: Flip references and remove the old leaf

**Files:**
- Delete: `skills/bio/genomics/mutational-signatures-and-selection.md` (via `git rm`)
- Modify: `skills/INDEX.md`, `skills/bio/genomics/SKILL.md`, `skills/bio/genomics/somatic-mutation-qa.md`, `commands/plan-analysis.md`, `skills/data-management/SKILL.md`
- Regenerate: `codex-skills/` (because `commands/plan-analysis.md` is a codex generator input)

**Interfaces:**
- Consumes: both new leaves (Tasks 1–2).
- Atomic: after this task, no reference to the old leaf remains, the old leaf is gone, and `codex-skills/science-plan-analysis/` matches fresh generation.

- [ ] **Step 1: Remove the old INDEX entry.** In `skills/INDEX.md`, DELETE the line:

```
- `genomics-mutational-signatures-and-selection`: `skills/bio/genomics/mutational-signatures-and-selection.md`
```

- [ ] **Step 2: Update the genomics router layers table.** In `skills/bio/genomics/SKILL.md`, REPLACE the single row:

```
| Signatures and selection (analysis QA) | [`mutational-signatures-and-selection.md`](./mutational-signatures-and-selection.md) | opportunity-model omission, COSMIC version drift, length-confounded driver ranks, circular validation |
```

with these two rows:

```
| Signatures and burden (analysis QA) | [`mutational-signatures-qa.md`](./mutational-signatures-qa.md) | opportunity-model omission, COSMIC version drift, low-count / panel-biased spectra, TMB denominator errors |
| Selection (interpretation gate) | [`driver-selection.md`](./driver-selection.md) | length / expression / replication-confounded driver ranks, raw-frequency selection tests, circular validation |
```

- [ ] **Step 3: Update the genomics ordering rule.** In `skills/bio/genomics/SKILL.md`, REPLACE:

```
Always complete `somatic-mutation-qa.md` before treating signature or selection
results as verdict-bearing.
```

with:

```
Always complete `somatic-mutation-qa.md` before treating signature or selection
results as verdict-bearing. Both downstream leaves require an explicit
mutation-opportunity model, realized differently per analysis — signature spectra
in trinucleotide context, tumor mutational burden as eligible mutations per
callable (interrogated) megabase, selection scores in coding length, sequence
context, and local mutation rate; counts without the appropriate opportunity
model are descriptive only.
```

- [ ] **Step 4: Fix the stale count prose.** In `skills/bio/genomics/SKILL.md` "Anticipated growth", REPLACE `established for the existing two leaves.` with `established for the existing leaves.` (drop the hardcoded count).

- [ ] **Step 5: Retarget the somatic-mutation-qa back-reference.** In `skills/bio/genomics/somatic-mutation-qa.md`, REPLACE the Companion line:

```
- [`mutational-signatures-and-selection.md`](mutational-signatures-and-selection.md) - downstream SBS signatures, TMB, dN/dS, dNdScv, and driver-ranking analyses.
```

with two lines:

```
- [`mutational-signatures-qa.md`](mutational-signatures-qa.md) - downstream SBS/DBS/ID signatures and tumor mutational burden.
- [`driver-selection.md`](driver-selection.md) - downstream dN/dS, dNdScv, and driver-ranking selection inference.
```

- [ ] **Step 6: Retarget `commands/plan-analysis.md` routing row.** REPLACE:

```
| SBS signatures, TMB, dN/dS, dNdScv, driver ranking | `genomics-somatic-mutation-qa`, `genomics-mutational-signatures-and-selection`, `study-design-power-floor-acknowledgement`, `study-design-sensitivity-arbitration` |
```

with:

```
| SBS signatures, TMB, dN/dS, dNdScv, driver ranking | `genomics-somatic-mutation-qa`, `genomics-mutational-signatures-qa`, `genomics-driver-selection`, `study-design-power-floor-acknowledgement`, `study-design-sensitivity-arbitration` |
```

- [ ] **Step 7: Retarget `commands/plan-analysis.md` scenario 2.** REPLACE:

```
2. **cBioPortal targeted-panel mutation frequency or dN/dS analysis** - include `genomics-somatic-mutation-qa`, `genomics-mutational-signatures-and-selection` for dN/dS/TMB/driver ranking, `study-design-power-floor-acknowledgement`, `study-design-bias-vs-variance-decomposition`, and `study-design-sensitivity-arbitration`.
```

with:

```
2. **cBioPortal targeted-panel mutation frequency or dN/dS analysis** - include `genomics-somatic-mutation-qa`, `genomics-mutational-signatures-qa` for TMB and signatures, `genomics-driver-selection` for dN/dS and driver ranking, `study-design-power-floor-acknowledgement`, `study-design-bias-vs-variance-decomposition`, and `study-design-sensitivity-arbitration`.
```

- [ ] **Step 8: Retarget `skills/data-management/SKILL.md` routing line.** REPLACE:

```
- Mutational signatures, TMB, dN/dS, driver selection → `../bio/genomics/mutational-signatures-and-selection.md`.
```

with two lines:

```
- Mutational signatures, TMB → `../bio/genomics/mutational-signatures-qa.md`.
- dN/dS, dNdScv, driver selection → `../bio/genomics/driver-selection.md`.
```

- [ ] **Step 9: Remove the old leaf file.**

```bash
git rm skills/bio/genomics/mutational-signatures-and-selection.md
```

- [ ] **Step 10: Regenerate the codex mirror.**

Run: `cd science && uv run --frozen python ../scripts/generate_codex_skills.py`
Expected: prints "Generated Codex skills in …". Then `git status --porcelain codex-skills/` — the ONLY expected change is inside `codex-skills/science-plan-analysis/` (the mirrored `plan-analysis.md` body). If any OTHER codex path changes, stop and report.

- [ ] **Step 11: Verify skills lint + targeted content-guard/codex tests green.**

Run (each separately; do NOT run the full suite — the controller owns that):
```bash
cd science
uv run --frozen science skills lint --root ../skills
uv run --frozen pytest tests/test_command_docs.py tests/test_codex_skills.py -p no:cacheprovider
```
Expected: skills lint exit 0; both test modules pass. Report the numeric passed count (do not rely on the `-q` summary line, which the warnings avalanche can bury).

- [ ] **Step 12: Commit.**

```bash
# the old-leaf deletion is already staged by `git rm` in Step 9
git add skills/INDEX.md skills/bio/genomics/SKILL.md skills/bio/genomics/somatic-mutation-qa.md commands/plan-analysis.md skills/data-management/SKILL.md codex-skills/
git commit -m "refactor(skills): retarget genomics signature/selection refs and remove merged leaf"
```

---

### Task 4: Green gate (controller-run)

**The controller runs this directly — do NOT dispatch to a subagent** (recurring lesson: subagents background the long suite and stall).

- [ ] **Step 1: Full suite must exit zero.**

```bash
cd science || exit 1
uv run --frozen pytest -p no:cacheprovider
test_status=$?
echo "PYTEST_EXIT: $test_status"
exit "$test_status"
```
Expected: `PYTEST_EXIT: 0` AND a zero exit status (the block fails closed — the exit status is pytest's, not `echo`'s). The repository contract requires the full suite to pass; ANY failure blocks the merge and must be resolved (there is no "pre-existing failure" carve-out for the pytest gate — ruff/pyright history is irrelevant here). If a failure surfaces, triage it as a real defect.

- [ ] **Step 2: Codex zero-additional-delta.** Re-run the generator on the committed tree and confirm the mirror already matches:

```bash
cd science && uv run --frozen python ../scripts/generate_codex_skills.py
git -C .. status --porcelain codex-skills/
```
Expected: empty output (the committed mirror matches fresh generation).

- [ ] **Step 3: Skills lint.** `cd science && uv run --frozen science skills lint --root ../skills` → exit 0.

- [ ] **Step 4: Final whole-branch review.** Use superpowers:requesting-code-review (opus). Assemble the branch review package with that skill's / the subagent-driven-development skill's `review-package` helper — the script lives in the skill's own directory, NOT in this repository, so invoke it by its skill-directory path (do not treat `scripts/review-package` as a repo-relative executable). Range: from `git merge-base main HEAD` to `HEAD`.

- [ ] **Step 5: Finish** via superpowers:finishing-a-development-branch.

## Self-Review

- **Spec coverage:** design §"two new leaves" (template-exact headings, TMB ownership, canonical output paths) → Tasks 1–2; §"router edits" + §"cross-reference reconciliation" → Task 3; §"guard/codex analysis" → Task 3 Steps 10–11 + Task 4. All covered.
- **Placeholder scan:** none — both leaves fully inlined with exact template headings; every edit gives exact before→after text.
- **Type/name consistency:** `genomics-mutational-signatures-qa`/`mutational-signatures-qa.md` and `genomics-driver-selection`/`driver-selection.md` used identically across INDEX, router, companions, commands, data-management. Signatures leaf carries `## Halt-On Conditions` (measurement-qa) and owns TMB (`tmb.parquet` + denominator rule); selection leaf carries `## Halt / escalation` (analysis-discipline), halts on a missing/unverifiable opportunity model, and uses "every applicable bias audit". Sibling links: backticked in Task 1, markdown links from Task 2 on.
