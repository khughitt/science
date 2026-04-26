---
name: data-genomics-somatic-mutation-qa
description: Use when ingesting or auditing tumor mutation calls from cBioPortal, AACR GENIE, TCGA/MC3, ICGC, MAF files, study supplements, or targeted-panel cohorts.
---

# Somatic Mutation QA

Use when ingesting or auditing tumor mutation calls from cBioPortal, AACR GENIE,
TCGA/MC3, ICGC, MAF files, study supplements, or targeted-panel cohorts.

Somatic mutation tables are deceptively simple: one row per variant, many ways
to get the denominator wrong. The core QA task is to distinguish true zeros,
uncallable positions, missing samples, and artifacts introduced by panel or
cohort harmonisation.

## Acquisition Checklist

1. **Lock the coordinate system.** Record genome build, chromosome naming,
   transcript reference, and whether coordinates are 0- or 1-based. Never join
   GRCh37 and GRCh38 variants without liftover plus post-liftover validation.
2. **Identify the unit of analysis.** Variant, gene, sample, patient, tumor
   specimen, biopsy time point, or study-cancer-gene cell. Multiple samples per
   patient are not independent unless the model explicitly treats them that way.
3. **Separate missing from zero.** A missing `(sample, gene)` cell can mean
   unmutated, not on panel, failed QC, or not in the exported table. Do not fill
   missing values with zero until callable territory is known.
4. **Define callable territory.** For WES/WGS, derive callable territory from
   the assay target/callable mask, depth/QC thresholds, mappability, and caller
   filters; do not assume every exonic/genomic base is callable after sample
   QC. For targeted panels, track panel and panel-version territory per sample.
   Store panel-gene or BED coverage before computing frequencies.
5. **Normalize sample identifiers.** cBioPortal sample IDs, patient IDs, and
   study IDs can encode different clinical specimens. Verify one-to-many
   relationships before aggregation.
6. **Audit variant classifications.** Decide whether splice, truncating, inframe,
   silent, UTR, and noncoding calls enter the endpoint. Driver-style summaries
   should usually exclude synonymous calls; mutational-signature spectra need
   all eligible SNVs.

## Minimum QA Tables

Produce these before downstream inference:

| Artifact | Required fields |
|---|---|
| `samples_qc` | sample_id, patient_id, study_id, cancer_type, assay, panel_id, qc_status |
| `callable_gene_sample` | sample_id, gene, callable, reason_if_uncallable |
| `mutation_long` | sample_id, gene, variant, consequence, build, source, pass_filter |
| `frequency_table` | group, gene, mutated_n, callable_n, frequency, missing_n |
| `audit_log` | row counts after each filter, dropped studies/samples, rationale |

For panel studies, denominators are per gene, not per cohort. A gene absent from
half the panels has half the maximum callable sample count.

## Common Failure Modes

- **NaN vs 0 collapse.** Treating absent rows as unmutated creates false low
  frequencies for genes not covered by a panel.
- **Panel version drift.** MSK-IMPACT, Foundation, and GENIE-style panels change
  gene content across time. A study-level `panel_id` is insufficient if sample
  rows carry version-specific panels.
- **Hypermutator dominance.** MSI-high, POLE/POLD1, temozolomide, UV, and other
  hypermutator processes can dominate gene rankings. Report inclusive and
  hypermutator-excluded results when mutation burden drives the endpoint.
- **Cohort-stage mixture.** Primary, metastatic, relapse, and treated samples
  have different mutation spectra. A pan-cancer frequency can be a cohort
  composition statistic rather than biology.
- **Gene-symbol drift.** Harmonize to stable IDs where possible, then display
  current symbols. Preserve the original symbol from the source table.
- **Variant recurrence artifacts.** Recurrent hotspots near low-complexity
  regions, paralogs, or panel edges need manual review before being treated as
  drivers.

## Analysis Rules

- Never compute mutation frequency without `callable_n`.
- Never compare panel and WES/WGS cohorts without panel-class or callable-size
  adjustment.
- Keep inclusive and exclusive sample counts side by side when excluding
  hypermutators or low-QC samples.
- When aggregating across studies, model study/cancer effects or aggregate
  within study first. Pooled raw counts overweight large studies and popular
  tumor types.
- For co-occurrence or mutual exclusivity, restrict to samples callable for both
  genes and adjust for cancer type, TMB, and study when feasible.

## Red Flags Worth Halting On

- A panel-bearing study has no panel metadata.
- More than 5% of mutated genes are absent from the callable-gene universe.
- Sample IDs duplicate across studies after normalization.
- Cancer-type labels are missing or mapped to broad `Other` for verdict-bearing
  analyses.
- Mutation counts per sample have a heavy tail but no hypermutator/MSI/POLE
  annotation.

## Output Package

Generate a `datapackage.json` for this directory; see [`../frictionless.md`](../frictionless.md).

```
data/processed/<cohort_id>/somatic_mutation_qa/
|-- mutation_long.parquet
|-- samples_qc.parquet
|-- callable_gene_sample.parquet
|-- frequency_table.parquet
|-- hypermutator_flags.parquet
|-- cohort_audit.json
`-- README.md
```

The audit should state which cells are structural zeros, true zeros, and
unknowns. That distinction is the main protection against silent false
negative mutation frequencies.

## Companion Skills

Load `mutational-signatures-and-selection.md` after this skill when the same
mutation calls feed SBS signatures, TMB, dN/dS, dNdScv, or driver-ranking
analyses.
