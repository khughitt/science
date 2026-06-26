---
name: data-proteomics-qa
description: Use when ingesting or QA-reviewing proteomics, phosphoproteomics, mass-spectrometry, peptide-intensity, TMT, LFQ, DIA, DDA, or protein-abundance datasets.
---

# Proteomics QA

Use when working with proteomics or phosphoproteomics measurements from mass
spectrometry, including peptide intensity tables, protein abundance matrices,
TMT/iTRAQ multiplexed runs, LFQ, DIA, DDA, MaxQuant, FragPipe, Spectronaut, or
CPTAC-style cohorts.

Proteomics datasets fail quietly through peptide-to-protein rollup choices,
missing-not-at-random intensities, batch/run effects, normalization artifacts,
shared peptides, and post-translational-modification localization ambiguity.

## Acquisition Checklist

1. **Record the measurement level.** Peptide, phosphosite, protein group,
   inferred protein, and pathway summary are different grains. Keep the raw
   grain and the rollup rule.
2. **Lock the search and quantification settings.** Record database release,
   enzyme, missed cleavages, FDR thresholds, match-between-runs, normalization,
   imputation, and protein inference settings.
3. **Preserve protein identifiers.** Keep UniProt accession, isoform, gene
   symbol, protein-group membership, and contaminant/reverse flags rather than
   collapsing to gene symbol alone.
4. **Separate biological absence from missing intensity.** Missing values may
   reflect low abundance, run failure, censoring, or search-space mismatch.
5. **Audit multiplex/run structure.** TMT channel, plex, LC-MS run, fraction,
   batch, and acquisition order must be available before contrasts are treated
   as biological.
6. **Validate PTM localization.** Phosphosite or other PTM analyses need site
   localization probability, ambiguity handling, and site-to-protein mapping.

## Minimum QA Metrics

| Metric | Red flag |
|---|---|
| Peptides per protein | Many verdict-bearing proteins have one peptide |
| Missingness by batch/run/channel | Missingness tracks acquisition structure |
| Intensity distribution by sample | Normalization or loading failures |
| Contaminant/reverse rate | Search quality or filtering issue |
| Protein-group ambiguity rate | Shared peptides dominate rollup |
| Replicate correlation | Technical or biological replicates disagree |
| PTM localization confidence | Site-level claims depend on ambiguous sites |

## Modeling Rules

- Analyze at the independent biological unit first; peptides inside a sample are
  repeated measurements, not independent samples.
- State whether the estimand is peptide abundance, protein abundance, site
  occupancy, phosphorylation abundance, or pathway-level activity.
- Do not impute missing intensities before deciding whether missingness is
  censoring, dropout, or run failure. If imputation is used, pre-specify the
  method and run a no-imputation or censoring-aware sensitivity check.
- For TMT/iTRAQ, include plex/channel structure and bridge/reference-channel
  behavior in the model or normalization audit.
- For cross-cohort comparisons, separate platform/search-pipeline effects from
  biology before pooling effect sizes.

## Common Failure Modes

- **Gene-symbol rollup.** Isoforms, paralogs, and protein groups collapse into
  one row and create false agreement with transcriptomics.
- **MNAR intensity loss.** Low-abundance proteins look differentially abundant
  because missing values were filled with arbitrary low values.
- **Plex or run confounding.** Case/control labels are aligned with TMT plex,
  acquisition date, or instrument batch.
- **Shared-peptide leakage.** Evidence for one protein is reused for another
  through ambiguous protein groups.
- **PTM site ambiguity.** Site-level claims use peptides whose modification
  position is not localized.

## Halt-On Conditions

- Search database, FDR threshold, or quantification method is unknown.
- Contrast labels are confounded with plex, run, batch, or acquisition order.
- Verdict-bearing proteins/sites lack peptide support or localization confidence.
- Missingness is high and not audited by sample group and acquisition structure.

## Output Package

Generate a `datapackage.json` for this directory; see [`frictionless.md`](./frictionless.md).

```
data/processed/<proteomics_dataset>/
|-- sample_metadata.parquet
|-- peptide_intensities.parquet
|-- protein_groups.parquet
|-- protein_abundance.parquet
|-- missingness_audit.parquet
|-- batch_plex_run_audit.parquet
|-- rollup_config.yaml
|-- ptm_localization_audit.parquet
`-- dataset_audit.json
```

The audit should state the measurement grain, identifier mapping, search
settings, normalization/imputation choices, batch/plex structure, and any
verdict downgrade caused by missingness or ambiguous rollup.

## Companion Skills

- [`protein-sequence-structure-qa.md`](protein-sequence-structure-qa.md) - protein identity, UniProt/isoform mapping, homology, and sequence-derived labels.
- [`frictionless.md`](frictionless.md) - data-package descriptors and validation conventions.
- [`../statistics/bias-vs-variance-decomposition.md`](../statistics/bias-vs-variance-decomposition.md) - separating preprocessing bias from estimator variance.
- [`../statistics/sensitivity-arbitration.md`](../statistics/sensitivity-arbitration.md) - pre-committed rules for imputation, rollup, and batch sensitivity disagreement.
