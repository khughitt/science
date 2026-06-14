# Schema Adoption Campaign — Manifest

Audited 2026-06-14. Statuses: `pending` | `done` | `no-op` | `blocked-data` | `blocked-scaffold`.
Paths are package directories relative to each project root. No pushes — all commits stay local.

## mm30  [~/d/cancer/cancer-types/multiple-myeloma]

| Package | Fmt | Tabular | Phase 1 (shape) | Phase 2 (meaning) | Notes |
|---|---|---|---|---|---|
| data/external/ccle_proteomics/2020-01 | json | 2 | done | pending | commit 5a32847d |
| data/external/ctrp_v2/2015 | json | 3 | done | pending | commit 5e368dd2 |
| data/external/gdsc_v2/2022-07-24 | json | 3 | done | pending | commit 65edc4d3 |
| data/external/oetjen_2018/2018-10 | json | 1 | done | pending | schema pre-existed (write a no-op); 2 non-tabular files absent |
| data/external/opentargets/25.03 | json | 3 | done | pending | commit a082d175 |
| data/external/walker_2024/2024-05 | json | 6 | done | pending | commit d66028e6 — 4 present tabular schema'd; 4 files absent locally (2 parquet + h5ad + qc_report.json) stay blocked-data |

## cancer-therapeutics  [~/d/cancer/therapeutics]  — ALL YAML, blocked on scaffold defect (see below)

| Package | Fmt | Tabular | Phase 1 (shape) | Phase 2 (meaning) | Notes |
|---|---|---|---|---|---|
| data/raw/chembl-activities | yaml | 1 | blocked-scaffold | blocked-scaffold | YAML timestamp coercion |
| data/raw/chembl | yaml | 1 | blocked-scaffold | blocked-scaffold | smoke-test that surfaced the defect; write reverted |
| data/raw/dgidb | yaml | 2 | blocked-scaffold | blocked-scaffold | 1 resource also blocked-data (../../processed path) |
| data/raw/drugcomb | yaml | 1 | blocked-scaffold | blocked-scaffold | |
| data/raw/nci-almanac | yaml | 0 | no-op | no-op | no tabular resources |
| data/raw/nsc-crosswalk | yaml | 1 | blocked-scaffold | blocked-scaffold | |
| data/raw/opentargets | yaml | 1 | blocked-scaffold | blocked-scaffold | |
| data/raw/string | yaml | 0 | no-op | no-op | no tabular resources |

## cancer-evolution  [~/d/cancer/mechanisms/evolution]

| Package | Fmt | Tabular | Phase 1 (shape) | Phase 2 (meaning) | Notes |
|---|---|---|---|---|---|
| data/raw/ampliconrepository-kim2024-pcawg | json | 9 | done | pending | commit 061b1d0 |
| data/raw/ampliconrepository-kim2024-tcga | json | 9 | done | pending | commit 141174c |
| data/raw/kim2024-supplement | json | 0 | no-op | no-op | no tabular resources |
| data/raw/nct02415621-trial-patient-data | json | 0 | no-op | no-op | no tabular resources |

## health-meta  [~/d/health/meta]

| Package | Fmt | Tabular | Phase 1 (shape) | Phase 2 (meaning) | Notes |
|---|---|---|---|---|---|
| code/scripts/external/reactome | yaml | 6 | blocked-data | blocked-data | all 6 CSVs absent locally — needs hydration (also YAML → blocked-scaffold) |

## Phase 1 status (2026-06-14)

- **JSON half DONE** — 8 packages schema'd with names+types and committed (local, not pushed),
  all verified value-safe (only `schema` added; every other descriptor field byte-identical):
  mm30 ×6 (ccle, ctrp_v2, gdsc_v2, oetjen[pre-existing], opentargets, walker[4 present resources]),
  cancer-evolution ×2 (ampliconrepository pcawg, tcga). Gate (`science datasets validate --path`)
  passes; partial packages (oetjen, walker) fail only on absent data files, as expected.
- **YAML half BLOCKED** — the 6 non-no-op cancer-therapeutics packages cannot be written until
  the scaffold defect below is fixed.

## Scaffold defect (blocks YAML writes) — for a separate science-repo cycle

`science datasets infer-schema --write` corrupts a value when re-rendering a YAML descriptor:
`infer_schema.load_descriptor` uses `yaml.safe_load`, which **implicitly parses an unquoted
ISO-8601 timestamp string into a `datetime`**; `_render_descriptor`'s `yaml.safe_dump` then
re-emits it as a YAML timestamp — e.g. `provenance.retrieved: 2026-05-31T13:20:44.428732+00:00`
became `2026-05-31 13:20:44.428732+00:00` (lost the `T`, type str→datetime). The chembl smoke
test caught this; the write was reverted (no corrupted descriptor was committed). This violates
the scaffold's "value-preserved" contract and affects every YAML descriptor carrying an unquoted
ISO timestamp (all 6 cancer-therapeutics targets carry `provenance.retrieved`). JSON is
unaffected (no implicit scalar coercion).

**Recommended fix:** make `load_descriptor`/`_render_descriptor` round-trip YAML scalars
faithfully — load with a loader whose implicit-timestamp (and ideally other risky implicit)
resolvers are removed so timestamps stay strings, OR otherwise guarantee non-schema scalars are
value-preserved. Add a regression test: a YAML descriptor with `retrieved: <ISO-with-T>` must
round-trip unchanged through `--write`. Then unblock the 6 YAML packages.

## Summary

- Effective working set: 14 packages with present local data.
- Phase 1 done: 8 (all JSON). Phase 1 blocked-scaffold: 6 (all cancer-therapeutics YAML).
- no-op (no tabular): nci-almanac, string, kim2024-supplement, nct02415621-trial-patient-data.
- blocked-data: reactome (whole package); plus absent resources within walker_2024 and dgidb.
