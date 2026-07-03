# Benchmark Fallback Rollup Decisions - 2026-07-03

## Context

This calibration uses `science benchmark test-triage --commons --source gap-fallback`
after fallback rollups were added to `fallback_diagnostics.rollups`.

Active projects sampled:

- `~/d/cancer/cancer-types/multiple-myeloma`
- `~/d/health/processes/post-acute-infection`
- `~/d/natural-systems`
- `~/d/cancer/data-sources/cbioportal`

Raw JSON snapshots are stored in:

- `docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/before.multiple-myeloma.json`
- `docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/before.post-acute-infection.json`
- `docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/before.natural-systems.json`
- `docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/before.cbioportal.json`

Rollup totals from the fresh snapshots:

- `dataset:ccle-proteomics-nusinow-2020#protein-lineage-association`: total 494; projects `cbioportal:36`, `multiple-myeloma:307`, `natural-systems:104`, `post-acute-infection:47`; facets `cross-sectional:494`, `multi-omic:494`, `multimodal:494`, `proteomics:494`.
- `dataset:cptac-proteogenomics#protein-rna-cross-modal`: total 491; projects `cbioportal:34`, `multiple-myeloma:297`, `natural-systems:113`, `post-acute-infection:47`; facets `bulk-rna-seq:491`, `cross-sectional:491`, `genomics:491`, `multi-omic:491`, `multimodal:491`, `proteomics:491`.
- `dataset:dream4-in-silico-network#network-reconstruction`: total 483; projects `cbioportal:42`, `multiple-myeloma:294`, `natural-systems:101`, `post-acute-infection:46`; facets `perturbation:483`, `simulated-gene-expression:483`, `time-series:483`.

## Decision Summary

| Benchmark task | Observed projects | Current state | Decision | Metadata change |
| --- | --- | --- | --- | --- |
| `dataset:ccle-proteomics-nusinow-2020#protein-lineage-association` | `cbioportal:36`, `multiple-myeloma:307`, `natural-systems:104`, `post-acute-infection:47` | `supported` / `runnable` / `deposit` | `keep-supported-fallback` | none |
| `dataset:cptac-proteogenomics#protein-rna-cross-modal` | `cbioportal:34`, `multiple-myeloma:297`, `natural-systems:113`, `post-acute-infection:47` | `candidate:requires-study-specific-staging` / `metadata-only` / `reference` | `needs-staging-recipe` | none, unless Task 3 finds a more precise durable reason |
| `dataset:dream4-in-silico-network#network-reconstruction` | `cbioportal:42`, `multiple-myeloma:294`, `natural-systems:101`, `post-acute-infection:46` | `candidate:requires-challenge-package-staging` / `metadata-only` / `pointer` | `valid-reference-only` | none, unless Task 3 confirms a concrete stageable package |
| `dataset:mmrf-commpass#progression-risk` | Suppressed in all sampled projects | `blocked:open-metadata-missing-progression-endpoint` | `keep-blocked-support` | none |

## Per-Benchmark Notes

### CCLE Proteomics

Decision: `keep-supported-fallback`.

Evidence:

- Current commons metadata is a runnable deposit with `datapackage: datapackage.yaml`.
- Task support is already `supported`.
- Rollup facets are protein/multimodal/cross-sectional and match the benchmark's intended broad fallback role.
- Example matched entities include `hypothesis:0001-non-tumor-signal-contamination`, `hypothesis:0003-gene-length-confounds-literature-attention`, `hypothesis:0005-healthy-somatic-background-atlas`, `hypothesis:0003-mutation-reshaping`, and `hypothesis:0004-attractor-convergence`.

Interpretation:

This remains a broad cell-line protein-abundance fallback, not a primary-tumor or causal benchmark.

### CPTAC Proteogenomics

Decision: `needs-staging-recipe`.

Evidence:

- Current commons metadata is `dataset_class: reference`.
- Task support is `candidate` with reason `requires-study-specific-staging`.
- Rollup facets are proteomics/multimodal/bulk-RNA/genomics and repeatedly match project needs.
- Example matched entities include `hypothesis:0001-non-tumor-signal-contamination`, `hypothesis:0002-cross-study-ranking-divergence-is-structured`, `hypothesis:0003-gene-length-confounds-literature-attention`, `hypothesis:0003-mutation-reshaping`, and `hypothesis:0004-attractor-convergence`.

Interpretation:

Keep it visible as a candidate. Do not mark it runnable until a concrete CPTAC study/package is selected, access terms are checked, and a datapackage or recipe exists.

### DREAM4 In Silico Network

Decision: `valid-reference-only`.

Evidence:

- Current commons metadata is `dataset_class: pointer`.
- Task support is `candidate` with reason `requires-challenge-package-staging`.
- Rollup facets are perturbation/time-series/simulated gene expression.
- Example matched entities include `hypothesis:0002-cross-study-ranking-divergence-is-structured`, `hypothesis:0005-healthy-somatic-background-atlas`, `hypothesis:0006-pre-malignant-n-minus-1-driver-carriage`, `hypothesis:0007-hd-lineage-shifts-the-ap-1-stress-arm-and-produces-lineage-specific-ap-1`, and `hypothesis:0011-proteasome-inhibitor-response-and-resistance-reflect-mechanism`.

Interpretation:

This is useful as a benchmark direction for mechanism/time-series validation, but it should remain metadata-only until the exact challenge package and access path are staged.

### MMRF CoMMpass

Decision: `keep-blocked-support`.

Evidence:

- Blocked fallback rows are suppressed from default fallback diagnostics.
- The blocked support reason reflects the current open-metadata progression endpoint limitation.

Interpretation:

No change in this slice.

## Follow-Up

Recommended next slice:

1. Audit CPTAC proteogenomics for a concrete study/package that can support `protein-rna-cross-modal`.
2. Audit DREAM4 access/package layout only if synthetic network reconstruction is a near-term priority.
3. Do not build extra review tooling until more than these recurring rollups require manual decisions.
