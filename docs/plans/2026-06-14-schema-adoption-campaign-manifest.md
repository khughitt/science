# Schema Adoption Campaign — Manifest

Audited 2026-06-14. Statuses: `pending` | `done` | `no-op` | `blocked-data`.
Paths are package directories relative to each project root. No pushes — all commits stay local.

## mm30  [~/d/cancer/cancer-types/multiple-myeloma]

| Package | Fmt | Tabular | Phase 1 (shape) | Phase 2 (meaning) | Notes |
|---|---|---|---|---|---|
| data/external/ccle_proteomics/2020-01 | json | 2 | pending | pending | |
| data/external/ctrp_v2/2015 | json | 3 | pending | pending | |
| data/external/gdsc_v2/2022-07-24 | json | 3 | pending | pending | |
| data/external/oetjen_2018/2018-10 | json | 1 | pending | pending | |
| data/external/opentargets/25.03 | json | 3 | pending | pending | |
| data/external/walker_2024/2024-05 | json | 6 | pending | pending | 4 resources data-absent locally: 2 parquet (cytogenetic_calls, functional_groups) + h5ad + qc_report.json — gate will fail on all four |

## cancer-therapeutics  [~/d/cancer/therapeutics]

| Package | Fmt | Tabular | Phase 1 (shape) | Phase 2 (meaning) | Notes |
|---|---|---|---|---|---|
| data/raw/chembl-activities | yaml | 1 | pending | pending | |
| data/raw/chembl | yaml | 1 | pending | pending | YAML smoke-test package (do first) |
| data/raw/dgidb | yaml | 2 | pending | pending | 1 resource blocked-data (../../processed path) |
| data/raw/drugcomb | yaml | 1 | pending | pending | |
| data/raw/nci-almanac | yaml | 0 | no-op | no-op | no tabular resources |
| data/raw/nsc-crosswalk | yaml | 1 | pending | pending | |
| data/raw/opentargets | yaml | 1 | pending | pending | |
| data/raw/string | yaml | 0 | no-op | no-op | no tabular resources |

## cancer-evolution  [~/d/cancer/mechanisms/evolution]

| Package | Fmt | Tabular | Phase 1 (shape) | Phase 2 (meaning) | Notes |
|---|---|---|---|---|---|
| data/raw/ampliconrepository-kim2024-pcawg | json | 9 | pending | pending | |
| data/raw/ampliconrepository-kim2024-tcga | json | 9 | pending | pending | |
| data/raw/kim2024-supplement | json | 0 | no-op | no-op | no tabular resources |
| data/raw/nct02415621-trial-patient-data | json | 0 | no-op | no-op | no tabular resources |

## health-meta  [~/d/health/meta]

| Package | Fmt | Tabular | Phase 1 (shape) | Phase 2 (meaning) | Notes |
|---|---|---|---|---|---|
| code/scripts/external/reactome | yaml | 6 | blocked-data | blocked-data | all 6 CSVs absent locally — needs hydration |

## Summary

- Effective working set: 14 packages with present local data.
- no-op (no tabular): nci-almanac, string, kim2024-supplement, nct02415621-trial-patient-data.
- blocked-data: reactome (whole package); 2 resources in walker_2024; 1 resource in dgidb.
