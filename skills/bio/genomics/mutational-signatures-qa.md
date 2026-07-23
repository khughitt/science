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
- [`driver-selection.md`](driver-selection.md) - gene-level selection and dN/dS inference on the same cohort.
- [`../../study-design/power-floor-acknowledgement.md`](../../study-design/power-floor-acknowledgement.md) - low-count signature and burden tests.
- [`../../study-design/sensitivity-arbitration.md`](../../study-design/sensitivity-arbitration.md) - pre-committed arbitration for hypermutator, panel, and low-count sensitivities.
