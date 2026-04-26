# Embeddings and Manifold QA

Use when analyzing high-dimensional embeddings, UMAP/t-SNE/PCA projections,
HDBSCAN clusters, Mapper graphs, CKA, kNN purity, Moran's I, archetypes, or
multi-lens comparisons in scientific datasets.

Embedding analyses are attractive because the pictures look decisive. The QA
goal is to separate robust structure from projection, sampling, leakage, and
covariate artifacts.

## Pre-Flight Checklist

1. **Define the row universe.** Every embedding, label table, and covariate table
   must share the same entity IDs and row order. Hash or assert row alignment
   before computing cross-lens metrics.
2. **Record the representation.** Model name, checkpoint, layer, pooling,
   dimensionality, preprocessing, whitening, residualization, and random seed
   are part of the data.
3. **Separate fit and display.** PCA/UMAP/t-SNE used for visualization should
   not silently become the analysis space for clustering or statistics unless
   that was pre-committed.
4. **Identify nuisance axes.** Length, depth, batch, taxonomy, tissue, study,
   abundance, or missingness often dominate PC1. Quantify them before
   biological interpretation.
5. **Check leakage.** Labels used to build embeddings, tune clusters, choose
   archetypes, or create splits are not independent evaluation labels.

## Minimum Diagnostics

| Diagnostic | Purpose |
|---|---|
| PC/covariate correlations | Find nuisance axes such as length or batch |
| Seed sweep | Distinguish stable structure from projection randomness |
| Hyperparameter sweep | UMAP neighbors/min_dist, HDBSCAN min_cluster_size, Mapper cover |
| Negative controls | Shuffled sequences, permuted labels, random features, batch labels |
| Holdout split | Test generalization without near-duplicate or taxonomy leakage |
| Local density check | Avoid interpreting density artifacts as clusters |
| Row-alignment assertions | Prevent cross-lens metric corruption |

## Projection Rules

- Treat UMAP and t-SNE as visual summaries unless a separate validation test
  supports the claimed structure.
- Do not compare distances across UMAP plots with different seeds or
  hyperparameters.
- If a claim depends on connected components, branches, or holes, validate it
  with graph/topological diagnostics in the original or pre-committed feature
  space.
- For PCA, report explained variance and top covariate correlations before
  interpreting components biologically.

## Clustering Rules

- HDBSCAN noise points are an output, not a nuisance to drop silently.
- Report cluster stability across seeds, subsamples, and hyperparameters.
- Avoid choosing clustering parameters by maximizing agreement with the
  evaluation label unless the goal is supervised tuning.
- For imbalanced labels, report baseline rates and enrichment, not just purity.

## Multi-Lens Comparisons

For CKA, Procrustes, nearest-neighbor overlap, or cross-manifold alignment:

- Use the same row universe in the same order.
- Center/scale consistently and state whether raw or residualized modes are
  compared.
- Compare against shuffled-row and matched-null baselines.
- Interpret high agreement cautiously when both lenses share a nuisance axis.
- Interpret low agreement cautiously when lenses encode different but valid
  levels of structure.

## Common Failure Modes

- **Pretty projection, weak claim.** The figure shows separation but no
  heldout, permutation, or covariate-adjusted test supports it.
- **Taxonomy or homology leakage.** Train/test splits contain close relatives,
  homologs, duplicate proteins, or repeated patients.
- **Length dominates everything.** PC1 or neighborhood structure tracks entity
  length, library size, or coverage rather than the intended biology.
- **Seed-dependent clusters.** Cluster identities shift across projection seeds
  but are treated as stable classes.
- **Metric mismatch.** Cosine-trained embeddings are analyzed with Euclidean
  distances without checking sensitivity.

## Output Package

```
results/<analysis>/embedding_qa/
|-- row_universe.parquet
|-- representation_manifest.json
|-- pc_covariate_correlations.parquet
|-- seed_sensitivity.parquet
|-- hyperparameter_sensitivity.parquet
|-- negative_controls.parquet
|-- figures/
`-- qa_summary.md
```

The summary should state which structures survived nuisance-axis,
seed/hyperparameter, and negative-control checks.

## Companion Skills

For protein-language-model or structure-derived embeddings, load
`protein-sequence-structure-qa.md` first enough to validate identity mapping,
homology leakage, label hierarchy, and split construction.
