---
name: transcriptomics-cohort-qa
description: Use when ingesting or QA-reviewing a single transcriptomic cohort (bulk RNA-seq, microarray, or scRNA-seq; GEO, ArrayExpress, MMRF, HCA, recount, ARCHS4) before it enters analysis.
archetype: measurement-qa
provenance: internal
---

# Transcriptomic Cohort QA

Answers: is this single expression cohort trustworthy for downstream inference before it enters analysis?

## Sources & ingestion/construction

Public deposits — GEO, ArrayExpress, MMRF CoMMpass, HCA, recount3, ARCHS4 —
each carry idiosyncrasies: undocumented normalisation, mislabelled samples,
silent-failure modes that look plausible until they invalidate inference. The
primary expression matrix arrives either as an AnnData object (inspect `.X`,
and check `.raw` and `.layers["counts"]`) or as a tabular genes×samples deposit
(CSV/TSV, which has no `.X`). Every deposit's README describes what *should* be
there; this leaf is about verifying what *is* there before the cohort enters
analysis.

## Pre-flight checklist

Answer all of these in writing before running any downstream analysis:

- [ ] **Primary expression matrix — what is it actually?** Raw counts,
      log-normalised, batch-corrected, z-scored, or residualised? **Detect
      matrix orientation first** (which axis is samples vs genes — `obs` rows
      vs `var` rows for AnnData); a surprising fraction of deposits silently
      change the matrix contents between revisions. For AnnData input, inspect
      the matrix directly (a tabular genes×samples deposit has no `.X` — inspect
      the loaded array instead):
      ```python
      # AnnData only.
      sub = a[:200].X.toarray() if sparse.issparse(a.X) else a.X[:200]
      print(f"min={sub.min():.3f}, max={sub.max():.3f}, integer-like={(sub == sub.astype(int)).all()}")
      ```
      Integer + max in thousands → raw counts; float + max ≤ ~15 →
      log-normalised; float symmetric around 0 → z-scored/residualised; float +
      max in thousands → linear normalised (TPM-like). Many AnnData deposits
      keep transformed values in `.X` and raw counts in `.layers["counts"]` or
      `.raw` — check both.
- [ ] **Gene-identifier axis.** Symbols (HGNC for human), Ensembl IDs, RefSeq,
      probe IDs, or "gene names" Excel has corrupted (`SEPT1` → `1-Sep`)?
      Resolve to a canonical ID layer at ingest. Symbol churn is real —
      `MARCH1` is now `MARCHF1`.
- [ ] **Sample identifier.** Patient, cell, library, technical replicate, or
      run? Collapse or exclude duplicates. GEO `geo_accession` is
      unique-per-sample; `Sample_title` is not. MMRF samples can have multiple
      time points per patient.
- [ ] **Cohort definition.** Diseased vs healthy, treated vs untreated, primary
      vs metastasis? Confirm the stage / treatment / disease columns are
      populated for every sample you intend to use.
- [ ] **Normalization state recorded.** Record and verify what normalisation the
      depositor applied. Whether that normalisation is *compatible* with a
      particular meta-analysis is a cross-cohort decision — see
      `data-integration.md`.
- [ ] **Single-cohort batch PCA.** Quick PCA coloured by batch, run, and
      biological group. If batch separates more strongly than biology, you have
      a confound; the cross-experiment remedy is a `data-integration.md`
      decision, not a single-cohort one.

## QA metrics

Detect matrix orientation before computing any per-axis metric — never assume
`.X.shape[0]` is samples.

| Metric | Passing range | Meaning of failure |
|---|---|---|
| `n_unique(sample_id)` vs length of the detected sample/cell axis | equal | non-unique sample IDs → hidden replicates/duplicates that bias per-sample statistics |
| Integer-like fraction of the primary expression matrix (200-row sample) | ≈1.0 for claimed raw counts; ≈0 for claimed transformed | matrix scale contradicts the README → wrong transformation assumed downstream |
| Per-group fraction of samples dropped by a QC filter | comparable across stratification groups | a group over-represented in the dropped fraction → filter is confounded with the question |

## Common failure modes

- **README says vs matrix is.** Documentation describes "what should be there,"
  not "what is there." Treat it as a hypothesis: if the README says counts are
  integer, sample 200 rows and check; if it says samples are unique, check
  `n_unique` against the detected sample axis; if it says cells are QC-filtered,
  check the per-cell metric distributions yourself.
- **Unlogged preprocessing decisions.** Filter thresholds, transformation
  choices, batch handling, and sample exclusions left without a provenance
  sidecar cannot be reconstructed or audited later.
- **Filters that don't commute with the question.** Detection-rate-per-gene
  filters drop genes low in some groups but high in others (removing biology,
  e.g. immune markers in a non-immune-enriched cohort); `mean ± 3 SD` sample QC
  drops more samples from groups whose mean is shifted (treatment-confounded
  filtering); doublet calling on aggregated batches masks batch-specific rates.
  When in doubt, filter once on the full cohort, log the mask, and check that no
  group is over-represented in the dropped fraction.

## Halt-On Conditions

- The contents of the primary expression matrix (or the applicable AnnData
  layer) cannot be determined from the data plus metadata.
- Sample identifiers are non-unique and no collapse/exclusion rule is defined.
- A QC filter drops a stratification group asymmetrically and no filter mask was
  logged.

## Minimum output package

    cohort-qa/
      summary.md          # what was checked, which Halt-On Conditions were evaluated, verdict
      cohort_audit.json   # raw + after-each-filter sample/cell/patient counts; patients
                          # dropped with reasons; gene-universe size at QC pass;
                          # normalisation status; batch-metadata schema

## Success test

Does the produced QA package contain the named files, and does the summary state which Halt-On Conditions were evaluated?

## Companion Skills

- `SKILL.md` — the transcriptomics router.
- `data-integration.md` — the multi-cohort integration decision that consumes this QA.
- `bulk-rnaseq-qa.md`, `microarray-qa.md`, `scrna-qa.md` — platform-specific QA.
- the `science-data-management` skill — Data-Package substrate for the cohort_audit sidecar.
