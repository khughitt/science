---
name: data-expression
description: Use when ingesting, preprocessing, or QA-reviewing transcriptomic datasets, including bulk RNA-seq, microarray, scRNA-seq, GEO, ArrayExpress, MMRF, HCA, recount, or ARCHS4 cohorts, especially before meta-analysis or when suspicious results may be preprocessing artifacts.
---

# Expression Data — Preprocessing & QA

Practical guidance for ingesting and quality-assessing transcriptomic
data. Every public deposit comes with idiosyncrasies: undocumented
normalisation, mislabelled samples, mixed-platform aggregations, and
silent-failure modes that look plausible until they invalidate downstream
inference. This skill collects the patterns and minimum-viable QA checks
that prevent the most common landmines.

## Three modalities, three QA mindsets

The three platform families share much of the QA toolkit but differ in
what can go wrong by default. Use the leaf files as platform-specific
reference; use this hub to remember the cross-cutting patterns.

| Modality | Leaf | Dominant failure modes |
|---|---|---|
| Bulk microarray | [`microarray-qa.md`](./microarray-qa.md) | platform heterogeneity, probe-to-gene mapping ambiguity, normalisation method conflated with cohort effects, batch / scanner artifacts |
| Bulk RNA-Seq | [`bulk-rnaseq-qa.md`](./bulk-rnaseq-qa.md) | counts vs TPM vs FPKM scale confusion, low library complexity, contamination (rRNA / DNA / adapter), 3'/5' bias from old library prep, gene-model version drift |
| Single-cell RNA-Seq | [`scrna-qa.md`](./scrna-qa.md) | doublets, ambient RNA, dying cells, batch / 10x-channel effects, cell-type composition shifts mistaken for biology |

## Universal pre-flight checklist

Before running any downstream analysis on a newly-acquired transcriptomic
dataset, answer all of these in writing:

1. **What is `.X` actually?** Raw counts, log-normalised, batch-corrected,
   z-scored, residualised? **Read the depositor's README and verify by
   inspecting the matrix yourself.** First confirm matrix orientation
   (`obs` rows vs `var` rows, samples vs genes); then check scale. A
   surprising fraction of deposits silently change the contents of `.X`
   between revisions.
   ```python
   sub = a[:200].X.toarray() if sparse.issparse(a.X) else a.X[:200]
   print(f"min={sub.min():.3f}, max={sub.max():.3f}, integer-like={(sub == sub.astype(int)).all()}")
   ```
   - Integer + max in thousands → raw counts.
   - Float + max ≤ ~15 → log-normalised (log1p of counts) or log2 + 1.
   - Float + range [-X, +X] symmetric around 0 → z-scored or residualised.
   - Float + max in thousands → linear normalised (TPM-like).
   Also check `.raw` and `.layers["counts"]`: many AnnData deposits keep
   transformed values in `.X` and raw counts in a layer.
2. **What gene identifier is the row axis?** Symbols (HGNC for human),
   Ensembl IDs, RefSeq, probe IDs (Affymetrix), or "gene names" that
   Excel has corrupted (`SEPT1` → `1-Sep`)? Resolve to a canonical ID
   layer at ingest time. Symbol churn is real — `MARCH1` is now `MARCHF1`.
3. **What is the sample identifier?** Patient, cell, library, technical
   replicate, run? Are there duplicates that need collapsing or
   excluding? GEO `geo_accession` is unique-per-sample; `Sample_title`
   is not. MMRF samples can have multiple time points per patient.
4. **What is the cohort definition?** Diseased vs healthy, treated vs
   untreated, primary vs metastasis? Is the labeling in `obs` or
   buried in a separate supplemental table? **Always check that the
   stage / treatment / disease columns are populated for every sample
   you intend to use.**
5. **Is the depositor's normalisation compatible with your meta-analysis?**
   If you're aggregating effect sizes across cohorts, scale differences
   matter (see MM30 D1: z-score before metafor). If you're aggregating
   p-values via SumZ, scale differences are tolerated but distributional
   assumptions are not.
6. **Are there obvious batch effects?** Run a quick PCA coloured by
   batch, run, and biological group. If batch separates more strongly
   than biology, you have a confound that needs explicit handling
   (ComBat, RUV, mixed-effects, exclusion).

## Idiom: validate by inspection, not by trust

Public deposits often contain README text that describes "what should
be there" rather than "what is there". Treat the documentation as a
hypothesis, not a fact:

- If the README says counts are integer, sample 200 rows and check.
- If the README says samples are unique, check `n_unique == n_rows`.
- If the README says cells are filtered for QC, check the per-cell
  metric distributions yourself.

The cost of one read-and-check pass is 5 minutes. The cost of building
a meta-analysis on a misinterpreted deposit and discovering it later
is days to weeks.

## Idiom: log every decision in a sidecar

Every preprocessing decision (filter threshold, transformation choice,
batch handling, sample exclusion) should produce a row in a
provenance sidecar that travels with the processed data. The format
doesn't matter; that the trail exists matters. Frictionless Data
Packages (see [`../SKILL.md`](../SKILL.md)) are a clean substrate;
plain text logs work too.

A single `cohort_audit.json` per cohort with:
- raw cell / sample / patient counts
- counts after each filter step
- patients dropped with reasons
- gene-universe size at QC pass
- normalisation status
- batch metadata schema

…is sufficient to reconstruct any decision later.

## Idiom: filter steps must commute with the question

If your downstream analysis stratifies by some covariate (disease stage,
cytogenetic group, treatment), preprocess in a way that doesn't change
group composition asymmetrically. Common pitfalls:

- **Filtering on detection rate per gene** drops genes with low
  expression in some groups but high in others (e.g., immune-cell
  markers in a non-immune-cell-enriched cohort). The filter then
  removes biological signal. Filter on raw count threshold instead,
  or apply detection-rate filters within group then take the union.
- **Sample QC thresholds set by `mean ± 3 SD`** drop more samples from
  groups whose mean is shifted from the cohort mean. If treatment
  shifts library complexity, this is mistreatment-confounded
  filtering.
- **Doublet calling on aggregated batches** masks batch-specific doublet
  rates. Per-batch doublet calls then aggregated.

When in doubt, do the filter once on the full cohort, log the filter
mask, and check that no group is over-represented in the dropped
fraction.

## Cross-platform aggregation: the fundamental tension

The whole point of a meta-analysis is to aggregate across cohorts.
Different platforms have different distributional shapes (microarray
intensities vs UMI counts vs read counts vs TPM). Three clean
strategies:

1. **Within-platform association testing → aggregate test statistics.**
   Run DESeq2 / limma / logistic / Cox per dataset; aggregate p-values
   (Stouffer's, Fisher's) or standardised effects (random-effects
   metafor). This is MM30's primary approach.
2. **Common reference normalisation.** Map all cohorts to a shared
   reference scale (gene-set rank, percentile, z-score) before
   testing. Loses platform-specific information but enables direct
   pooling.
3. **Hierarchical models with platform random effects.** The most
   principled but compute- and assumption-heavy. Often worth it for
   high-stakes confirmatory inference.

State which strategy you're using before designing per-cohort
preprocessing. The choice cascades.

## When to invoke

- First contact with a new transcriptomic deposit.
- Designing a meta-analysis that will pool across platforms.
- Debugging a suspicious downstream result that might be preprocessing-
  driven.
- Writing the data section of a methods paper or preprint.
- Reviewing someone else's preprocessing pipeline.

## Companion skills

- [`../SKILL.md`](../SKILL.md) — generic data-management conventions.
- [`../frictionless.md`](../frictionless.md) — Frictionless Data Package
  format for the cohort_audit / preprocessing-provenance sidecars.
- [`../../statistics/SKILL.md`](../../statistics/SKILL.md) — statistical
  decisions that depend on data characteristics (count vs continuous,
  zero-inflation, etc.).
- [`../../research/SKILL.md`](../../research/SKILL.md) — literature
  context for QA decisions that depend on the field consensus
  (e.g., what counts as a doublet rate).
