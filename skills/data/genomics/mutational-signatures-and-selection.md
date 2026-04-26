---
name: data-genomics-mutational-signatures-and-selection
description: Use when analyzing SBS/DBS/ID mutational signatures, tumor mutational burden, replication-timing bias, driver-gene enrichment, dN/dS, dNdScv, or selection signals.
---

# Mutational Signatures and Selection

Use when analyzing SBS/DBS/ID mutational signatures, tumor mutational burden,
replication-timing bias, driver-gene enrichment, dN/dS, dNdScv, or selection
signals from somatic mutation data.

Signature and selection analyses share one constraint: mutation counts are not
exchangeable across genome, gene, cancer type, assay, or mutational process.
Every result needs an explicit opportunity model.

## Pre-Flight Checks

1. **Mutation opportunity.** Record callable territory by sample, panel, gene,
   trinucleotide context, and genome build. Counts without opportunity are
   descriptive only.
2. **Signature input eligibility.** SBS96 spectra need eligible SNVs with
   reference context from the matching genome build. Exome and panel data need
   exome/panel-appropriate opportunity normalization.
3. **Reference signature version.** Record COSMIC version, genome build, exome
   vs genome setting, and whether split signatures such as SBS40a/b/c are
   collapsed or retained.
4. **Cancer-type restrictions.** Restrict assignment to plausible signatures
   for the cancer family only when that rule is pre-committed. Over-restriction
   hides novel or rare processes; no restriction overfits low-count spectra.
5. **Gene length and sequence context.** Driver rankings and dN/dS need coding
   length, trinucleotide opportunity, and local mutation-rate covariates.
6. **Cohort-stage and treatment.** Therapy-induced signatures and relapse
   cohorts can shift both burden and selection. Primary-only and treated/relapse
   cohorts should not be silently pooled.

## Signature QA

| Check | Why it matters |
|---|---|
| Total mutations per spectrum | Low-count spectra produce unstable assignments |
| Reconstruction error | High error means signatures do not explain the sample |
| Known positive controls | UV in melanoma, tobacco in lung, SBS1 age trend |
| Forbidden signatures | Strong UV in hematologic cancer or SBS4 in brain may flag mapping errors |
| SBS1/SBS5 exposures | Clock-like signals; compare with age/replication timing only with tissue-aware controls and pre-specified interpretation |
| Hypermutator processes | MSI, POLE, APOBEC, UV can dominate downstream rankings |

For sample-level signature assignment, label low-count spectra as underpowered
instead of forcing precise proportions.

## Selection QA

- Use dNdScv or another context-aware method for gene-level selection. Raw
  mutation frequency is not a selection test.
- Include known driver lists only as validation or priors, not as circular
  evidence for discovering the same drivers.
- Separate positive selection, negative selection, and passenger burden.
- Check whether top-ranked genes are simply long, late-replicating, highly
  expressed, panel-enriched, or cancer-type-specific.
- For pathway-level tests, define pathway membership before looking at results
  and handle overlapping pathways explicitly.

## Bias Audits

Run these before interpreting ranks:

1. Correlate gene score with coding length.
2. Correlate gene score with replication timing or a proxy if available.
3. Stratify by cancer type and assay class.
4. Repeat with hypermutators excluded.
5. Check whether genes absent from targeted panels were treated as zero.
6. Compare known driver enrichment against a matched negative-control gene set.

If any technical covariate explains the ranking as well as the biological
hypothesis, report the result as confounded unless the model adjusts for it.

## Common Failure Modes

- **Panel spectra treated as exomes.** SBS96 from small panels is often too
  sparse and panel-biased for unrestricted assignment.
- **COSMIC version drift.** Signature names and splits change across releases.
  Store the exact database file or checksum.
- **Length-adjusted ranks interpreted as selection.** Length adjustment alone
  does not account for context, expression, replication timing, or cancer type.
- **Study pooling before normalization.** Large studies dominate spectrum and
  driver estimates unless per-study effects are modeled.
- **Circular validation.** A method tuned on CGC/Bailey drivers cannot use those
  same drivers as independent evidence of success.

## Reporting

Include:

- mutation universe and opportunity model,
- assay class and panel handling,
- signature database version,
- low-count and hypermutator rules,
- covariates in the selection model,
- sensitivity results that change verdict interpretation,
- known limitations that remain after adjustment.

## Minimum Artifacts

Generate a `datapackage.json` for this directory; see [`../frictionless.md`](../frictionless.md).

```
results/<analysis>/signature_selection_qa/
|-- input_manifest.json
|-- spectra_sbs96.parquet
|-- opportunity_model.parquet
|-- signature_database_manifest.json
|-- signature_assignments.parquet
|-- reconstruction_error.parquet
|-- low_count_flags.parquet
|-- hypermutator_flags.parquet
|-- selection_covariates.parquet
|-- bias_audit.parquet
`-- qa_summary.md
```

The summary should state whether input calls and denominators were already
audited. If not, load `somatic-mutation-qa.md` first and complete that audit
before treating signatures or selection tests as verdict-bearing.

## Companion Skills

- [`somatic-mutation-qa.md`](somatic-mutation-qa.md) - input-call and denominator QA required before signature or selection verdicts.
- [`../../statistics/power-floor-acknowledgement.md`](../../statistics/power-floor-acknowledgement.md) - low-count signature and driver tests.
- [`../../statistics/sensitivity-arbitration.md`](../../statistics/sensitivity-arbitration.md) - pre-committed arbitration for hypermutator, panel, and low-count sensitivities.
