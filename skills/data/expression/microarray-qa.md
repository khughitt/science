---
name: data-expression-microarray-qa
description: Use when ingesting or QA-reviewing bulk microarray cohorts (Affymetrix, Agilent, Illumina BeadArray) for legacy meta-analysis.
---

# Bulk Microarray QA

Practical QA for bulk microarray cohorts (Affymetrix GeneChip, Agilent,
Illumina BeadArray, custom platforms). Most public microarray data
is now legacy (most cohorts pre-date 2015 RNA-Seq adoption), but it
remains relevant for meta-analysis of disease cohorts where the
microarray data is the only large-n option (MM30 includes 28 microarray
GEO cohorts). For platform-general conventions see [`SKILL.md`](./SKILL.md).

## The probe-to-gene problem

Microarray data is per-*probe*, not per-gene. Every QA workflow has to
solve probe-to-gene mapping early:

1. **Get the probe annotation.** GEO platforms (`GPL96`, `GPL570`,
   `GPL10558`, …) have annotation tables that map probe IDs to gene
   symbols / Entrez IDs / Ensembl IDs. Bioconductor packages
   (`hgu133a.db`, `hgu133plus2.db`, …) provide the same.
2. **Multi-probe-per-gene resolution.** A gene often has multiple
   probes hitting different parts of the transcript. Resolution
   options:
   - **Median collapse** (most common): per-sample median of all probes
     hitting the gene. Robust, default, MM30 uses this.
   - **Maximum probe**: take the probe with highest expression.
     Sensitive to artifacts; less common.
   - **Signature-specific**: choose the probe with best literature
     validation. Documentation-heavy; rarely worth it.
3. **Multi-gene-per-probe ambiguity.** Some probes target multiple
   genes (paralogs, isoforms). Drop or flag these — don't use them
   for gene-level inference.
4. **Symbol versioning.** HGNC gene-symbol drift is real. `MARCH1` →
   `MARCHF1`, `SEPT1` → `SEPTIN1`, etc. Resolve via Ensembl ID at
   probe annotation time; symbols are display-only.

## Cohort acquisition checklist

1. **What normalisation did the depositor apply?** Three common cases:
   - **Raw CEL files** (Affymetrix) — apply your own normalisation
     (RMA, MAS5, GCRMA). RMA is standard.
   - **Already normalised** (most GEO entries) — usually RMA or
     MAS5; sometimes quantile-normalised across the deposited
     cohort. Stated in the GEO Series record under "Data
     processing".
   - **Pre-collapsed to genes** — depositor has already applied
     probe-to-gene collapse. Document the method used.
   ```python
   # Quick distributional sanity check
   sub = X[:, :100]  # first 100 samples
   print(f"min={sub.min():.3f}, max={sub.max():.3f}, "
         f"per-sample median range: [{median(per_sample_median):.2f}, ...]")
   # log2 expression typical: range [2, 14], per-sample median ~7
   # raw intensity (rare in GEO): range thousands
   ```

2. **Which platform variant?** Affymetrix HG-U133A vs HG-U133_Plus_2
   have different probe sets. Cross-platform meta-analysis requires
   collapsing both to gene symbols / Ensembl IDs first.

3. **Single-channel vs two-colour Agilent?** Two-colour Agilent gives
   log-ratios (test/reference) per spot, not absolute values.
   Different normalisation pipeline (loess); different statistical
   modelling (paired vs unpaired).

4. **Which sample annotations are reliable?** GEO Series records have
   per-sample `characteristics_ch1` fields that depositors fill in
   inconsistently. Treat them as best-effort metadata; cross-validate
   against the publication's Table 1 / supplemental cohort table
   when available.

## Minimum-viable per-sample QC

Less standardised than RNA-Seq, but worth checking:

| Metric | Typical range | Red flag |
|---|---|---|
| Per-sample log2 expression median | 6–9 | outliers > 1 SD from cohort median → batch / scanner / hyb failure |
| Per-sample IQR | 3–5 | very narrow → flat / failed array; very wide → mixed chip |
| Per-sample 3'/5' ratio (Affy actin / GAPDH) | 1.0–3.0 | > 5.0 → degraded RNA |
| Probe-set present-call rate (MAS5) | 30–60% | < 20% → bad chip; > 80% → unusual |

For Affymetrix data with raw CEL files, `arrayQualityMetrics`
(Bioconductor) automates a thorough QA report.

## Cross-platform meta-analysis (the hard problem)

The fundamental difficulty: probe-set vs probe-set vs gene-symbol
expression scales are not comparable. Three strategies:

1. **Per-cohort DE testing → aggregate statistics**, MM30's default.
   Run linear models (limma) per cohort on the cohort's native
   probe-collapsed gene-level matrix; aggregate p-values (Stouffer's,
   sumlog) or z-scored effects (random-effects metafor).
2. **Cross-cohort rank normalisation** before pooling. Each gene's
   per-sample expression is converted to within-sample rank, then
   meta-tested. Conservative but loses magnitude information.
3. **Surrogate Variable Analysis** (`sva`) for cross-cohort
   harmonisation. Estimate latent confounders, regress them out,
   then pool. Compute-heavy and assumption-heavy; use only when
   strategies 1 + 2 fail.

State which strategy upfront. Mixing is rarely defensible.

## Quantile normalisation: standard, but assumption-heavy

Quantile normalisation is standard for many single-channel microarray
pipelines, especially RMA. It is not automatically a bug. The hidden
assumption is that most genes are not globally shifted between samples.
That assumption becomes fragile for strong cell-composition shifts,
gross tumor-normal differences, or mixed tissues. Symptoms worth
investigating:

- Per-sample histograms are pixel-perfect identical across all
  samples in a biologically heterogeneous cohort.
- Disease-vs-healthy contrasts have unexpectedly compressed global
  effect-size distributions.
- PCA separates by scanner / processing date more than by biology
  after normalisation.

If raw CEL files are available, rerun a controlled pipeline and compare
the primary contrast. If not, inherit the depositor's matrix but state
the normalisation as a limitation rather than treating the scale as
fully comparable to newly processed cohorts.

## Halt-On Conditions

- Platform variant is unknown or ambiguous across samples.
- No probe annotation is available for the platform or custom CDF used.
- Quantile-normalization assumptions are violated because the cohort is biologically heterogeneous.
- Two-colour data are being treated as a single-channel intensity matrix.

## Probe-set obsolescence

Affymetrix probes were designed against gene-model versions current
at array design (often pre-2010). Some probes target gene regions
that have since been re-annotated, deprecated, or split. Bioconductor
annotation packages reflect the original mapping; modern annotations
(BrainArray custom CDFs, `hgu133plus2hsentrezgcdf`) re-map probes
against current Ensembl or RefSeq. The choice between original and
re-mapped CDFs is methodologically consequential — original
preserves what the original publications used; re-mapped is
biologically more accurate but breaks reproducibility against
historical results.

## Output: a per-cohort QA package

Generate a `datapackage.json` for this directory; see [`../frictionless.md`](../frictionless.md).

```
data/processed/<cohort_id>/
├── cohort_audit.json         # platform GPL ID, normalisation method, sample counts
├── per_sample_metrics.tsv    # log2 median, IQR, 3'/5' ratio, present rate
├── probe_to_gene_log.tsv     # collapse method, multi-probe genes flagged
├── pca_diagnostic.html       # PCA coloured by batch + biology
├── gene_collapsed_expression.parquet
└── README.md
```

## When microarray is the wrong tool

For greenfield analyses (no existing microarray cohort), use RNA-Seq.
Microarray remains relevant only for legacy meta-analysis where the
disease cohort has no RNA-Seq alternative at adequate n. The MM30
project includes 28 microarray cohorts because the alternative would
be an n ≈ 700 (MMRF) instead of n ≈ 5,400 meta-analysis.

## Companion Skills

- [`SKILL.md`](SKILL.md) - expression-data hub conventions for cross-platform cohort QA.
- [`bulk-rnaseq-qa.md`](bulk-rnaseq-qa.md) - companion checks when aggregating microarray with RNA-seq cohorts.
- [`../../statistics/bias-vs-variance-decomposition.md`](../../statistics/bias-vs-variance-decomposition.md) - separating platform bias from estimator variance.
