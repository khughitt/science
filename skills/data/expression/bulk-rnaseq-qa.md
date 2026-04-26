---
name: data-expression-bulk-rnaseq-qa
description: Use when ingesting or QA-reviewing bulk RNA-Seq cohorts (TCGA, GTEx, recount3, ARCHS4, GEO, MMRF), especially before meta-analysis.
---

# Bulk RNA-Seq QA

Practical QA for bulk RNA-Seq cohorts (TCGA, GTEx, recount3, ARCHS4,
GEO deposits, MMRF CoMMpass). For platform-general conventions see
[`SKILL.md`](./SKILL.md).

## Cohort acquisition checklist

1. **Counts vs TPM vs FPKM vs other.** This is the dominant source of
   silent bugs. Inspect the matrix yourself:
   - **Raw counts:** integer, library-size-dependent, range 0 to
     hundreds of thousands per gene. Required for DESeq2 / edgeR.
   - **TPM:** float, per-sample sums to ≈ 1M per sample. Library-size-
     normalised. Comparable across samples but not appropriate for
     count-based testing.
   - **FPKM / RPKM:** legacy, library-size + length-normalised. Avoid
     unless you have to.
   - **VST / rlog / log2(TPM+1):** depositor's variance-stabilised
     transform. Float, range ~[0, 20]. Comparable across samples for
     PCA / clustering / linear modelling.
   ```python
   # Assumes genes x samples. Transpose if rows are samples.
   col_sums = X.sum(axis=0)
   print(f"Per-sample sums: median={median(col_sums):.0f} CV={stdev(col_sums)/mean(col_sums):.3f}")
   # CV ≈ 0  → already normalised (TPM, library-size-corrected)
   # CV > 0.3 → raw counts (library size varies)
   ```
   Do not run DESeq2 / edgeR on TPM, FPKM, z-scores, or batch-corrected
   residuals. If raw counts are unavailable, switch to a continuous-scale
   model and state that count-based inference is out of scope.

2. **Gene model version.** GENCODE v27 vs v44 differ by thousands of
   gene-name renames and additions. Cross-cohort meta-analysis on
   different gene-model versions silently drops genes from the
   intersection. Lock the gene model at ingest; harmonise via Ensembl
   ID (stable across versions for the same biological gene) rather
   than gene symbol.

3. **Library preparation chemistry.** Poly-A selected, ribosomal-
   depleted, 3'-tag-only (Quant-seq, MARS-seq). 3'-tag protocols
   produce strong 3' bias and are NOT comparable to whole-transcript
   protocols at the gene-isoform level — only at the gene level. Old
   datasets (pre-2014) often used poly-A selection with degraded RNA,
   producing pronounced 3' bias even on "whole-transcript" protocols.

4. **Sample-level metadata completeness.** For every sample you intend
   to analyse, the cohort metadata must include: disease status,
   tissue, treatment, batch / sequencing run, collection date,
   library prep batch. Missing values in any of these become
   silent confounders.

5. **Technical replicates vs biological replicates.** A "sample" might
   be a single library, multiple libraries from the same patient, or
   multiple sequencing runs of the same library. Check the metadata
   schema before treating samples as independent.

## Minimum-viable per-sample QC

| Metric | Typical range | Red flag |
|---|---|---|
| Total reads / sample | 20–100M | < 5M → underpowered; > 200M → likely contamination |
| % reads aligned to genome | 70–95% | < 50% → contamination, mis-trimmed adapters |
| % reads aligned to gene model | 50–85% | < 30% → ribosomal contamination, intronic-heavy degradation |
| % rRNA contamination | < 5% | > 20% → poly-A selection failed or sample degraded |
| 3'/5' ratio (gene body coverage) | ~ 1.0 (uniform) | > 2.0 → 3' degradation; < 0.5 → 5' degradation |
| Median TIN (transcript integrity) | > 70 | < 50 → degraded RNA |
| Per-sample expressed genes | 12k–18k for Ensembl-coding | < 8k → low complexity / low depth |

## PCA / cohort structure

A first-pass PCA on log-transformed (or VST) expression coloured by:

- **Disease status / treatment / sex** — the biology you want to model.
- **Batch / sequencing run / library prep date** — confounders.
- **Tissue source / extraction protocol** — if mixed.

If batch separates more strongly than biology, you have a confound to
handle (model batch as a covariate, ComBat, RUVSeq, or — in extreme
cases — exclude). Document the choice in the cohort_audit sidecar.

For meta-analysis aggregating multiple cohorts: PCA per cohort
separately, never pool first. The cross-cohort PCA is dominated by
batch and is not informative for biology.

## Filter genes, don't filter aggressively

Standard filter: keep genes with ≥ 10 counts in ≥ N samples (where N
≈ smallest group size). This drops technical-zero / very-low-expression
genes without removing biology. Don't filter on detection rate alone
in cohorts with mixed cell-type composition (see SKILL.md "filter
steps must commute with the question").

## Counts-based testing

For raw count input, the default tools are DESeq2 (R) and limma-voom
(R). Choose one and stick with it across the analysis — both are
defensible; mixing produces incomparable effect-size scales.

For meta-analysis across cohorts:

- **Per-cohort DE → aggregate test statistics** is the MM30 default.
  Each cohort's per-gene effect size is z-scored within cohort before
  aggregation (see MM30 D1).
- **Pooled test on a common-reference normalisation** is appropriate
  when sample-size imbalance is small and platforms are similar.

State which strategy in the pre-registration.

## Continuous-covariate adjustment

When testing on continuous covariates (age, ISS stage as continuous,
purity), use the same model formula across all cohorts. Mixed-formula
adjustments (cohort A: `~ age`, cohort B: `~ age + sex`, cohort C:
unadjusted) produce incomparable effect sizes that cannot be
meaningfully meta-analysed.

For ordinal covariates (stage I / II / III), choose between treating
as continuous (linear assumption) or as factor (no linearity
assumption, more parameters). Document the choice.

## When to suspect pseudobulk vs true bulk

Some "bulk" RNA-Seq cohorts are actually scRNA-Seq pseudobulks. They
have:

- Per-sample read counts in the millions (not 20-100M).
- Per-sample gene counts < 8k.
- Per-cohort PCA showing extreme heterogeneity.

GSE106218 in MM30 is a documented pseudobulk that was incorrectly
treated as bulk in early analyses; it now is excluded (D7). When in
doubt, check the original publication's methods section.

## Output: a per-cohort QA package

Generate a `datapackage.json` for this directory; see [`../frictionless.md`](../frictionless.md).

```
data/processed/<cohort_id>/
├── cohort_audit.json         # filter steps, sample counts at each step
├── per_sample_metrics.tsv    # total_reads, % aligned, % rRNA, 3/5 ratio
├── pca_diagnostic.html       # PCA coloured by batch + biology
├── gene_filter_log.tsv       # which genes dropped, by which filter
├── counts_or_normalized.parquet  # the matrix used downstream
└── README.md                 # one-paragraph summary
```
