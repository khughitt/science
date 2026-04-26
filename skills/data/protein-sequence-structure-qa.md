---
name: data-protein-sequence-structure-qa
description: Use when working with protein sequences, UniProt mappings, Pfam/InterPro/CATH labels, Foldseek/MMseqs clusters, PLM embeddings, DeepLoc/Meltome labels, or sequence/structure benchmark splits.
---

# Protein Sequence and Structure QA

Use when working with protein sequences, UniProt mappings, Pfam/InterPro/CATH
labels, Foldseek/MMseqs clusters, PLM embeddings, DeepLoc/Meltome labels, or
sequence/structure benchmark splits.

Protein datasets fail quietly through identifier drift, isoforms, homology
leakage, label hierarchy mismatch, and length or taxonomy confounding.

## Acquisition Checklist

1. **Choose the protein identity.** UniProt accession, isoform accession,
   gene symbol, Ensembl protein, PDB chain, AlphaFold model, and cluster
   representative are different entities. Record the mapping and keep original
   IDs.
2. **Lock sequence version.** Store source release, sequence length, checksum,
   organism taxid, and whether fragments or low-evidence proteins were kept.
3. **Handle isoforms explicitly.** Do not collapse isoforms unless the analysis
   is gene-level. If collapsed, state whether canonical, longest, or reviewed
   isoform was chosen.
4. **Validate labels.** Pfam, InterPro, CATH, SCOP, ECOD, DeepLoc, and Meltome
   labels have different coverage and hierarchy. Preserve label source and
   version.
5. **Check cluster semantics.** MMseqs clusters depend on sequence identity,
   coverage, e-value, and representative choice. Foldseek clusters depend on
   structural similarity/alignment score, coverage, e-value, TM-score or
   equivalent thresholds, and representative choice. A representative is not
   always the biological archetype.
6. **Plan leakage control.** Benchmark splits should be cluster-disjoint at an
   appropriate homology or structure threshold before model training.

## Minimum QA Metrics

| Metric | Red flag |
|---|---|
| Sequence length distribution | Long-tail dominates embedding PCs or benchmark labels |
| Missing label rate by taxon | Label coverage is taxonomy-biased |
| Cluster size distribution | A few universal families dominate results |
| Duplicate sequence count | Exact duplicates span train/test or label groups |
| Near-neighbor train/test distance | Holdout proteins are too close to training proteins |
| Label hierarchy consistency | Child label appears without expected parent |
| Fragment / low-confidence rate | Fragments drive clusters or label errors |

## Benchmark Rules

- Split by homology/structure clusters, not random proteins, when evaluating
  generalization.
- Keep length and taxonomy baselines. A model that predicts labels from length
  or phylum may not have learned the intended representation.
- Evaluate label coverage separately from label accuracy. Missing labels are not
  negatives unless the source defines them that way.
- Use heldout clusters for downstream heads and keep a small validation slice
  cluster-disjoint from both training and final test sets.
- Report per-label and macro metrics when classes are imbalanced.

## Embedding and Lens Rules

- Record model, checkpoint, pooling, layer, truncation, and batch settings.
- Check whether PC1 tracks length, disorder, taxonomy, or ortholog-group size.
- Residualization is a scientific choice. Keep raw and residualized modes as
  separate named artifacts with provenance.
- For multi-lens comparisons, assert identical row order and compare against
  shuffled-row baselines.
- For sequence shuffling controls, preserve length and optionally amino-acid
  composition depending on the null being tested.

## Common Failure Modes

- **Gene-symbol joins.** Protein labels joined by gene symbol merge paralogs and
  isoforms. Prefer stable protein accessions.
- **Homology leakage.** Random splits make family-level prediction look like
  out-of-family generalization.
- **Taxonomic coverage bias.** Well-annotated model organisms dominate Pfam,
  CATH, GO, or Meltome labels.
- **Representative bias.** Large cluster representatives overstate universal
  proteins and understate rare families.
- **Hierarchy leakage.** Predicting CATH class from CATH topology labels is not
  independent validation.

## Halt-On Conditions

- Identifier mapping is ambiguous, especially gene-symbol joins across paralog families.
- Train/test homology overlap exceeds the pre-set threshold.
- Label hierarchy is inconsistent or leaks the prediction target.

## Output Package

Generate a `datapackage.json` for this directory; see [`frictionless.md`](./frictionless.md).

```
data/processed/<protein_dataset>/
|-- proteins.parquet
|-- id_mapping.parquet
|-- sequence_qc.parquet
|-- labels_<source>.parquet
|-- clusters_<method>.parquet
|-- splits.parquet
|-- leakage_audit.parquet
`-- dataset_audit.json
```

The audit should make it possible to reconstruct exactly which protein entity,
sequence version, label source, and split rule each result used.

## Companion Skills

- [`embeddings-manifold-qa.md`](embeddings-manifold-qa.md) - PLM embeddings, UMAP/HDBSCAN/Mapper, CKA, Moran's I, archetypes, and multi-lens comparisons.
- [`SKILL.md`](SKILL.md) - generic data-management conventions for processed protein datasets.
