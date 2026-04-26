# Single-Cell RNA-Seq QA

Practical QA pipeline for scRNA-seq data, with emphasis on what goes
wrong silently. For platform-general QA conventions see
[`SKILL.md`](./SKILL.md).

## Cohort acquisition checklist

When you ingest a new scRNA-seq cohort:

1. **What technology?** 10x Chromium 3' v2 / v3 / v3.1, MARS-seq,
   Smart-seq2, BD Rhapsody, snRNA-seq vs scRNA-seq. The technology
   sets the per-cell complexity floor (10x median ~3-15k UMI;
   MARS-seq ~1-3k; Smart-seq2 lower-cell-count higher-depth, often
   read-counts not UMI). Mixing technologies in one analysis without
   accounting for these differences is a primary source of false
   "biological" signal.

2. **What did the depositor filter?** Most public h5ad files have already
   been filtered for empty droplets and minimum UMI / gene counts.
   That is the depositor's filter, not yours. Re-record the filter
   thresholds; do not assume they match what your downstream analysis
   needs. Especially fragile: depositor filters that select for a
   specific cell-type subset and remove others.

3. **Are doublets called?** Check `obs` for a `doublet_score`,
   `predicted_doublet`, or similar column. If absent, you'll need to
   call them yourself (Scrublet, DoubletFinder, Solo). If present,
   confirm what tool was used and what threshold was applied —
   different tools give substantially different doublet calls and
   conservative thresholds vary by 2x.

4. **Is ambient RNA corrected?** Tools like CellBender, SoupX, and
   DecontX subtract estimated ambient contamination from each cell.
   If correction was applied, `.X` is no longer integer counts. If
   uncorrected, very lowly-expressed-yet-broadly-detected genes are
   suspect (likely ambient).

5. **What metadata is per-cell vs per-sample?** `disease_stage`,
   `treatment_status`, `donor_id` should be per-cell columns in
   `adata.obs` so they survive subsetting. Patient-level metadata
   (age, sex, treatment timing) often lives in a separate sidecar
   that needs joining at ingest.

## Minimum-viable per-cell QC

These four metrics catch most acute problems. Compute them, plot them,
log the thresholds applied:

| Metric | Typical 10x range | Red flag |
|---|---|---|
| `n_counts` (UMI / cell) | 1k–50k | mass below 500 → empty droplets / low-quality cells |
| `n_genes` (genes / cell) | 500–5k | mass below 200 or above 8k → low-quality / doublet |
| `pct_mito` (% mito reads) | 5–15% | sustained > 20% → dying cells; very high values mean ambient mito-pollution |
| `pct_ribo` (% ribosomal) | 10–30% | low-then-high cohort spread → batch effect, not biology |

Don't apply uniform `mean ± 3 SD` thresholds across mixed-tissue or
mixed-disease cohorts — different tissues have different baseline
mito% (heart and muscle high, lymphoid lower). Threshold per cell-
type-or-tissue group when feasible.

## Doublet handling

Default to flagging not removing — you want the call available for
downstream filtering decisions. A reasonable pipeline:

```python
import scrublet as scr
counts = adata.layers["counts"]
scrub = scr.Scrublet(counts, expected_doublet_rate=0.06)  # 10x default
doublet_scores, predicted_doublets = scrub.scrub_doublets(
    min_counts=2, min_cells=3, min_gene_variability_pctl=85, n_prin_comps=30
)
adata.obs["doublet_score"] = doublet_scores
adata.obs["predicted_doublet"] = predicted_doublets
```

Per-batch / per-channel runs of Scrublet are more accurate than
pooled runs (Scrublet's null is generated from the input matrix; if
the matrix is a heterogeneous batch concatenation, the null is
biased). When working with a multi-channel cohort, run one Scrublet
per `batch_id` or `library_id` and concatenate.

`expected_doublet_rate` scales linearly with cell-load on the chip;
~0.06 at 8k cells loaded, ~0.10 at 16k. Read the publication's loading
density before defaulting.

## Ambient RNA — the silent bias

Ambient RNA (unbound transcripts in the droplet supernatant) appears
in every cell at low levels and looks identical to "low-but-real
expression" of cell-type-marker genes in non-expressing cell types.
Symptoms:

- B-cell markers (CD79A, MS4A1) detectable in 10–30% of T cells.
- Hemoglobin (HBB, HBA1, HBA2) detectable in non-erythrocytes.
- Cell-type confidence scores are noisy at the boundary.

If your downstream analysis depends on rare-cell-type classification,
sub-cell-type stratification, or low-expression marker gene biology,
ambient correction (CellBender or SoupX) is worth the compute.

If your downstream analysis is at the bulk-pseudobulk or cell-type-
proportion level, ambient is less critical but should still be
documented.

## Cell-cycle phase scoring

Tirosh et al. 2016 gene lists are the de-facto standard for cell-cycle
phase scoring on transcriptome data. Both `scanpy.tl.score_genes_cell_cycle`
and `Seurat::CellCycleScoring` use them.

Phase composition shifts are a primary confounder for any
proliferation-related claim. For any analysis that touches E2F /
G2M / cell-cycle biology, score phase per cell at QC time and
include `phase` as a covariate or explicit stratification axis. Don't
trust "we residualised proliferation" claims that didn't measure
phase composition first.

## Batch / channel effects

scRNA-seq is profoundly batch-sensitive. Plot:

1. PCA / UMAP coloured by `batch_id` and `donor_id`. If batch
   structure is the dominant axis of variation, batch effects
   dominate biology.
2. Per-batch median `n_counts`. If medians differ by >2x, library
   prep was inconsistent.
3. Per-batch cell-type composition. Mismatched cell-type recovery
   across batches is endemic; this is the difference between "every
   batch saw the same biology" and "every batch saw a different
   subset of biology".

Batch correction (Harmony, scVI, BBKNN, ComBat) is downstream of QA;
the QA step is to *characterize* batch structure so downstream
correction is informed.

## Stage / disease-axis verification

For disease-progression cohorts (MGUS → SMM → MM, healthy → cancer,
treatment-naive → relapsed):

1. Verify the staging column maps to the publication's labels. Off-
   by-one errors and silent label permutations are common.
2. Verify per-stage cell counts match the publication's reported
   counts to within 5% — if they don't, ask why before any analysis.
3. Verify patient-stage assignments are unique. A patient at multiple
   time points should appear in multiple stages with distinct cell
   pools, not double-counted.

For paired pre/post cohorts:

1. Verify `donor_id` matches across the pair.
2. Verify the time elapsed between samples is documented; collapsing
   pre/post pairs sampled days apart with pairs sampled years apart
   misrepresents the biology.

## Cell-type assignment

Most public deposits ship with `cell_type` annotations from the
depositor's pipeline. They are usually right at the broad level
(B-cell vs T-cell vs myeloid) and unreliable at the fine level
(CD8 effector memory vs central memory). Either:

- **Use the depositor's broad annotations**, accepting the granularity
  trade-off, or
- **Re-cluster with your reference panel** and propagate annotations
  via marker-gene scoring (CellTypist, SingleR, scANVI). Document
  which path you took.

If `cell_type` is missing entirely (`unassigned` for all cells; common
for raw-counts public deposits), score against a marker panel at run
time. Avoid using a black-box automated classifier without first
checking that the marker-set output looks sane on your cohort.

## Pseudobulk for cross-platform aggregation

When mixing scRNA-seq with bulk RNA-seq cohorts in a meta-analysis,
pseudobulk by patient-and-cell-type before testing:

```python
# Aggregate counts per (donor_id, cell_type)
pseudobulk = (
    adata.to_df(layer="counts")
    .assign(donor_id=adata.obs["donor_id"].values,
            cell_type=adata.obs["cell_type"].values)
    .groupby(["donor_id", "cell_type"]).sum()
)
```

Test on the resulting pseudobulk matrix with bulk methods (DESeq2,
limma-voom). The cell-level p-values from per-cell tests are not
comparable to bulk-cohort p-values.

## A note on "the depositor filtered cells"

A depositor's filter is one of:

- **Depth-based** (per-cell UMI / gene minimum): fine to inherit; just
  log the threshold.
- **Doublet-removal**: usually fine if the tool is documented; treat
  as one more filter step.
- **Cell-type subset**: not fine to inherit silently — the cohort
  is no longer representative of the original biology. State it.
- **Disease-state filtering** (kept only diagnosed / progressed /
  responding): not fine. State the resulting cohort definition
  prominently in any downstream analysis.

When the depositor's filter cannot be reversed (raw FASTQ unavailable),
state the filter as a known limitation in any pre-registration or
manuscript.

## Output: a per-cohort QA package

A reasonable QA artifact for each ingested cohort:

```
data/processed/<cohort_id>/
├── cohort_audit.json         # filter chain, counts at each step, dropped patients
├── per_cell_metrics.parquet  # n_counts, n_genes, pct_mito, doublet_score, phase, …
├── per_donor_summary.tsv     # n_cells, mean_counts, stage, dropped_reason
├── figures/
│   ├── qc_violins.html       # per-stage / per-batch violins of QC metrics
│   ├── pca_by_batch.html     # batch-coloured PC1/PC2
│   └── cell_type_composition.html
└── README.md                  # one-paragraph summary + threshold rationale
```

This artifact is sufficient for downstream analyses to inherit the
QA without re-deriving it, and for reviewers to audit the
preprocessing without rerunning anything.
